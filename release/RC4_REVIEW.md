# Revisión técnica RC 0.9.0-rc4

Fecha: 2026-08-22

## Dictamen

Los hallazgos de código P0/P1 de la revisión RC3 fueron tratados en RC4. La suite local ampliada pasa 65/65. La decisión permanece `SHADOW READY / PILOT NO GO` porque todavía existen controles que sólo pueden verificarse o cerrarse en la infraestructura y con terceros.

## Hallazgos cerrados en código

| Hallazgo | Corrección | Evidencia |
|---|---|---|
| Supresión GLOBAL invisible bajo RLS | Política de lectura tenant+global y rol administrativo de escritura separado | migración 004 + tests de migración/repositorio |
| Policy sin evidencia CRM en shadow | Cadena CRM habilitada con excepción HTTP allowlisted | Compose + test del cliente |
| Memoria no acotada | TTL/capacidad y stores PostgreSQL | tests de durabilidad/concurrencia |
| Nonce sólo por proceso | `PostgresNonceStore` | tests de replay/expiración |
| Idempotencia por proceso | reserva atómica PostgreSQL por tenant | tests de reserva/conflicto |
| Workload auth apagada | obligatoria en producción | configuración + tests |
| Rate-limit suplantable | identidad interna sólo tras firma | test HTTP de spoofing |
| Decisiones reutilizables/antiguas | one-shot, tenant-bound y frescura | tests de Policy |
| DSN sin TLS fuerte | `verify-full` obligatorio | tests de configuración |
| HTTP débil | longitud, MIME, JSON, timeout y límite | tests HTTP |
| Dependencias sin hashes | lock transitivo + `--require-hashes` | Dockerfile/lock |

## Riesgo residual externo

La excepción HTTP de shadow debe eliminarse al instalar TLS interno. La integración PostgreSQL real, migración 004, permisos del rol global, múltiples réplicas, certificados, healthchecks y rollback requieren prueba en VM 110. También permanecen abiertos contratos, credenciales, REPEP, enforcement de voz, digests OCI, licencias/SBOM final, pentest y capacidad efectiva del host.
