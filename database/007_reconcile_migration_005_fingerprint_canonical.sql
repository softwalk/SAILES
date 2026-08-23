-- ============================================================================
-- 007_reconcile_migration_005_fingerprint_canonical.sql
-- Migración de validación canónica del fingerprint de los objetos de 005.
--
-- CONTEXTO (hallazgo P0 del dictamen):
--   La 006 fue aplicada en VM 110 con una versión cuyo fingerprint de validación
--   usaba el algoritmo simple (2014d5d8...). La versión con fingerprint validado
--   (función ampliada, cobertura completa de objetos, valor canónico de47dcf7...)
--   es una MEJORA, pero no puede reemplazar la 006 ya aplicada (trazabilidad).
--
--   006 (aplicada, checksum 4f87541289fe) registra la reconciliación básica.
--   007 (esta) añade la VALIDACIÓN CANÓNICA del fingerprint: recalcula el
--   fingerprint con cobertura completa y lo compara contra el valor esperado
--   de47dcf79021fad19ba61aa308a372cb3a0d3da837c2b73191f4e7abd3934765,
--   fallando si no coincide.
--
-- PRINCIPIO:
--   NO toca la fila 006 (histórica). Añade la función canónica y la validación.
--   En instalaciones nuevas (donde 006 se aplica con la versión canónica), 007
--   valida el fingerprint. En VM 110 (006 ya aplicada), 007 valida que los
--   objetos de 005 siguen produciendo el fingerprint canónico.
--
-- APLICAR SOLO a través de operations/23_apply_migration_007.sh con las
--   variables psql: checksum, approved_by, approved_date, evidence_ref, evidence_sha256.
-- ============================================================================
\set ON_ERROR_STOP on

BEGIN;

-- 1. Verificar que 006 está registrada (con cualquier checksum válido)
DO $$
DECLARE recorded text;
BEGIN
  SELECT checksum INTO recorded FROM schema_migration
   WHERE version='006_reconcile_migration_005_applied_checksum';
  IF recorded IS NULL THEN
    RAISE EXCEPTION 'migration 006 no registrada: aplique 006 antes de 007';
  END IF;
END $$;

-- 2. Función canónica de fingerprint de los objetos de 005 (cobertura completa)
CREATE OR REPLACE FUNCTION app.migration_005_object_fingerprint_canonical()
RETURNS text LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
  WITH lines(line) AS (
    SELECT 'TABLE:schema_migration_reconciliation:' ||
           coalesce(string_agg(attname || ':' || atttypid::text || ':' || attnotnull::text, ',' ORDER BY attnum),'')
      FROM pg_attribute WHERE attrelid='public.schema_migration_reconciliation'::regclass AND attnum>0
    UNION ALL
    SELECT 'CONSTRAINT:' || conname FROM pg_constraint WHERE conrelid='public.schema_migration_reconciliation'::regclass
    UNION ALL
    SELECT 'FUNC:' || md5(pg_get_functiondef('app.migration_004_object_fingerprint()'::regprocedure))
    UNION ALL
    SELECT 'FUNC:' || md5(pg_get_functiondef('app.prevent_migration_reconciliation_mutation()'::regprocedure))
    UNION ALL
    SELECT 'TRIGGER:' || tgname || ':' || pg_get_triggerdef(oid)
      FROM pg_trigger WHERE tgrelid='public.schema_migration_reconciliation'::regclass
                           AND tgname='trg_migration_reconciliation_append_only'
    UNION ALL
    SELECT 'GRANT:atlantis_auditor:SELECT:schema_migration_reconciliation'
     WHERE has_table_privilege('atlantis_auditor','public.schema_migration_reconciliation','SELECT')
    UNION ALL
    SELECT 'NEG:runtime:' || (NOT has_table_privilege('atlantis_runtime','public.schema_migration_reconciliation','SELECT'))::text
    UNION ALL
    SELECT 'NEG:relacl_public:' || coalesce((SELECT (relacl IS NULL OR NOT (relacl::text LIKE '%=%'))::text FROM pg_class WHERE oid='public.schema_migration_reconciliation'::regclass),'true')
    UNION ALL
    SELECT 'ROW004:' || object_fingerprint FROM public.schema_migration_reconciliation
     WHERE version='004_security_and_durability'
  )
  SELECT encode(digest(convert_to(string_agg(line,E'\n' ORDER BY line) || E'\n','UTF8'),'sha256'),'hex') FROM lines
$fn$;
REVOKE ALL ON FUNCTION app.migration_005_object_fingerprint_canonical() FROM PUBLIC;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_auditor') THEN
    GRANT EXECUTE ON FUNCTION app.migration_005_object_fingerprint_canonical() TO atlantis_auditor;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_migrator') THEN
    GRANT EXECUTE ON FUNCTION app.migration_005_object_fingerprint_canonical() TO atlantis_migrator;
  END IF;
END $$;

-- 3. VALIDAR el fingerprint canónico contra el valor esperado
DO $$
DECLARE actual text;
BEGIN
  SELECT app.migration_005_object_fingerprint_canonical() INTO actual;
  IF actual IS DISTINCT FROM 'de47dcf79021fad19ba61aa308a372cb3a0d3da837c2b73191f4e7abd3934765' THEN
    RAISE EXCEPTION 'migration 005 canonical fingerprint mismatch: expected de47dcf7..., got %', actual;
  END IF;
END $$;

-- 4. Registrar la validación canónica (append-only, en la tabla de reconciliación 005)
-- Añado una marca de validación canónica sin tocar la fila 006.
CREATE TABLE IF NOT EXISTS schema_migration_validation (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  migration_version text NOT NULL,
  validation_type text NOT NULL,
  fingerprint text NOT NULL CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
  expected_fingerprint text NOT NULL CHECK (expected_fingerprint ~ '^[a-f0-9]{64}$'),
  match boolean NOT NULL,
  approved_by text NOT NULL CHECK (length(btrim(approved_by)) BETWEEN 3 AND 200),
  approved_date date NOT NULL CHECK (approved_date <= CURRENT_DATE),
  evidence_ref text NOT NULL,
  evidence_sha256 text NOT NULL CHECK (evidence_sha256 ~ '^[a-f0-9]{64}$'),
  validated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (migration_version, validation_type)
);
CREATE OR REPLACE FUNCTION app.prevent_migration_validation_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, pg_temp AS $fn$
BEGIN
  RAISE EXCEPTION 'schema_migration_validation is append-only';
END
$fn$;
REVOKE ALL ON FUNCTION app.prevent_migration_validation_mutation() FROM PUBLIC;
DROP TRIGGER IF EXISTS trg_migration_validation_append_only ON schema_migration_validation;
CREATE TRIGGER trg_migration_validation_append_only
BEFORE UPDATE OR DELETE ON schema_migration_validation
FOR EACH ROW EXECUTE FUNCTION app.prevent_migration_validation_mutation();

INSERT INTO schema_migration_validation
  (migration_version, validation_type, fingerprint, expected_fingerprint, match,
   approved_by, approved_date, evidence_ref, evidence_sha256)
VALUES
  ('005_reconcile_migration_004_checksum', 'canonical_fingerprint',
   app.migration_005_object_fingerprint_canonical(),
   'de47dcf79021fad19ba61aa308a372cb3a0d3da837c2b73191f4e7abd3934765',
   (app.migration_005_object_fingerprint_canonical() = 'de47dcf79021fad19ba61aa308a372cb3a0d3da837c2b73191f4e7abd3934765'),
   NULLIF(btrim(:'approved_by'),''), :'approved_date'::date,
   NULLIF(btrim(:'evidence_ref'),''), :'evidence_sha256')
ON CONFLICT (migration_version, validation_type) DO NOTHING;

-- 5. Registrar 007 con su checksum y verificar
SELECT set_config('atlantis.migration_007_checksum', :'checksum', true);
INSERT INTO schema_migration(version,checksum)
VALUES ('007_reconcile_migration_005_fingerprint_canonical', :'checksum')
ON CONFLICT (version) DO NOTHING;
DO $$
DECLARE recorded text;
BEGIN
  SELECT checksum INTO recorded FROM schema_migration
   WHERE version='007_reconcile_migration_005_fingerprint_canonical';
  IF recorded IS DISTINCT FROM current_setting('atlantis.migration_007_checksum') THEN
    RAISE EXCEPTION 'migration 007 checksum mismatch: %', recorded;
  END IF;
END $$;

REVOKE ALL ON schema_migration_validation FROM PUBLIC;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_runtime') THEN
    REVOKE ALL ON schema_migration_validation FROM atlantis_runtime;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_auditor') THEN
    GRANT SELECT ON schema_migration_validation TO atlantis_auditor;
  END IF;
END $$;

COMMIT;
