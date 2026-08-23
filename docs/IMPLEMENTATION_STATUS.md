# Estado final alcanzable en este entorno

## Completado y probado

- Política determinística fail-closed, REPEP por campaña con excepción B2B
  aprobada/evidenciada, consentimiento, supresión, horarios y frecuencia.
- Campañas y aprobaciones ligadas a hash; sensibilidad y opt-out humano.
- Tokens JIT firmados, audiencia, TTL, claims, replay y consumo PostgreSQL atómico.
- OpenOutreach por CLI externo verificado por digest; OpenSales/SalesGPT sin side effects.
- Leads con procedencia, allowlist, licencia, deduplicación y scoring explicable.
- Orquestación versionada, checkpoints, restore, humano, expiración, compensación, retry, circuit breaker, outbox y DLQ.
- Kimi/DeepSeek intercambiables, redacción, clasificación, presupuesto, salud y fallback.
- Transportes HTTPS para Meta Cloud, VICIdial, Atlantis-Neobot y Marketia; SSRF/redirect bloqueados.
- Webhooks firmados, timestamp, deduplicación y repositorio PostgreSQL.
- CRM de contactos, campañas, consentimientos, interacciones, oportunidades, memoria y solicitudes ARCO.
- OIDC RS256, scopes/roles/tenant y firma HMAC entre servicios.
- Auditoría encadenada por tenant y recuperación de checkpoint.
- Dockerfiles separados, Compose de nueve servicios, source gate y SBOM de fuente propia.

## Imposible cerrar sin recursos externos

La palabra “terminado” para producción requiere los ocho elementos de `release/BLOCKERS.yaml`. En este entorno no existen Docker/PostgreSQL, credenciales, contratos de Marketia/Neobot, WABA, acceso VICIdial, mecanismo REPEP autorizado, IdP, claves KMS ni dictamen legal. El sistema queda como release candidate bloqueada, no como producto autorizado para contactar personas.
