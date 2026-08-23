-- Esquema lógico inicial v0.1. Aplicar inmediatamente 002_hardening_v1_1.sql.
-- No desplegar este archivo solo: carece deliberadamente de los controles completos de v1.1.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE campaign_status AS ENUM ('DRAFT','VALIDATING','PENDING_APPROVAL','APPROVED','RUNNING','PAUSED','COMPLETED','REJECTED','BLOCKED');
CREATE TYPE policy_result AS ENUM ('ALLOW','DENY','REVIEW');
CREATE TYPE channel_type AS ENUM ('VOICE','WHATSAPP');

CREATE TABLE tenant (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  policy_profile jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contact (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  display_name text, company_name text, email_ciphertext bytea, phone_token text,
  phone_ciphertext bytea, lifecycle_stage text NOT NULL DEFAULT 'DISCOVERED',
  version bigint NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE (tenant_id, phone_token)
);

CREATE TABLE field_provenance (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contact_id uuid NOT NULL REFERENCES contact(id),
  field_name text NOT NULL, source_type text NOT NULL, source_ref text NOT NULL,
  source_license text, observed_at timestamptz NOT NULL, confidence numeric(5,4) NOT NULL,
  value_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE consent_ledger (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contact_id uuid NOT NULL REFERENCES contact(id),
  channel channel_type NOT NULL, purpose text NOT NULL, status text NOT NULL CHECK (status IN ('GRANTED','REVOKED','EXPIRED')),
  capture_source text NOT NULL, notice_version text, evidence_uri text, evidence_hash text,
  captured_at timestamptz NOT NULL, valid_until timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE suppression (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid, contact_id uuid REFERENCES contact(id),
  phone_token text, channel channel_type, purpose text, scope text NOT NULL CHECK (scope IN ('GLOBAL','TENANT','CHANNEL','PURPOSE')),
  reason text NOT NULL, source text NOT NULL, effective_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz
);

CREATE TABLE repep_check (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, phone_token text NOT NULL,
  result text NOT NULL CHECK (result IN ('LISTED','NOT_LISTED','AMBIGUOUS','ERROR')),
  source_method text NOT NULL, source_reference text, checked_at timestamptz NOT NULL,
  valid_until timestamptz NOT NULL, evidence_hash text NOT NULL, raw_evidence_uri text,
  UNIQUE (tenant_id, phone_token, checked_at)
);

CREATE TABLE campaign (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES tenant(id),
  name text NOT NULL, owner_user_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE campaign_version (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, campaign_id uuid NOT NULL REFERENCES campaign(id),
  version_no integer NOT NULL, status campaign_status NOT NULL DEFAULT 'DRAFT', purpose text NOT NULL,
  definition jsonb NOT NULL, artifact_hash text NOT NULL, created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (campaign_id, version_no), UNIQUE (campaign_id, artifact_hash)
);

CREATE TABLE approval (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, subject_type text NOT NULL,
  subject_id uuid NOT NULL, subject_hash text NOT NULL, decision text NOT NULL CHECK (decision IN ('APPROVE','REJECT')),
  approver_user_id uuid NOT NULL, approver_role text NOT NULL, comment text,
  decided_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contactability_decision (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contact_id uuid NOT NULL,
  campaign_version_id uuid NOT NULL REFERENCES campaign_version(id), channel channel_type NOT NULL,
  purpose text NOT NULL, result policy_result NOT NULL, reason_codes jsonb NOT NULL,
  evidence_ids jsonb NOT NULL, policy_version text NOT NULL, content_hash text NOT NULL,
  decided_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL
);

CREATE TABLE outbound_authorization (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, decision_id uuid NOT NULL REFERENCES contactability_decision(id),
  channel channel_type NOT NULL, nonce_hash text NOT NULL UNIQUE, token_hash text NOT NULL UNIQUE,
  issued_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL, consumed_at timestamptz,
  revoked_at timestamptz
);

CREATE TABLE interaction (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contact_id uuid NOT NULL REFERENCES contact(id),
  campaign_version_id uuid REFERENCES campaign_version(id), channel channel_type NOT NULL,
  provider text NOT NULL, provider_ref text, direction text NOT NULL, status text NOT NULL,
  content_uri text, content_hash text, started_at timestamptz, ended_at timestamptz,
  correlation_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, provider, provider_ref)
);

CREATE TABLE opportunity (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contact_id uuid NOT NULL REFERENCES contact(id),
  stage text NOT NULL, amount numeric(18,2), currency char(3), sensitivity jsonb NOT NULL DEFAULT '{}',
  owner_user_id uuid, version bigint NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE memory_fact (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contact_id uuid NOT NULL REFERENCES contact(id),
  predicate text NOT NULL, value jsonb NOT NULL, fact_kind text NOT NULL CHECK (fact_kind IN ('DECLARED','OBSERVED','INFERRED')),
  source_interaction_id uuid REFERENCES interaction(id), confidence numeric(5,4) NOT NULL,
  classification text NOT NULL, valid_from timestamptz NOT NULL, valid_until timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE graph_run (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, contact_id uuid NOT NULL,
  campaign_version_id uuid NOT NULL, stage text NOT NULL, status text NOT NULL,
  state_schema_version integer NOT NULL, correlation_id uuid NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE graph_checkpoint (
  run_id uuid NOT NULL REFERENCES graph_run(id), checkpoint_no bigint NOT NULL,
  tenant_id uuid NOT NULL, state jsonb NOT NULL, state_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (run_id, checkpoint_no)
);

CREATE TABLE model_call (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, run_id uuid REFERENCES graph_run(id),
  task_alias text NOT NULL, provider text NOT NULL, model_id text NOT NULL, prompt_version text NOT NULL,
  data_classification text NOT NULL, input_tokens bigint, output_tokens bigint, latency_ms integer,
  estimated_cost numeric(18,8), outcome text NOT NULL, redaction_applied boolean NOT NULL,
  correlation_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE marketia_sync (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, entity_type text NOT NULL,
  entity_id uuid NOT NULL, marketia_ref text, direction text NOT NULL, contract_version text NOT NULL,
  status text NOT NULL, source_version text, target_version text, error jsonb,
  correlation_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE outbox_event (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, event_type text NOT NULL,
  aggregate_type text NOT NULL, aggregate_id uuid NOT NULL, aggregate_version bigint NOT NULL,
  payload jsonb NOT NULL, correlation_id uuid NOT NULL, causation_id uuid,
  occurred_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz
);

CREATE TABLE inbox_event (
  consumer text NOT NULL, event_id uuid NOT NULL, tenant_id uuid NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(), processed_at timestamptz,
  PRIMARY KEY (consumer, event_id)
);

CREATE TABLE audit_event (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, actor_type text NOT NULL,
  actor_id text NOT NULL, action text NOT NULL, resource_type text NOT NULL, resource_id text NOT NULL,
  decision_id uuid, reason_codes jsonb, correlation_id uuid NOT NULL, event_hash text NOT NULL,
  previous_hash text, occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_contact_stage ON contact (tenant_id, lifecycle_stage);
CREATE INDEX idx_repep_latest ON repep_check (tenant_id, phone_token, checked_at DESC);
CREATE INDEX idx_outbox_unpublished ON outbox_event (occurred_at) WHERE published_at IS NULL;
CREATE INDEX idx_audit_correlation ON audit_event (tenant_id, correlation_id, occurred_at);
CREATE INDEX idx_interaction_contact ON interaction (tenant_id, contact_id, created_at DESC);

-- En producción: ALTER TABLE ... ENABLE/FORCE ROW LEVEL SECURITY y políticas que
-- comparen tenant_id con current_setting('app.tenant_id')::uuid para cada tabla.
