# Trazabilidad OpenSpec v1.2 → implementación MVP

| Capacidad | Evidencia implementada | Estado |
|---|---|---|
| lead-intelligence | `outreach_cli.py`, validación de procedencia y proceso externo | Parcial; falta upstream real fijado/evals |
| campaign-orchestration | `CRMStore` versiona, hashea, aprueba e invalida cambios | MVP probado |
| conversation-engine | `SalesGPTPolicy` bloquea efectos, opt-out y sensibilidad | MVP probado; falta SalesGPT real |
| compliance-governance | PolicyEngine + JIT + replay + razones | MVP probado |
| workflow-orchestration | WorkflowEngine, API HTTP, checkpoints, humano, outbox, idempotencia | MVP probado; falta runtime LangGraph |
| model-routing | Redacción, clasificación, fallback, schema y presupuesto | MVP probado; faltan cuentas/model IDs aprobados |
| channel-voice | API, verificación de token, consumo PostgreSQL y shadow mode | Parcial; falta control en Asterisk originate |
| channel-whatsapp | API, token, firma Meta, challenge, deduplicación y shadow mode | Parcial; falta envío Meta real |
| marketia-integration | Contrato allowlist y campos protegidos | MVP probado; falta API Marketia |
| crm-memory | Esquema, repositorio dev y repositorio PostgreSQL con RLS contextual | Parcial; falta prueba en PostgreSQL real |
| security-observability | Hash de auditoría, separación, minimización básica | Parcial; faltan OIDC/mTLS/OTel/KMS |
| license-compliance | Proceso GPL externo y gate fuente/distribución | MVP probado |
| supply-chain-governance | Scanner de código y distribución fail-closed | MVP probado; lock sigue bloqueado |

## Pruebas automatizadas

Las 40 pruebas cubren: REPEP, opt-in, hash de campaña, kill switch, JIT/replay, auditoría tenant, idempotencia, aprobación humana, Marketia, SalesGPT, fallback, PII, PostgreSQL boundaries, secretos por archivo, DSN seguro, OIDC, workload HMAC, E.164, scoring, sensibilidad, retry/DLQ, circuit breaker, restore, SSRF, transportes, prompt injection, webhooks y migraciones.

## Definition of Done del incremento 0.2

- [x] Núcleo ejecutable sin dependencias descargadas.
- [x] Ningún contacto real habilitado por defecto.
- [x] Pruebas de invariantes críticas verdes.
- [x] Gate fuente verde y gate distribución bloqueado intencionalmente.
- [x] Servicios propietarios separados por directorio/artefacto.
- [ ] Contratos/proveedores reales confirmados.
- [ ] Componentes e imágenes fijados por digest.
- [ ] SBOM, avisos, licencias, fuentes y attestation de una release.
- [ ] Validación legal de REPEP, WhatsApp, grabación y retención.
- [ ] Prueba E2E sobre Asterisk/VICIdial y Meta Cloud API.
