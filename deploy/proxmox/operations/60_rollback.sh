#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
backup_dir="${2:-${ATLANTIS_BACKUP_DIR:-$ATLANTIS_BACKUP_ROOT/latest}}"
require_file "$backup_dir/rollback-images.yaml"
require_file "$backup_dir/atlantis.dump"
(cd "$backup_dir" && sha256sum -c SHA256SUMS >/dev/null) || die "backup checksum validation failed"

log "Rolling application containers back; migration 004 remains because it is additive and security-critical"
docker compose --env-file "$ATLANTIS_ENV_FILE" -f "$ATLANTIS_COMPOSE_FILE" -f "$backup_dir/rollback-images.yaml" up -d --no-build --remove-orphans
docker compose --env-file "$ATLANTIS_ENV_FILE" -f "$ATLANTIS_COMPOSE_FILE" -f "$backup_dir/rollback-images.yaml" ps
log "PASS application rollback requested. Database restore is intentionally manual and requires a maintenance window."
