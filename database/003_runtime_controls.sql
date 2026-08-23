-- Runtime controls for Atlantis RC1. Apply after 001_schema.sql and 002_hardening.sql.
BEGIN;

CREATE TABLE schema_migration (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now(),
  checksum text NOT NULL
);

CREATE TABLE idempotency_record (
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  service_name text NOT NULL,
  idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 16 AND 128),
  request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
  response_status integer,
  response_body jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, service_name, idempotency_key)
);

CREATE TABLE workload_nonce (
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  service_id text NOT NULL,
  nonce text NOT NULL,
  issued_at timestamptz NOT NULL,
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, service_id, nonce)
);

CREATE TABLE frequency_counter (
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  contact_id uuid NOT NULL,
  campaign_version_id uuid NOT NULL,
  channel channel_type NOT NULL,
  window_start timestamptz NOT NULL,
  count integer NOT NULL DEFAULT 0 CHECK (count >= 0),
  PRIMARY KEY (tenant_id, contact_id, campaign_version_id, channel, window_start),
  FOREIGN KEY (contact_id,tenant_id) REFERENCES contact(id,tenant_id),
  FOREIGN KEY (campaign_version_id,tenant_id) REFERENCES campaign_version(id,tenant_id)
);

ALTER TABLE outbox_event ADD COLUMN attempt_count integer NOT NULL DEFAULT 0;
ALTER TABLE outbox_event ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE outbox_event ADD COLUMN locked_by text;
ALTER TABLE outbox_event ADD COLUMN locked_at timestamptz;

CREATE INDEX idx_outbox_ready ON outbox_event (tenant_id,next_attempt_at,occurred_at)
WHERE published_at IS NULL;
CREATE INDEX idx_idempotency_expiry ON idempotency_record (expires_at);
CREATE INDEX idx_workload_nonce_expiry ON workload_nonce (expires_at);

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
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['idempotency_record','workload_nonce','frequency_counter'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
    EXECUTE format('CREATE POLICY tenant_isolation ON %I USING (tenant_id=app.current_tenant_id()) WITH CHECK (tenant_id=app.current_tenant_id())',table_name);
  END LOOP;
END $$;

COMMIT;
