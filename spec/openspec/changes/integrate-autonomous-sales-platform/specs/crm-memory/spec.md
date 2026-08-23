# CRM and memory

## ADDED Requirements

### Requirement: PostgreSQL como sistema de registro
PostgreSQL SHALL almacenar entidades comerciales, permisos, interacciones, oportunidades, checkpoints, decisiones y eventos. Cada tabla de negocio sujeta a tenant SHALL incluir `tenant_id` con FK; cada agregado mutable SHALL incluir timestamps y versión optimista. Las relaciones SHALL usar claves compuestas para impedir referencias cruzadas aun si RLS se configura mal.

#### Scenario: Acceso cruzado
- **GIVEN** una sesión del tenant A
- **WHEN** consulta un ID perteneciente al tenant B
- **THEN** RLS devuelve cero filas y emite señal de acceso denegado

### Requirement: Memoria con fuente y vigencia
Un hecho de memoria SHALL contener sujeto, predicado, valor, fuente, confianza, clasificación, `valid_from` y `valid_until`; inferencias SHALL distinguirse de hechos declarados.

#### Scenario: Preferencia vencida
- **GIVEN** una preferencia con `valid_until` pasado
- **WHEN** se personaliza un mensaje
- **THEN** no se usa sin reconfirmación

### Requirement: Consistencia por eventos
Cambios de estado y publicación de eventos SHALL usar outbox transaccional; consumidores SHALL deduplicar con inbox.

#### Scenario: Reintento de cierre
- **GIVEN** un evento `opportunity.won` ya aplicado
- **WHEN** el broker lo reentrega
- **THEN** no se duplica ingreso, atribución ni notificación

### Requirement: Derechos y retención
El sistema SHALL soportar exportación, rectificación, supresión y legal hold conforme a política aplicable, preservando una prueba mínima de exclusión cuando esté permitido.

#### Scenario: Solicitud de supresión
- **GIVEN** una solicitud validada
- **WHEN** vence el periodo operativo
- **THEN** se elimina o anonimiza PII, se preserva el bloqueo mínimo y se audita el proceso
