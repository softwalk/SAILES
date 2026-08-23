# Model routing

## ADDED Requirements

### Requirement: Proveedores intercambiables
Kimi K3 y DeepSeek SHALL exponerse mediante `ModelGateway`; flujos y prompts SHALL referir alias de capacidad, no IDs de proveedor. El registro SHALL poder cambiar modelos sin migrar estado de campaña, pero cada conversación SHALL fijar proveedor/modelo salvo fallback auditado y cada cambio SHALL pasar evaluaciones y canary.

#### Scenario: Kimi no disponible
- **GIVEN** una tarea cuyo fallback DeepSeek está permitido
- **WHEN** el circuit breaker de Kimi abre
- **THEN** se enruta a DeepSeek, se conserva el schema y se registra motivo, latencia y costo

### Requirement: Enrutamiento por política
La selección SHALL considerar clasificación de datos, región, residencia, retención, uso para entrenamiento, subprocesadores, capacidades, calidad, latencia, presupuesto y salud. Un proveedor no aprobado para cierta clase de datos SHALL quedar excluido.

#### Scenario: PII restringida
- **GIVEN** una solicitud con datos clasificados que no pueden salir del entorno aprobado
- **WHEN** sólo hay proveedores externos no autorizados
- **THEN** se redactan/tokenizan los datos o se envía a revisión; nunca se degrada la política

### Requirement: Salida estructurada
Las decisiones de agente SHALL cumplir JSON Schema y reglas semánticas antes de persistir o crear herramientas.

#### Scenario: Acción inválida
- **GIVEN** una salida que propone un canal no permitido
- **WHEN** el validador la procesa
- **THEN** la rechaza aunque el JSON sea sintácticamente válido

### Requirement: Presupuesto y observabilidad
Cada llamada SHALL registrar alias, proveedor/modelo real, versión de prompt, tokens, caché, latencia, coste estimado, resultado y redacción aplicada, sin guardar secretos ni razonamiento privado.

#### Scenario: Presupuesto agotado
- **GIVEN** una campaña que alcanzó su límite diario
- **WHEN** solicita personalización no crítica
- **THEN** se difiere o usa plantilla determinista aprobada y se notifica al propietario
