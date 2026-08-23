# Revisión técnica RC 0.9.0-rc3

Fecha: 2026-08-22  
Base: `vm110-source-clean.zip` y `vm110-source-manifest.sha256` suministrados por el operador.

## Integridad de entrada

- 130 archivos de fuente manifestados.
- 130 hashes SHA-256 coincidentes.
- Sin archivos no manifestados, enlaces simbólicos, `.git`, `.venv`, cachés, bases locales ni claves privadas.
- El paquete documental externo contiene credenciales bootstrap históricas; no se incorporó al artefacto RC3.

## Defectos encontrados y corregidos

1. La fuente recibida fallaba 1 de 40 pruebas porque el contrato aún esperaba `SET LOCAL`; se actualizó para verificar `set_config(..., true)` y el tenant parametrizado.
2. `_persist_decision` generaba un `action_intent` aleatorio por reintento y podía dejar filas huérfanas; se reemplazó por un repositorio transaccional con ID determinístico.
3. Todos los intentos se persistían como `ALLOWED`; ahora se mapean `ALLOW→ALLOWED`, `DENY→DENIED`, `REVIEW→REVIEW`.
4. La decisión se persistía al pedir el token; ahora se persiste al decidir, antes de exponer un `decision_id` autorizable.
5. Un contexto perdido tras reinicio provocaba `KeyError`; ahora falla cerrado con `404 DECISION_CONTEXT_NOT_FOUND`.
6. El gate de fuente inspeccionaba entornos virtuales locales; ahora excluye directorios generados conocidos.
7. La imagen base instalaba psycopg v3 y psycopg2 sin que el código usara psycopg2; se eliminó el driver redundante.
8. El overlay no definía healthchecks para los siete servicios; se añadió un sondeo HTTP común con puerto explícito.
9. El contrato OpenAPI omitía `POST /outbound-authorizations`; se añadió el request, token de respuesta y errores fail-closed.

## Riesgos que permanecen abiertos

- La recuperación de contexto autorizable después de reiniciar Policy Gateway no está implementada; falla cerrado.
- La integración PostgreSQL real de RC3 requiere prueba en VM 110, incluida RLS, rollback y concurrencia.
- La imagen base fija versiones, pero faltan hashes de paquetes, lock transitivo, textos de licencia y attestations.
- Los IDs exactos y términos de Kimi/DeepSeek, contratos externos, REPEP y credenciales sandbox siguen pendientes.
- La VM 110 tiene ~1.78 GiB efectivos y ~60 MiB disponibles según la evidencia recibida: piloto `NO GO`.
- Secretos bootstrap documentados y puertos administrativos continúan pendientes de rotación/endurecimiento.

## Dictamen

`GO` para revisión de fuente y despliegue controlado en **shadow**.  
`NO GO` para contacto real, piloto externo, producción o distribución de VM/ISO/appliance.
