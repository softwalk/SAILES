#!/usr/bin/env bash
set -euo pipefail

readonly OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_DIR="$(cd "$OPS_DIR/../../.." && pwd)"
readonly ATLANTIS_ROOT="${ATLANTIS_ROOT:-/opt/atlantis}"
readonly ATLANTIS_COMPOSE_FILE="${ATLANTIS_COMPOSE_FILE:-$REPO_DIR/deploy/proxmox/compose.application.yaml}"
readonly ATLANTIS_ENV_FILE="${ATLANTIS_ENV_FILE:-$ATLANTIS_ROOT/infrastructure/.env}"
readonly ATLANTIS_SECRET_DIR="${ATLANTIS_SECRET_DIR:-$ATLANTIS_ROOT/secrets}"
readonly ATLANTIS_BACKUP_ROOT="${ATLANTIS_BACKUP_ROOT:-$ATLANTIS_ROOT/backups/rc5}"
readonly ATLANTIS_EVIDENCE_ROOT="${ATLANTIS_EVIDENCE_ROOT:-$ATLANTIS_ROOT/documentation/evidence/rc5}"
readonly ATLANTIS_RELEASE="0.9.0-rc5"

log() { printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { log "FAIL $*" >&2; exit 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "missing command: $1"; }
require_file() { [[ -f "$1" ]] || die "missing file: $1"; }
require_directory() { [[ -d "$1" ]] || die "missing directory: $1"; }

assert_safe_root() {
  [[ "$ATLANTIS_ROOT" = /* ]] || die "ATLANTIS_ROOT must be absolute"
  [[ "$ATLANTIS_ROOT" != "/" && "$ATLANTIS_ROOT" != "/opt" ]] || die "unsafe ATLANTIS_ROOT"
}

require_execute() {
  [[ "${1:-}" == "--execute" ]] || die "dry stop: rerun with --execute after reviewing output"
}

compose() {
  docker compose --env-file "$ATLANTIS_ENV_FILE" -f "$ATLANTIS_COMPOSE_FILE" "$@"
}

read_secret() {
  local path="$1"
  require_file "$path"
  tr -d '\r\n' < "$path"
}

database_psql() {
  local password_file="${ATLANTIS_DATABASE_MIGRATOR_PASSWORD_HOST_FILE:-$ATLANTIS_SECRET_DIR/postgres_migrator_password.txt}"
  local host="${ATLANTIS_DATABASE_HOST_FROM_VM:-127.0.0.1}"
  local port="${ATLANTIS_DATABASE_PORT:-5432}"
  local database="${ATLANTIS_DATABASE_NAME:-atlantis}"
  local user="${ATLANTIS_DATABASE_MIGRATOR_USER:-atlantis_migrator}"
  PGPASSWORD="$(read_secret "$password_file")" psql \
    "host=$host port=$port dbname=$database user=$user sslmode=${ATLANTIS_DATABASE_SSLMODE:-verify-full} sslrootcert=${ATLANTIS_DATABASE_SSLROOTCERT_HOST:-$ATLANTIS_SECRET_DIR/postgres_ca.crt}" \
    -v ON_ERROR_STOP=1 "$@"
}

database_runtime_psql() {
  local password_file="${ATLANTIS_DATABASE_PASSWORD_HOST_FILE:-$ATLANTIS_SECRET_DIR/postgres_runtime_password.txt}"
  local host="${ATLANTIS_DATABASE_HOST_FROM_VM:-127.0.0.1}"
  local port="${ATLANTIS_DATABASE_PORT:-5432}"
  local database="${ATLANTIS_DATABASE_NAME:-atlantis}"
  local user="${ATLANTIS_DATABASE_USER:-atlantis_runtime}"
  PGPASSWORD="$(read_secret "$password_file")" psql \
    "host=$host port=$port dbname=$database user=$user sslmode=${ATLANTIS_DATABASE_SSLMODE:-verify-full} sslrootcert=${ATLANTIS_DATABASE_SSLROOTCERT_HOST:-$ATLANTIS_SECRET_DIR/postgres_ca.crt}" \
    -v ON_ERROR_STOP=1 "$@"
}

write_evidence_line() {
  local file="$1" key="$2" value="$3"
  printf '%s=%s\n' "$key" "$value" >> "$file"
}
