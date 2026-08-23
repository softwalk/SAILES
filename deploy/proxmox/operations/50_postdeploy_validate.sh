#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_command curl
require_command docker
install -d -m 700 "$ATLANTIS_EVIDENCE_ROOT"
report="$ATLANTIS_EVIDENCE_ROOT/postdeploy-validation.txt"
: > "$report"

fail=0
for port in 8081 8082 8083 8084 8085 8086 8087; do
  body="$(curl --fail --silent --show-error --max-time 5 "http://127.0.0.1:$port/health" 2>/dev/null || true)"
  if [[ "$body" == *'"status": "ok"'* || "$body" == *'"status":"ok"'* ]]; then
    write_evidence_line "$report" "health_$port" PASS
  else
    write_evidence_line "$report" "health_$port" FAIL
    fail=1
  fi
done
policy_health="$(curl --fail --silent --max-time 5 http://127.0.0.1:8081/health || true)"
[[ "$policy_health" == *'"shadow_mode": true'* || "$policy_health" == *'"shadow_mode":true'* ]] || { write_evidence_line "$report" shadow_mode FAIL; fail=1; }

rls_count="$(database_psql -Atqc "SELECT count(*) FROM pg_class WHERE relrowsecurity AND relforcerowsecurity AND relnamespace='public'::regnamespace")"
(( rls_count >= 35 )) || { write_evidence_line "$report" forced_rls_tables "$rls_count"; fail=1; }
write_evidence_line "$report" forced_rls_tables "$rls_count"
policy_count="$(database_psql -Atqc "SELECT count(*) FROM pg_policy WHERE polrelid='suppression'::regclass AND polname IN ('suppression_tenant_and_global_read','suppression_global_admin')")"
[[ "$policy_count" == "2" ]] || { write_evidence_line "$report" suppression_policies "$policy_count"; fail=1; }
write_evidence_line "$report" suppression_policies "$policy_count"

PYTHONPATH="$REPO_DIR/shared" python3 -m unittest discover -s "$REPO_DIR/tests" > "$ATLANTIS_EVIDENCE_ROOT/unit-tests.txt" 2>&1 || fail=1
PYTHONPATH="$REPO_DIR/shared" python3 "$REPO_DIR/tools/shadow_e2e.py" > "$ATLANTIS_EVIDENCE_ROOT/shadow-e2e.txt" 2>&1 || fail=1
PYTHONPATH="$REPO_DIR/shared" python3 "$REPO_DIR/tools/dr_drill.py" > "$ATLANTIS_EVIDENCE_ROOT/dr-drill.txt" 2>&1 || fail=1

compose ps > "$ATLANTIS_EVIDENCE_ROOT/compose-ps.txt"
docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' > "$ATLANTIS_EVIDENCE_ROOT/container-resources.tsv"
sha256sum "$ATLANTIS_EVIDENCE_ROOT"/*.txt "$ATLANTIS_EVIDENCE_ROOT"/*.tsv > "$ATLANTIS_EVIDENCE_ROOT/SHA256SUMS"
chmod 600 "$ATLANTIS_EVIDENCE_ROOT"/*
[[ "$fail" -eq 0 ]] || die "post-deployment validation failed; inspect $ATLANTIS_EVIDENCE_ROOT"
log "PASS post-deployment validation evidence=$ATLANTIS_EVIDENCE_ROOT"
