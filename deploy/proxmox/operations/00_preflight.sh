#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
assert_safe_root

fail=0

for command in docker python3 openssl psql pg_dump sha256sum curl awk sed stat ss ip; do
  if command -v "$command" >/dev/null 2>&1; then log "PASS command=$command"; else log "FAIL command=$command"; fail=1; fi
done
docker compose version >/dev/null 2>&1 || { log "FAIL docker compose plugin"; fail=1; }

expected_host="${ATLANTIS_EXPECTED_HOST:-atlantis-core}"
expected_ip="${ATLANTIS_EXPECTED_IP:-192.168.100.160}"
[[ "$(hostname)" == "$expected_host" ]] || { log "FAIL hostname expected=$expected_host actual=$(hostname)"; fail=1; }
ip -brief address | grep -Fq "$expected_ip" || { log "FAIL expected IP missing: $expected_ip"; fail=1; }

memory_kib="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
minimum_memory_kib="${ATLANTIS_MIN_MEMORY_KIB:-7340032}"
(( memory_kib >= minimum_memory_kib )) || { log "FAIL effective memory KiB=$memory_kib required=$minimum_memory_kib"; fail=1; }
available_disk_kib="$(df -Pk "$ATLANTIS_ROOT" 2>/dev/null | awk 'NR==2 {print $4}' || true)"
minimum_disk_kib="${ATLANTIS_MIN_DISK_KIB:-10485760}"
[[ -n "$available_disk_kib" ]] && (( available_disk_kib >= minimum_disk_kib )) || { log "FAIL available disk KiB=${available_disk_kib:-0} required=$minimum_disk_kib"; fail=1; }

for directory in infrastructure repositories secrets backups documentation; do
  [[ -d "$ATLANTIS_ROOT/$directory" ]] || { log "FAIL missing directory $ATLANTIS_ROOT/$directory"; fail=1; }
done
for network in atlantis-platform_atlantis-control atlantis-platform_atlantis-data; do
  docker network inspect "$network" >/dev/null 2>&1 || { log "FAIL missing Docker network $network"; fail=1; }
done

require_file "$ATLANTIS_COMPOSE_FILE"
require_file "$ATLANTIS_ENV_FILE"
grep -Eq '^ATLANTIS_SHADOW_MODE=(true|"true")$' "$ATLANTIS_ENV_FILE" || { log "FAIL ATLANTIS_SHADOW_MODE must be true"; fail=1; }
grep -Eq '^ATLANTIS_REQUIRE_WORKLOAD_AUTH=(true|"true")$' "$ATLANTIS_ENV_FILE" || { log "FAIL workload auth must be true"; fail=1; }
grep -Eq '^ATLANTIS_REQUIRE_DURABLE_STATE=(true|"true")$' "$ATLANTIS_ENV_FILE" || { log "FAIL durable state must be true"; fail=1; }
grep -Eq '^ATLANTIS_CRM_STORAGE=(postgres|"postgres")$' "$ATLANTIS_ENV_FILE" || { log "FAIL CRM storage must be postgres"; fail=1; }

docker compose --env-file "$ATLANTIS_ENV_FILE" -f "$ATLANTIS_COMPOSE_FILE" config -q || { log "FAIL compose config"; fail=1; }
if ss -lntH | awk '{print $4}' | grep -Eq '(^|:)(808[1-7])$' && ss -lntH | awk '{print $4}' | grep -E '(^|:)(808[1-7])$' | grep -Evq '^(127\.0\.0\.1|\[::1\]):'; then
  log "FAIL application port exposed beyond loopback"; fail=1
fi

[[ "$fail" -eq 0 ]] || die "preflight blocked"
log "PASS RC4 preflight host=$expected_host memory_kib=$memory_kib disk_available_kib=$available_disk_kib"
