#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
require_command docker
require_file "$ATLANTIS_ENV_FILE"

base_source="${PYTHON_BASE_IMAGE:-$(sed -n 's/^PYTHON_BASE_IMAGE=//p' "$ATLANTIS_ENV_FILE" | tail -1)}"
base_source="${base_source%\"}"; base_source="${base_source#\"}"
[[ "$base_source" =~ @sha256:[a-f0-9]{64}$ ]] || die "PYTHON_BASE_IMAGE must be pinned by sha256 digest"
base_tag="atlantis-python-base:$ATLANTIS_RELEASE"

log "Building immutable runtime base"
docker build --pull=false --build-arg "PYTHON_BASE_IMAGE=$base_source" -f "$REPO_DIR/deploy/proxmox/base/Dockerfile" -t "$base_tag" "$REPO_DIR"

declare -A dockerfiles=(
  [policy_gateway]=services/policy_gateway/Dockerfile
  [crm_api]=services/crm_api/Dockerfile
  [orchestrator]=services/orchestrator/Dockerfile
  [model_gateway]=services/model_gateway/Dockerfile
  [channel_adapters]=services/channel_adapters/Dockerfile
)
for service in policy_gateway crm_api orchestrator model_gateway channel_adapters; do
  tag="atlantis-${service//_/-}:$ATLANTIS_RELEASE"
  log "Building $tag"
  docker build --pull=false --build-arg "PYTHON_BASE_IMAGE=$base_tag" -f "$REPO_DIR/${dockerfiles[$service]}" -t "$tag" "$REPO_DIR"
done
docker tag "atlantis-channel-adapters:$ATLANTIS_RELEASE" "atlantis-voice-adapter:$ATLANTIS_RELEASE"
docker tag "atlantis-channel-adapters:$ATLANTIS_RELEASE" "atlantis-whatsapp-adapter:$ATLANTIS_RELEASE"
docker tag "atlantis-channel-adapters:$ATLANTIS_RELEASE" "atlantis-marketia-adapter:$ATLANTIS_RELEASE"

install -d -m 700 "$ATLANTIS_EVIDENCE_ROOT"
output="$ATLANTIS_EVIDENCE_ROOT/image-digests.tsv"
: > "$output"
for image in "$base_tag" \
  "atlantis-policy-gateway:$ATLANTIS_RELEASE" "atlantis-crm-api:$ATLANTIS_RELEASE" \
  "atlantis-orchestrator:$ATLANTIS_RELEASE" "atlantis-model-gateway:$ATLANTIS_RELEASE" \
  "atlantis-voice-adapter:$ATLANTIS_RELEASE" "atlantis-whatsapp-adapter:$ATLANTIS_RELEASE" \
  "atlantis-marketia-adapter:$ATLANTIS_RELEASE"; do
  id="$(docker image inspect --format '{{.Id}}' "$image")"
  [[ "$id" =~ ^sha256:[a-f0-9]{64}$ ]] || die "invalid local image digest for $image"
  printf '%s\t%s\n' "$image" "$id" >> "$output"
done
chmod 600 "$output"
log "PASS images built; digests recorded at $output"
