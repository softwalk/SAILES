# Estado de implementación RC5

## Completado y probado

- Política determinística fail-closed, REPEP por campaña con excepción B2B
  aprobada/evidenciada, consentimiento, supresión, horarios y frecuencia.
- Campañas y aprobaciones ligadas a hash; sensibilidad y opt-out humano.
- Tokens JIT firmados, audiencia, TTL, claims, replay y consumo PostgreSQL atómico.
- OpenOutreach por CLI externo verificado por digest; OpenSales/SalesGPT sin side effects.
- Leads con procedencia, allowlist, licencia, deduplicación y scoring explicable.
- Orquestación versionada y durable en PostgreSQL, checkpoints con hash, recuperación tras reinicio, humano, expiración, compensación, retry, circuit breaker, outbox y DLQ.
- OpenRouter/Kimi/DeepSeek intercambiables, endpoint OpenRouter allowlisted, secretos por archivo, redacción, clasificación, reserva presupuestaria diaria durable antes de llamar, salud y fallback.
- Transportes HTTPS para Meta Cloud, VICIdial, Atlantis-Neobot y Marketia; SSRF/redirect bloqueados.
- Webhooks firmados, timestamp, deduplicación y repositorio PostgreSQL.
- CRM de contactos, campañas, consentimientos, interacciones, oportunidades, memoria y solicitudes ARCO.
- OIDC RS256 real en los endpoints de aprobación, con scopes/roles/tenant, además de firma HMAC independiente entre servicios.
- Auditoría append-only encadenada por tenant; runtime sin privilegios directos de mutación.
- Dockerfiles separados, Compose de nueve servicios, source gate y SBOM de fuente propia.

## Validado en el código fuente

- 100 pruebas unitarias/de invariantes, E2E shadow/HTTP, DR, carga y gate de fuente.
- Scripts para probar RLS cruzado, recuperación del orquestador, replay JIT tras reinicio y cadena de auditoría contra la VM real.
- Soak shadow de cuatro horas con contactos externos en cero y llamadas sintéticas a modelos acotadas.

## Pendiente en la infraestructura real

La palabra “terminado” para producción requiere aplicar la migración 008, configurar el IdP real, ejecutar las pruebas de reinicio/RLS/replay, completar el soak y cerrar `release/BLOCKERS.yaml`. Este entorno no tiene acceso a la VM ni a las aprobaciones de terceros. El sistema queda como release candidate en shadow, no como producto autorizado para contactar personas.
