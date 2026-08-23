# Cambios desde el último ZIP — RC3 a RC4

Fecha: 2026-08-22  
Base comparada: `Atlantis_Autonomous_Sales_Platform_RC_0.9.0_Source.zip`, versión RC3  
SHA-256 de la base: `f469a91597e35a674af4aed840e9c10ffe90c7bed9375eaf204aaa6eb7410894`

## Resumen

RC4 aplica los hallazgos de la revisión profunda de seguridad, SQL e infraestructura. No habilita contacto real ni convierte el paquete en una distribución aprobada: el modo autorizado sigue siendo desarrollo/shadow hasta cerrar `release/BLOCKERS.yaml`.

## Seguridad y aislamiento multi-tenant

1. Se agregó `database/004_security_and_durability.sql` y su copia OpenSpec.
2. Las supresiones `scope='GLOBAL'` ya son visibles a todos los tenants durante la evaluación de contactabilidad, sin permitir que un tenant las modifique.
3. La creación, cambio o borrado de supresiones globales requiere el rol `atlantis_suppression_admin`, separado y sin login directo.
4. La API CRM de tenant rechaza intentos de crear una supresión GLOBAL.
5. La autenticación HMAC de workloads queda activada por defecto en producción.
6. La identidad usada por el rate limiter sólo proviene de una firma ya validada; un cliente no puede evadirlo cambiando `X-Atlantis-Service`.
7. Los nonces anti-replay se guardan en PostgreSQL en producción y sobreviven reinicios/réplicas.

## Decisiones y autorizaciones

1. El contexto de decisión queda ligado al tenant y se consume una sola vez.
2. Las decisiones expiran según `ATLANTIS_DECISION_MAX_AGE_SECONDS` (120 s en el overlay).
3. Una autorización de voz sólo admite audiencia `voice-adapter`; WhatsApp sólo `whatsapp-adapter`.
4. Las decisiones futuras, caducadas, denegadas o con tenant/canal inconsistente fallan cerrado.

## Durabilidad y consumo de memoria

1. Se añadió `shared/atlantis_contracts/persistence.py`.
2. Idempotencia y nonces usan PostgreSQL en producción; en desarrollo usan mapas/conjuntos TTL con capacidad máxima.
3. La idempotencia reserva atómicamente una clave antes de ejecutar, distingue conflicto, solicitud en curso y respuesta cacheada.
4. Los estados internos del Policy Gateway, orquestador y deduplicación de webhooks quedaron acotados por TTL/capacidad.
5. Se añadió una función SQL de purga para estado runtime expirado.

## HTTP, TLS y transporte interno

1. POST exige `Content-Length` válido, no negativo y dentro del límite.
2. POST exige `Content-Type: application/json` y un objeto JSON como raíz.
3. Se añadió timeout de lectura, bind configurable y banner HTTP reducido.
4. Decimal se serializa como cadena decimal exacta para evitar pérdida binaria.
5. El cliente interno limita respuesta, valida content type, bloquea redirects y admite CA/certificado/clave mTLS.
6. HTTP interno sólo puede usarse en shadow y con hostname incluido explícitamente en `ATLANTIS_SHADOW_HTTP_ALLOWLIST`.
7. En producción PostgreSQL exige `sslmode=verify-full` y CA explícita.

## Infraestructura y supply chain

1. El overlay Proxmox usa CRM PostgreSQL de forma predeterminada.
2. Todos los servicios reciben autenticación workload y estado durable; secretos se montan como archivos.
3. La evidencia CRM queda conectada en shadow por excepción HTTP allowlisted; para piloto debe cambiarse a HTTPS/mTLS.
4. Kimi y DeepSeek usan claves virtuales separadas, no la master key de LiteLLM.
5. Se agregó `requirements-runtime.in` y un lock completo con hashes de 38 paquetes.
6. La imagen base instala con `pip --require-hashes`; se conserva únicamente psycopg v3.
7. Se mantuvieron healthchecks, contenedores read-only, uid no root, capabilities eliminadas y puertos ligados a localhost.

## Pruebas y contratos

- Suite unitaria/invariantes: 65/65 PASS.
- Nuevas pruebas: supresión global/RLS, TTL y reservas concurrentes, frescura/one-shot de decisiones, TLS PostgreSQL, validación HTTP, allowlist shadow y evasión de rate limit.
- OpenAPI actualizado para exigir `tenant_id` en autorización y limitar GLOBAL a la ruta administrativa.
- El test histórico de PostgreSQL ahora valida `set_config('app.tenant_id', ..., true)`.

## Archivos principales agregados

- `database/004_security_and_durability.sql`
- `spec/database/004_security_and_durability.sql`
- `shared/atlantis_contracts/persistence.py`
- `tests/test_durable_state.py`
- `tests/test_http_hardening.py`
- `tests/test_operations_kit.py`
- `deploy/proxmox/operations/` (kit completo de rollout y rollback)
- `deploy/proxmox/base/requirements-runtime.in`
- `deploy/proxmox/base/requirements-runtime.lock`
- `release/RC4_REVIEW.md`

## Pendientes que no pueden cerrarse sólo con código

- Rotación de credenciales bootstrap y secretos por servicio.
- TLS/mTLS interno real y CA instalada en la VM.
- Memoria efectiva del host Proxmox suficiente para el piloto.
- Digests OCI finales de los siete servicios y commit del repositorio.
- Contratos/cuentas/credenciales de Meta, Marketia, Neobot, VICIdial, REPEP y modelos.
- SAST/DAST/SCA, pentest, textos de licencias, SBOM de imágenes, fuentes correspondientes y attestation firmada.
- Patch y prueba de enforcement dentro de `originate` de Asterisk/VICIdial.

Por estos pendientes, RC4 es un candidato de fuente para shadow y revisión; no es una appliance/VM/ISO distribuible ni autoriza campañas reales.
