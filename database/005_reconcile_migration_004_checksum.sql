-- Reconcile legacy migration 004 without rewriting history.
-- Required psql variables: checksum, approved_by, approved_date, evidence_ref,
-- evidence_sha256. Apply only through operations/21_apply_migration_005.sh.
\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE schema_migration_reconciliation (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  version text NOT NULL,
  legacy_checksum text NOT NULL CHECK (legacy_checksum ~ '^[a-f0-9]{64}$'),
  canonical_checksum text NOT NULL CHECK (canonical_checksum ~ '^[a-f0-9]{64}$'),
  object_fingerprint text NOT NULL CHECK (object_fingerprint ~ '^[a-f0-9]{64}$'),
  approved_by text NOT NULL CHECK (length(btrim(approved_by)) BETWEEN 3 AND 200),
  approved_date date NOT NULL CHECK (approved_date <= CURRENT_DATE),
  evidence_ref text NOT NULL CHECK (length(btrim(evidence_ref)) BETWEEN 3 AND 500),
  evidence_sha256 text NOT NULL CHECK (evidence_sha256 ~ '^[a-f0-9]{64}$'),
  reconciled_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (version, legacy_checksum, canonical_checksum)
);

CREATE OR REPLACE FUNCTION app.migration_004_object_fingerprint()
RETURNS text
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public, pg_temp
AS $function$
  WITH lines(line) AS (
    SELECT 'FUNC:' || md5(pg_get_functiondef('app.purge_expired_runtime_state(uuid)'::regprocedure))
    UNION ALL
    SELECT 'GRANT:' || privilege_type
      FROM unnest(ARRAY['DELETE','INSERT','REFERENCES','SELECT','TRIGGER','TRUNCATE','UPDATE']) AS privilege_type
     WHERE has_table_privilege('atlantis_suppression_admin','public.suppression',privilege_type)
    UNION ALL
    SELECT 'POLICY:' || pol.polname || ':' || coalesce(pg_get_expr(pol.polqual,pol.polrelid),'') || ':' ||
           coalesce(pg_get_expr(pol.polwithcheck,pol.polrelid),'') || ':' || pol.polcmd
      FROM pg_policy pol
     WHERE pol.polrelid='public.suppression'::regclass
    UNION ALL
    SELECT 'ROLE:' || rolname || ':' || rolsuper::text || rolinherit::text ||
           rolcreaterole::text || rolcreatedb::text || rolcanlogin::text || rolbypassrls::text
      FROM pg_roles WHERE rolname='atlantis_suppression_admin'
  )
  SELECT encode(digest(convert_to(string_agg(line,E'\n' ORDER BY line) || E'\n','UTF8'),'sha256'),'hex')
    FROM lines
$function$;

REVOKE ALL ON FUNCTION app.migration_004_object_fingerprint() FROM PUBLIC;

CREATE OR REPLACE FUNCTION app.prevent_migration_reconciliation_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $function$
BEGIN
  RAISE EXCEPTION 'schema_migration_reconciliation is append-only';
END;
$function$;

REVOKE ALL ON FUNCTION app.prevent_migration_reconciliation_mutation() FROM PUBLIC;
CREATE TRIGGER trg_migration_reconciliation_append_only
BEFORE UPDATE OR DELETE ON schema_migration_reconciliation
FOR EACH ROW EXECUTE FUNCTION app.prevent_migration_reconciliation_mutation();

DO $block$
DECLARE
  recorded text;
  actual_fingerprint text;
BEGIN
  SELECT checksum INTO recorded FROM schema_migration
   WHERE version='004_security_and_durability';
  IF recorded IS DISTINCT FROM '9c1850fcaa632f2189deac5e9b66e02fa85be92a920b6cae7696c9b691e4bacb' THEN
    RAISE EXCEPTION 'unexpected migration 004 checksum: %', recorded;
  END IF;
  SELECT app.migration_004_object_fingerprint() INTO actual_fingerprint;
  IF actual_fingerprint IS DISTINCT FROM '53e77f497b6ee0e30963dd08a734dd7b2d1a997c52c742ee42bb4c6228818b6d' THEN
    RAISE EXCEPTION 'migration 004 object fingerprint mismatch: %', actual_fingerprint;
  END IF;
END
$block$;

INSERT INTO schema_migration_reconciliation
  (version,legacy_checksum,canonical_checksum,object_fingerprint,
   approved_by,approved_date,evidence_ref,evidence_sha256)
VALUES
  ('004_security_and_durability',
   '9c1850fcaa632f2189deac5e9b66e02fa85be92a920b6cae7696c9b691e4bacb',
   'f07309b514f1fb1bb4546a3c09712123b45de255c202e25b9f6c098d6eb3ba2e',
   '53e77f497b6ee0e30963dd08a734dd7b2d1a997c52c742ee42bb4c6228818b6d',
   NULLIF(btrim(:'approved_by'),''), :'approved_date'::date,
   NULLIF(btrim(:'evidence_ref'),''), :'evidence_sha256');

SELECT set_config('atlantis.migration_005_checksum', :'checksum', true);
INSERT INTO schema_migration(version,checksum)
VALUES ('005_reconcile_migration_004_checksum', :'checksum')
ON CONFLICT (version) DO NOTHING;

DO $block$
DECLARE recorded text;
BEGIN
  SELECT checksum INTO recorded FROM schema_migration
   WHERE version='005_reconcile_migration_004_checksum';
  IF recorded IS DISTINCT FROM current_setting('atlantis.migration_005_checksum') THEN
    RAISE EXCEPTION 'migration 005 checksum mismatch: %', recorded;
  END IF;
END
$block$;

REVOKE ALL ON schema_migration_reconciliation FROM PUBLIC;
DO $block$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_runtime') THEN
    REVOKE ALL ON schema_migration_reconciliation FROM atlantis_runtime;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_auditor') THEN
    GRANT SELECT ON schema_migration_reconciliation TO atlantis_auditor;
    GRANT EXECUTE ON FUNCTION app.migration_004_object_fingerprint() TO atlantis_auditor;
  END IF;
END
$block$;

COMMIT;
