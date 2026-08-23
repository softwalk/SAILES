# Threat model resumido — STRIDE/LINDDUN

| Riesgo | Activo | Control implementado | Evidencia pendiente |
|---|---|---|---|
| Suplantación de servicio | APIs internas | HMAC por request, timestamp, nonce y replay protection | mTLS/API gateway real |
| Suplantación humana | Aprobaciones | Verificador OIDC RS256, scopes, roles y tenant | IdP/JWKS reales y segregación en UI |
| Manipulación de campaña | Contenido aprobado | JSON canónico, SHA-256 y re-aprobación material | Prueba UI completa |
| Replay de contacto | Canal | JIT firmado, TTL, audiencia, claims y consumo SQL atómico | Prueba PostgreSQL/VICIdial real |
| Repudio | Auditoría | Cadena por tenant, secuencia y verificación de exportación | WORM/KMS/attestation |
| Exposición de PII | Logs/modelos | Redacción estructurada, tokenización, routing restringido y OpenRouter fuera de `RESTRICTED` por defecto | DLP, DPIA y KMS reales |
| Robo de clave de modelo | OpenRouter/Kimi/DeepSeek | Secretos montados como archivo, sin valores en `.env`/Git/logs y endpoint OpenRouter HTTPS allowlisted | Vault/KMS y rotación automática |
| SSRF/redirección | Proveedores | HTTPS y host allowlist; redirects bloqueados | Egress firewall |
| Elevación de privilegio | Multi-tenant | Tenant en JWT, `SET LOCAL`, RLS `FORCE` en esquema | Test con roles PostgreSQL reales |
| Prompt injection | Agentes | Fuentes no confiables, outputs limitados, modelos sin herramientas de canal | Suite adversarial con modelos reales |
| Contacto ilícito | Persona | REPEP o excepción B2B aprobada/opt-in/supresión/horarios/frecuencia fail-closed | Dictamen legal y evidencia real |
| Reidentificación | Analítica | Datos tenant-scoped y exportación controlada | Políticas de agregación/k-anonimato |
| Retención excesiva | CRM/audio | ARCO, legal hold modelado, clasificación y vigencia de memoria | Jobs de borrado y storage real |

## Resultado

El código controla las rutas lógicas críticas, pero no puede cerrar riesgos de infraestructura, identidad, proveedor o jurisdicción sin los ambientes y aprobaciones indicados en `release/BLOCKERS.yaml`.
