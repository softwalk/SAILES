# Conversation engine

## ADDED Requirements

### Requirement: SalesGPT como motor de recomendación
SalesGPT SHALL mantener etapa, intención, necesidades, objeciones, evidencias y próximo paso; SHALL emitir respuestas y acciones estructuradas, pero SHALL NOT invocar canales, contratos, pagos ni CRM fuera de herramientas gobernadas.

#### Scenario: Objeción normal
- **GIVEN** un prospecto autorizado que plantea una objeción contemplada
- **WHEN** SalesGPT genera respuesta
- **THEN** responde usando conocimiento aprobado, registra la objeción y propone un próximo paso permitido

### Requirement: Escalamiento sensible
El motor SHALL interrumpir el grafo ante queja, amenaza legal, revocación, datos sensibles, negociación fuera de límites, baja confianza o solicitud contractual.

#### Scenario: Solicitud de descuento alto
- **GIVEN** un umbral autónomo de 10%
- **WHEN** el prospecto solicita 20%
- **THEN** SalesGPT no promete el descuento y crea una aprobación sensible con contexto y borrador

### Requirement: Veracidad y límites
El motor SHALL citar internamente los fragmentos de conocimiento que sustentan afirmaciones de producto y SHALL declarar incertidumbre en vez de inventar.

#### Scenario: Pregunta sin respuesta autorizada
- **GIVEN** una pregunta no cubierta por conocimiento vigente
- **WHEN** el modelo intenta contestar
- **THEN** el validador exige aclaración o handoff y bloquea una afirmación no sustentada

### Requirement: Revocación inmediata
Una intención inequívoca de no contacto SHALL crear exclusión interna antes de cualquier otra acción.

#### Scenario: “No me contacten”
- **GIVEN** una conversación activa
- **WHEN** el usuario revoca contacto
- **THEN** se confirma de forma breve, se suprime por canales aplicables y se cancelan acciones pendientes

