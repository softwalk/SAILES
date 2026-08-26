#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
minutes="${2:-240}"
grep -Eq '^ATLANTIS_SHADOW_MODE=(true|"true")$' "$ATLANTIS_ENV_FILE" || die "soak must run in shadow mode"
[[ "$minutes" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "minutes must be numeric"

tenant_id="$(database_psql -Atqc "SELECT id FROM tenant ORDER BY created_at LIMIT 1")"
[[ -n "$tenant_id" ]] || die "tenant required for soak"
evidence_dir="$ATLANTIS_EVIDENCE_ROOT/soak-$(date -u +'%Y%m%dT%H%M%SZ')"
install -d -m 700 "$evidence_dir"
python3 "$REPO_DIR/tools/shadow_soak.py" --minutes "$minutes" --tenant "$tenant_id" \
  --workload-secrets "$ATLANTIS_SECRET_DIR/workload_secrets.json" \
  --output "$evidence_dir/soak.jsonl"
sha256sum "$evidence_dir/soak.jsonl" > "$evidence_dir/SHA256SUMS"
chmod 600 "$evidence_dir"/*
log "PASS shadow soak evidence=$evidence_dir"
