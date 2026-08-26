#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
require_command psql
require_command sha256sum

migration="$REPO_DIR/database/008_pilot_readiness.sql"
require_file "$migration"
backup_dir="${ATLANTIS_BACKUP_DIR:-$ATLANTIS_BACKUP_ROOT/latest}"
require_file "$backup_dir/atlantis.dump"
(cd "$backup_dir" && sha256sum -c SHA256SUMS >/dev/null) || die "backup checksum validation failed"

checksum="$(sha256sum "$migration" | awk '{print $1}')"
recorded="$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='008_pilot_readiness'" 2>/dev/null || true)"
if [[ -n "$recorded" ]]; then
  [[ "$recorded" == "$checksum" ]] || die "migration 008 checksum mismatch"
  log "migration 008 already recorded; verifying effective objects"
else
  database_psql -v checksum="$checksum" -f "$migration"
fi

forced="$(database_psql -Atqc "SELECT count(*) FROM pg_class WHERE relname IN ('workflow_event','model_budget_daily','model_budget_reservation') AND relrowsecurity AND relforcerowsecurity")"
[[ "$forced" == "3" ]] || die "migration 008 forced RLS validation failed"
database_psql -Atqc "SELECT proacl::text FROM pg_proc WHERE oid='app.append_audit_event(uuid,text,text,text,text,text,uuid,jsonb,uuid)'::regprocedure" | grep -q atlantis_runtime || die "runtime audit grant missing"
log "PASS migration 008 applied/recorded and effective objects verified"
