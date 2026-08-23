# Plataforma Autónoma de Ventas Atlantis — paquete OpenSpec v1.2

Especificación ejecutable para una plataforma de prospección y venta asistida por IA, con control humano, cumplimiento por canal y trazabilidad de extremo a extremo.

## Alcance de integración

| Componente | Responsabilidad delimitada |
|---|---|
| OpenOutreach | Descubrir y precalificar prospectos. Se ejecuta sin modificar como proceso/CLI externo; nunca se importa en código propietario ni recibe credenciales de canal. Si se distribuye una modificación, su código fuente se publica bajo GPLv3. |
| OpenSales | Referencia/adaptador para segmentos, secuencias y contenido; se deshabilitan sus herramientas de envío y Google Sheets. |
| SalesGPT | Mantener contexto conversacional, detectar etapa, manejar objeciones y proponer siguiente acción; las acciones pasan por políticas. |
| LangGraph | Máquina de estados persistente, reintentos, interrupciones humanas, compensaciones y auditoría. |
| Node-RED | Automatización visual opcional bajo Apache-2.0; sustituye cualquier dependencia de n8n. Se ejecuta aislado y sólo invoca APIs autorizadas. Cada nodo adicional requiere revisión de licencia. |
| VICIdial / Atlantis-Neobot | VICIdial ejecuta llamadas únicamente con autorización efímera; Atlantis-Neobot permanece como servicio propietario separado y no se enlaza dentro de componentes copyleft. |
| WhatsApp | `WhatsAppProvider` usa Cloud API oficial directamente en producción; Evolution API es un adaptador opcional y debe usar su transporte oficial. |
| PostgreSQL | Sistema de registro para CRM, consentimiento, auditoría, memoria, eventos y checkpoints. |
| Kimi K3 / DeepSeek | Proveedores intercambiables detrás de `ModelGateway`; selección por tarea, política, coste y disponibilidad. |
| REPEP | Control configurable por campaña. Inicia desactivado; voz promocional sólo omite consulta cuando existe excepción B2B aprobada y evidenciada. REPEP es operado por Profeco. |
| Marketia | Servicio propietario separado para campañas, activos, atribución, seguimiento y sincronización de resultados. |
| Servicios Atlantis | Atlantis-Neobot, Marketia, Policy Gateway, CRM API y todos los adaptadores se construyen, publican y despliegan como servicios propietarios separados, con imágenes, repositorios y SBOM propios. |
| Humano | Aprobar campañas inicialmente y resolver acciones/oportunidades sensibles. |

## Estructura

- `openspec/changes/integrate-autonomous-sales-platform/proposal.md`: por qué, alcance, métricas y riesgos.
- `openspec/changes/integrate-autonomous-sales-platform/design.md`: arquitectura, estados, seguridad y decisiones.
- `openspec/changes/integrate-autonomous-sales-platform/tasks.md`: plan de implementación verificable.
- `openspec/changes/integrate-autonomous-sales-platform/specs/*/spec.md`: requisitos y escenarios Given/When/Then.
- `contracts/openapi.yaml`: contrato mínimo de control y adaptadores.
- `database/schema.sql`: esquema lógico inicial para PostgreSQL.
- `database/002_hardening_v1_1.sql`: migración de aislamiento tenant, RLS y entidades operativas faltantes.
- `runbooks/pilot-and-operations.md`: despliegue, piloto, reversión e incidentes.
- `compliance/component-lock.yaml`: registro bloqueante de versiones, digests, licencias y modelos.
- `compliance/DISTRIBUTION_GATE.md`: condiciones para entregar appliance, VM, plantilla, snapshot o ISO.
- `tools/validate_distribution.py`: gate fail-closed; debe fallar mientras falte evidencia de distribución.

## Principios no negociables

1. Ningún adaptador de canal decide por sí mismo si puede contactar.
2. Toda llamada saliente exige autorización efímera ligada a contacto, campaña, propósito y versión.
3. WhatsApp promocional exige opt-in demostrable, plantilla válida cuando aplique y exclusión interna vigente.
4. Una modificación material invalida la aprobación de campaña.
5. Cuando REPEP está activo, su indisponibilidad o ambigüedad bloquea llamadas promocionales. Cuando está inactivo, falta de excepción B2B aprobada/evidenciada también bloquea (`fail closed`).
6. El modelo propone; las políticas determinísticas y el humano autorizan.
7. Cada decisión debe poder reconstruirse con evidencia, versión y actor.
8. La autorización se emite justo antes de ejecutar, no al insertar una acción en una cola.
9. Un cambio de versión del grafo, prompt, modelo, política o conocimiento queda ligado a cada ejecución.
10. Ningún repositorio OSS se considera listo para producción sin evaluar licencia, seguridad, madurez y contratos.
11. Atlantis-Neobot, Marketia, Policy Gateway, CRM API y adaptadores no se incorporan, enlazan ni compilan dentro de OpenOutreach, VICIdial/Asterisk u otro componente copyleft.
12. Toda release fija repositorio, tag, commit, imagen por digest y licencia de cada componente y modelo; un campo `TBD`, alias mutable o licencia desconocida bloquea promoción.
13. Ninguna appliance, VM, plantilla, ISO o imagen para cliente se entrega sin SBOM, THIRD_PARTY_NOTICES, textos de licencia y paquete de código fuente correspondiente.

## Correcciones incorporadas en v1.2

- Se formalizan límites propietarios separados para Atlantis-Neobot, Marketia, Policy Gateway, CRM API y adaptadores.
- OpenOutreach queda limitado a proceso/CLI externo sin modificaciones; toda modificación distribuida exige liberación GPLv3 del código correspondiente.
- n8n queda prohibido y se sustituye por Node-RED core Apache-2.0, con revisión individual de cada nodo adicional.
- Se agrega un manifiesto bloqueante que fija repositorio, tag, commit, imagen/digest y licencia de cada componente y modelo.
- Se crea un gate específico que impide entregar appliance, VM, plantilla o ISO sin SBOM, avisos, licencias y paquete de fuentes.

## Correcciones heredadas de v1.1

- El control de VICIdial se exige en el punto real de `originate/dial`, no sólo al importar leads.
- El adaptador directo a WhatsApp Cloud API es la ruta preferida; Evolution API queda opcional.
- REPEP se modela como snapshots adquiridos por un mecanismo autorizado, con identificador, vigencia, recibo y evidencia; no se presupone una API en línea.
- Se agregan claves foráneas compuestas y RLS `FORCE` para aislamiento multi-tenant.
- Se completa el contrato OpenAPI con enlace de intención, contacto, campaña, hash de contenido y webhooks Meta.
- Se agregan versiones de grafo, acciones humanas, conocimiento, solicitudes ARCO, legal hold, webhooks y DLQ.
- Se registran los riesgos de licencia de OpenOutreach y Evolution API vigentes en 2026.
- Se añade un validador local reproducible en `tools/validate_package.py`.

## Uso con OpenSpec

Desde la raíz de un repositorio inicializado con OpenSpec, copie `openspec/` y revise primero `proposal.md`. Después valide los artefactos con la versión instalada de la CLI y ejecute la implementación por bloques de `tasks.md`. Esta propuesta usa el flujo actual `proposal → specs → design → tasks`.

## Supuestos que requieren confirmación antes del sprint 1

- Contratos/API y autenticación reales de Marketia y Atlantis-Neobot.
- Mecanismo autorizado de consulta masiva de REPEP disponible para la empresa.
- Países, industrias reguladas, horarios y bases jurídicas del tratamiento.
- Cuenta de WhatsApp Business, plantillas, números, límites y mecanismo de opt-in.
- Política de grabación, aviso y retención de audio validada por asesoría jurídica.
- Licencias y versiones exactas de cada proyecto, imagen y modelo; no se incorporará código ni se entregará artefacto con campos pendientes en `compliance/component-lock.yaml`.
- Alcance B2B/B2C, sectores regulados y registros sectoriales adicionales a REPEP.
- Control exacto en Asterisk/VICIdial que impedirá `originate` sin autorización de un solo uso.
- Residencia y transferencia internacional permitida para cada clase de datos enviada a Kimi o DeepSeek.

## Validación

```bash
python3 tools/validate_package.py
openspec validate integrate-autonomous-sales-platform --strict
python3 tools/validate_distribution.py  # debe pasar únicamente para una entrega a cliente
```

El primer comando no requiere dependencias externas y valida también el manifiesto de licencias y los artefactos de entrega. El segundo requiere una instalación confiable y fijada de la CLI oficial.
