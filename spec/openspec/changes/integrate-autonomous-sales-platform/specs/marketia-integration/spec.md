# Marketia integration

## ADDED Requirements

### Requirement: Contrato anti-corrupción
Marketia SHALL integrarse mediante un adaptador con mapeo explícito de campañas, segmentos, activos, UTM, costos, conversiones y estados; su esquema interno no SHALL filtrarse al dominio central.

#### Scenario: Campo desconocido
- **GIVEN** un webhook Marketia con versión no soportada
- **WHEN** llega al adaptador
- **THEN** se conserva de forma segura, no modifica CRM y se envía a cola de incompatibilidad

### Requirement: Propiedad y resolución de conflictos
Cada campo sincronizado SHALL tener sistema propietario. Consentimiento, exclusión, REPEP, aprobación y autorización SHALL ser propiedad exclusiva del plano de control.

#### Scenario: Marketia intenta habilitar contacto
- **GIVEN** un contacto suprimido en el sistema central
- **WHEN** Marketia envía estado `contactable=true`
- **THEN** se ignora ese campo, se conserva la supresión y se registra el conflicto

### Requirement: Atribución correlacionada
El sistema SHALL propagar `campaign_id`, `campaign_version_id`, `contact_id` tokenizado, `interaction_id`, UTM y correlation ID para unir inversión, actividad y resultado.

#### Scenario: Conversión tardía
- **GIVEN** una oportunidad ganada después de terminar campaña
- **WHEN** se registra el cierre
- **THEN** Marketia recibe un evento idempotente ligado a la versión original

### Requirement: Reconciliación
La integración SHALL ejecutar reconciliación incremental y diaria, medir atraso y disponer de dead-letter queue con reintento manual.

#### Scenario: Marketia caído
- **GIVEN** indisponibilidad de Marketia
- **WHEN** se produce una conversión
- **THEN** el CRM confirma localmente, el outbox retiene el evento y lo reenvía sin duplicar al recuperarse

