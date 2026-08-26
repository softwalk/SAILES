# Configuración segura de OpenRouter

OpenRouter se integra exclusivamente mediante `model_gateway`; ningún agente o
adaptador de canal recibe su clave. El código no contiene credenciales.

## 1. Rotar y guardar el secreto

Si una clave se compartió por chat, correo, ticket o captura, revocarla en
OpenRouter y generar una nueva. En VM 110, introducirla sin imprimirla:

```bash
sudo install -o 10001 -g root -m 0400 /dev/null /opt/atlantis/secrets/openrouter_api_key.txt
sudo bash -c 'umask 077; read -rsp "OpenRouter key: " OPENROUTER_KEY </dev/tty; printf "%s" "$OPENROUTER_KEY" > /opt/atlantis/secrets/openrouter_api_key.txt; unset OPENROUTER_KEY; printf "\n" >/dev/tty'
sudo chown 10001:root /opt/atlantis/secrets/openrouter_api_key.txt
sudo chmod 0400 /opt/atlantis/secrets/openrouter_api_key.txt
```

La entrada permanece oculta. No usar `echo CLAVE`, historial de shell,
argumentos de procesos ni variables en Compose.

## 2. Configurar el proveedor

En `/opt/atlantis/infrastructure/.env`:

```dotenv
ATLANTIS_MODEL_PROVIDER_ORDER=openrouter,kimi,deepseek
ATLANTIS_MODEL_MAX_COST_UNITS_PER_REQUEST=4000
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL_ID=PROVEEDOR/MODELO-EXACTO-APROBADO
OPENROUTER_API_KEY_FILE=/run/secrets/openrouter_api_key
OPENROUTER_HTTP_REFERER=https://DOMINIO-CORPORATIVO
OPENROUTER_APP_TITLE=Atlantis Autonomous Sales
RESTRICTED_PROVIDER_ALLOWLIST=
KIMI_BASE_URL=http://atlantis-platform-model_gateway-1:4000/v1
DEEPSEEK_BASE_URL=http://atlantis-platform-model_gateway-1:4000/v1
```

`UNSET` deshabilita OpenRouter. No usar `openrouter/auto` en producción porque
es un alias mutable. `RESTRICTED_PROVIDER_ALLOWLIST` debe permanecer vacío hasta
que Legal/Privacidad apruebe proveedor, modelo y transferencia de datos.

## 3. Validar y desplegar en shadow

```bash
cd /opt/atlantis/repositories/atlantis-sales-platform
sudo deploy/proxmox/operations/01_prepare_secret_permissions.sh --execute
sudo deploy/proxmox/operations/01_validate_secrets.sh
sudo docker compose --env-file /opt/atlantis/infrastructure/.env \
  -f deploy/proxmox/compose.application.yaml up -d --build model_gateway
curl --fail --silent http://127.0.0.1:8084/health
```

La salud debe incluir `openrouter` en `configured_providers`. Probar sólo con
datos sintéticos en `SHADOW`; una respuesta satisfactoria no autoriza campañas
ni datos personales reales.

Validar también DNS/TCP desde el contenedor. El endpoint `/health` informa
configuración, no garantiza por sí solo conectividad con los proveedores:

```bash
sudo deploy/proxmox/operations/02_validate_model_provider_connectivity.sh
```

El techo `ATLANTIS_MODEL_MAX_COST_UNITS_PER_REQUEST` lo fija el servidor. El
gateway rechaza antes de llamar al proveedor cuando el prompt no cabe en el
presupuesto y transmite al proveedor únicamente el remanente como
`max_completion_tokens`. Los proveedores detrás de LiteLLM reciben
`max_tokens` por compatibilidad con sus adaptadores actuales.

## 4. Revocación y rollback

Para deshabilitar de inmediato, retirar `openrouter` de
`ATLANTIS_MODEL_PROVIDER_ORDER`, recrear `model_gateway` y revocar la clave en
OpenRouter. La ausencia de clave o modelo produce `OPENROUTER_NOT_CONFIGURED` y
el gateway usa el siguiente proveedor permitido o falla de forma segura.
