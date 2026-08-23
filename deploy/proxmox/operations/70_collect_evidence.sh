#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
install -d -m 700 "$ATLANTIS_EVIDENCE_ROOT"

report="$ATLANTIS_EVIDENCE_ROOT/release-evidence.txt"
: > "$report"
write_evidence_line "$report" release "$ATLANTIS_RELEASE"
write_evidence_line "$report" collected_at "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
write_evidence_line "$report" hostname "$(hostname)"
write_evidence_line "$report" kernel "$(uname -sr)"
write_evidence_line "$report" source_tree_sha256 "$(python3 -c "import json; print(json.load(open('$REPO_DIR/release/candidate/source-manifest.json'))['source_tree_sha256'])")"
if git -C "$REPO_DIR" rev-parse HEAD >/dev/null 2>&1; then write_evidence_line "$report" source_commit "$(git -C "$REPO_DIR" rev-parse HEAD)"; else write_evidence_line "$report" source_commit UNVERSIONED_SOURCE; fi
write_evidence_line "$report" migration_004 "$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='004_security_and_durability'")"
write_evidence_line "$report" distribution_gate BLOCKED_PENDING_LEGAL_ARTIFACTS

compose ps > "$ATLANTIS_EVIDENCE_ROOT/compose-ps-final.txt"
database_psql -AtF $'\t' -c "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c WHERE c.relnamespace='public'::regnamespace AND c.relkind='r' ORDER BY c.relname" > "$ATLANTIS_EVIDENCE_ROOT/postgres-rls.tsv"
database_psql -AtF $'\t' -c "SELECT schemaname,tablename,policyname,roles,cmd FROM pg_policies ORDER BY tablename,policyname" > "$ATLANTIS_EVIDENCE_ROOT/postgres-policies.tsv"
cp "$REPO_DIR/release/BLOCKERS.yaml" "$ATLANTIS_EVIDENCE_ROOT/BLOCKERS.yaml"
cp "$REPO_DIR/release/candidate/source-sbom.cdx.json" "$ATLANTIS_EVIDENCE_ROOT/source-sbom.cdx.json"

find "$ATLANTIS_EVIDENCE_ROOT" -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$ATLANTIS_EVIDENCE_ROOT/SHA256SUMS"
chmod 600 "$ATLANTIS_EVIDENCE_ROOT"/*
log "PASS evidence collected at $ATLANTIS_EVIDENCE_ROOT"
