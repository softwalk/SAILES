#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_execute "${1:-}"
assert_safe_root
for command in pg_dump sha256sum docker; do require_command "$command"; done

timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
backup_dir="$ATLANTIS_BACKUP_ROOT/$timestamp"
[[ ! -e "$backup_dir" ]] || die "backup destination already exists: $backup_dir"
install -d -m 700 "$backup_dir"

password_file="${ATLANTIS_DATABASE_MIGRATOR_PASSWORD_HOST_FILE:-$ATLANTIS_SECRET_DIR/postgres_migrator_password.txt}"
host="${ATLANTIS_DATABASE_HOST_FROM_VM:-127.0.0.1}"
port="${ATLANTIS_DATABASE_PORT:-5432}"
database="${ATLANTIS_DATABASE_NAME:-atlantis}"
user="${ATLANTIS_DATABASE_MIGRATOR_USER:-atlantis_migrator}"
dsn="host=$host port=$port dbname=$database user=$user sslmode=${ATLANTIS_DATABASE_SSLMODE:-verify-full} sslrootcert=${ATLANTIS_DATABASE_SSLROOTCERT_HOST:-$ATLANTIS_SECRET_DIR/postgres_ca.crt}"

log "Creating encrypted-transport PostgreSQL backup"
PGPASSWORD="$(read_secret "$password_file")" pg_dump "$dsn" --format=custom --no-owner --no-privileges --file "$backup_dir/atlantis.dump"
PGPASSWORD="$(read_secret "$password_file")" pg_dump "$dsn" --schema-only --no-owner --no-privileges --file "$backup_dir/schema.sql"
docker ps --no-trunc --format '{{.Names}}\t{{.Image}}\t{{.Status}}' > "$backup_dir/docker-before.tsv"
docker image ls --no-trunc --digests --format '{{.Repository}}\t{{.Tag}}\t{{.Digest}}\t{{.ID}}' > "$backup_dir/images-before.tsv"
docker compose --env-file "$ATLANTIS_ENV_FILE" -f "$ATLANTIS_COMPOSE_FILE" config > "$backup_dir/compose.resolved.yaml"
if git -C "$REPO_DIR" rev-parse HEAD >/dev/null 2>&1; then git -C "$REPO_DIR" rev-parse HEAD > "$backup_dir/source-commit.txt"; else printf 'UNVERSIONED_SOURCE\n' > "$backup_dir/source-commit.txt"; fi
(cd "$backup_dir" && sha256sum atlantis.dump schema.sql docker-before.tsv images-before.tsv compose.resolved.yaml source-commit.txt > SHA256SUMS)
chmod 600 "$backup_dir"/*
ln -sfn "$backup_dir" "$ATLANTIS_BACKUP_ROOT/latest"
log "PASS backup_dir=$backup_dir"
