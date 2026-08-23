-- Atlantis OpenSpec v1.1 hardening migration.
-- Diseñada para aplicarse inmediatamente después de schema.sql en una base nueva.
BEGIN;

ALTER TABLE tenant ADD COLUMN version bigint NOT NULL DEFAULT 1;
ALTER TABLE tenant ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE campaign ADD COLUMN version bigint NOT NULL DEFAULT 1;
ALTER TABLE campaign ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE graph_run ADD COLUMN version bigint NOT NULL DEFAULT 1;
ALTER TABLE graph_run ADD COLUMN workflow_version text NOT NULL DEFAULT 'sales-graph@1';
ALTER TABLE graph_checkpoint ADD COLUMN workflow_version text NOT NULL DEFAULT 'sales-graph@1';

ALTER TABLE contact ADD CONSTRAINT uq_contact_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE campaign ADD CONSTRAINT uq_campaign_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE campaign_version ADD CONSTRAINT uq_campaign_version_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE contactability_decision ADD CONSTRAINT uq_decision_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE interaction ADD CONSTRAINT uq_interaction_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE graph_run ADD CONSTRAINT uq_graph_run_id_tenant UNIQUE (id, tenant_id);

ALTER TABLE contact ADD CONSTRAINT fk_contact_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE field_provenance ADD CONSTRAINT fk_field_provenance_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE field_provenance ADD CONSTRAINT fk_field_provenance_contact_tenant FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id);
ALTER TABLE consent_ledger ADD CONSTRAINT fk_consent_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE consent_ledger ADD CONSTRAINT fk_consent_contact_tenant FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id);
ALTER TABLE suppression ADD CONSTRAINT fk_suppression_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE suppression ADD CONSTRAINT fk_suppression_contact_tenant FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id);
ALTER TABLE repep_check ADD CONSTRAINT fk_repep_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE campaign ADD CONSTRAINT fk_campaign_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE campaign_version ADD CONSTRAINT fk_campaign_version_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE campaign_version ADD CONSTRAINT fk_campaign_version_campaign_tenant FOREIGN KEY (campaign_id, tenant_id) REFERENCES campaign(id, tenant_id);
ALTER TABLE approval ADD CONSTRAINT fk_approval_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE contactability_decision ADD CONSTRAINT fk_decision_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE contactability_decision ADD CONSTRAINT fk_decision_contact_tenant FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id);
ALTER TABLE contactability_decision ADD CONSTRAINT fk_decision_campaign_tenant FOREIGN KEY (campaign_version_id, tenant_id) REFERENCES campaign_version(id, tenant_id);
ALTER TABLE outbound_authorization ADD CONSTRAINT fk_authorization_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE outbound_authorization ADD CONSTRAINT fk_authorization_decision_tenant FOREIGN KEY (decision_id, tenant_id) REFERENCES contactability_decision(id, tenant_id);
ALTER TABLE interaction ADD CONSTRAINT fk_interaction_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE interaction ADD CONSTRAINT fk_interaction_contact_tenant FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id);
ALTER TABLE interaction ADD CONSTRAINT fk_interaction_campaign_tenant FOREIGN KEY (campaign_version_id, tenant_id) REFERENCES campaign_version(id, tenant_id);
ALTER TABLE opportunity ADD CONSTRAINT fk_opportunity_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE opportunity ADD CONSTRAINT fk_opportunity_contact_tenant FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id);
ALTER TABLE memory_fact ADD CONSTRAINT fk_memory_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE memory_fact ADD CONSTRAINT fk_memory_contact_tenant FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id);
ALTER TABLE memory_fact ADD CONSTRAINT fk_memory_interaction_tenant FOREIGN KEY (source_interaction_id, tenant_id) REFERENCES interaction(id, tenant_id);
ALTER TABLE graph_run ADD CONSTRAINT fk_graph_run_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE graph_run ADD CONSTRAINT fk_graph_run_contact_tenant FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id);
ALTER TABLE graph_run ADD CONSTRAINT fk_graph_run_campaign_tenant FOREIGN KEY (campaign_version_id, tenant_id) REFERENCES campaign_version(id, tenant_id);
ALTER TABLE graph_checkpoint ADD CONSTRAINT fk_checkpoint_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE graph_checkpoint ADD CONSTRAINT fk_checkpoint_run_tenant FOREIGN KEY (run_id, tenant_id) REFERENCES graph_run(id, tenant_id);
ALTER TABLE model_call ADD CONSTRAINT fk_model_call_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE model_call ADD CONSTRAINT fk_model_call_run_tenant FOREIGN KEY (run_id, tenant_id) REFERENCES graph_run(id, tenant_id);
ALTER TABLE marketia_sync ADD CONSTRAINT fk_marketia_sync_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE outbox_event ADD CONSTRAINT fk_outbox_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE inbox_event ADD CONSTRAINT fk_inbox_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);
ALTER TABLE audit_event ADD CONSTRAINT fk_audit_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id);

ALTER TABLE field_provenance ADD CONSTRAINT chk_field_confidence CHECK (confidence BETWEEN 0 AND 1);
ALTER TABLE memory_fact ADD CONSTRAINT chk_memory_confidence CHECK (confidence BETWEEN 0 AND 1);
ALTER TABLE suppression ADD CONSTRAINT chk_suppression_subject CHECK (contact_id IS NOT NULL OR phone_token IS NOT NULL);
ALTER TABLE suppression ADD CONSTRAINT chk_suppression_scope CHECK (
  (scope = 'GLOBAL' AND tenant_id IS NULL AND contact_id IS NULL AND phone_token IS NOT NULL)
  OR (scope = 'TENANT' AND tenant_id IS NOT NULL)
  OR (scope = 'CHANNEL' AND tenant_id IS NOT NULL AND channel IS NOT NULL)
  OR (scope = 'PURPOSE' AND tenant_id IS NOT NULL AND purpose IS NOT NULL)
);
ALTER TABLE outbound_authorization ADD CONSTRAINT chk_authorization_expiry CHECK (expires_at > issued_at AND expires_at <= issued_at + interval '5 minutes');
ALTER TABLE interaction ADD CONSTRAINT chk_interaction_direction CHECK (direction IN ('INBOUND','OUTBOUND'));
CREATE UNIQUE INDEX uq_outbox_aggregate_version ON outbox_event (tenant_id, aggregate_type, aggregate_id, aggregate_version, event_type);

CREATE TABLE repep_snapshot (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  dataset_id text NOT NULL,
  source_method text NOT NULL,
  contract_or_receipt_ref text NOT NULL,
  effective_at timestamptz NOT NULL,
  acquired_at timestamptz NOT NULL,
  valid_until timestamptz NOT NULL,
  evidence_uri text NOT NULL,
  evidence_hash text NOT NULL CHECK (evidence_hash ~ '^[a-f0-9]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, dataset_id),
  UNIQUE (id, tenant_id),
  CHECK (valid_until > effective_at)
);
ALTER TABLE repep_check ADD COLUMN snapshot_id uuid;
ALTER TABLE repep_check ALTER COLUMN snapshot_id SET NOT NULL;
ALTER TABLE repep_check ADD CONSTRAINT fk_repep_snapshot_tenant FOREIGN KEY (snapshot_id, tenant_id) REFERENCES repep_snapshot(id, tenant_id);

CREATE TABLE action_intent (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  contact_id uuid NOT NULL,
  campaign_version_id uuid NOT NULL,
  purpose text NOT NULL,
  channel channel_type NOT NULL,
  content_hash text NOT NULL CHECK (content_hash ~ '^[a-f0-9]{64}$'),
  workflow_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('PLANNED','EVALUATING','ALLOWED','DENIED','REVIEW','DISPATCHED','CANCELLED','EXPIRED')),
  requested_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  version bigint NOT NULL DEFAULT 1,
  UNIQUE (id, tenant_id),
  FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id),
  FOREIGN KEY (campaign_version_id, tenant_id) REFERENCES campaign_version(id, tenant_id)
);
ALTER TABLE contactability_decision ADD COLUMN action_intent_id uuid;
ALTER TABLE contactability_decision ALTER COLUMN action_intent_id SET NOT NULL;
ALTER TABLE contactability_decision ADD CONSTRAINT fk_decision_intent_tenant FOREIGN KEY (action_intent_id, tenant_id) REFERENCES action_intent(id, tenant_id);

CREATE TABLE campaign_artifact (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  campaign_version_id uuid NOT NULL, artifact_kind text NOT NULL, canonical_manifest jsonb NOT NULL,
  artifact_hash text NOT NULL CHECK (artifact_hash ~ '^[a-f0-9]{64}$'), created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (campaign_version_id, artifact_kind, artifact_hash), UNIQUE (id, tenant_id),
  FOREIGN KEY (campaign_version_id, tenant_id) REFERENCES campaign_version(id, tenant_id)
);

CREATE TABLE policy_rule_set (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  version text NOT NULL, jurisdiction text NOT NULL, product_scope text NOT NULL,
  rules jsonb NOT NULL, rules_hash text NOT NULL CHECK (rules_hash ~ '^[a-f0-9]{64}$'),
  status text NOT NULL CHECK (status IN ('DRAFT','APPROVED','RETIRED')),
  approved_by uuid, approved_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, version), UNIQUE (id, tenant_id)
);

CREATE TABLE knowledge_pack (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  version text NOT NULL, status text NOT NULL CHECK (status IN ('DRAFT','APPROVED','RETIRED')),
  content_uri text NOT NULL, content_hash text NOT NULL CHECK (content_hash ~ '^[a-f0-9]{64}$'),
  approved_by uuid, approved_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, version), UNIQUE (id, tenant_id)
);

CREATE TABLE human_action (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  run_id uuid, subject_type text NOT NULL, subject_id uuid NOT NULL, subject_hash text NOT NULL,
  reason_code text NOT NULL, required_role text NOT NULL, status text NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CANCELLED')),
  assigned_user_id uuid, decision_comment text, decided_by uuid, decided_at timestamptz,
  expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  version bigint NOT NULL DEFAULT 1, UNIQUE (id, tenant_id),
  FOREIGN KEY (run_id, tenant_id) REFERENCES graph_run(id, tenant_id)
);

CREATE TABLE webhook_receipt (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  provider text NOT NULL, provider_event_id text NOT NULL, body_hash text NOT NULL,
  signature_valid boolean NOT NULL, received_at timestamptz NOT NULL DEFAULT now(), processed_at timestamptz,
  status text NOT NULL CHECK (status IN ('RECEIVED','PROCESSED','REJECTED','QUARANTINED')),
  correlation_id uuid NOT NULL, UNIQUE (tenant_id, provider, provider_event_id)
);

CREATE TABLE dead_letter_event (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  source_event_id uuid NOT NULL, consumer text NOT NULL, payload_hash text NOT NULL,
  error_code text NOT NULL, error_detail jsonb, attempt_count integer NOT NULL,
  status text NOT NULL CHECK (status IN ('OPEN','RETRYING','RESOLVED','DISCARDED')),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE data_subject_request (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  contact_id uuid NOT NULL, request_type text NOT NULL CHECK (request_type IN ('ACCESS','RECTIFICATION','CANCELLATION','OPPOSITION','REVOCATION','PORTABILITY')),
  identity_verification_ref text NOT NULL, status text NOT NULL, due_at timestamptz NOT NULL,
  completed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (contact_id, tenant_id) REFERENCES contact(id, tenant_id)
);

CREATE TABLE legal_hold (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  subject_type text NOT NULL, subject_id uuid NOT NULL, reason text NOT NULL,
  starts_at timestamptz NOT NULL, ends_at timestamptz, released_by uuid, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_chain_head (
  tenant_id uuid PRIMARY KEY REFERENCES tenant(id), last_sequence_no bigint NOT NULL DEFAULT 0,
  last_event_hash text, updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE audit_event ADD COLUMN sequence_no bigint NOT NULL;
ALTER TABLE audit_event ADD COLUMN event_signature text;
ALTER TABLE audit_event ADD CONSTRAINT uq_audit_sequence UNIQUE (tenant_id, sequence_no);
ALTER TABLE audit_event ADD CONSTRAINT uq_audit_hash UNIQUE (tenant_id, event_hash);

CREATE OR REPLACE FUNCTION prevent_audit_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_event is append-only';
END;
$$;
CREATE TRIGGER trg_audit_no_update BEFORE UPDATE OR DELETE ON audit_event
FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

CREATE SCHEMA IF NOT EXISTS app;
CREATE OR REPLACE FUNCTION app.current_tenant_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
$$;

DO $$
DECLARE
  table_name text;
  tenant_tables text[] := ARRAY[
    'contact','field_provenance','consent_ledger','suppression','repep_snapshot','repep_check',
    'campaign','campaign_version','campaign_artifact','policy_rule_set','approval','action_intent','contactability_decision',
    'outbound_authorization','interaction','opportunity','memory_fact','knowledge_pack','graph_run',
    'graph_checkpoint','human_action','model_call','marketia_sync','outbox_event','inbox_event',
    'webhook_receipt','dead_letter_event','data_subject_request','legal_hold','audit_chain_head','audit_event'
  ];
BEGIN
  FOREACH table_name IN ARRAY tenant_tables LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I USING (tenant_id = app.current_tenant_id()) WITH CHECK (tenant_id = app.current_tenant_id())',
      table_name
    );
  END LOOP;
END $$;

COMMIT;

-- Operación obligatoria fuera de esta migración:
-- 1. El rol de aplicación no debe ser propietario, superusuario ni tener BYPASSRLS.
-- 2. La inserción de audit_event debe bloquear audit_chain_head FOR UPDATE y asignar sequence_no/hash en la misma transacción.
-- 3. Cifrado de aplicación, KMS y particiones se configuran por ambiente.
