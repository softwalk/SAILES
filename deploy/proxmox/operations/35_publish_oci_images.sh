#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
require_command docker

REGISTRY="${OCI_REGISTRY:-ghcr.io/softwalk}"
RELEASE="${ATLANTIS_RELEASE:-0.9.0-rc5}"

log "Publishing Atlantis OCI images to $REGISTRY"

images=(
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
  remote_digest="$(docker buildx imagetools inspect "$remote_tag" --format '{{json .Manifest.Digest}}' | tr -d '"')"
  [[ "$remote_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || die "registry did not return a manifest digest for $remote_tag"
  printf '%s\t%s@%s\n' "$img" "$REGISTRY/$img" "$remote_digest" >> "$output"
done

chmod 600 "$output"
log "PASS OCI images published; digests recorded at $output"
