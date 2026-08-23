# Despliegue sobre la infraestructura Atlantis instalada

## Destino validado

Este RC se alinea exclusivamente con VM 110 `atlantis-core` (`192.168.100.160`): 4 vCPU, 4 GiB RAM, 60 GiB NVMe, Docker Engine y raíz `/opt/atlantis`. El hipervisor (`192.168.100.154`), VM 100, VM 102 y los invitados 101/103/210 quedan fuera del alcance de cualquier script de este paquete. Hermes en VM 102 (`192.168.100.155`) es un ejecutor subordinado y no un nodo de despliegue de Atlantis.

La fuente autoritativa y legible por máquina es `deploy/proxmox/inventory.yaml`. No se debe usar `deploy/compose.lab.yaml` en VM 110; ese archivo sigue siendo sólo para pruebas aisladas.

## Preflight obligatorio (sin mutaciones)

1. Copiar o actualizar el repositorio en `/opt/atlantis/repositories/atlantis-sales-platform`.
2. Comparar `deploy/proxmox/.env.proxmox.example` con `/opt/atlantis/infrastructure/.env`; nunca copiar valores secretos al repositorio.
3. Rotar la clave maestra de LiteLLM y la contraseña inicial de Grafana mencionadas en el informe. Guardar cada valor en un archivo `0400` o `0600` bajo `/opt/atlantis/secrets/`.
4. Crear secretos separados para PostgreSQL runtime, JIT, Evidence API, AMQP y cada proveedor. No reutilizar una clave maestra entre servicios.
5. Ejecutar:

```bash
cd /opt/atlantis/repositories/atlantis-sales-platform
bash deploy/proxmox/validate_infrastructure.sh
bash ci/run_all.sh
```

El validador no cambia el host. Falla si detecta una VM/IP equivocada, rutas o redes faltantes, permisos débiles, bindings de datos no locales o credenciales bootstrap conocidas.

## Ajustes de red

- Servicios de datos y control sensibles: sólo loopback o redes Docker internas.
- Ingress permitido: Caddy en 80/443.
- Node-RED 1880, Grafana 3001, Prometheus 9090 y RabbitMQ Management 15672: limitar a VPN o CIDR administrativo. No publicarlos en Internet.
- Los adaptadores de canal usan la red `atlantis-application_channels` para salida; no se concede salida a PostgreSQL.
- Verificar los nombres DNS reales de los contenedores `postgres` y `litellm` en las redes externas antes del arranque. Si difieren, ajustar sólo las variables de entorno no secretas.

## Despliegue application-only

`deploy/proxmox/compose.application.yaml` no recrea PostgreSQL, RabbitMQ, Valkey, LiteLLM, Node-RED, Caddy ni observabilidad. Se conecta a las redes ya instaladas y construye únicamente los servicios funcionales de esta entrega.

Debido a que Policy Gateway y CRM API ya ocupan 8081/8082, el cambio debe ser controlado:

1. Tomar snapshot de VM 110 y dump cifrado de PostgreSQL.
2. Registrar `docker compose ls`, `docker ps`, digests y estado de salud.
3. Detener sólo los contenedores propietarios anteriores de Policy Gateway/CRM; no ejecutar `docker compose down` contra la plataforma base.
4. Validar configuración:

```bash
docker compose --env-file /opt/atlantis/infrastructure/.env \
  -f deploy/proxmox/compose.application.yaml config --quiet
```

5. Construir y registrar los digests resultantes. El piloto sigue bloqueado hasta que esos digests y su attestación aparezcan en el inventario de release.
6. Arrancar en shadow mode:

```bash
docker compose --env-file /opt/atlantis/infrastructure/.env \
  -f deploy/proxmox/compose.application.yaml up -d --build
```

7. Probar `127.0.0.1:8081` a `:8087`, confirmar que ningún adaptador realizó efectos externos y después aplicar el fragmento Caddy de forma transaccional (`caddy validate` antes de recargar).

## Límite de 4 GiB

El overlay asigna un máximo aproximado de 1.47 GiB a los siete servicios nuevos. No descargar ni ejecutar modelos locales en VM 110. Las inferencias locales y la investigación profunda deben ejecutarse en VM 102 y sólo mediante un contrato autenticado. Si el consumo total sostenido supera 80% de RAM o hay swap/thrashing, detener el despliegue y ampliar VM 110 a 8 GiB antes del piloto.

## PostgreSQL y dependencias runtime

RC4 acepta el password mediante `ATLANTIS_DATABASE_PASSWORD_FILE`, construye el DSN en memoria y exige `ATLANTIS_DATABASE_SSLMODE=verify-full` con `ATLANTIS_DATABASE_SSLROOTCERT` en producción. El overlay usa `ATLANTIS_CRM_STORAGE=postgres` por defecto. La imagen propietaria instala psycopg desde `requirements-runtime.lock` con hashes. Las migraciones se aplican en orden `001_schema.sql`, `002_hardening.sql`, `003_runtime_controls.sql`, `004_security_and_durability.sql` y, exclusivamente para instalaciones con el checksum legacy conocido, `005_reconcile_migration_004_checksum.sql`. La 005 conserva la historia, exige aprobación humana y verifica los objetos efectivos. Los servicios usan `atlantis_runtime` sin `BYPASSRLS`. La administración de supresión GLOBAL requiere un flujo separado que asuma `atlantis_suppression_admin`; nunca debe exponerse en la API normal del tenant.

## Promoción y rollback

La secuencia obligatoria es: source gate → preflight → snapshot/dump → shadow → pruebas contractuales → allowlist interna → piloto pequeño → revisión legal/seguridad → autonomía gradual. Para rollback, retirar el fragmento Caddy, detener sólo `atlantis-application`, restaurar los contenedores propietarios anteriores y verificar DB/RabbitMQ. No exportar VM, ISO, snapshot ni appliance a un cliente mientras el gate de distribución esté bloqueado.
