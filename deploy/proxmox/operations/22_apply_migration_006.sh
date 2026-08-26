#!/usr/bin/env bash
# ============================================================================
# 22_apply_migration_006.sh — Aplica la migración 006 de reconciliación de la 005.
# Condicional: solo aplica si 005 está registrada como 853d8622 (VM 110 existente).
#   En instalaciones nuevas (005 = 5ba50e9c), 006 no aplica y se omite.
# Requiere aprobación nominativa obligatoria + backup PostgreSQL REAL.
# Uso: 22_apply_migration_006.sh --execute --approved-by "Nombre Apellido" \
#        --approved-date YYYY-MM-DD --evidence-ref PATH [--evidence-sha256 SHA]
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck source=lib.sh
source ./lib.sh

EXECUTE=0
APPROVED_BY=""
APPROVED_DATE=""
EVIDENCE_REF=""
EVIDENCE_SHA=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) EXECUTE=1; shift ;;
    --approved-by) APPROVED_BY="$2"; shift 2 ;;
    --approved-date) APPROVED_DATE="$2"; shift 2 ;;
    --evidence-ref) EVIDENCE_REF="$2"; shift 2 ;;
    --evidence-sha256) EVIDENCE_SHA="$2"; shift 2 ;;
    *) echo "arg desconocido: $1" >&2; exit 2 ;;
  esac
done

fail() { echo "FAIL 006: $*" >&2; exit 1; }

[[ "$EXECUTE" == "1" ]] || fail "debe pasar --execute (aplicación explícita)"

SQL="$REPO_DIR/database/006_reconcile_migration_005_applied_checksum.sql"
[[ -f "$SQL" ]] || fail "no existe $SQL"

# --- Condicional: ¿005 está registrada como 853d8622 (existente) o 5ba50e9c (nueva)? ---
CK005_REGISTERED=$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='005_reconcile_migration_004_checksum'" 2>/dev/null || true)
if [[ -z "$CK005_REGISTERED" ]]; then
  CK004_REGISTERED=$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='004_security_and_durability'" 2>/dev/null || true)
  if [[ "$CK004_REGISTERED" == "f07309b514f1fb1bb4546a3c09712123b45de255c202e25b9f6c098d6eb3ba2e" ]]; then
    echo "SKIP 006: migration 004 es canónica y 005 no aplica."
    exit 0
  fi
  fail "migration 005 no registrada y migration 004 no es canónica"
fi
if [[ "$CK005_REGISTERED" == "5ba50e9c2e465eea7e65a8c47f0ae89d2791e498ddd02c95c6dda04fa9e91d8d" ]]; then
  echo "SKIP 006: migration 005 ya registrada con checksum corregido (instalación nueva). 006 no aplica."
  exit 0
fi
if [[ "$CK005_REGISTERED" != "853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e" ]]; then
  fail "unexpected migration 005 checksum: $CK005_REGISTERED"
fi
echo "005 registrada como 853d8622 (existente) -> 006 aplica."

CK006_EXPECTED=$(sha256sum "$SQL" | awk '{print $1}')
CK006_RECORDED=$(database_psql -Atqc "SELECT checksum FROM schema_migration WHERE version='006_reconcile_migration_005_applied_checksum'" 2>/dev/null || true)
if [[ -n "$CK006_RECORDED" ]]; then
  [[ "$CK006_RECORDED" == "$CK006_EXPECTED" ]] || fail "migration 006 checksum mismatch"
  RECONCILED=$(database_psql -Atqc "SELECT count(*) FROM schema_migration_reconciliation_005 WHERE version='005_reconcile_migration_004_checksum' AND registered_checksum='853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e' AND executed_checksum='5ba50e9c2e465eea7e65a8c47f0ae89d2791e498ddd02c95c6dda04fa9e91d8d' AND approved_by IS NOT NULL AND approved_date IS NOT NULL AND evidence_sha256 ~ '^[a-f0-9]{64}$'" 2>/dev/null || true)
  [[ "$RECONCILED" == "1" ]] || fail "migration 006 reconciliation evidence missing"
  echo "PASS 006 ya aplicada; checksum y evidencia verificados."
  exit 0
fi

[[ -n "$APPROVED_BY" ]] || fail "aprobador humano obligatorio (--approved-by)"
[[ "$APPROVED_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || fail "fecha aprobación obligatoria (--approved-date YYYY-MM-DD)"
[[ -n "$EVIDENCE_REF" ]] || fail "referencia de evidencia obligatoria (--evidence-ref)"

# --- Backup PostgreSQL REAL y obligatorio (dump + checksum + verificación) ---
TS=$(date +%Y%m%d_%H%M%S)
BK="$ATLANTIS_ROOT/backups/pre_006_$TS"
mkdir -p "$BK" || fail "no se pudo crear $BK"
DUMP="$BK/atlantis_pre006.dump"
echo "Backup PostgreSQL real en $DUMP ..."
docker exec atlantis-platform-postgres-1 pg_dump -U atlantis -d atlantis -F c -f "/tmp/atlantis_pre006.dump" \
  || fail "pg_dump falló"
docker cp "atlantis-platform-postgres-1:/tmp/atlantis_pre006.dump" "$DUMP" || fail "no se pudo extraer el dump"
[[ -s "$DUMP" ]] || fail "dump vacío o no creado: $DUMP"
sha256sum "$DUMP" > "$DUMP.sha256" || fail "no se pudo calcular el checksum del dump"
sha256sum -c "$DUMP.sha256" >/dev/null || fail "checksum del dump no verifica"
echo "Backup verificado: $(cat "$DUMP.sha256")"
echo "$BK" > /tmp/006_backup_dir.txt

# --- Checksum del archivo 006 ---
CK006="$CK006_EXPECTED"

# --- Si no se pasó evidence-sha256, lo calculo del archivo de evidencia ---
if [[ -z "$EVIDENCE_SHA" ]]; then
  EV="$ATLANTIS_ROOT/$EVIDENCE_REF"
  [[ -f "$EV" ]] || fail "archivo de evidencia no existe: $EV (pase --evidence-sha256 si no está en disco)"
  EVIDENCE_SHA=$(sha256sum "$EV" | awk '{print $1}')
fi

# --- Aplico la 006 ---
database_psql -v ON_ERROR_STOP=1 \
  -v checksum="$CK006" \
  -v approved_by="$APPROVED_BY" \
  -v approved_date="$APPROVED_DATE" \
  -v evidence_ref="$EVIDENCE_REF" \
  -v evidence_sha256="$EVIDENCE_SHA" \
  -f "$SQL" || fail "migración 006 falló (¿fingerprint no coincide con el esperado?)"

echo "PASS 006 aplicada: reconciliación de 005 (registered 853d8622 + executed 5ba50e9c) registrada."
echo "Verificación:"
database_psql -c "SELECT version, left(checksum,10) FROM schema_migration WHERE version LIKE '00%' ORDER BY version;"
database_psql -c "SELECT version, left(registered_checksum,10) reg, left(executed_checksum,10) exec, approved_by, approved_date FROM schema_migration_reconciliation_005;"
