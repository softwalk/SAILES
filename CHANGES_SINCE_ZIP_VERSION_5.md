# Cambios desde el ZIP versión 5

Fecha: 2026-08-22  
Base: Atlantis RC4, ZIP estable versión 5  
SHA-256 anterior: `902d2148e73a721407e3b1f7480a0483b24c31e0976c7236dcfe586d50ae435e`

## Kit operativo agregado

Se añadió `deploy/proxmox/operations/` con los siguientes componentes:

| Archivo | Función |
|---|---|
| `00_preflight.sh` | Valida VM/IP, RAM efectiva, disco, Docker, redes, puertos, Compose y controles shadow |
| `01_prepare_secret_permissions.sh` | Limita los secretos requeridos a uid 10001 y modo 0400 |
| `01_validate_secrets.sh` | Verifica existencia, permisos, longitud, JSON y cadena/expiración PKI |
| `10_backup.sh` | Genera dump PostgreSQL, esquema, inventarios y checksums |
| `20_apply_migration_004.sh` | Aplica migración 004 sólo tras backup; controla checksum y postcondiciones |
| `30_build_images.sh` | Construye base y siete imágenes; registra IDs SHA-256 |
| `40_deploy_shadow.sh` | Etiqueta imágenes anteriores y despliega exclusivamente en shadow |
| `50_postdeploy_validate.sh` | Ejecuta healthchecks, RLS, 62 pruebas, shadow E2E, DR y recursos |
| `60_rollback.sh` | Restaura las imágenes anteriores sin retirar la corrección RLS |
| `70_collect_evidence.sh` | Consolida evidencias, políticas, SBOM, bloqueos y checksums |
| `run_rc4_rollout.sh` | Ejecuta la secuencia completa con guardas y parada segura |

## Ajustes adicionales

- Compose fija nombres de imagen RC4 para los siete servicios.
- Se eliminó `group_add:[1000]`; ya no hay grupo compartido para secretos.
- Los archivos de secreto quedan `0400`, propiedad del uid no-root 10001, y sólo se montan en los servicios que los necesitan.
- Inventario VM 110 actualizado a 8192 MiB configurados con mínimo efectivo de 7168 MiB.
- El validador anterior ahora delega al preflight RC4.
- Se añadió `ATLANTIS_RELEASE_TAG=0.9.0-rc4` al ejemplo Proxmox.
- Se añadieron cuatro pruebas del kit operativo; total 62/62 PASS.
- Se actualizaron README, Makefile, changelog, bloqueos y documentación de despliegue.

## Límites deliberados

- El snapshot Proxmox debe hacerse desde el hipervisor y no se automatiza desde la VM invitada.
- La restauración PostgreSQL es manual y exige ventana de mantenimiento y aprobación humana.
- La migración 004 no se revierte automáticamente porque corrige el acceso a supresiones GLOBAL.
- El rollout no habilita contacto real ni cierra contratos, pentest o paquete legal de distribución.
- El paquete fue validado localmente; su ejecución real en VM 110 todavía debe producir las evidencias operativas.
