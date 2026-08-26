# Manual de cierre técnico del piloto RC5

## Objetivo y resultado esperado

Este procedimiento actualiza VM 110 sin habilitar contactos reales y produce evidencia verificable de persistencia, aislamiento por tenant, identidad humana, presupuesto de modelos, auditoría y anti-replay. Un `PASS` técnico no reemplaza las aprobaciones legal, privacidad, seguridad y operación.

Flujo obligatorio:

1. preparar IdP, secretos y snapshot;
2. ejecutar rollout RC5 en shadow;
3. validar controles con reinicios reales;
4. ejecutar soak shadow de cuatro horas;
5. correr el gate técnico;
6. cerrar bloqueos externos y sólo entonces evaluar un piloto limitado.

## 1. Preparación sin cambios de servicio

En Proxmox, crear un snapshot nominativo de VM 110. En la VM:

```bash
cd /opt/atlantis/repositories/atlantis-sales-platform
git fetch origin
git status --short
git pull --ff-only origin main
git rev-parse HEAD
```

El árbol debe estar limpio. Copiar `deploy/proxmox/operations/rollout.env.example` a `/opt/atlantis/infrastructure/rc5-rollout.env`, completar valores y aplicar `root:root`, modo `0600`.

## 2. OIDC humano real

Registrar dos permisos en el IdP:

- `campaign:approve`, rol `CAMPAIGN_APPROVER`;
- `human-action:decide`, rol `HUMAN_REVIEWER`.

Los tokens deben usar RS256, incluir `iss`, `aud`, `sub` UUID, `tenant_id`, `scope`, `roles`, `iat`, `nbf`, `exp` y un `kid` aprobado. Crear sólo el mapa de claves públicas:

```bash
sudo install -d -o root -g root -m 0755 /opt/atlantis/infrastructure/oidc
sudo install -o root -g root -m 0644 public_keys.json \
  /opt/atlantis/infrastructure/oidc/public_keys.json
```

Formato:

```json
{"kid-produccion-1":"-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n"}
```

Configurar en `/opt/atlantis/infrastructure/.env`:

```dotenv
ATLANTIS_REQUIRE_HUMAN_OIDC=true
ATLANTIS_OIDC_ISSUER=https://idp.example/realms/atlantis
ATLANTIS_OIDC_AUDIENCE=atlantis-human-api
ATLANTIS_OIDC_PUBLIC_KEYS_FILE=/etc/atlantis/oidc/public_keys.json
ATLANTIS_OIDC_CAMPAIGN_APPROVER_ROLE=CAMPAIGN_APPROVER
ATLANTIS_OIDC_HUMAN_REVIEWER_ROLE=HUMAN_REVIEWER
ATLANTIS_MODEL_DAILY_BUDGET_UNITS=100000
ATLANTIS_REQUIRE_COMPLETED_SOAK=true
ATLANTIS_SHADOW_MODE=true
```

Nunca copiar claves privadas ni tokens OIDC al repositorio o a la evidencia.

Inmediatamente antes de la prueba de controles, obtener dos access tokens de vida
corta para el tenant de la campaña y guardarlos fuera del repositorio:

```bash
sudo install -d -o root -g root -m 0700 /run/atlantis
sudo install -o root -g root -m 0400 campaign_approver.token /run/atlantis/campaign_approver.token
sudo install -o root -g root -m 0400 human_reviewer.token /run/atlantis/human_reviewer.token
```

El probe valida criptográficamente ambos tokens, pero no los copia a la evidencia.
El operador debe eliminarlos de `/run/atlantis` al finalizar la ventana.

## 3. Rollout RC5

```bash
cd /opt/atlantis/repositories/atlantis-sales-platform
sudo deploy/proxmox/operations/run_rc5_rollout.sh \
  /opt/atlantis/infrastructure/rc5-rollout.env --execute
```

La operación crea y verifica backup, conserva migraciones históricas, valida condicionalmente 006/007, aplica 008, construye imágenes, despliega shadow y recoge evidencia. Si falla, detenerse; no alterar checksums registrados ni editar migraciones 001–007.

## 4. Prueba de controles con reinicios

Requiere al menos un contacto, una campaña aprobada y una decisión `ALLOW` de voz reciente. El token JIT de prueba se genera localmente, no se imprime, se consume en shadow y después se redacta.

```bash
sudo deploy/proxmox/operations/80_validate_pilot_controls.sh --execute
```

Debe demostrar:

- un tenant alterno no puede leer el contacto;
- `atlantis_runtime` no puede actualizar auditoría directamente;
- el orquestador continúa el mismo run después de reiniciar;
- el adaptador rechaza el mismo JIT después de reiniciar;
- secuencia, enlaces y hashes de auditoría son válidos;
- CRM y orquestador reportan `human_identity=oidc`.
- dos tokens humanos efímeros pasan firma, issuer, audience, vigencia, scope, rol y tenant.

## 5. Soak shadow

```bash
sudo deploy/proxmox/operations/90_shadow_soak.sh --execute 240
```

La prueba toma salud cada 30 segundos y realiza como máximo 16 solicitudes sintéticas al gateway. No crea llamadas ni mensajes. El límite diario durable se reserva antes de cada llamada al modelo.

## 6. Gate final técnico

```bash
sudo deploy/proxmox/operations/00_preflight_pilot_gate.sh
```

Sólo aceptar `TECHNICAL PILOT GATE: PASS`. Verificar que la evidencia esté bajo `/opt/atlantis/documentation/evidence/rc5`, con `SHA256SUMS`, commit exacto y ocho digests OCI.

## 7. Criterios que siguen fuera del código

No activar `ATLANTIS_SHADOW_MODE=false` hasta cerrar por escrito:

- dictamen REPEP/B2B y reglas por campaña;
- DPIA, transferencias y términos de modelos;
- Meta/WABA, VICIdial/Neobot y Marketia;
- pentest y revisión de red/credenciales bootstrap;
- SBOM de distribución, avisos, licencias, fuentes correspondientes y attestation.

## Recuperación

Un fallo de aplicación puede volver a las imágenes anteriores con `60_rollback.sh`. La base de datos no se restaura automáticamente: requiere ventana, aprobador y el dump verificado. No borrar ni modificar filas de `schema_migration`.
