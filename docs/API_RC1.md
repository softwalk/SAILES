# API runtime RC1

Todas las operaciones mutables requieren `Idempotency-Key` de 16–128 caracteres. Cuando `ATLANTIS_REQUIRE_WORKLOAD_AUTH=true`, también requieren `X-Atlantis-Service`, `X-Atlantis-Timestamp`, `X-Atlantis-Nonce` y `X-Atlantis-Signature`.

| Servicio | Operación | Seguridad adicional |
|---|---|---|
| CRM | `POST /v1/contacts` | Tenant autenticado |
| CRM | `POST /v1/campaign-versions` | Creador de campaña |
| CRM | `POST /v1/campaign-versions/approve` | Aprobador humano; hash exacto obligatorio |
| CRM | `POST /v1/suppressions` | Propaga opt-out |
| CRM | `POST /v1/interactions` | Idempotencia proveedor/ref |
| CRM | `POST /v1/opportunities` | Sensibilidad |
| CRM | `POST /v1/memory-facts` | Procedencia/confianza |
| CRM | `POST /v1/privacy/requests` | Identidad verificada |
| CRM | `POST /v1/contactability-evidence` | Sólo Policy Gateway |
| Policy | `POST /v1/contactability/decisions` | Evidencia obtenida del CRM fuera de shadow |
| Policy | `POST /v1/outbound-authorizations` | Sólo decisión ALLOW vigente |
| Orquestador | `POST /v1/runs` | Workflow fijado |
| Orquestador | `POST /v1/runs/transition` | Evento único |
| Orquestador | `POST /v1/human-actions/decide` | OIDC/rol aprobador en gateway |
| Model | `POST /v1/models/complete` | Clasificación y presupuesto |
| Voz | `POST /v1/voice/calls` | Token JIT, PostgreSQL y provider configurado |
| WhatsApp | `POST /v1/whatsapp/messages` | Token JIT y Meta Cloud API |
| Marketia | `POST /v1/marketia/sync` | Campos allowlist |
| Webhooks | `GET/POST /v1/webhooks/...` | Challenge o firma HMAC de proveedor |

El modelo de errores es JSON `{ "error": "REASON_CODE" }`. Denegaciones de autenticación/política usan 403, replay/conflictos 409, payload excesivo 413 y proveedor no disponible 503.

La operación de aprobación debe publicarse detrás del gateway OIDC con el scope
`campaign:approve`. La firma HMAC entre servicios autentica al workload, pero no
sustituye la identidad ni el rol del aprobador humano.
