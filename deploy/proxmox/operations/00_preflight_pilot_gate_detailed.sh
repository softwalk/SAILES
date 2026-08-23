#!/usr/bin/env bash
# Gate canónico — salida detallada (todos los controles PASS + FAIL).
set -uo pipefail
cd "$(dirname "$0")"
source ./lib.sh
ENV_FILE="${ATLANTIS_ENV_FILE:-/opt/atlantis/infrastructure/.env}"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
pass() { log "PASS $*"; }
fail() { log "FAIL $*"; }

echo "### Gate canónico — salida detallada (todos los controles) ###"
echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

for cmd in docker psql openssl curl python3; do
  command -v "$cmd" >/dev/null 2>&1 && pass "comando $cmd presente" || fail "comando $cmd ausente"
done

owner=$(stat -c '%u' "$ENV_FILE" 2>/dev/null || echo "?")
mode=$(stat -c '%a' "$ENV_FILE" 2>/dev/null || echo "?")
[[ "$owner" == "0" ]] && pass "environment file root-owned" || fail "environment file must be root-owned (owner=$owner)"
[[ "$mode" == "600" || "$mode" == "400" ]] && pass "environment file mode $mode" || fail "environment file mode must be 0600/0400 (mode=$mode)"

declare -A vars
while IFS='=' read -r k v; do [[ "$k" =~ ^[A-Z] ]] && vars[$k]="$v"; done < <(sudo cat "$ENV_FILE" 2>/dev/null || true)
for key in ATLANTIS_ENV ATLANTIS_DATABASE_SSLMODE ATLANTIS_DATABASE_SSLROOTCERT ATLANTIS_REQUIRE_WORKLOAD_AUTH ATLANTIS_REQUIRE_DURABLE_STATE ATLANTIS_CRM_STORAGE ATLANTIS_SHADOW_MODE; do
  [[ -n "${vars[$key]:-}" ]] && pass "$key presente" || fail "$key ausente"
done

[[ "${vars[ATLANTIS_ENV]:-}" == "production" ]] && pass "ATLANTIS_ENV=production" || fail "ATLANTIS_ENV must equal production (actual: ${vars[ATLANTIS_ENV]:-UNSET})"
[[ "${vars[ATLANTIS_DATABASE_SSLMODE]:-}" == "verify-full" ]] && pass "sslmode=verify-full" || fail "sslmode must equal verify-full"
[[ "${vars[ATLANTIS_DATABASE_SSLROOTCERT]:-}" == "/run/secrets/postgres_ca" ]] && pass "SSLROOTCERT=/run/secrets/postgres_ca" || fail "unexpected PostgreSQL CA container path"
[[ "${vars[ATLANTIS_REQUIRE_WORKLOAD_AUTH]:-}" == "true" ]] && pass "workload auth=true" || fail "workload authentication must be true"
[[ "${vars[ATLANTIS_REQUIRE_DURABLE_STATE]:-}" == "true" ]] && pass "durable state=true" || fail "durable state must be true"
[[ "${vars[ATLANTIS_CRM_STORAGE]:-}" == "postgres" ]] && pass "CRM storage=postgres" || fail "CRM storage must be postgres"
[[ "${vars[ATLANTIS_SHADOW_MODE]:-}" == "true" ]] && pass "shadow mode=true" || fail "shadow mode must be true"

PW=$(sudo cat /opt/atlantis/secrets/postgres_runtime_password.txt 2>/dev/null || true)
if [[ -n "$PW" ]]; then
  tls=$(PGPASSWORD="$PW" psql "host=127.0.0.1 port=5432 dbname=atlantis user=atlantis_runtime sslmode=verify-full sslrootcert=/opt/atlantis/secrets/postgres_ca.crt" -Atqc "SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()" 2>/dev/null || true)
  [[ "$tls" == "t" ]] && pass "runtime PostgreSQL connection uses verified TLS" || fail "runtime PostgreSQL session is not TLS"
else
  fail "no se pudo leer postgres_runtime_password"
fi

mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
mem_available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
(( mem_total >= 7340032 )) && pass "effective RAM ${mem_total}KiB >= 7340032KiB" || fail "effective RAM ${mem_total}KiB below 7340032KiB"
(( mem_available >= 2097152 )) && pass "available RAM ${mem_available}KiB >= 2097152KiB" || fail "available RAM ${mem_available}KiB below 2097152KiB"

ck004=$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='004_security_and_durability'" 2>/dev/null || true)
[[ "$ck004" == "9c1850fcaa632f2189deac5e9b66e02fa85be92a920b6cae7696c9b691e4bacb" ]] && pass "migration 004 checksum verificado" || fail "migration 004 checksum no verificado"
fp004=$(database_psql -Atqc "SELECT app.migration_004_object_fingerprint()" 2>/dev/null || true)
[[ "$fp004" == "53e77f497b6ee0e30963dd08a734dd7b2d1a997c52c742ee42bb4c6228818b6d" ]] && pass "migration 004 fingerprint canónico" || fail "migration 004 fingerprint mismatch"

commit=$(cd /opt/atlantis/repositories/atlantis-sales-platform && git rev-parse HEAD 2>/dev/null || true)
[[ -n "$commit" ]] && pass "Git commit presente (${commit:0:12})" || fail "sin commit Git"
dirty=$(cd /opt/atlantis/repositories/atlantis-sales-platform && git status --porcelain 2>/dev/null | wc -l)
[[ "$dirty" == "0" ]] && pass "source worktree limpio" || fail "source worktree is dirty"

if [[ -f "$ATLANTIS_EVIDENCE_ROOT/image-digests.tsv" ]]; then
  dc=0; ok=0
  while IFS=$'\t' read -r image digest; do
    [[ -n "$image" ]] || continue
    dc=$((dc+1))
    cur=$(docker image inspect --format '{{.Id}}' "$image" 2>/dev/null || true)
    [[ "$cur" == "$digest" ]] && ok=$((ok+1))
  done < "$ATLANTIS_EVIDENCE_ROOT/image-digests.tsv"
  [[ "$dc" == "8" && "$ok" == "8" ]] && pass "8/8 image digests MATCH" || fail "image digests: $ok/$dc MATCH"
else
  fail "image digest evidence missing"
fi

prov=$(curl --fail --silent --max-time 5 http://127.0.0.1:8084/health 2>/dev/null | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("configured_providers",[])))' 2>/dev/null || echo 0)
(( prov >= 1 )) && pass "proveedor de modelos configurado ($prov)" || fail "no approved model provider configured"

hc=0
for port in 8081 8082 8083 8084 8085 8086 8087; do
  curl --fail --silent --max-time 3 "http://127.0.0.1:$port/health" >/dev/null 2>&1 && hc=$((hc+1))
done
[[ "$hc" == "7" ]] && pass "7/7 servicios healthy" || fail "servicios healthy: $hc/7"

echo ""
echo "=== FIN ==="
