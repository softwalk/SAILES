# Workflow orchestration

## ADDED Requirements

### Requirement: Ejecución durable y versionada
LangGraph SHALL persistir cada run con `workflow_version`, `state_schema_version`, `thread_id`, correlation ID y checkpoint. Un run pausado SHALL reanudarse con el mismo artefacto de grafo o mediante una migración explícita y probada.

#### Scenario: Despliegue durante una aprobación
- **GIVEN** un run interrumpido a la espera de aprobación humana en `sales-graph@1`
- **WHEN** se despliega `sales-graph@2`
- **THEN** el run permanece en la versión 1 o se migra con una función aprobada; nunca se reanuda silenciosamente con semántica distinta

### Requirement: Efectos idempotentes
Los nodos SHALL ser deterministas respecto de su entrada persistida y SHALL ejecutar efectos externos sólo mediante tareas/outbox idempotentes. Reanudar un nodo SHALL NOT repetir una llamada, mensaje, cobro, firma ni actualización no idempotente.

#### Scenario: Caída después del envío
- **GIVEN** que el proveedor aceptó un mensaje y el worker cae antes de guardar la respuesta
- **WHEN** LangGraph reanuda el nodo
- **THEN** la clave idempotente reconcilia el envío existente y no crea un segundo mensaje

### Requirement: Interrupciones humanas gobernadas
Cada interrupción SHALL registrar motivo, datos mínimos para decidir, rol requerido, SLA, expiración y decisiones permitidas. La reanudación SHALL validar que el actor conserva permisos y que campaña, contacto y políticas no cambiaron.

#### Scenario: Aprobación vencida
- **GIVEN** una oportunidad sensible cuya revisión excedió el SLA y cuya campaña cambió
- **WHEN** un aprobador intenta reanudarla
- **THEN** el sistema invalida el contexto anterior, repite preflight y solicita una nueva decisión

### Requirement: Reintentos y compensación
Errores SHALL clasificarse como transitorios, permanentes o de política. Sólo los transitorios SHALL reintentarse automáticamente con backoff y jitter; denegaciones de política SHALL NOT reintentarse. Toda compensación SHALL ser idempotente y auditada.

#### Scenario: REPEP no disponible
- **GIVEN** una decisión de voz bloqueada por evidencia REPEP no vigente
- **WHEN** vence el backoff de un worker
- **THEN** no reutiliza la decisión anterior ni marca; crea un nuevo intento de evaluación sujeto a límites y revisión

### Requirement: Automatización visual permisiva y subordinada
Node-RED core SHALL sustituir cualquier uso de n8n y SHALL ejecutarse como servicio aislado bajo una versión, commit, imagen digest y licencia Apache-2.0 aprobados. Todo nodo adicional SHALL tener licencia OSI-compatible aprobada. Node-RED SHALL NOT decidir contactabilidad, escribir directamente en tablas gobernadas ni invocar canales sin Policy Gateway.

#### Scenario: Flujo intenta evadir el Policy Gateway
- **GIVEN** un flujo Node-RED que intenta llamar directamente al adaptador de voz o WhatsApp
- **WHEN** CI valida el flow JSON o el egress del contenedor
- **THEN** la build o ejecución se bloquea y se registra un hallazgo de arquitectura

#### Scenario: Nodo adicional sin licencia aprobada
- **GIVEN** un paquete `node-red-contrib-*` ausente del manifiesto de componentes
- **WHEN** se construye la imagen Node-RED
- **THEN** CI bloquea la imagen hasta fijar repositorio, versión, commit, licencia y hash
