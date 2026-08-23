# Changelog

## Unreleased — OpenRouter

- Integrado OpenRouter en `model_gateway` con endpoint HTTPS oficial allowlisted,
  autenticación Bearer desde Docker secret y modelo explícito.
- Añadido orden configurable `openrouter,kimi,deepseek`, fallback existente y
  bloqueo de OpenRouter para datos `RESTRICTED` salvo allowlist aprobada.
- Rechazados endpoints alternativos, credenciales embebidas en URL y el alias
  mutable `openrouter/auto`.
- Añadidos runbook, OpenSpec, configuración Proxmox y pruebas de secreto,
  encabezados, endpoint, routing y clasificación.

## 0.9.0-rc4 - 2026-08-22

- Corregida la política RLS de supresiones GLOBAL; su escritura requiere el rol separado `atlantis_suppression_admin`.
- Sustituidos caches ilimitados de decisiones, ejecuciones, idempotencia y nonces por almacenamiento durable PostgreSQL o estructuras TTL acotadas de desarrollo.
- La idempotencia HTTP usa reserva atómica, detecta solicitudes concurrentes y queda aislada por tenant.
- La autenticación HMAC entre workloads es obligatoria por defecto en producción; el rate limit ya no confía en headers no autenticados.
- Decisiones de contacto ligadas a tenant/canal, con frescura máxima y consumo único del contexto.
- Validación HTTP reforzada: `Content-Length`, tamaño, `application/json`, objeto raíz y timeout de lectura.
- PostgreSQL exige TLS `verify-full` en producción y admite CA/certificado/clave explícitos.
- Cliente interno con CA/mTLS configurable; HTTP sólo mediante allowlist explícita en shadow.
- CRM PostgreSQL es el valor predeterminado del overlay Proxmox y la evidencia CRM queda conectada en shadow.
- Dependencias runtime y transitivas fijadas con hashes; el build usa `pip --require-hashes`.
- Credenciales de proveedor LLM separadas y secretos/DNS/TLS reflejados en Compose.
- Suite ampliada de 45 a 65 pruebas; se añaden migraciones 004/005 y pruebas del kit operativo y pilot gate.
- ZIP v7 conserva el checksum legacy de 004, exige aprobación humana y registra reconciliación append-only con fingerprint calculado desde PostgreSQL.
- Añadido kit operativo para VM 110: preflight de capacidad, validación de secretos/PKI, backup, migración verificada, build/digests, despliegue shadow, evidencias y rollback de imágenes.

## 0.9.0-rc3 - 2026-08-22

- Imported and verified the VM 110 clean-source manifest (130/130 SHA-256 matches).
- Replaced invalid parameterized `SET LOCAL` statements with transactional `set_config()` calls.
- Added exact JSON handling for PostgreSQL UUID/date/Decimal values.
- Persisted action intents and policy decisions before JIT authorization ledger writes.
- Made decision persistence retry-safe through deterministic action-intent identifiers.
- Preserved denied/review decision status instead of marking every intent as allowed.
- Added contract tests for PostgreSQL tenant context, decision persistence and native-type JSON serialization (45 total tests).
- Added healthchecks to all seven application services and separated the runtime database secret.
- Removed the unused psycopg2 driver; runtime services use psycopg v3 only.
- Kept pilot and distribution blocked due to capacity, security, external-contract and supply-chain evidence.

## 0.9.0-rc2 - 2026-08-22

- Aligned deployment with Proxmox VM 110 (`atlantis-core`, `192.168.100.160`, 4 vCPU/4 GiB/60 GiB).
- Added an immutable infrastructure inventory and an application-only Compose overlay for the installed Docker networks.
- Added Docker-secret support for PostgreSQL and provider credentials; removed the need to place database passwords in DSNs.
- Added conservative per-service CPU, memory, PID, capability and log limits for the 4 GiB host.
- Added a read-only infrastructure validator and explicit remediation gates for bootstrap credentials and exposed admin ports.
- Preserved VM 102 Hermes as a subordinate research executor and all pre-existing guests as no-touch assets.

## 0.9.0-rc1 — 2026-08-22

- Seguridad OIDC RS256 y HMAC entre servicios; rate limiting e idempotencia.
- Evidencia de Policy Gateway obtenida del CRM fuera de shadow mode.
- REPEP verificable, E.164, lead scoring, deduplicación y prompt-injection quarantine.
- Retry, circuit breaker, outbox PostgreSQL/RabbitMQ, DLQ, checkpoint restore y DR drill.
- Transportes reales desactivados para Meta Cloud API, VICIdial, Neobot y Marketia.
- CRM ampliado a interacciones, oportunidades, memoria y ARCO.
- Migración 003 con nonces, idempotencia, frecuencia y auditoría serializada.
- 37 pruebas, E2E HTTP, carga concurrente, source SBOM y threat model.

## 0.2.0 — 2026-08-22

- Repositorios PostgreSQL para CRM y ledger JIT, con `SET LOCAL app.tenant_id`.
- Consumo atómico de tokens en los adaptadores.
- APIs HTTP para orquestador, Model Gateway, voz, WhatsApp y Marketia.
- Webhooks HMAC para Meta, VICIdial, Atlantis-Neobot y Marketia.
- Challenge de Meta en texto plano, deduplicación, control temporal y payload máximo.
- Dockerfiles separados y composición de nueve servicios de laboratorio.
- Flujo E2E en proceso y flujo HTTP Policy → WhatsApp shadow.
- Pruebas ampliadas de 15 a 19.

## 0.1.0 — 2026-08-22

- Primer núcleo ejecutable basado en OpenSpec v1.2.
