# Dictamen de alineación con la infraestructura instalada

## Resultado

El código RC2 es desplegable como actualización application-only sobre VM 110, pero no debe promoverse a piloto ni distribuirse como appliance todavía. La infraestructura base está lista; las credenciales externas, dependencias runtime, contrato Hermes, endpoints de canales y evidencias de release siguen siendo gates explícitos.

## Mapeo implementado

| Infraestructura instalada | Ajuste en RC2 |
|---|---|
| VM 110, 4 vCPU/4 GiB/60 GiB | Límites de CPU/RAM/PID/log por servicio; no se ejecutan modelos locales |
| `/opt/atlantis/*` | Rutas absolutas y secretos externos en el overlay Proxmox |
| Redes control/data existentes | Redes externas con nombres exactos del informe |
| PostgreSQL en red de datos | DSN construido en memoria desde archivo secreto; usuario runtime separado |
| LiteLLM en `:4000` | Kimi/DeepSeek se enrutan internamente a LiteLLM con key en archivo secreto |
| RabbitMQ y Valkey instalados | Se conservan como dependencias externas; el broker no se recrea |
| Caddy, Node-RED y observabilidad | Se conservan; sólo se aporta fragmento de rutas funcionales, sin UIs administrativas |
| Hermes VM 102 | Inventariado como ejecutor subordinado no modificable desde esta entrega |
| OpenOutreach GPLv3 | Ejecutable externo en `/opt/atlantis/opensource/...`, validado por SHA-256 |
| Servicios propietarios | Permanecen en imágenes/procesos separados de OpenOutreach y Node-RED |

## Correcciones de seguridad prioritarias

1. Rotar las credenciales bootstrap que el informe documenta literalmente.
2. Sustituir el usuario general `atlantis` por roles separados para migración, runtime y auditoría.
3. Restringir 1880/3001/9090/15672 a una red administrativa; el hecho de estar en LAN no equivale a autorización.
4. No habilitar HTTPS público hasta definir dominio, certificado, WAF/rate limits y autenticación de operador.
5. No activar llamadas/WhatsApp por la mera presencia de credenciales: Policy Gateway, REPEP, consentimiento, horario, campaña aprobada y JIT deben pasar en la misma decisión.

## Inconsistencias del informe que se tratan como riesgo

- El informe dice que 31 de 32 tablas tienen RLS. La excepción debe identificarse y justificarse antes del piloto; no se acepta una cifra agregada como prueba suficiente.
- RabbitMQ, Node-RED, Prometheus y Grafana aparecen ligados a `0.0.0.0`. El release no presupone que la LAN sea un perímetro confiable.
- Se documentó una key maestra estática para LiteLLM y una contraseña bootstrap de Grafana. Ambas se consideran comprometidas por exposición documental y deben rotarse.
- El estado `READY` de servicios base no demuestra que sus imágenes propietarias contienen `psycopg`, LangGraph y Pika aprobados. El digest final de cada imagen construida sigue pendiente.
- El contrato de Hermes (autenticación, endpoint, timeout, presupuesto, clasificación de datos y auditoría) no figura en el informe; el RC sólo registra la ruta de integración y no envía tareas todavía.

## Gates que no pueden automatizarse desde este paquete

- Introducción y rotación de credenciales reales.
- Verificación del CIDR/VPN administrativo.
- Identificación de nombres DNS de servicios existentes dentro de Docker.
- Prueba real de REPEP y contratos con Meta, VICIdial, Atlantis-Neobot y Marketia.
- Aprobación legal de modelos, datos transferidos y grabación de llamadas.
- SBOM/avisos/código fuente correspondiente y attestación final de la appliance del cliente.
