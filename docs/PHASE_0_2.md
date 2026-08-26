# Fase 0.2 — Stack integrado en shadow mode

## Alcance completado

La fase conecta los límites que en 0.1 existían sólo como clases de dominio. Policy Gateway, CRM API, orquestador, Model Gateway y los adaptadores tienen procesos HTTP independientes. El flujo de contacto puede ejecutarse hasta el recibo `SHADOW_ACCEPTED`, pero ningún transporte real está implementado.

## Configuraciones de almacenamiento

- `ATLANTIS_CRM_STORAGE=memory`: únicamente laboratorio/desarrollo; el overlay Proxmox RC5 usa PostgreSQL.
- `ATLANTIS_CRM_STORAGE=postgres`: exige `ATLANTIS_DATABASE_URL` y un driver psycopg instalado desde un lock aprobado.
- Policy Gateway usa PostgreSQL automáticamente cuando existe `ATLANTIS_DATABASE_URL`; fuera de shadow no acepta ledger en memoria.
- Los adaptadores consumen la autorización directamente en PostgreSQL fuera de shadow. La transición a producción sigue bloqueada porque los transportes reales aún no están aprobados.

## Contratos HTTP agregados

| Servicio | Endpoint |
|---|---|
| Orquestador | `POST /v1/runs` |
| Orquestador | `POST /v1/runs/transition` |
| Orquestador | `POST /v1/human-actions/decide` |
| Model Gateway | `POST /v1/models/complete` |
| Voz | `POST /v1/voice/calls` |
| WhatsApp | `POST /v1/whatsapp/messages` |
| Meta | `GET/POST /v1/webhooks/meta/whatsapp` |
| VICIdial | `POST /v1/webhooks/vicidial` |
| Atlantis-Neobot | `POST /v1/webhooks/atlantis-neobot` |
| Marketia | `POST /v1/marketia/sync`, `POST /v1/webhooks/marketia` |

## Próximo incremento obligatorio

1. Ejecutar PostgreSQL real y pruebas de migración/RLS entre tenants.
2. Incorporar un driver psycopg fijado con hash en una imagen base interna.
3. Implementar checkpointer LangGraph PostgreSQL y RabbitMQ/outbox worker.
4. Confirmar contratos reales de Marketia y Atlantis-Neobot.
5. Implementar Meta Cloud API en sandbox y webhook persistente.
6. Implementar el enforcement dentro de Asterisk/VICIdial antes de `originate`.
