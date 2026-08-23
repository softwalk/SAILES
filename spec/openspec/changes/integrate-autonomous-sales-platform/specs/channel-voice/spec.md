# Voice channel

## ADDED Requirements

### Requirement: Adaptador común de voz
VICIdial y Atlantis-Neobot SHALL implementar `VoiceProvider` con capacidades declaradas: aprovisionar lead/lista, iniciar/cancelar llamada, transferir a humano, obtener estado y recibir disposición. Las diferencias de proveedor SHALL permanecer dentro del adaptador.

#### Scenario: Cambio de proveedor
- **GIVEN** una campaña configurada para Atlantis-Neobot
- **WHEN** operaciones la cambia a VICIdial antes de encolar
- **THEN** el flujo de negocio conserva el mismo contrato y registra el proveedor efectivo

### Requirement: Marcación protegida
El adaptador SHALL validar autorización efímera antes de crear o iniciar una llamada, incluso si el registro ya existe en VICIdial. Un control en el punto efectivo de `originate/dial` SHALL impedir que campañas predictivas, APIs administrativas, cargas directas o procesos internos eludan la autorización.

#### Scenario: Lead importado sin token
- **GIVEN** un lead presente en una lista de VICIdial
- **WHEN** se intenta marcar sin autorización válida
- **THEN** la capa de integración bloquea la marcación y alerta sobre desalineación

#### Scenario: Marcación interna del dialer
- **GIVEN** un lead en estado marcable dentro de VICIdial pero sin token vigente
- **WHEN** el dialer predictivo o Asterisk intenta originar la llamada
- **THEN** el control de originate la rechaza antes de señalizar hacia la red y registra la ruta que intentó el bypass

### Requirement: Disposiciones y grabaciones
Los eventos de llamada SHALL normalizar `queued`, `ringing`, `answered`, `human_detected`, `transferred`, `completed`, `failed` y `disposition`. La grabación SHALL obedecer política por jurisdicción y campaña.

#### Scenario: Grabación no permitida
- **GIVEN** una política que prohíbe grabación para la campaña
- **WHEN** inicia la llamada
- **THEN** el proveedor recibe `recording=false` y el sistema verifica que no exista archivo

### Requirement: Corte seguro
El sistema SHALL poder pausar campaña y revocar autorizaciones pendientes en menos de 60 segundos; llamadas activas seguirán la política de terminación segura.

#### Scenario: Kill switch
- **GIVEN** un incidente de cumplimiento
- **WHEN** un compliance reviewer activa la pausa global
- **THEN** cesan nuevas llamadas, se invalidan tokens y se audita el alcance
