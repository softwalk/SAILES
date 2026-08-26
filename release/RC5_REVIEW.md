# Dictamen técnico RC 0.9.0-rc5

## Veredicto

El código fuente queda **SHADOW READY**. El piloto permanece **NO GO** hasta aplicar y probar los controles RC5 en VM 110, activar OIDC humano real, completar el soak de cuatro horas y cerrar las aprobaciones externas de `BLOCKERS.yaml`.

## Cambios desde 38b3199

- workflow/checkpoints/eventos durables y recuperables después de reiniciar el orquestador;
- replay JIT durable en PostgreSQL también en shadow;
- OIDC RS256 obligatorio para aprobación humana en piloto;
- presupuesto diario de modelos con reserva previa y conciliación durable;
- auditoría tenant-safe append-only en rutas críticas;
- migración 008 con RLS forzado;
- runners 006/007 condicionales para fingerprints legacy/canónicos sin reescribir historia;
- pruebas de RLS cruzado, reinicios, replay, integridad de auditoría y soak;
- versión, manuales, trazabilidad y bloqueos reconciliados.

## Validación local

- `compileall`: PASS;
- pruebas unitarias/invariantes: 101/101 PASS;
- shadow E2E, HTTP E2E y DR drill: PASS;
- carga concurrente: supera la meta de 100/s en la máquina de validación;
- compliance source: PASS;
- package validator: PASS con avisos esperados de componentes externos;
- compliance distribution: BLOCKED de forma esperada por seis artefactos externos.

No se afirma que el SQL 008 ni los reinicios se hayan ejecutado en VM 110 desde este entorno. La evidencia correspondiente sólo será válida cuando la produzcan `80_validate_pilot_controls.sh` y `90_shadow_soak.sh` en esa VM.
