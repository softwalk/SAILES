# Auditoría técnica del OpenSpec Atlantis

**Fecha de corte:** 22 de agosto de 2026  
**Objeto revisado:** `Atlantis_Autonomous_Sales_OpenSpec` v1.0  
**Resultado corregido:** `Atlantis_Autonomous_Sales_OpenSpec_v1.2`

## Veredicto ejecutivo

La versión 1.0 tenía una buena arquitectura conceptual y controles correctos en intención, pero **no debía pasar directamente a implementación**. La revisión encontró cinco fallas críticas, diez altas y varias omisiones medias. La versión 1.1 corrige los defectos documentales y de contrato identificables sin disponer todavía de las APIs privadas de Marketia y Atlantis‑Neobot ni del acuerdo empresarial de acceso a REPEP.

La v1.2 queda apta para iniciar **descubrimiento técnico y legal**, no para producción ni distribución. El sprint de construcción debe permanecer bloqueado hasta cerrar los gates enumerados al final; una appliance/VM/ISO requiere además el gate de distribución.

## Adenda de licenciamiento v1.2

- Atlantis-Neobot, Marketia, Policy Gateway, CRM API y adaptadores quedan como servicios propietarios separados.
- OpenOutreach se limita al upstream sin modificar mediante proceso/CLI; un fork distribuido activa la obligación de fuente GPLv3.
- n8n se excluye y Node-RED core Apache-2.0 se incorpora como automatización auxiliar aislada.
- Toda dependencia, imagen y modelo debe fijarse por repositorio, revisión/commit, digest y licencia.
- Se bloquea técnicamente cualquier entrega de appliance, VM, plantilla, snapshot o ISO sin SBOM, avisos, licencias, fuentes correspondientes y attestation.

## Hallazgos críticos

| ID | Hallazgo en v1.0 | Riesgo | Corrección en v1.1 |
|---|---|---|---|
| C-01 | VICIdial sólo validaba token en el adaptador/importación. Un dialer predictivo puede originar desde una lista interna sin volver a pasar por ese punto. | Llamada real sin REPEP/token aunque el plano de control parezca correcto. | Se exige control también en el punto exacto de `originate/dial` en Asterisk/VICIdial y una prueba de bypass end-to-end. |
| C-02 | El esquema prometía aislamiento por tenant, pero múltiples tablas no tenían FK a `tenant`, varias relaciones sólo referían `id` y RLS era un comentario. | Referencias cruzadas y fuga de datos entre clientes por error de aplicación o configuración. | Migración con FKs compuestas `(id, tenant_id)`, `ENABLE/FORCE RLS`, políticas por tabla y requisito de rol sin `BYPASSRLS`. |
| C-03 | No existía capability spec de LangGraph; sólo diseño y tareas. | La pieza central carecía de requisitos verificables para reanudación, idempotencia, interrupciones y migración. | Se agregó `workflow-orchestration/spec.md` con escenarios de despliegue, crash, HITL y reintentos. |
| C-04 | `ActionIntent`, acciones humanas, reglas versionadas y artefactos aprobados aparecían en texto/API, pero no tenían persistencia suficiente. | Auditoría incompleta; imposibilidad de demostrar qué se autorizó o reanudar de forma segura. | Se agregaron tablas `action_intent`, `human_action`, `policy_rule_set`, `campaign_artifact` y `knowledge_pack`. |
| C-05 | El webhook genérico trataba Evolution como WhatsApp productivo y exigía una firma inventada uniforme. Meta usa challenge y `X-Hub-Signature-256`. | Rechazo de webhooks válidos o aceptación insegura; acoplamiento innecesario. | Endpoint Meta dedicado con challenge/firma sobre cuerpo crudo; Cloud API directa es la ruta preferida y Evolution queda opcional. |

## Hallazgos altos

| ID | Hallazgo en v1.0 | Corrección |
|---|---|---|
| A-01 | REPEP se describía como una consulta potencialmente en línea sin modelar el modo empresarial real. | Snapshot autorizado con lote, fecha efectiva, recibo/contrato, hash y vigencia jurídica; `fail closed`. |
| A-02 | No se exigían registros sectoriales adicionales cuando el producto lo requiera. | Gate de matriz por jurisdicción, B2B/B2C, producto y sector; REPEP permanece obligatorio para voz promocional. |
| A-03 | La autorización podía emitirse antes de esperar en cola, dejando una ventana de revocación. | Emisión justo a tiempo después de retirar de cola y repetir preflight. |
| A-04 | Los comandos de voz/WhatsApp llevaban casi sólo el token; no exponían todos los campos a cotejar. | El contrato vincula intención, tenant, contacto, campaña, proveedor y hash exacto de contenido/guion. |
| A-05 | El hash de aprobación no definía canonicalización ni todos los elementos materiales. | Manifiesto JSON canónico con audiencia, contenido, conocimiento, prompts, horarios, límites y reglas. |
| A-06 | Un checkpoint de LangGraph podía reanudarse con código nuevo no compatible. | `workflow_version` por run/checkpoint y migración explícita probada. |
| A-07 | El fallback Kimi/DeepSeek no fijaba proveedor por conversación ni exigía canary. | Afinidad por conversación salvo fallback auditado; evals, canary y rollback por cambio. |
| A-08 | La cadena de auditoría con `previous_hash` podía bifurcarse por concurrencia. | Secuencia única por tenant, `audit_chain_head`, inserción serializada y exportación WORM; actualización/borrado bloqueados. |
| A-09 | No había persistencia concreta para webhooks, DLQ, solicitudes ARCO o legal hold. | Se agregaron `webhook_receipt`, `dead_letter_event`, `data_subject_request` y `legal_hold`. |
| A-10 | Las licencias/madurez se dejaban como revisión genérica. | Capability de supply chain, gates en CI y decisiones explícitas por componente. |

## Riesgos específicos de componentes verificados

### OpenOutreach

- El proyecto actual se enfoca en descubrimiento/calificación y exportación; no envía mensajes.
- La licencia observada es GPLv3. Incorporar o enlazar código dentro del núcleo propietario puede tener consecuencias de copyleft.
- Decisión v1.1: límite de proceso/servicio y contrato de datos hasta dictamen legal; nunca recibe credenciales de canal.

### OpenSales

- Es MIT, pero muestra baja madurez pública y contiene rutas directas a SendGrid, Google Sheets y fuentes externas.
- Decisión v1.1: tratarlo como referencia o adaptador; retirar herramientas de envío, Sheets y credenciales. No asumirlo como orquestador enterprise.

### SalesGPT

- Es MIT y sirve como referencia conversacional, pero el proyecto upstream incluye creación de enlaces de pago.
- Decisión v1.1: cargar sólo política/etapas; deshabilitar herramientas de pago, firma, descuentos y canales por construcción.

### Evolution API

- Soporta tanto Baileys como Cloud API oficial.
- La licencia observada en 2026 añade condiciones de notificación y ciertas versiones introducen activación obligatoria; no debe tratarse como Apache 2.0 puro sin matices.
- Decisión v1.1: adaptador directo a Meta Cloud API como primera opción. Evolution sólo si su versión/licencia/activación y telemetría son aprobadas.

### LangGraph

- Checkpoints e interrupts sí soportan ejecución durable y HITL.
- La documentación oficial advierte que un nodo puede volver a ejecutarse al reanudar; los efectos anteriores al interrupt deben ser idempotentes.
- Decisión v1.1: outbox/tareas idempotentes y versión fija de workflow por run.

### REPEP

- Profeco permite a proveedores obtener los números inscritos previo registro/pago; no se debe diseñar como si existiera una API pública estable.
- Decisión v1.1: snapshots adquiridos por medio autorizado, evidencia de origen y vigencia acordada con Legal.

## Omisiones medias corregidas

- Falta de respuesta de error uniforme en OpenAPI.
- Ausencia de endpoint de activación de campaña y decisión de acciones humanas.
- Falta de semántica para webhooks duplicados y firma Meta.
- Falta de restricciones de confianza entre 0 y 1.
- Falta de límite SQL verificable para TTL de autorización.
- Falta de unicidad de eventos outbox por agregado/versión/tipo.
- Falta de vínculo explícito entre decisión y `action_intent`.
- Ambigüedad entre Cloud API directa y Evolution.
- Contradicción entre “cada fila tiene versión” y el esquema real; se restringió a agregados mutables.
- Falta de pruebas contractuales de adaptadores y despliegues con runs pausados.

## Validaciones ejecutadas

| Prueba | Resultado |
|---|---|
| Parseo YAML de `openspec/config.yaml` y `contracts/openapi.yaml` | Correcto |
| Estructura de 12 capability specs | Correcta |
| Cada requirement contiene lenguaje normativo | Correcto |
| Cada requirement tiene al menos un escenario Given/When/Then | Correcto |
| Referencias `$ref` locales del OpenAPI | Correctas |
| `operationId` únicos y parámetros de path completos | Correcto |
| Scopes OAuth declarados | Correcto |
| Controles mínimos esperados en SQL | Correcto |
| Validador local `tools/validate_package.py` | PASS; una advertencia esperada por URLs placeholder |
| CLI oficial `openspec validate --strict` | No concluyente: el registro npm devolvió `ECOMPROMISED Lock compromised`; no se ignoró esa alerta de integridad |
| Ejecución real de migraciones PostgreSQL | Pendiente: el entorno de revisión no dispone de servidor PostgreSQL |

## Bloqueadores que siguen abiertos

1. Contrato real de Marketia: API, autenticación, webhooks, ownership y resolución de conflictos.
2. Contrato de Atlantis‑Neobot y punto exacto donde inicia/autoriza una llamada.
3. Alta empresarial, pago, formato, periodicidad y vigencia jurídica de los datos REPEP.
4. Alcance B2B/B2C, países, sectores y registros sectoriales adicionales.
5. Política de grabación, aviso, retención y transferencia internacional validada por Legal.
6. Cuenta Meta, números, plantillas, opt-in, límites y calidad de WhatsApp.
7. DPA, residencia, retención y uso para entrenamiento de Kimi y DeepSeek.
8. Dictamen legal de licencias/arquitectura y commits exactos de todos los proyectos OSS.
9. Proveedor de identidad, KMS/secretos, object storage, observabilidad y RabbitMQ.
10. Ejecución de las migraciones contra PostgreSQL real y pruebas de RLS con roles de aplicación.

## Recomendación

Usar v1.2 como baseline y cerrar primero las tareas `0.x`. No iniciar integración de canales reales hasta demostrar los gates técnicos y de licencias. No entregar artefactos instalables a clientes hasta que `tools/validate_distribution.py` termine satisfactoriamente. Después ejecutar shadow mode y piloto allowlist con aprobación del 100%.
