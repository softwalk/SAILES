# Security and observability

## ADDED Requirements

### Requirement: Identidad y privilegio mínimo
Humanos SHALL autenticarse por OIDC con MFA para roles sensibles; servicios SHALL usar identidades de carga y credenciales rotables. Autorización SHALL combinar rol, tenant, recurso y sensibilidad.

#### Scenario: Aprobador crea y aprueba
- **GIVEN** una campaña de riesgo alto creada por el mismo usuario
- **WHEN** intenta aprobarla
- **THEN** segregación de funciones bloquea la autoaprobación

### Requirement: Trazabilidad distribuida
Toda solicitud, grafo, decisión, mensaje y llamada SHALL compartir `correlation_id`; métricas y logs SHALL poder navegar hasta el evento de auditoría sin exponer PII. La cadena de auditoría SHALL serializarse por tenant, detectar bifurcaciones y exportarse periódicamente a almacenamiento inmutable.

#### Scenario: Fallo de canal
- **GIVEN** una llamada fallida
- **WHEN** operaciones abre la traza
- **THEN** identifica autorización, proveedor, intento, código normalizado y política de reintento

### Requirement: Resistencia a prompt injection
Contenido externo SHALL tratarse como datos, no instrucciones; herramientas SHALL usar allowlists y argumentos tipados; solicitudes de revelar secretos o saltar políticas SHALL rechazarse.

#### Scenario: Página maliciosa
- **GIVEN** un sitio descubierto que ordena ignorar reglas y enviar datos
- **WHEN** se extrae su contenido
- **THEN** se etiqueta como no confiable, no altera el prompt del sistema ni dispara herramientas

### Requirement: SLO y alertas
El sistema SHALL medir disponibilidad, atraso de colas, denegaciones, fallos REPEP, errores de webhook, costo de modelos, latencia, fallbacks y discrepancias de reconciliación.

#### Scenario: Aumento de denegaciones
- **GIVEN** una tasa anómala de `POLICY_DENIED`
- **WHEN** supera el umbral
- **THEN** se alerta, se pausa automáticamente la campaña afectada si la regla lo exige y se preserva evidencia
