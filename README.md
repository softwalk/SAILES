# Atlantis Autonomous Sales Platform — Release Candidate 0.9.0-rc5

Implementación de referencia del OpenSpec v1.2. El repositorio entrega un release candidate ejecutable para campaña, aprobación humana, cumplimiento fail-closed, autorización JIT, orquestación durable, proveedores intercambiables y adaptadores aislados.

> Estado: **release candidate / shadow mode**. No es una appliance distribuible ni autoriza contacto real. Consulte `release/BLOCKERS.yaml` antes de cualquier piloto.

> Alcance RC5-B2B: exclusivamente campañas B2B aprobadas y evidenciadas. REPEP queda fuera de este alcance; WhatsApp está diferido y desactivado en el despliegue predeterminado. Véase `release/SCOPE_RC5_B2B.yaml`.

## Lo que ya funciona

- Policy Gateway determinístico y `fail closed` para voz/WhatsApp.
- REPEP configurable por campaña e inicialmente desactivado. Para voz promocional,
  desactivarlo sólo es válido con campaña B2B, excepción aprobada y evidencia
  jurídica persistida; B2C continúa exigiendo REPEP vigente y fail-closed.
- Consentimiento, supresiones, horario, frecuencia, aprobación y hash de campaña.
- Tokens HMAC JIT con audiencia, TTL máximo de 5 minutos y consumo único.
- Campañas versionadas; cualquier cambio material invalida la aprobación.
- Orquestador determinístico, checkpoints, interrupción humana, outbox e idempotencia.
- Model Gateway con OpenRouter, Kimi y DeepSeek intercambiables, redacción de PII, fallback y presupuesto. OpenRouter usa exclusivamente `https://openrouter.ai/api/v1`, clave montada como secreto y un ID de modelo explícito.
- Adaptadores separados: OpenOutreach CLI externo, OpenSales, SalesGPT, voz, WhatsApp y Marketia.
- CRM/memoria/auditoría con repositorio de desarrollo y esquema PostgreSQL endurecido.
- Composición de laboratorio y overlay application-only alineado con VM 110 en Proxmox; PostgreSQL y Node-RED permanecen aislados.
- Gate de supply chain que detecta n8n, imports de OpenOutreach y artefactos de distribución incompletos.
- Repositorios PostgreSQL para CRM y consumo atómico de tokens, activables sólo con driver fijado.
- Persistencia transaccional e idempotente de `action_intent` y decisiones antes de emitir autorizaciones JIT.
- Healthchecks explícitos para los siete servicios del overlay Proxmox.
- APIs HTTP de orquestador, Model Gateway y adaptadores en shadow mode.
- Webhooks Meta y proveedores con HMAC, límite temporal, deduplicación y límite de payload.
- Flujo E2E HTTP Policy Gateway → WhatsApp shadow, incluyendo bloqueo de replay.
- OIDC RS256, RBAC/scopes/tenant y autenticación HMAC entre workloads.
- E.164, tokenización, snapshots REPEP, scoring/deduplicación y guard contra prompt injection.
- Retry, circuit breaker, DLQ, restauración de checkpoints y outbox PostgreSQL/RabbitMQ opcional.
- Transportes HTTPS reales —desactivados— para Meta, VICIdial, Neobot y Marketia.
- Rate limiting, idempotencia HTTP, SSRF/redirect protection y auditoría verificable.
- Supresión GLOBAL visible bajo RLS, con escritura reservada a un rol administrativo separado.
- Nonces e idempotencia durables en PostgreSQL, con reservas atómicas y límites TTL en desarrollo.
- Decisiones ligadas a tenant, canal y antigüedad máxima; el contexto se consume una sola vez.
- PostgreSQL con `verify-full`, CA explícita y autenticación workload obligatoria en producción.
- Validación HTTP estricta de longitud, tipo de contenido, objeto JSON y tiempo de lectura.
- Dependencias Python transitivas fijadas con hashes mediante `--require-hashes`.
- Prueba concurrente de 100 grafos y 100 webhooks por encima de la meta.

## Inicio rápido

```bash
cp .env.example .env
python3 -m unittest discover -s tests -v
python3 tools/demo.py
python3 tools/shadow_e2e.py
python3 tools/http_e2e.py
python3 tools/load_test.py
python3 tools/dr_drill.py
python3 tools/compliance_gate.py --mode source
```

Para la infraestructura instalada, comenzar por `docs/INFRASTRUCTURE_ALIGNMENT.md` y `docs/PROXMOX_DEPLOYMENT.md`. El inventario ejecutable está en `deploy/proxmox/inventory.yaml`; no usar el compose de laboratorio sobre VM 110.

El rollout controlado de RC5 está en `deploy/proxmox/operations/README.md`. Incluye preflight, backup, migraciones hasta 008, build, despliegue shadow, pruebas de persistencia/replay, soak de cuatro horas, evidencias y rollback de imágenes. Ningún script habilita contacto real.

La entrega ZIP v7 añade reconciliación append-only de la migración 004 y un gate técnico de piloto con comprobación TLS real, RAM, Git, imágenes y modelos. La migración 005 no se aplica sin aprobador humano nominativo.

Para levantar un servicio de demostración:

```bash
PYTHONPATH=shared:services/policy_gateway python3 -m app.server
curl http://127.0.0.1:8081/health
```

## Arquitectura y límites

Cada directorio de `services/` representa un artefacto desplegable independiente. Los servicios comparten únicamente contratos de datos permisivos de `shared/`; no importan OpenOutreach, VICIdial, Node-RED ni otro componente copyleft. OpenOutreach sólo se ejecuta como un proceso externo explícitamente allowlisted.

| Servicio | Estado MVP | Rol |
|---|---|---|
| policy_gateway | HTTP :8081 | Decisión y autorización de contacto |
| crm_api | HTTP :8082 | CRM, consentimiento, evidencia y auditoría |
| orchestrator | HTTP :8083 | Estado, aprobaciones, outbox y reintentos |
| model_gateway | HTTP :8084 | OpenRouter/Kimi/DeepSeek, redacción y fallback |
| voice_adapter | HTTP :8085, shadow | VICIdial/Atlantis-Neobot tras token JIT |
| whatsapp_adapter | Diferido / perfil opcional | Fuera del alcance RC5-B2B; no se inicia por defecto |
| marketia_adapter | HTTP :8087 | Sincronización sin autoridad de cumplimiento |

## Reglas de producción

1. Ejecutar siempre primero en `shadow mode`.
2. El adaptador real sólo acepta autorización emitida inmediatamente antes de enviar/marcar.
3. El punto `originate` de Asterisk/VICIdial debe repetir la validación; el adaptador por sí solo no basta.
4. El CRM PostgreSQL es la autoridad. El repositorio en memoria sólo sirve para pruebas.
5. La imagen base fija versiones y hashes de psycopg, Pika, LangGraph y transitivas; producción requiere además textos de licencia, digests OCI por servicio y attestation final aprobada.
6. No entregar VM/ISO/plantilla hasta que `tools/compliance_gate.py --mode distribution` pase y existan SBOM, avisos, licencias, fuentes y attestation.
7. Las claves de proveedores de modelos sólo se montan desde `/run/secrets`; nunca se guardan en `.env`, Git, trazas, prompts o artefactos de soporte. OpenRouter permanece excluido de datos `RESTRICTED` salvo allowlist aprobada por Legal/Privacidad.

## Estado OpenSpec y cierre

La matriz está en `docs/TRACEABILITY.md` y el cierre alcanzable en `docs/IMPLEMENTATION_STATUS.md`. Los bloqueos externos y de infraestructura de `release/BLOCKERS.yaml` impiden declarar producción o distribución aunque el código fuente pase sus pruebas.
