#!/usr/bin/env bash
# Technical readiness gate only. A PASS never replaces legal/security approval.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
assert_safe_root

fail=0
gate_fail() { log "FAIL pilot-technical-gate: $*"; fail=1; }
gate_pass() { log "PASS $*"; }
for command in python3 psql openssl git docker curl awk stat sha256sum; do
  command -v "$command" >/dev/null 2>&1 || gate_fail "missing command=$command"
done

require_file "$ATLANTIS_ENV_FILE"
owner="$(stat -c '%u' "$ATLANTIS_ENV_FILE")"; mode="$(stat -c '%a' "$ATLANTIS_ENV_FILE")"
[[ "$owner" == "0" ]] || gate_fail "environment file must be root-owned"
[[ "$mode" == "600" || "$mode" == "400" ]] || gate_fail "environment file mode must be 0600/0400"

env_value() {
  python3 - "$ATLANTIS_ENV_FILE" "$1" <<'PY'
import sys
path,key=sys.argv[1:]
values=[]
for raw in open(path,encoding='utf-8'):
    line=raw.strip()
    if not line or line.startswith('#') or '=' not in line: continue
    name,value=line.split('=',1)
    if name.strip()==key:
        value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'": value=value[1:-1]
        values.append(value)
if len(values)!=1:
    raise SystemExit(f'{key} must occur exactly once')
print(values[0])
PY
}

load_setting() {
  local key="$1" target="$2" value
  if value="$(env_value "$key" 2>/dev/null)"; then
    printf -v "$target" '%s' "$value"
  else
    gate_fail "$key missing or duplicated"
    printf -v "$target" '%s' ''
  fi
}

load_setting ATLANTIS_ENV environment
load_setting ATLANTIS_DATABASE_SSLMODE sslmode
load_setting ATLANTIS_DATABASE_SSLROOTCERT sslrootcert_container
load_setting ATLANTIS_REQUIRE_WORKLOAD_AUTH workload_auth
load_setting ATLANTIS_REQUIRE_DURABLE_STATE durable_state
load_setting ATLANTIS_CRM_STORAGE crm_storage
load_setting ATLANTIS_SHADOW_MODE shadow_mode
load_setting ATLANTIS_REQUIRE_HUMAN_OIDC human_oidc
load_setting ATLANTIS_REQUIRE_COMPLETED_SOAK completed_soak
[[ "$environment" == "production" ]] && gate_pass "ATLANTIS_ENV=production" || gate_fail "ATLANTIS_ENV must equal production"
[[ "$sslmode" == "verify-full" ]] && gate_pass "sslmode=verify-full" || gate_fail "sslmode must equal verify-full"
[[ "$sslrootcert_container" == "/run/secrets/postgres_ca" ]] || gate_fail "unexpected PostgreSQL CA container path"
[[ "$workload_auth" == "true" ]] || gate_fail "workload authentication must be true"
[[ "$durable_state" == "true" ]] || gate_fail "durable state must be true"
[[ "$crm_storage" == "postgres" ]] || gate_fail "CRM storage must be postgres"
[[ "$shadow_mode" == "true" ]] || gate_fail "technical gate must run before activation, with shadow mode true"
[[ "$human_oidc" == "true" ]] || gate_fail "human OIDC must be required for pilot"
[[ "$completed_soak" == "true" ]] || gate_fail "completed soak evidence must be required for pilot"

ca_file="${ATLANTIS_DATABASE_SSLROOTCERT_HOST:-$ATLANTIS_SECRET_DIR/postgres_ca.crt}"
if [[ -s "$ca_file" ]]; then
  openssl x509 -in "$ca_file" -noout -checkend 2592000 >/dev/null 2>&1 || gate_fail "PostgreSQL CA invalid or expires within 30 days"
else gate_fail "PostgreSQL CA missing: $ca_file"; fi

mem_total="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
mem_available="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
min_total="${ATLANTIS_MIN_MEMORY_KIB:-7340032}"
min_available="${ATLANTIS_MIN_AVAILABLE_MEMORY_KIB:-2097152}"
(( mem_total >= min_total )) || gate_fail "effective RAM ${mem_total}KiB below ${min_total}KiB"
(( mem_available >= min_available )) || gate_fail "available RAM ${mem_available}KiB below ${min_available}KiB"

if [[ "$fail" -eq 0 ]]; then
  export ATLANTIS_DATABASE_SSLMODE=verify-full
  if tls_used="$(database_runtime_psql -Atqc "SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")"; then
    [[ "$tls_used" == "t" ]] && gate_pass "runtime PostgreSQL connection uses verified TLS" || gate_fail "runtime PostgreSQL session is not TLS"
  else gate_fail "runtime PostgreSQL verify-full connection failed"; fi
fi

canonical="f07309b514f1fb1bb4546a3c09712123b45de255c202e25b9f6c098d6eb3ba2e"
legacy="9c1850fcaa632f2189deac5e9b66e02fa85be92a920b6cae7696c9b691e4bacb"
expected_fingerprint="53e77f497b6ee0e30963dd08a734dd7b2d1a997c52c742ee42bb4c6228818b6d"
recorded="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='004_security_and_durability'" 2>/dev/null || true)"
if [[ "$recorded" == "$canonical" ]]; then
  gate_pass "migration 004 canonical checksum"
elif [[ "$recorded" == "$legacy" ]]; then
  row="$(database_psql -AtF $'\t' -c "SELECT object_fingerprint,approved_by,approved_date,evidence_ref,evidence_sha256 FROM schema_migration_reconciliation WHERE version='004_security_and_durability' AND legacy_checksum='$legacy' AND canonical_checksum='$canonical'" 2>/dev/null || true)"
  IFS=$'\t' read -r stored_fingerprint approver approval_date evidence_ref evidence_sha <<< "$row"
  [[ "$stored_fingerprint" == "$expected_fingerprint" ]] || gate_fail "stored reconciliation fingerprint mismatch"
  [[ -n "$approver" && -n "$approval_date" ]] || gate_fail "migration reconciliation lacks human approval"
  [[ "$evidence_sha" =~ ^[a-f0-9]{64}$ ]] || gate_fail "migration reconciliation lacks evidence SHA-256"
  actual="$(database_psql -Atqc "SELECT app.migration_004_object_fingerprint()" 2>/dev/null || true)"
  [[ "$actual" == "$expected_fingerprint" ]] || gate_fail "current migration 004 object fingerprint mismatch"
  evidence_path="$evidence_ref"; [[ "$evidence_path" = /* ]] || evidence_path="$ATLANTIS_ROOT/$evidence_path"
  if [[ -f "$evidence_path" ]]; then
    [[ "$(sha256sum "$evidence_path" | awk '{print $1}')" == "$evidence_sha" ]] || gate_fail "reconciliation evidence file hash mismatch"
  else gate_fail "reconciliation evidence file missing"; fi
  expected_007="$(sha256sum "$REPO_DIR/database/007_reconcile_migration_005_fingerprint_canonical.sql" | awk '{print $1}')"
  recorded_007="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='007_reconcile_migration_005_fingerprint_canonical'" 2>/dev/null || true)"
  [[ "$recorded_007" == "$expected_007" ]] || gate_fail "legacy path requires canonical migration 007"
  canonical_validation="$(database_psql -Atqc "SELECT count(*) FROM schema_migration_validation WHERE migration_version='005_reconcile_migration_004_checksum' AND validation_type='canonical_fingerprint' AND match" 2>/dev/null || true)"
  [[ "$canonical_validation" == "1" ]] || gate_fail "canonical migration 005 fingerprint validation missing"
else gate_fail "migration 004 checksum unrecognized: ${recorded:-missing}"; fi

recorded_008="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='008_pilot_readiness'" 2>/dev/null || true)"
[[ "$recorded_008" =~ ^[a-f0-9]{64}$ ]] && gate_pass "migration 008 pilot controls applied" || gate_fail "migration 008 missing or invalid"
direct_audit_privileges="$(database_psql -Atqc "SELECT has_table_privilege('atlantis_runtime','audit_event','INSERT') OR has_table_privilege('atlantis_runtime','audit_event','UPDATE') OR has_table_privilege('atlantis_runtime','audit_event','DELETE')")"
[[ "$direct_audit_privileges" == "f" ]] && gate_pass "runtime has no direct audit mutation privilege" || gate_fail "runtime can mutate audit_event directly"
audit_execute="$(database_psql -Atqc "SELECT has_function_privilege('atlantis_runtime','app.append_audit_event(uuid,text,text,text,text,text,uuid,jsonb,uuid)','EXECUTE')")"
[[ "$audit_execute" == "t" ]] && gate_pass "runtime can append only through tenant-safe audit function" || gate_fail "runtime audit append function grant missing"

if git -C "$REPO_DIR" rev-parse --verify HEAD >/dev/null 2>&1; then
  commit="$(git -C "$REPO_DIR" rev-parse HEAD)"
  [[ "$commit" =~ ^[a-f0-9]{40}$ || "$commit" =~ ^[a-f0-9]{64}$ ]] || gate_fail "source commit is not an immutable object ID"
  [[ -z "$(git -C "$REPO_DIR" status --porcelain)" ]] || gate_fail "source worktree is dirty"
else gate_fail "source tree has no Git commit"; fi

digest_file="$ATLANTIS_EVIDENCE_ROOT/image-digests.tsv"
if [[ -f "$digest_file" ]]; then
  digest_count=0
  while IFS=$'\t' read -r image digest; do
    [[ -n "$image" ]] || continue
    [[ "$digest" =~ ^sha256:[a-f0-9]{64}$ ]] || { gate_fail "invalid image digest for $image"; continue; }
    current="$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null || true)"
    [[ "$current" == "$digest" ]] || gate_fail "running image content differs: $image"
    digest_count=$((digest_count + 1))
  done < "$digest_file"
  [[ "$digest_count" == "8" ]] || gate_fail "expected 8 image digests, found $digest_count"
else gate_fail "image digest evidence missing"; fi

provider_count="$(curl --fail --silent --max-time 5 http://127.0.0.1:8084/health 2>/dev/null | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("configured_providers",[])))' 2>/dev/null || printf 0)"
(( provider_count >= 1 )) || gate_fail "no approved model provider configured"
"$OPS_DIR/02_validate_model_provider_connectivity.sh" >/dev/null 2>&1 || gate_fail "configured model provider is not reachable from model_gateway"
for port in 8081 8082 8083 8084 8085 8086 8087; do
  curl --fail --silent --max-time 5 "http://127.0.0.1:$port/health" >/dev/null 2>&1 || gate_fail "service health failed on port $port"
done
crm_health="$(curl --fail --silent --max-time 5 http://127.0.0.1:8082/health 2>/dev/null || true)"
orchestrator_health="$(curl --fail --silent --max-time 5 http://127.0.0.1:8083/health 2>/dev/null || true)"
[[ "$crm_health" == *'"human_identity":"oidc"'* || "$crm_health" == *'"human_identity": "oidc"'* ]] || gate_fail "CRM human OIDC is not active"
[[ "$orchestrator_health" == *'"human_identity":"oidc"'* || "$orchestrator_health" == *'"human_identity": "oidc"'* ]] || gate_fail "orchestrator human OIDC is not active"
[[ "$orchestrator_health" == *'"runtime":"postgres"'* || "$orchestrator_health" == *'"runtime": "postgres"'* ]] || gate_fail "orchestrator is not using PostgreSQL state"

latest_soak="$(find "$ATLANTIS_EVIDENCE_ROOT" -maxdepth 2 -type f -path '*/soak-*/soak.jsonl' -print 2>/dev/null | sort | tail -n 1)"
if [[ -n "$latest_soak" ]]; then
  soak_result="$(python3 - "$latest_soak" <<'PY'
import json,sys
lines=[json.loads(line) for line in open(sys.argv[1],encoding='utf-8') if line.strip()]
summary=next((row for row in reversed(lines) if row.get('type')=='summary'),{})
ok=(summary.get('status')=='PASS' and float(summary.get('duration_minutes',0))>=240
    and int(summary.get('failures',1))==0 and int(summary.get('external_contacts_executed',1))==0)
print('PASS' if ok else 'FAIL')
PY
)"
  [[ "$soak_result" == "PASS" ]] && gate_pass "four-hour shadow soak evidence valid" || gate_fail "shadow soak evidence incomplete or failed"
else
  gate_fail "four-hour shadow soak evidence missing"
fi

if (( fail )); then
  log "TECHNICAL PILOT GATE: BLOCKED"
  exit 1
fi
log "TECHNICAL PILOT GATE: PASS — external legal, privacy and security approvals remain mandatory"
