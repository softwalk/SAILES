# Kit de despliegue RC4 — VM 110

Este directorio automatiza un despliegue controlado de RC4 en `atlantis-core` (`192.168.100.160`). No activa contacto real, no modifica VM 102 y no supera el gate legal de distribución.

## Controles de seguridad

- Los scripts mutantes exigen `--execute`.
- El rollout se detiene si `ATLANTIS_SHADOW_MODE` no es `true`.
- Preflight exige al menos 7 GiB de RAM efectiva y 10 GiB libres.
- Se exige backup PostgreSQL válido antes de migrar o desplegar.
- Migración 004 se verifica por SHA-256; un checksum legacy sólo se acepta mediante migración 005 aprobada y fingerprint vigente.
- El rollback cambia sólo imágenes de aplicación. No revierte la migración 004 porque es aditiva y corrige un fallo de seguridad.
- Los secretos nunca se imprimen en los reportes.

## Preparación

1. Crear snapshot de VM 110 desde Proxmox. Este paso no puede ejecutarse desde la VM invitada.
2. Copiar el repositorio a `/opt/atlantis/repositories/atlantis-sales-platform`.
3. Copiar `rollout.env.example` a `/opt/atlantis/infrastructure/rc4-rollout.env`.
   El archivo debe ser propiedad de `root` y tener modo `0600` o `0400`.
4. Completar `/opt/atlantis/infrastructure/.env`, manteniendo:

   - `ATLANTIS_SHADOW_MODE=true`
   - `ATLANTIS_REQUIRE_WORKLOAD_AUTH=true`
   - `ATLANTIS_REQUIRE_DURABLE_STATE=true`
   - `ATLANTIS_CRM_STORAGE=postgres`
   - `ATLANTIS_DATABASE_SSLMODE=verify-full`

5. Crear todos los archivos listados por `01_validate_secrets.sh`. El rollout los deja `0400`, propiedad del uid 10001, y cada contenedor sólo monta los secretos que necesita; se eliminó el acceso grupal compartido. Los certificados deben provenir de la CA interna autorizada. No generar certificados autofirmados improvisados para piloto.
6. Confirmar que `PYTHON_BASE_IMAGE` contiene un digest `@sha256:...`.
7. Si la VM conserva el checksum legacy de 004, completar en `rc4-rollout.env` el aprobador, fecha y archivo de evidencia para la migración 005. Nunca usar un nombre genérico o automatizado como aprobador.

## Ejecución

Primero ejecutar sólo validaciones:

```bash
cd /opt/atlantis/repositories/atlantis-sales-platform
set -a
source /opt/atlantis/infrastructure/rc4-rollout.env
set +a
deploy/proxmox/operations/00_preflight.sh
sudo deploy/proxmox/operations/01_prepare_secret_permissions.sh --execute
sudo deploy/proxmox/operations/01_validate_secrets.sh
```

Después de revisar los resultados:

```bash
sudo deploy/proxmox/operations/run_rc4_rollout.sh \
  /opt/atlantis/infrastructure/rc4-rollout.env --execute
```

La secuencia es: preflight → secretos → dump → migración 004 → reconciliación 005 cuando aplique → build → despliegue shadow → pruebas → evidencias.

Después de resolver RAM, TLS, Git, imágenes y modelos, ejecutar el gate técnico:

```bash
sudo deploy/proxmox/operations/00_preflight_pilot_gate.sh
```

Un resultado PASS no habilita campañas: aún se requieren aprobaciones legal, privacidad, seguridad y operación.

## Rollback

Si falla la aplicación después del despliegue:

```bash
sudo deploy/proxmox/operations/60_rollback.sh --execute \
  /opt/atlantis/backups/rc4/<timestamp>
```

El rollback de base de datos no es automático. Para restaurar `atlantis.dump` se requiere ventana de mantenimiento, aprobación humana y procedimiento de recuperación probado. La migración 004 debe conservarse salvo dictamen de seguridad contrario.

## Evidencias producidas

- Dump PostgreSQL y checksum.
- Compose resuelto antes del cambio.
- Inventario de contenedores e imágenes anteriores.
- Digests locales de la base y siete servicios RC4.
- Healthchecks, 65 pruebas, shadow E2E y DR drill.
- Estado RLS y políticas PostgreSQL.
- Uso de recursos por contenedor.
- Copia de bloqueos y SBOM de fuente.

Estas evidencias no sustituyen SAST/SCA/DAST, pentest, SBOM de imágenes, textos legales, fuentes correspondientes ni attestation firmada.
