-- Durable workflow, cumulative model budget and tenant-safe audit controls for pilot readiness.
BEGIN;

CREATE TABLE workflow_event (
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  run_id uuid NOT NULL,
  event_id uuid NOT NULL,
  event_type text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id,run_id,event_id),
  FOREIGN KEY (run_id,tenant_id) REFERENCES graph_run(id,tenant_id)
);

CREATE TABLE model_budget_daily (
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  budget_date date NOT NULL,
  reserved_units bigint NOT NULL DEFAULT 0 CHECK (reserved_units >= 0),
  spent_units bigint NOT NULL DEFAULT 0 CHECK (spent_units >= 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id,budget_date)
);

CREATE TABLE model_budget_reservation (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  budget_date date NOT NULL,
  task_alias text NOT NULL,
  reserved_units bigint NOT NULL CHECK (reserved_units > 0),
  actual_units bigint CHECK (actual_units >= 0),
  status text NOT NULL CHECK (status IN ('RESERVED','SETTLED','RELEASED')),
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  settled_at timestamptz,
  UNIQUE (id,tenant_id)
);

CREATE INDEX idx_model_budget_reservation_expiry
ON model_budget_reservation (tenant_id,expires_at) WHERE status='RESERVED';

ALTER TABLE model_call
  ADD COLUMN cost_units bigint CHECK (cost_units >= 0);

DO $$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['workflow_event','model_budget_daily','model_budget_reservation'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (tenant_id=app.current_tenant_id()) WITH CHECK (tenant_id=app.current_tenant_id())',
      table_name
    );
  END LOOP;
END $$;

CREATE OR REPLACE FUNCTION app.append_audit_event(
  p_tenant_id uuid, p_actor_type text, p_actor_id text, p_action text,
  p_resource_type text, p_resource_id text, p_decision_id uuid,
  p_reason_codes jsonb, p_correlation_id uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_event_id uuid := gen_random_uuid();
  v_sequence bigint;
  v_previous text;
  v_occurred timestamptz := clock_timestamp();
  v_hash text;
BEGIN
  IF p_tenant_id IS DISTINCT FROM app.current_tenant_id() THEN
    RAISE EXCEPTION 'audit tenant context mismatch';
  END IF;
  IF p_actor_id IS NULL OR p_actor_id = '' OR p_action IS NULL OR p_action = ''
     OR p_resource_type IS NULL OR p_resource_type = '' OR p_resource_id IS NULL OR p_resource_id = '' THEN
    RAISE EXCEPTION 'audit identity and resource are required';
  END IF;
  INSERT INTO audit_chain_head (tenant_id,last_sequence_no,last_event_hash)
  VALUES (p_tenant_id,0,NULL) ON CONFLICT (tenant_id) DO NOTHING;
  SELECT last_sequence_no+1,last_event_hash INTO v_sequence,v_previous
  FROM audit_chain_head WHERE tenant_id=p_tenant_id FOR UPDATE;
  v_hash := encode(digest(concat_ws('|',p_tenant_id::text,v_sequence::text,coalesce(v_previous,''),
    p_actor_type,p_actor_id,p_action,p_resource_type,p_resource_id,coalesce(p_decision_id::text,''),
    coalesce(p_reason_codes::text,''),p_correlation_id::text,v_occurred::text),'sha256'),'hex');
  INSERT INTO audit_event (id,tenant_id,actor_type,actor_id,action,resource_type,resource_id,
    decision_id,reason_codes,correlation_id,event_hash,previous_hash,occurred_at,sequence_no)
  VALUES (v_event_id,p_tenant_id,p_actor_type,p_actor_id,p_action,p_resource_type,p_resource_id,
    p_decision_id,p_reason_codes,p_correlation_id,v_hash,v_previous,v_occurred,v_sequence);
  UPDATE audit_chain_head SET last_sequence_no=v_sequence,last_event_hash=v_hash,updated_at=now()
  WHERE tenant_id=p_tenant_id;
  RETURN v_event_id;
END;
$$;

REVOKE ALL ON FUNCTION app.append_audit_event(uuid,text,text,text,text,text,uuid,jsonb,uuid) FROM PUBLIC;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_runtime') THEN
    REVOKE ALL ON workflow_event,model_budget_daily,model_budget_reservation FROM atlantis_runtime;
    GRANT SELECT,INSERT ON workflow_event TO atlantis_runtime;
    GRANT SELECT,INSERT,UPDATE ON model_budget_daily,model_budget_reservation TO atlantis_runtime;
    GRANT SELECT,INSERT,UPDATE ON graph_run,human_action TO atlantis_runtime;
    GRANT SELECT,INSERT ON graph_checkpoint,model_call TO atlantis_runtime;
    REVOKE ALL ON audit_chain_head,audit_event FROM atlantis_runtime;
    GRANT EXECUTE ON FUNCTION app.append_audit_event(uuid,text,text,text,text,text,uuid,jsonb,uuid) TO atlantis_runtime;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atlantis_auditor') THEN
    GRANT SELECT ON workflow_event,model_budget_daily,model_budget_reservation TO atlantis_auditor;
  END IF;
END $$;

SELECT set_config('atlantis.migration_008_checksum', :'checksum', true);
INSERT INTO schema_migration(version,checksum)
VALUES ('008_pilot_readiness', :'checksum')
ON CONFLICT (version) DO NOTHING;
DO $$
DECLARE recorded text;
BEGIN
  SELECT checksum INTO recorded FROM schema_migration WHERE version='008_pilot_readiness';
  IF recorded IS DISTINCT FROM current_setting('atlantis.migration_008_checksum') THEN
    RAISE EXCEPTION 'migration 008 checksum mismatch: %', recorded;
  END IF;
END $$;

COMMIT;
