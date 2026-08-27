# Kit de despliegue RC5 — VM 110

Este directorio automatiza un despliegue controlado de RC5 en `atlantis-core` (`192.168.100.160`). No activa contacto real, no modifica VM 102 y no supera el gate legal de distribución.

## Controles de seguridad

- Los scripts mutantes exigen `--execute`.
- El rollout se detiene si `ATLANTIS_SHADOW_MODE` no es `true`.
- Preflight exige al menos 7 GiB de RAM efectiva y 10 GiB libres.
- Se exige backup PostgreSQL válido antes de migrar o desplegar.
- Migración 004 se verifica por SHA-256; un checksum legacy sólo se acepta mediante migración 005 aprobada y fingerprint vigente.
- La ruta legacy verifica 006 y 007 sin reescribir su historia; 008 añade controles durables y RLS.
- Los endpoints humanos requieren OIDC RS256 para superar el gate de piloto.
- El probe reinicia orquestador y voz para demostrar persistencia y anti-replay.
- El rollback cambia sólo imágenes de aplicación. No revierte la migración 004 porque es aditiva y corrige un fallo de seguridad.
- Los secretos nunca se imprimen en los reportes.

## Preparación

1. Crear snapshot de VM 110 desde Proxmox. Este paso no puede ejecutarse desde la VM invitada.
2. Copiar el repositorio a `/opt/atlantis/repositories/atlantis-sales-platform`.
3. Copiar `rollout.env.example` a `/opt/atlantis/infrastructure/rc5-rollout.env`.
   El archivo debe ser propiedad de `root` y tener modo `0600` o `0400`.
4. Completar `/opt/atlantis/infrastructure/.env`, manteniendo:

   - `ATLANTIS_SHADOW_MODE=true`
   - `ATLANTIS_REQUIRE_WORKLOAD_AUTH=true`
   - `ATLANTIS_REQUIRE_DURABLE_STATE=true`
   - `ATLANTIS_CRM_STORAGE=postgres`
   - `ATLANTIS_DATABASE_SSLMODE=verify-full`
   - `ATLANTIS_REQUIRE_HUMAN_OIDC=true` una vez configurado el IdP
   - `ATLANTIS_REQUIRE_COMPLETED_SOAK=true`

5. Crear todos los archivos listados por `01_validate_secrets.sh`. El rollout los deja `0400`, propiedad del uid 10001, y cada contenedor sólo monta los secretos que necesita; se eliminó el acceso grupal compartido. Los certificados deben provenir de la CA interna autorizada. No generar certificados autofirmados improvisados para piloto.
   Para OpenRouter, guardar la clave rotada exclusivamente en
   `/opt/atlantis/secrets/openrouter_api_key.txt`; nunca colocarla en `.env`,
   Compose, Git, prompts o reportes. Configurar un `OPENROUTER_MODEL_ID` exacto
   y aprobado; `UNSET` mantiene el proveedor deshabilitado de forma segura.
6. Confirmar que `PYTHON_BASE_IMAGE` contiene un digest `@sha256:...`.
7. Si la VM conserva checksums legacy, completar en `rc5-rollout.env` el aprobador, fecha y archivo de evidencia para las migraciones de reconciliación. Nunca usar un nombre genérico o automatizado como aprobador.
8. Instalar el mapa de claves públicas OIDC en `/opt/atlantis/infrastructure/oidc/public_keys.json`; no se guardan claves privadas en Atlantis.

## Ejecución

Primero ejecutar sólo validaciones:

```bash
cd /opt/atlantis/repositories/atlantis-sales-platform
set -a
source /opt/atlantis/infrastructure/rc5-rollout.env
set +a
deploy/proxmox/operations/00_preflight.sh
sudo deploy/proxmox/operations/01_prepare_secret_permissions.sh --execute
sudo deploy/proxmox/operations/01_validate_secrets.sh
```

Después de revisar los resultados:

```bash
sudo deploy/proxmox/operations/run_rc5_rollout.sh \
  /opt/atlantis/infrastructure/rc5-rollout.env --execute
```

La secuencia es: preflight → secretos → dump → migraciones/reconciliaciones 004–008 → build → despliegue shadow → pruebas → evidencias.

### Acelerador OIDC exclusivamente técnico en shadow

Cuando todavía no esté disponible el IdP corporativo, RC5 puede levantar un
Keycloak 26.7.2 temporal, sólo en `127.0.0.1:8180`, para probar criptográficamente
issuer, audience, firma RS256, tenant, scopes y roles. El instalador exige el
digest OCI fijado y además resuelve la imagen a su ID local inmutable; conserva el realm en un volumen dedicado, elimina el
secreto bootstrap del contenedor permanente y borra los access tokens al terminar.

```bash
sudo deploy/proxmox/operations/03_setup_shadow_oidc_keycloak.sh --execute
```

Este comando reinicia únicamente CRM y orquestador, ejecuta automáticamente
`80_validate_pilot_controls.sh` y mantiene `ATLANTIS_SHADOW_MODE=true`. Usa
`start-dev` y password grant sólo para la validación técnica: **no satisface MFA,
TLS/HA ni la aprobación del IdP de producción y no autoriza contacto real**.

Después del rollout y con OIDC corporativo activo, o después de la validación
técnica anterior:

```bash
sudo deploy/proxmox/operations/80_validate_pilot_controls.sh --execute
sudo deploy/proxmox/operations/90_shadow_soak.sh --execute 240
sudo deploy/proxmox/operations/00_preflight_pilot_gate.sh
```

El primer comando verifica RLS cruzado, auditoría append-only, recuperación del workflow y replay JIT después de reiniciar contenedores. El segundo mantiene cuatro horas de shadow, sin contacto externo y con máximo 16 llamadas sintéticas de 300 unidades.

Después de resolver RAM, TLS, Git, imágenes y modelos, ejecutar el gate técnico:

```bash
sudo deploy/proxmox/operations/00_preflight_pilot_gate.sh
```

Un resultado PASS no habilita campañas: aún se requieren aprobaciones legal, privacidad, seguridad y operación.

## Rollback

Si falla la aplicación después del despliegue:

```bash
sudo deploy/proxmox/operations/60_rollback.sh --execute \
  /opt/atlantis/backups/rc5/<timestamp>
```

El rollback de base de datos no es automático. Para restaurar `atlantis.dump` se requiere ventana de mantenimiento, aprobación humana y procedimiento de recuperación probado. La migración 004 debe conservarse salvo dictamen de seguridad contrario.

## Evidencias producidas

- Dump PostgreSQL y checksum.
- Compose resuelto antes del cambio.
- Inventario de contenedores e imágenes anteriores.
- Digests locales de la base y seis servicios RC5-B2B. WhatsApp permanece fuera del perfil predeterminado.
- Healthchecks, 101 pruebas, shadow E2E y DR drill.
- Evidencia de reinicio, RLS, anti-replay, cadena de auditoría y soak.
- Estado RLS y políticas PostgreSQL.
- Uso de recursos por contenedor.
- Copia de bloqueos y SBOM de fuente.

Estas evidencias no sustituyen SAST/SCA/DAST, pentest, SBOM de imágenes, textos legales, fuentes correspondientes ni attestation firmada.
