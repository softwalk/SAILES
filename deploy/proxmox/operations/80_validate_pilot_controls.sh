#!/usr/bin/env bash
# Destructive only to container process uptime: restarts orchestrator and voice adapter.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
assert_safe_root
for command in python3 psql curl docker; do require_command "$command"; done

token_context=""
redact_token_context() {
  [[ -n "$token_context" && -f "$token_context" ]] || return 0
  python3 - "$token_context" <<'PY'
import json,os,sys
path=sys.argv[1]
try: value=json.load(open(path,encoding='utf-8'))
except (OSError,ValueError): raise SystemExit(0)
value['token']='[REDACTED_AFTER_USE]'
temporary=path+'.tmp'
open(temporary,'w',encoding='utf-8').write(json.dumps(value,separators=(',',':')))
os.chmod(temporary,0o600)
os.replace(temporary,path)
PY
}
trap redact_token_context EXIT

grep -Eq '^ATLANTIS_SHADOW_MODE=(true|"true")$' "$ATLANTIS_ENV_FILE" || die "pilot controls must run in shadow mode"
recorded_008="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='008_pilot_readiness'" 2>/dev/null || true)"
[[ "$recorded_008" =~ ^[a-f0-9]{64}$ ]] || die "migration 008 is not applied"

evidence_dir="$ATLANTIS_EVIDENCE_ROOT/pilot-controls-$(date -u +'%Y%m%dT%H%M%SZ')"
install -d -m 700 "$evidence_dir"
report="$evidence_dir/results.txt"
: > "$report"
exec > >(tee -a "$report") 2>&1

row="$(database_psql -AtF $'\t' -c "SELECT c.tenant_id,c.id,cv.id FROM contact c JOIN campaign_version cv ON cv.tenant_id=c.tenant_id WHERE cv.status='APPROVED' ORDER BY cv.created_at DESC,c.created_at DESC LIMIT 1")"
IFS=$'\t' read -r tenant_id contact_id campaign_version_id <<< "$row"
[[ -n "$tenant_id" && -n "$contact_id" && -n "$campaign_version_id" ]] || die "approved campaign/contact fixture missing"

visible="$(database_runtime_psql -Atqc "SELECT set_config('app.tenant_id','$tenant_id',false); SELECT count(*) FROM contact WHERE id='$contact_id'" | tail -n 1)"
hidden="$(database_runtime_psql -Atqc "SELECT set_config('app.tenant_id','ffffffff-ffff-ffff-ffff-ffffffffffff',false); SELECT count(*) FROM contact WHERE id='$contact_id'" | tail -n 1)"
[[ "$visible" == "1" && "$hidden" == "0" ]] || die "RLS isolation failed visible=$visible hidden=$hidden"
echo "PASS RLS cross-tenant isolation"

if database_runtime_psql -Atqc "SELECT set_config('app.tenant_id','$tenant_id',false); UPDATE audit_event SET actor_id=actor_id WHERE tenant_id='$tenant_id'" >/dev/null 2>&1; then
  die "runtime can mutate append-only audit"
fi
echo "PASS direct audit mutation denied"

env_setting() {
  python3 - "$ATLANTIS_ENV_FILE" "$1" <<'PY'
import sys
path,key=sys.argv[1:]
matches=[]
for raw in open(path,encoding='utf-8'):
    line=raw.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    name,value=line.split('=',1)
    if name.strip()==key:
        value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'": value=value[1:-1]
        matches.append(value)
if len(matches)!=1 or not matches[0]: raise SystemExit(1)
print(matches[0])
PY
}
oidc_issuer="${ATLANTIS_OIDC_ISSUER:-$(env_setting ATLANTIS_OIDC_ISSUER)}"
oidc_audience="${ATLANTIS_OIDC_AUDIENCE:-$(env_setting ATLANTIS_OIDC_AUDIENCE)}"
campaign_role="${ATLANTIS_OIDC_CAMPAIGN_APPROVER_ROLE:-$(env_setting ATLANTIS_OIDC_CAMPAIGN_APPROVER_ROLE)}"
reviewer_role="${ATLANTIS_OIDC_HUMAN_REVIEWER_ROLE:-$(env_setting ATLANTIS_OIDC_HUMAN_REVIEWER_ROLE)}"
oidc_keys="${ATLANTIS_OIDC_PUBLIC_KEYS_HOST_FILE:-/opt/atlantis/infrastructure/oidc/public_keys.json}"
campaign_token="${ATLANTIS_CAMPAIGN_APPROVER_TOKEN_HOST_FILE:-/run/atlantis/campaign_approver.token}"
reviewer_token="${ATLANTIS_HUMAN_REVIEWER_TOKEN_HOST_FILE:-/run/atlantis/human_reviewer.token}"
require_file "$oidc_keys"
for sensitive in "$campaign_token" "$reviewer_token"; do
  require_file "$sensitive"
  [[ "$(stat -c '%u' "$sensitive")" == "0" ]] || die "ephemeral OIDC token file must be root-owned: $sensitive"
  [[ "$(stat -c '%a' "$sensitive")" == "400" ]] || die "ephemeral OIDC token file must use mode 0400: $sensitive"
done
python3 "$REPO_DIR/tools/validate_human_oidc.py" --issuer "$oidc_issuer" --audience "$oidc_audience" \
  --tenant "$tenant_id" --public-keys "$oidc_keys" --campaign-token "$campaign_token" \
  --reviewer-token "$reviewer_token" --campaign-role "$campaign_role" --reviewer-role "$reviewer_role"

workflow_context="$evidence_dir/workflow-context.json"
python3 "$REPO_DIR/tools/pilot_live_probe.py" workflow-before \
  --workload-secrets "$ATLANTIS_SECRET_DIR/workload_secrets.json" --context "$workflow_context" \
  --tenant "$tenant_id" --campaign-version "$campaign_version_id" --contact "$contact_id"
compose restart orchestrator >/dev/null
for _ in {1..30}; do curl --fail --silent --max-time 2 http://127.0.0.1:8083/health >/dev/null 2>&1 && break; sleep 2; done
curl --fail --silent --max-time 3 http://127.0.0.1:8083/health >/dev/null || die "orchestrator did not recover"
python3 "$REPO_DIR/tools/pilot_live_probe.py" workflow-after \
  --workload-secrets "$ATLANTIS_SECRET_DIR/workload_secrets.json" --context "$workflow_context"
workflow_run_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_id"])' "$workflow_context")"

decision_file="$evidence_dir/decision.tsv"
database_psql -AtF $'\t' -c "SELECT tenant_id,contact_id,campaign_version_id,id,channel,purpose,content_hash FROM contactability_decision WHERE tenant_id='$tenant_id' AND result='ALLOW' AND channel='VOICE' ORDER BY decided_at DESC LIMIT 1" > "$decision_file"
[[ -s "$decision_file" ]] || die "ALLOW VOICE decision required for replay probe"
token_context="$evidence_dir/token-context.json"
python3 "$REPO_DIR/tools/pilot_live_probe.py" make-token --decision "$decision_file" \
  --jit-secret "$ATLANTIS_SECRET_DIR/jit_secret.txt" --context "$token_context"

read_json() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$token_context" "$1"; }
jti="$(read_json jti)"; nonce_hash="$(read_json nonce_hash)"; token_hash="$(read_json token_hash)"
decision_id="$(read_json decision_id)"; issued_at="$(read_json iat)"; expires_at="$(read_json exp)"
database_psql -v jti="$jti" -v tenant="$tenant_id" -v decision="$decision_id" -v nonce="$nonce_hash" \
  -v token="$token_hash" -v issued="$issued_at" -v expires="$expires_at" -c \
  "INSERT INTO outbound_authorization(id,tenant_id,decision_id,channel,nonce_hash,token_hash,issued_at,expires_at) VALUES (:'jti',:'tenant',:'decision','VOICE',:'nonce',:'token',to_timestamp((:'issued')::double precision),to_timestamp((:'expires')::double precision))"
python3 "$REPO_DIR/tools/pilot_live_probe.py" voice-before \
  --workload-secrets "$ATLANTIS_SECRET_DIR/workload_secrets.json" --context "$token_context"
compose restart voice_adapter >/dev/null
for _ in {1..30}; do curl --fail --silent --max-time 2 http://127.0.0.1:8085/health >/dev/null 2>&1 && break; sleep 2; done
python3 "$REPO_DIR/tools/pilot_live_probe.py" voice-after \
  --workload-secrets "$ATLANTIS_SECRET_DIR/workload_secrets.json" --context "$token_context"

audit_anomalies="$(database_psql -Atqc "WITH ordered AS (SELECT tenant_id,sequence_no,previous_hash,event_hash,row_number() OVER(PARTITION BY tenant_id ORDER BY sequence_no) rn,lag(event_hash) OVER(PARTITION BY tenant_id ORDER BY sequence_no) expected_previous FROM audit_event) SELECT count(*) FROM ordered WHERE sequence_no<>rn OR previous_hash IS DISTINCT FROM expected_previous")"
[[ "$audit_anomalies" == "0" ]] || die "audit chain link/sequence anomalies=$audit_anomalies"
audit_hash_anomalies="$(database_psql -Atqc "SELECT count(*) FROM audit_event WHERE event_hash <> encode(digest(concat_ws('|',tenant_id::text,sequence_no::text,coalesce(previous_hash,''),actor_type,actor_id,action,resource_type,resource_id,coalesce(decision_id::text,''),coalesce(reason_codes::text,''),correlation_id::text,occurred_at::text),'sha256'),'hex')")"
[[ "$audit_hash_anomalies" == "0" ]] || die "audit chain hash anomalies=$audit_hash_anomalies"
echo "PASS append-only audit chain sequence, links and hashes"

database_psql -AtF $'\t' -c "SELECT sequence_no,action,resource_type,resource_id,event_hash,previous_hash,occurred_at FROM audit_event WHERE tenant_id='$tenant_id' ORDER BY sequence_no DESC LIMIT 100" > "$evidence_dir/audit-events.tsv"
database_psql -AtF $'\t' -c "SELECT id,stage,status,workflow_version,version,updated_at FROM graph_run WHERE tenant_id='$tenant_id' AND id='$workflow_run_id'" > "$evidence_dir/workflow-run.tsv"
database_psql -AtF $'\t' -c "SELECT id,decision_id,consumed_at,expires_at FROM outbound_authorization WHERE tenant_id='$tenant_id' AND id='$jti'" > "$evidence_dir/jit-replay.tsv"

crm_identity="$(curl --fail --silent http://127.0.0.1:8082/health | python3 -c 'import json,sys; print(json.load(sys.stdin).get("human_identity","missing"))')"
orchestrator_identity="$(curl --fail --silent http://127.0.0.1:8083/health | python3 -c 'import json,sys; print(json.load(sys.stdin).get("human_identity","missing"))')"
if [[ "$crm_identity" == "oidc" && "$orchestrator_identity" == "oidc" ]]; then
  echo "PASS human OIDC active"
else
  die "human OIDC not active crm=$crm_identity orchestrator=$orchestrator_identity"
fi

redact_token_context
token_context=""

find "$evidence_dir" -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$evidence_dir/SHA256SUMS"
chmod 600 "$evidence_dir"/*
echo "PASS pilot shadow controls evidence=$evidence_dir"
