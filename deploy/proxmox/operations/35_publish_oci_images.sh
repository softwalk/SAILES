#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
require_command docker

REGISTRY="${OCI_REGISTRY:-ghcr.io/softwalk}"
RELEASE="${ATLANTIS_RELEASE:-0.9.0-rc5}"

log "Publishing Atlantis OCI images to $REGISTRY"

images=(
  atlantis-python-base
  atlantis-policy-gateway
  atlantis-crm-api
  atlantis-orchestrator
  atlantis-model-gateway
  atlantis-voice-adapter
  atlantis-whatsapp-adapter
  atlantis-marketia-adapter
)

install -d -m 700 "$ATLANTIS_EVIDENCE_ROOT"
output="$ATLANTIS_EVIDENCE_ROOT/published-image-digests.tsv"
: > "$output"

for img in "${images[@]}"; do
  local_tag="$img:$RELEASE"
  remote_tag="$REGISTRY/$img:$RELEASE"
  log "Tagging and pushing $remote_tag"
  docker tag "$local_tag" "$remote_tag"
  docker push "$remote_tag"
  remote_digest="$(docker inspect --format="{{index .RepoDigests 0}}" "$remote_tag" 2>/dev/null || echo "$remote_tag@$(docker image inspect --format {{.Id}} "$local_tag")")"
  printf %st%sn "$img" "$remote_digest" >> "$output"
done

chmod 600 "$output"
log "PASS OCI images published; digests recorded at $output"
