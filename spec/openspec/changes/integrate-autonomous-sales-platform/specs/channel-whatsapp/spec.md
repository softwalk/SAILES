# WhatsApp channel

## ADDED Requirements

### Requirement: Transporte soportado
`WhatsAppProvider` SHALL usar un adaptador directo a WhatsApp Cloud API oficial como ruta productiva preferida. Evolution API MAY funcionar como adaptador opcional sólo con transporte Cloud API oficial, versión/licencia aprobada y funciones no requeridas deshabilitadas. Conectores WhatsApp Web/Baileys SHALL limitarse a pruebas aisladas y no usar números productivos.

#### Scenario: Configuración productiva no oficial
- **GIVEN** un tenant de producción
- **WHEN** intenta activar un transporte Baileys
- **THEN** la configuración se rechaza y se registra una violación de control

#### Scenario: Evolution sin licencia aprobada
- **GIVEN** una versión de Evolution API sin dictamen de licencia o activación operativa válida
- **WHEN** se intenta promoverla a producción
- **THEN** el despliegue se bloquea y se conserva la ruta directa a Cloud API

### Requirement: Opt-in demostrable
Todo WhatsApp iniciado por la empresa SHALL exigir consentimiento específico y demostrable con identidad del negocio, propósito, canal, texto/versión, fuente, timestamp y estado no revocado.

#### Scenario: Consentimiento ausente
- **GIVEN** un contacto calificado sin opt-in de WhatsApp
- **WHEN** una campaña intenta enviarle un mensaje promocional
- **THEN** Policy Gateway deniega y no crea mensaje en Evolution API

### Requirement: Plantillas y ventana conversacional
El adaptador SHALL determinar si aplica plantilla aprobada, validar idioma/variables y respetar la ventana vigente y límites de Meta.

#### Scenario: Plantilla no aprobada
- **GIVEN** que el contacto está fuera de ventana y la plantilla no está aprobada
- **WHEN** se solicita envío
- **THEN** se bloquea y se solicita corrección de campaña

### Requirement: Opt-out e inbound
Palabras y expresiones de baja SHALL procesarse con clasificación robusta, confirmación mínima y supresión inmediata. Los webhooks inbound SHALL validar challenge de suscripción, firma sobre el cuerpo crudo, ventana temporal, cuenta/número esperado y deduplicación.

#### Scenario: Webhook repetido
- **GIVEN** el mismo `message_id` recibido dos veces
- **WHEN** se procesa el segundo evento
- **THEN** se reconoce sin duplicar conversación, CRM ni respuesta
