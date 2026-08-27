#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
require_command psql

migration="$REPO_DIR/database/005_reconcile_migration_004_checksum.sql"
require_file "$migration"
backup_dir="${ATLANTIS_BACKUP_DIR:-$ATLANTIS_BACKUP_ROOT/latest}"
require_file "$backup_dir/atlantis.dump"
(cd "$backup_dir" && sha256sum -c SHA256SUMS >/dev/null) || die "backup checksum validation failed"

canonical_004="f07309b514f1fb1bb4546a3c09712123b45de255c202e25b9f6c098d6eb3ba2e"
legacy_004="9c1850fcaa632f2189deac5e9b66e02fa85be92a920b6cae7696c9b691e4bacb"
recorded_004="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='004_security_and_durability'")"
if [[ "$recorded_004" == "$canonical_004" ]]; then
  log "PASS migration 004 is canonical; reconciliation 005 is not applicable"
  exit 0
fi
[[ "$recorded_004" == "$legacy_004" ]] || die "unrecognized migration 004 checksum=$recorded_004"

migration_checksum="$(sha256sum "$migration" | awk '{print $1}')"
recorded_005="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='005_reconcile_migration_004_checksum'" 2>/dev/null || true)"
if [[ -n "$recorded_005" ]]; then
  [[ "$recorded_005" == "$migration_checksum" || "$recorded_005" == "853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e" ]] || die "migration 005 checksum mismatch"
  actual="$(database_psql -Atqc "SELECT app.migration_004_object_fingerprint()")"
  [[ "$actual" == "53e77f497b6ee0e30963dd08a734dd7b2d1a997c52c742ee42bb4c6228818b6d" ]] || die "current object fingerprint mismatch"
  approved_count="$(database_psql -Atqc "SELECT count(*) FROM schema_migration_reconciliation WHERE version='004_security_and_durability' AND legacy_checksum='$legacy_004' AND canonical_checksum='$canonical_004' AND approved_by IS NOT NULL AND approved_date IS NOT NULL AND evidence_sha256 ~ '^[a-f0-9]{64}$'")"
  [[ "$approved_count" == "1" ]] || die "migration 005 reconciliation approval/evidence missing"
  log "PASS migration 005 already applied and verified"
  exit 0
fi

approved_by="${ATLANTIS_MIGRATION_APPROVED_BY:-}"
approved_date="${ATLANTIS_MIGRATION_APPROVED_DATE:-}"
evidence_file="${ATLANTIS_MIGRATION_EVIDENCE_FILE:-}"
[[ ${#approved_by} -ge 3 ]] || die "ATLANTIS_MIGRATION_APPROVED_BY is required"
[[ "$approved_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || die "ATLANTIS_MIGRATION_APPROVED_DATE must be YYYY-MM-DD"
require_file "$evidence_file"
evidence_sha256="$(sha256sum "$evidence_file" | awk '{print $1}')"
evidence_ref="${ATLANTIS_MIGRATION_EVIDENCE_REF:-documentation/evidence/rc6/$(basename "$evidence_file")}" 

database_psql -v checksum="$migration_checksum" -v approved_by="$approved_by" \
  -v approved_date="$approved_date" -v evidence_ref="$evidence_ref" \
  -v evidence_sha256="$evidence_sha256" -f "$migration"

row="$(database_psql -AtF $'\t' -c "SELECT approved_by,approved_date,evidence_sha256,object_fingerprint FROM schema_migration_reconciliation WHERE version='004_security_and_durability' AND legacy_checksum='$legacy_004' AND canonical_checksum='$canonical_004'")"
IFS=$'\t' read -r stored_approver stored_date stored_evidence stored_fingerprint <<< "$row"
[[ "$stored_approver" == "$approved_by" && "$stored_date" == "$approved_date" ]] || die "stored approval mismatch"
[[ "$stored_evidence" == "$evidence_sha256" && "$stored_fingerprint" == "53e77f497b6ee0e30963dd08a734dd7b2d1a997c52c742ee42bb4c6228818b6d" ]] || die "stored evidence/fingerprint mismatch"
log "PASS migration 005 applied without rewriting migration 004 history"
