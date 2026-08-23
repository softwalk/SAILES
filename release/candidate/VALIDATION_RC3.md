# Evidencia de validación RC 0.9.0-rc3

Fecha: 2026-08-22  
Comando: `bash ci/run_all.sh`

| Control | Resultado |
|---|---|
| Compilación Python | PASS |
| Pruebas unitarias/invariantes | PASS — 45/45 |
| Shadow E2E | PASS |
| HTTP E2E | PASS — idempotencia y replay bloqueado |
| Carga | PASS — 100 grafos y 100 webhooks |
| Rendimiento observado | 2447.7 grafos/s; 9872.2 webhooks/s |
| DR drill | PASS — restore, cadena de auditoría y RPO 0 |
| Compliance de fuente | PASS |
| OpenSpec/OpenAPI | PASS — 13 capacidades, 12 operaciones, 2 advertencias de entorno |
| SBOM de fuente propia | GENERADO — CycloneDX 1.6 |
| Gate de distribución | BLOCKED — esperado y obligatorio |

Las tasas son una medición local de prueba, no una garantía de capacidad de VM 110. El gate de distribución falla porque faltan SBOM final, avisos definitivos, textos de licencias, fuentes correspondientes, lock final y attestation firmada.
