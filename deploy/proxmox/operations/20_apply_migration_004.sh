#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
require_command psql

migration="$REPO_DIR/database/004_security_and_durability.sql"
require_file "$migration"
backup_dir="${ATLANTIS_BACKUP_DIR:-$ATLANTIS_BACKUP_ROOT/latest}"
require_file "$backup_dir/atlantis.dump"
(cd "$backup_dir" && sha256sum -c SHA256SUMS >/dev/null) || die "backup checksum validation failed"

checksum="$(sha256sum "$migration" | awk '{print $1}')"
prerequisites="$(database_psql -Atqc "SELECT to_regclass('public.schema_migration') IS NOT NULL AND to_regclass('public.suppression') IS NOT NULL")"
[[ "$prerequisites" == "t" ]] || die "migrations 001-003 must be applied before migration 004"
recorded="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='004_security_and_durability'" 2>/dev/null || true)"
if [[ -n "$recorded" ]]; then
  if [[ "$recorded" == "$checksum" ]]; then
    log "PASS migration 004 already applied with canonical checksum=$checksum"
    exit 0
  fi
  if [[ "$recorded" == "9c1850fcaa632f2189deac5e9b66e02fa85be92a920b6cae7696c9b691e4bacb" ]]; then
    log "PASS migration 004 legacy checksum preserved; migration 005 reconciliation required"
    exit 0
  fi
  die "migration 004 has unrecognized checksum=$recorded"
fi

policy_exists="$(database_psql -Atqc "SELECT EXISTS(SELECT 1 FROM pg_policy WHERE polrelid='suppression'::regclass AND polname='suppression_tenant_and_global_read')")"
[[ "$policy_exists" == "f" ]] || die "migration policy exists without schema_migration record; manual reconciliation required"

log "Applying migration 004 checksum=$checksum"
database_psql -f "$migration"
database_psql -v version="004_security_and_durability" -v checksum="$checksum" -c \
  "INSERT INTO schema_migration(version,checksum) VALUES (:'version',:'checksum') ON CONFLICT (version) DO NOTHING"

database_psql -Atqc "SELECT polname FROM pg_policy WHERE polrelid='suppression'::regclass ORDER BY polname" | grep -Fxq suppression_tenant_and_global_read || die "global suppression read policy missing"
database_psql -Atqc "SELECT rolname FROM pg_roles WHERE rolname='atlantis_suppression_admin'" | grep -Fxq atlantis_suppression_admin || die "suppression admin role missing"
log "PASS migration 004 applied and verified"
