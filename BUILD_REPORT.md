# Informe de construcción — Release Candidate 0.9.0-rc4

Fecha de corte: 2026-08-22  
Contrato: Atlantis OpenSpec v1.2  
Modo permitido: desarrollo y shadow mode

## Resultado reproducido localmente

- 65/65 pruebas unitarias y de invariantes: PASS.
- Shadow E2E y HTTP E2E: PASS; idempotencia, conflicto y replay bloqueados.
- Load test: 100 grafos y 100 webhooks por encima de la meta de 100/s.
- DR drill: checkpoint restore, cadena de auditoría y RPO simulado 0: PASS.
- Source compliance gate: PASS.
- OpenSpec/OpenAPI: PASS; las advertencias restantes corresponden a evidencias externas.
- SBOM CycloneDX de fuente: generado; no sustituye el SBOM final de imágenes.
- Gate de distribución: BLOCKED de forma intencional.

## Mejoras RC4

- RLS de supresión GLOBAL corregido y administración global separada.
- Idempotencia y nonces durables en PostgreSQL; memoria de desarrollo acotada por TTL.
- Contexto de decisión tenant-bound, fresco, one-shot y ligado a audiencia/canal.
- Autenticación workload obligatoria por defecto en producción; rate limiting no suplantable por headers.
- HTTP endurecido y clientes internos con CA/mTLS configurable.
- PostgreSQL `verify-full` obligatorio en producción.
- CRM PostgreSQL predeterminado en Proxmox y evidencia CRM conectada en shadow.
- Lock transitivo con hashes y build con `--require-hashes`.

## Límites del resultado

RC4 no fue desplegado remotamente desde este entorno. La integración contra PostgreSQL/TLS, redes y proveedores reales debe repetirse en VM 110. La excepción HTTP allowlisted hacia CRM existe sólo para shadow; antes de piloto debe reemplazarse con HTTPS/mTLS. Los bloqueos externos, de capacidad, credenciales, contratos y supply chain permanecen en `release/BLOCKERS.yaml`.

No se construyó ni entregó appliance, VM, ISO, snapshot o imagen de cliente.
