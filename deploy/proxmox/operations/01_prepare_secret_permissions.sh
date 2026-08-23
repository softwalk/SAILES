#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
[[ "$(id -u)" == "0" ]] || die "secret permission preparation requires root"
require_directory "$ATLANTIS_SECRET_DIR"

required=(
  postgres_runtime_password.txt postgres_migrator_password.txt postgres_ca.crt
  workload_secrets.json jit_secret.txt evidence_workload_secret.txt
  kimi_litellm_key.txt deepseek_litellm_key.txt amqp_url.txt
  internal_ca.crt policy_client.crt policy_client.key
  meta_access_token.txt meta_app_secret.txt meta_webhook_verify_token.txt
  vicidial_api_password.txt vicidial_webhook_secret.txt
  neobot_api_token.txt neobot_webhook_secret.txt
  marketia_api_token.txt marketia_webhook_secret.txt
)
count=0
for name in "${required[@]}"; do
  path="$ATLANTIS_SECRET_DIR/$name"
  require_file "$path"
  chown 10001:root "$path"
  chmod 400 "$path"
  count=$((count + 1))
done
(( count > 0 )) || die "no secret files found"
log "PASS protected $count secret files as uid 10001 mode 0400"
