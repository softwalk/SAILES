#!/usr/bin/env bash
set -euo pipefail
ops_dir="$(cd "$(dirname "$0")" && pwd)"
config="${1:-/opt/atlantis/infrastructure/rc4-rollout.env}"
[[ -f "$config" ]] || { printf 'FAIL missing rollout config: %s\n' "$config" >&2; exit 1; }
[[ "${2:-}" == "--execute" ]] || { printf 'FAIL explicit --execute required\n' >&2; exit 1; }
[[ "$(stat -c '%u' "$config")" == "0" ]] || { printf 'FAIL rollout config must be owned by root\n' >&2; exit 1; }
config_mode="$(stat -c '%a' "$config")"
[[ "$config_mode" == "600" || "$config_mode" == "400" ]] || { printf 'FAIL rollout config must use mode 0600/0400\n' >&2; exit 1; }
set -a
source "$config"
set +a

on_error() {
  rc=$?
  printf 'FAIL rollout stopped with code %s. Review evidence and use 60_rollback.sh only if application images changed.\n' "$rc" >&2
  exit "$rc"
}
trap on_error ERR

"$ops_dir/00_preflight.sh"
"$ops_dir/01_prepare_secret_permissions.sh" --execute
"$ops_dir/01_validate_secrets.sh"
"$ops_dir/10_backup.sh" --execute
"$ops_dir/20_apply_migration_004.sh" --execute
"$ops_dir/21_apply_migration_005.sh" --execute
"$ops_dir/22_apply_migration_006.sh" --execute --approved-by "${APPROVED_BY:-}" --approved-date "${APPROVED_DATE:-}" --evidence-ref "${EVIDENCE_REF:-}" ${EVIDENCE_SHA:+--evidence-sha256 "$EVIDENCE_SHA"}
"$ops_dir/30_build_images.sh" --execute
"$ops_dir/40_deploy_shadow.sh" --execute
"$ops_dir/50_postdeploy_validate.sh"
"$ops_dir/70_collect_evidence.sh"
printf 'PASS Atlantis RC4 rollout completed in SHADOW mode. Pilot remains blocked.\n'
