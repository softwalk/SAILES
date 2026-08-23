-- ============================================================================
-- 006_reconcile_migration_005_applied_checksum.sql
-- Migración de reconciliación del checksum de la migración 005.
-- CONTEXTO: la fila 005 registra checksum 853d8622 (archivo original del ZIP v7,
--   con pol.polcmd sin cast), pero en VM 110 se ejecutó una versión con
--   pol.polcmd::text (checksum 5ba50e9c). Se registró el original mientras se
--   ejecutaron bytes diferentes. 006 reconcilia SIN tocar la fila 005.
-- APLICAR SOLO a través de operations/22_apply_migration_006.sh con las
--   variables psql: checksum, approved_by, approved_date, evidence_ref, evidence_sha256.
-- ============================================================================
\set ON_ERROR_STOP on

BEGIN;

-- 1. Verificar que la fila 005 sigue con el checksum registrado (original)
DO $$
DECLARE recorded text;
BEGIN
  SELECT checksum INTO recorded FROM schema_migration
   WHERE version='005_reconcile_migration_004_checksum';
  IF recorded IS DISTINCT FROM '853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e' THEN
    RAISE EXCEPTION 'unexpected migration 005 checksum: %', recorded;
  END IF;
END $$;

-- 2. Tabla de reconciliación de 005 (append-only)
CREATE TABLE IF NOT EXISTS schema_migration_reconciliation_005 (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  version text NOT NULL,
  registered_checksum text NOT NULL CHECK (registered_checksum ~ '^[a-f0-9]{64}$'),
  executed_checksum text NOT NULL CHECK (executed_checksum ~ '^[a-f0-9]{64}$'),
  object_fingerprint text NOT NULL CHECK (object_fingerprint ~ '^[a-f0-9]{64}$'),
  approved_by text NOT NULL CHECK (length(btrim(approved_by)) BETWEEN 3 AND 200),
  approved_date date NOT NULL CHECK (approved_date <= CURRENT_DATE),
  evidence_ref text NOT NULL CHECK (length(btrim(evidence_ref)) BETWEEN 3 AND 500),
  evidence_sha256 text NOT NULL CHECK (evidence_sha256 ~ '^[a-f0-9]{64}$'),
  reconciled_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (version, registered_checksum, executed_checksum)
);

-- 3. Función + trigger append-only
CREATE OR REPLACE FUNCTION app.prevent_migration_005_reconciliation_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
BEGIN
  RAISE EXCEPTION 'schema_migration_reconciliation_005 is append-only';
END
$fn$;
REVOKE ALL ON FUNCTION app.prevent_migration_005_reconciliation_mutation() FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_migration_005_reconciliation_append_only ON schema_migration_reconciliation_005;
CREATE TRIGGER trg_migration_005_reconciliation_append_only
BEFORE UPDATE OR DELETE ON schema_migration_reconciliation_005
FOR EACH ROW EXECUTE FUNCTION app.prevent_migration_005_reconciliation_mutation();

-- 4. Fingerprint de los objetos que 005 creó (determinista)
CREATE OR REPLACE FUNCTION app.migration_005_object_fingerprint()
RETURNS text LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
  WITH lines(line) AS (
    SELECT 'FUNC:' || md5(pg_get_functiondef('app.migration_004_object_fingerprint()'::regprocedure))
    UNION ALL
    SELECT 'FUNC:' || md5(pg_get_functiondef('app.prevent_migration_reconciliation_mutation()'::regprocedure))
    UNION ALL
    SELECT 'TRIGGER:trg_migration_reconciliation_append_only'
      FROM pg_trigger WHERE tgrelid='public.schema_migration_reconciliation'::regclass
                           AND tgname='trg_migration_reconciliation_append_only'
    UNION ALL
    SELECT 'GRANT:atlantis_auditor:SELECT:schema_migration_reconciliation'
     WHERE has_table_privilege('atlantis_auditor','public.schema_migration_reconciliation','SELECT')
  )
  SELECT encode(digest(convert_to(string_agg(line,E'\n' ORDER BY line) || E'\n','UTF8'),'sha256'),'hex') FROM lines
$fn$;
REVOKE ALL ON FUNCTION app.migration_005_object_fingerprint() FROM PUBLIC;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_auditor') THEN
    GRANT EXECUTE ON FUNCTION app.migration_005_object_fingerprint() TO atlantis_auditor;
  END IF;
END $$;

-- 5. Insertar la reconciliación de 005 (fuera del bloque DO para que las variables se interpolen)
INSERT INTO schema_migration_reconciliation_005
  (version, registered_checksum, executed_checksum, object_fingerprint,
   approved_by, approved_date, evidence_ref, evidence_sha256)
VALUES
  ('005_reconcile_migration_004_checksum',
   '853d86220033dff82930c9e8e91589b6602eba6b00a43c795741a716143cf23e',
   '5ba50e9c2e465eea7e65a8c47f0ae89d2791e498ddd02c95c6dda04fa9e91d8d',
   app.migration_005_object_fingerprint(),
   NULLIF(btrim(:'approved_by'),''), :'approved_date'::date,
   NULLIF(btrim(:'evidence_ref'),''), :'evidence_sha256')
ON CONFLICT (version, registered_checksum, executed_checksum) DO NOTHING;

-- 6. Registrar 006 con su checksum y verificar
SELECT set_config('atlantis.migration_006_checksum', :'checksum', true);
INSERT INTO schema_migration(version,checksum)
VALUES ('006_reconcile_migration_005_applied_checksum', :'checksum')
ON CONFLICT (version) DO NOTHING;
DO $$
DECLARE recorded text;
BEGIN
  SELECT checksum INTO recorded FROM schema_migration
   WHERE version='006_reconcile_migration_005_applied_checksum';
  IF recorded IS DISTINCT FROM current_setting('atlantis.migration_006_checksum') THEN
    RAISE EXCEPTION 'migration 006 checksum mismatch: %', recorded;
  END IF;
END $$;

REVOKE ALL ON schema_migration_reconciliation_005 FROM PUBLIC;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_runtime') THEN
    REVOKE ALL ON schema_migration_reconciliation_005 FROM atlantis_runtime;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_auditor') THEN
    GRANT SELECT ON schema_migration_reconciliation_005 TO atlantis_auditor;
  END IF;
END $$;

COMMIT;
