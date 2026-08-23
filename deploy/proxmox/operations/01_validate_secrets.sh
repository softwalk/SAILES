#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
assert_safe_root

required=(
  postgres_runtime_password.txt postgres_migrator_password.txt postgres_ca.crt
  workload_secrets.json jit_secret.txt evidence_workload_secret.txt
  openrouter_api_key.txt kimi_litellm_key.txt deepseek_litellm_key.txt amqp_url.txt
  internal_ca.crt policy_client.crt policy_client.key
  meta_access_token.txt meta_app_secret.txt meta_webhook_verify_token.txt
  vicidial_api_password.txt vicidial_webhook_secret.txt
  neobot_api_token.txt neobot_webhook_secret.txt
  marketia_api_token.txt marketia_webhook_secret.txt
)
fail=0
for name in "${required[@]}"; do
  path="$ATLANTIS_SECRET_DIR/$name"
  if [[ ! -s "$path" ]]; then log "FAIL missing or empty secret $path"; fail=1; continue; fi
  mode="$(stat -c '%a' "$path")"
  [[ "$mode" == "400" ]] || { log "FAIL mode=$mode expected=400 file=$path"; fail=1; }
  [[ "$(stat -c '%u' "$path")" == "10001" ]] || { log "FAIL owner uid must be 10001 file=$path"; fail=1; }
done

[[ "$fail" -eq 0 ]] || die "secret file presence/permission validation blocked"

python3 - "$ATLANTIS_SECRET_DIR/workload_secrets.json" <<'PY' || fail=1
import json,sys
data=json.load(open(sys.argv[1], encoding='utf-8'))
assert isinstance(data,dict) and data, 'workload secret map empty'
for key,value in data.items():
    assert isinstance(key,str) and key, 'invalid service id'
    assert isinstance(value,str) and len(value.encode()) >= 32, f'secret too short: {key}'
print(f'PASS workload secret entries={len(data)}')
PY

for name in jit_secret.txt evidence_workload_secret.txt; do
  bytes="$(wc -c < "$ATLANTIS_SECRET_DIR/$name")"
  (( bytes >= 32 )) || { log "FAIL secret shorter than 32 bytes: $name"; fail=1; }
done
python3 - "$ATLANTIS_SECRET_DIR/openrouter_api_key.txt" <<'PY' || fail=1
import sys
value=open(sys.argv[1], encoding='utf-8').read().strip()
assert value.startswith('sk-or-v1-') and len(value) >= 40, 'OpenRouter key format invalid'
print('PASS OpenRouter secret format')
PY
openssl verify -CAfile "$ATLANTIS_SECRET_DIR/internal_ca.crt" "$ATLANTIS_SECRET_DIR/policy_client.crt" >/dev/null || { log "FAIL policy client certificate chain"; fail=1; }
openssl x509 -checkend 2592000 -noout -in "$ATLANTIS_SECRET_DIR/policy_client.crt" >/dev/null || { log "FAIL policy client certificate expires within 30 days"; fail=1; }
cert_pub="$(openssl x509 -in "$ATLANTIS_SECRET_DIR/policy_client.crt" -pubkey -noout | openssl sha256)"
key_pub="$(openssl pkey -in "$ATLANTIS_SECRET_DIR/policy_client.key" -pubout | openssl sha256)"
[[ "$cert_pub" == "$key_pub" ]] || { log "FAIL policy certificate/private key mismatch"; fail=1; }

[[ "$fail" -eq 0 ]] || die "secret validation blocked"
log "PASS secret and certificate validation"
