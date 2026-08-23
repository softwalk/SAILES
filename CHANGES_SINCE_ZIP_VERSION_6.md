# Cambios desde el ZIP versión 6

Fecha: 2026-08-22  
Software: Atlantis `0.9.0-rc4`  
Entrega: ZIP versión 7  
SHA-256 del ZIP versión 6: `f31688125ee075adb9baec7715806123dcc6df3451c0a1a94802318c02b1283b`

## Reconciliación segura de migración 004

- Añadida `database/005_reconcile_migration_004_checksum.sql`.
- La fila histórica 004 con checksum `9c1850...` nunca se sobrescribe.
- Fingerprint corregido: incluye los seis atributos del rol, cuatro grants, cinco policies completas y función de purga.
- Fingerprint canónico esperado: `53e77f497b6ee0e30963dd08a734dd7b2d1a997c52c742ee42bb4c6228818b6d`.
- La migración recalcula el fingerprint directamente desde PostgreSQL y falla ante diferencias.
- Aprobador, fecha, referencia y SHA-256 de evidencia son obligatorios.
- El registro de reconciliación es append-only mediante trigger.
- Un checksum 005 diferente provoca error; `ON CONFLICT` no puede ocultarlo.
- Runtime y PUBLIC no reciben acceso a la tabla de reconciliación.

## Rollout

- Añadido `21_apply_migration_005.sh` con backup obligatorio y aprobación explícita.
- `20_apply_migration_004.sh` reconoce únicamente el checksum canónico o el legacy conocido.
- Si 004 es canónica, 005 se omite; si es legacy, 005 es obligatoria.
- Rollouts posteriores verifican aprobación, evidencia y fingerprint sin pedir nuevamente datos humanos.

## Gate técnico de piloto

Se añadió `00_preflight_pilot_gate.sh`, que bloquea ante:

- ambiente distinto de `production`;
- PostgreSQL diferente de `verify-full` o sesión real sin TLS;
- CA ausente, inválida o próxima a vencer;
- workload auth, estado durable o CRM PostgreSQL desactivados;
- shadow mode desactivado antes de aprobación;
- menos de 7 GiB totales o 2 GiB disponibles;
- reconciliación sin aprobación, evidencia o fingerprint vigente;
- árbol sin commit Git o con cambios locales;
- menos de ocho digests de imagen o contenido diferente;
- ningún proveedor de modelo configurado;
- alguno de los siete servicios sin healthcheck.

Un PASS es sólo técnico y no reemplaza aprobaciones legal, privacidad, seguridad o proveedor.

## Validación

- Suite ampliada a 65 pruebas.
- Scripts mutantes continúan exigiendo `--execute`.
- La migración 005 se entrega sin aplicar: requiere aprobador humano nominativo.
- El piloto continúa bloqueado por RAM efectiva, TLS, modelos, Git/digests y controles externos.
