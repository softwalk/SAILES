#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
require_command docker
require_file "$ATLANTIS_EVIDENCE_ROOT/image-digests.tsv"
backup_dir="${ATLANTIS_BACKUP_DIR:-$ATLANTIS_BACKUP_ROOT/latest}"
require_file "$backup_dir/atlantis.dump"

grep -Eq '^ATLANTIS_SHADOW_MODE=(true|"true")$' "$ATLANTIS_ENV_FILE" || die "shadow mode is not explicitly true"
export ATLANTIS_RELEASE_TAG="$ATLANTIS_RELEASE"
services=(policy_gateway crm_api orchestrator model_gateway voice_adapter marketia_adapter)

rollback_file="$backup_dir/rollback-images.yaml"
printf 'services:\n' > "$rollback_file"
for service in "${services[@]}"; do
  cid="$(compose ps -a -q "$service" 2>/dev/null || true)"
  [[ -n "$cid" ]] || continue
  image_id="$(docker inspect --format '{{.Image}}' "$cid")"
  rollback_tag="atlantis-rollback-${service}:$(basename "$(readlink -f "$backup_dir")")"
  docker tag "$image_id" "$rollback_tag"
  printf '  %s:\n    image: %s\n' "$service" "$rollback_tag" >> "$rollback_file"
done
chmod 600 "$rollback_file"

log "Deploying RC5 with contact disabled by shadow mode"
compose up -d --no-build --remove-orphans

deadline=$((SECONDS + 240))
while (( SECONDS < deadline )); do
  unhealthy=0
  for service in "${services[@]}"; do
    cid="$(compose ps -q "$service")"
    [[ -n "$cid" ]] || { unhealthy=1; continue; }
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid")"
    [[ "$status" == "healthy" ]] || unhealthy=1
  done
  [[ "$unhealthy" -eq 0 ]] && break
  sleep 5
done
for service in "${services[@]}"; do
  cid="$(compose ps -q "$service")"
  [[ -n "$cid" ]] || die "service missing after deployment: $service"
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid")"
  [[ "$status" == "healthy" ]] || die "service not healthy: $service status=$status; run 60_rollback.sh"
done
compose ps > "$ATLANTIS_EVIDENCE_ROOT/compose-ps-after.txt"
log "PASS RC5 shadow deployment healthy"
