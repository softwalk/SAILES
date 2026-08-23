# Evidencia de validación RC 0.9.0-rc4

Fecha: 2026-08-22  
Comando canónico: `bash ci/run_all.sh`

| Control | Resultado |
|---|---|
| Compilación Python | PASS |
| Pruebas unitarias/invariantes | PASS — 65/65 |
| Shadow E2E | PASS |
| HTTP E2E | PASS — idempotencia y replay bloqueado |
| Carga | PASS — 100 grafos y 100 webhooks; cifras no contractuales |
| DR drill | PASS — restore, cadena de auditoría y RPO simulado 0 |
| Compliance de fuente | PASS |
| OpenSpec/OpenAPI | PASS con advertencias de evidencia externa |
| SBOM de fuente propia | GENERADO — CycloneDX 1.6 |
| Gate de distribución | BLOCKED — esperado y obligatorio |

El gate de distribución continúa bloqueado hasta contar con inventario final, textos de licencias, SBOM de imágenes, fuentes correspondientes, digests/commits, contratos y attestation firmada. La validación local no sustituye las pruebas PostgreSQL/TLS/rollback en VM 110.
