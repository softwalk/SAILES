#!/usr/bin/env bash
# Validate/apply the canonical legacy-005 fingerprint. Clean installations whose
# migration 005 was canonical never need this reconciliation-only migration.
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
shift

approved_by=""; approved_date=""; evidence_ref=""; evidence_sha=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --approved-by) approved_by="${2:-}"; shift 2 ;;
    --approved-date) approved_date="${2:-}"; shift 2 ;;
    --evidence-ref) evidence_ref="${2:-}"; shift 2 ;;
    --evidence-sha256) evidence_sha="${2:-}"; shift 2 ;;
    *) die "unknown migration 007 argument: $1" ;;
  esac
done

readonly canonical_005="5ba50e9c2e465eea7e65a8c47f0ae89d2791e498ddd02c95c6dda04fa9e91d8d"
readonly legacy_005="853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e"
recorded_005="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='005_reconcile_migration_004_checksum'" 2>/dev/null || true)"
if [[ -z "$recorded_005" ]]; then
  recorded_004="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='004_security_and_durability'" 2>/dev/null || true)"
  if [[ "$recorded_004" == "f07309b514f1fb1bb4546a3c09712123b45de255c202e25b9f6c098d6eb3ba2e" ]]; then
    log "SKIP migration 007: migration 004 is canonical; reconciliations 005-007 do not apply"
    exit 0
  fi
fi
if [[ "$recorded_005" == "$canonical_005" ]]; then
  log "SKIP migration 007: migration 005 is canonical; legacy reconciliation does not apply"
  exit 0
fi
[[ "$recorded_005" == "$legacy_005" ]] || die "migration 005 checksum is missing or unrecognized"
recorded_006="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='006_reconcile_migration_005_applied_checksum'" 2>/dev/null || true)"
[[ "$recorded_006" =~ ^[a-f0-9]{64}$ ]] || die "legacy migration 005 requires migration 006 before 007"

migration="$REPO_DIR/database/007_reconcile_migration_005_fingerprint_canonical.sql"
require_file "$migration"
checksum="$(sha256sum "$migration" | awk '{print $1}')"
recorded_007="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='007_reconcile_migration_005_fingerprint_canonical'" 2>/dev/null || true)"
if [[ -n "$recorded_007" ]]; then
  [[ "$recorded_007" == "$checksum" ]] || die "migration 007 checksum mismatch"
  valid="$(database_psql -Atqc "SELECT count(*) FROM schema_migration_validation WHERE migration_version='005_reconcile_migration_004_checksum' AND validation_type='canonical_fingerprint' AND match")"
  [[ "$valid" == "1" ]] || die "migration 007 canonical validation evidence missing"
  log "PASS migration 007 already applied and validated"
  exit 0
fi

[[ ${#approved_by} -ge 3 ]] || die "migration 007 requires nominative --approved-by"
[[ "$approved_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || die "migration 007 requires --approved-date YYYY-MM-DD"
[[ -n "$evidence_ref" ]] || die "migration 007 requires --evidence-ref"
if [[ -z "$evidence_sha" ]]; then
  evidence_path="$evidence_ref"; [[ "$evidence_path" = /* ]] || evidence_path="$ATLANTIS_ROOT/$evidence_path"
  require_file "$evidence_path"
  evidence_sha="$(sha256sum "$evidence_path" | awk '{print $1}')"
fi
[[ "$evidence_sha" =~ ^[a-f0-9]{64}$ ]] || die "migration 007 evidence SHA-256 invalid"

backup_dir="${ATLANTIS_BACKUP_DIR:-$ATLANTIS_BACKUP_ROOT/latest}"
require_file "$backup_dir/atlantis.dump"
(cd "$backup_dir" && sha256sum -c SHA256SUMS >/dev/null) || die "backup checksum validation failed"
database_psql -v checksum="$checksum" -v approved_by="$approved_by" -v approved_date="$approved_date" \
  -v evidence_ref="$evidence_ref" -v evidence_sha256="$evidence_sha" -f "$migration"
log "PASS migration 007 applied and canonical fingerprint validated"
