# Compliance and governance

## ADDED Requirements

### Requirement: Gateway único de contactabilidad
Toda acción saliente SHALL obtener una decisión determinista de Policy Gateway inmediatamente antes de ejecutarse. La decisión SHALL incluir reglas evaluadas, evidencia, versión, TTL y resultado `ALLOW`, `DENY` o `REVIEW`.

#### Scenario: Adaptador intenta omitir el gateway
- **GIVEN** un comando sin autorización firmada válida
- **WHEN** llega a voz o WhatsApp
- **THEN** el adaptador lo rechaza, no contacta y emite alerta de seguridad

### Requirement: REPEP configurable por campaña con excepción B2B controlada
Cada versión de campaña SHALL contener `repep.enabled`, cuyo valor inicial SHALL
ser `false`. Antes de una llamada promocional:

- Si `repep.enabled=true`, el sistema SHALL comprobar REPEP mediante un snapshot
  obtenido por un mecanismo autorizado por Profeco y SHALL conservar número
  normalizado/tokenizado, resultado, lote, fecha efectiva, contrato/recibo,
  timestamp, vigencia y hash. Error, ambigüedad o caducidad SHALL resultar en `DENY`.
- Si `repep.enabled=false`, el sistema SHALL permitir continuar únicamente cuando
  la versión aprobada declare `exemption_type=B2B`, tenga aprobación humana y una
  referencia de evidencia jurídica no vacía. La falta de cualquiera de estos
  elementos SHALL resultar en `DENY`.
- La matriz jurídica SHALL añadir registros sectoriales aplicables y SHALL impedir
  usar la excepción B2B para campañas B2C o contactos de consumidores.

La configuración y evidencia SHALL formar parte del hash inmutable de campaña.

#### Scenario: Número inscrito
- **GIVEN** evidencia vigente de que el número está inscrito en REPEP
- **WHEN** se solicita llamada promocional
- **THEN** se deniega sin excepción automatizada y se suprimen intentos futuros según política

#### Scenario: Servicio REPEP no disponible
- **GIVEN** que no existe evidencia local vigente y la consulta autorizada falla
- **WHEN** se solicita una llamada promocional
- **THEN** se bloquea, se reprograma para revisión y nunca se marca como permitido

#### Scenario: Campaña B2B aprobada con REPEP desactivado
- **GIVEN** una campaña de voz promocional aprobada con `repep.enabled=false`
- **AND** `exemption_type=B2B`, aprobación humana y referencia de evidencia jurídica
- **WHEN** Policy Gateway evalúa el contacto
- **THEN** no exige snapshot REPEP para esa intención y conserva la excepción en auditoría

#### Scenario: REPEP desactivado sin evidencia B2B
- **GIVEN** una campaña de voz promocional con `repep.enabled=false`
- **AND** falta clasificación B2B, aprobación o evidencia
- **WHEN** Policy Gateway evalúa el contacto
- **THEN** la decisión es `DENY` y no se emite autorización

### Requirement: Exclusión interna y consentimiento
El sistema SHALL mantener exclusiones globales y por tenant/canal/propósito. La revocación SHALL prevalecer sobre una autorización anterior y SHALL propagarse a colas y proyecciones.

#### Scenario: Revocación durante campaña
- **GIVEN** acciones futuras ya encoladas
- **WHEN** se registra una revocación
- **THEN** se invalidan autorizaciones no consumidas y se cancelan las acciones antes de la ejecución

### Requirement: Autorizaciones efímeras
Una autorización SHALL emitirse justo a tiempo después de retirar la acción para ejecución, repetir el preflight y quedar firmada y ligada a tenant, contacto, campaña, versión, propósito, canal, contenido/guion hash, horario y nonce; SHALL ser de un solo uso y vencer en máximo cinco minutos.

#### Scenario: Reutilización
- **GIVEN** una autorización ya consumida
- **WHEN** un adaptador intenta reutilizarla
- **THEN** se rechaza y se genera un evento de posible replay

#### Scenario: Cambio después de encolar
- **GIVEN** una acción en cola cuyo contacto fue suprimido después de planificarla
- **WHEN** el worker intenta obtener autorización
- **THEN** el nuevo preflight devuelve `DENY`, no se emite token y se cancela la acción

### Requirement: Auditoría reconstruible
El sistema SHALL registrar quién/qué/por qué/cuándo, entradas relevantes, decisión, versión y efecto de cada acción externa sin almacenar secretos ni razonamiento interno del modelo.

#### Scenario: Investigación de llamada
- **GIVEN** un identificador de llamada
- **WHEN** un auditor autorizado solicita trazabilidad
- **THEN** obtiene campaña, aprobación, REPEP, política, autorización, adaptador, disposición y correlación de eventos
