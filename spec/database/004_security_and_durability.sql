-- Security and durability controls for Atlantis RC4. Apply after 003_runtime_controls.sql.
BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'atlantis_suppression_admin') THEN
    CREATE ROLE atlantis_suppression_admin NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END
$$;

DROP POLICY IF EXISTS tenant_isolation ON suppression;

CREATE POLICY suppression_tenant_and_global_read ON suppression
FOR SELECT
USING (
  tenant_id = app.current_tenant_id()
  OR (scope = 'GLOBAL' AND tenant_id IS NULL)
);

CREATE POLICY suppression_tenant_insert ON suppression
FOR INSERT
WITH CHECK (
  tenant_id = app.current_tenant_id()
  AND scope <> 'GLOBAL'
);

CREATE POLICY suppression_tenant_update ON suppression
FOR UPDATE
USING (tenant_id = app.current_tenant_id() AND scope <> 'GLOBAL')
WITH CHECK (tenant_id = app.current_tenant_id() AND scope <> 'GLOBAL');

CREATE POLICY suppression_tenant_delete ON suppression
FOR DELETE
USING (tenant_id = app.current_tenant_id() AND scope <> 'GLOBAL');

CREATE POLICY suppression_global_admin ON suppression
FOR ALL TO atlantis_suppression_admin
USING (scope = 'GLOBAL' AND tenant_id IS NULL)
WITH CHECK (scope = 'GLOBAL' AND tenant_id IS NULL AND contact_id IS NULL AND phone_token IS NOT NULL);

GRANT SELECT, INSERT, UPDATE, DELETE ON suppression TO atlantis_suppression_admin;

CREATE OR REPLACE FUNCTION app.purge_expired_runtime_state(p_tenant_id uuid)
RETURNS TABLE(deleted_idempotency bigint, deleted_nonces bigint)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_idempotency bigint;
  v_nonces bigint;
BEGIN
  IF p_tenant_id IS DISTINCT FROM app.current_tenant_id() THEN
    RAISE EXCEPTION 'tenant context mismatch';
  END IF;
  DELETE FROM idempotency_record WHERE tenant_id=p_tenant_id AND expires_at <= now();
  GET DIAGNOSTICS v_idempotency = ROW_COUNT;
  DELETE FROM workload_nonce WHERE tenant_id=p_tenant_id AND expires_at <= now();
  GET DIAGNOSTICS v_nonces = ROW_COUNT;
  RETURN QUERY SELECT v_idempotency,v_nonces;
END;
$$;

REVOKE ALL ON FUNCTION app.purge_expired_runtime_state(uuid) FROM PUBLIC;

COMMIT;

