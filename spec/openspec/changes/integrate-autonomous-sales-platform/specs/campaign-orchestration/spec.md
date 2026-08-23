# Campaign orchestration

## ADDED Requirements

### Requirement: Campañas versionadas
OpenSales SHALL producir un plan declarativo con audiencia, propósito, canales, horario, cadencia, límites, variantes, conocimiento permitido, métricas y reglas de salida. Cada cambio material SHALL crear una versión inmutable nueva.

#### Scenario: Cambio posterior a aprobación
- **GIVEN** una campaña aprobada
- **WHEN** cambia segmento, contenido, canal, frecuencia, propósito, oferta o política
- **THEN** se crea una nueva versión en `DRAFT` y se detiene la versión previa según la política de despliegue

### Requirement: Aprobación inicial obligatoria
Toda versión ejecutable SHALL requerir aprobación humana con identidad, rol, comentario, timestamp y hash SHA-256 de un manifiesto JSON canónico que incluya audiencia, contenido por canal, conocimiento, prompts, propósito, horario, frecuencia y reglas.

#### Scenario: Activación sin aprobación
- **GIVEN** una campaña en `DRAFT` o `PENDING_APPROVAL`
- **WHEN** un servicio intenta activarla
- **THEN** la API responde `403 POLICY_DENIED`, no encola acciones y audita el intento

### Requirement: Personalización fundamentada
La personalización SHALL usar solamente hechos con fuente y SHALL separar afirmaciones verificadas de hipótesis internas.

#### Scenario: Dato no sustentado
- **GIVEN** una propuesta de mensaje que contiene una cifra no existente en la base aprobada
- **WHEN** se valida el borrador
- **THEN** se bloquea o elimina la afirmación y se registra la regla que falló

### Requirement: Límites de presión comercial
La campaña SHALL aplicar topes por contacto, empresa, canal y periodo, además de horarios y pausas globales.

#### Scenario: Frecuencia agotada
- **GIVEN** un contacto que alcanzó el máximo semanal
- **WHEN** se calcula la siguiente acción
- **THEN** se pospone hasta la siguiente ventana permitida sin solicitar autorización de canal
