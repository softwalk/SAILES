# Propuesta: integrar plataforma autónoma de prospección y ventas

## Resumen

Construir una plataforma multi-tenant que descubra prospectos, prepare campañas personalizadas, converse por voz y WhatsApp, actualice el CRM y recomiende cierres, manteniendo a un humano en los puntos de riesgo y bloqueando automáticamente todo contacto no permitido.

La autonomía se limita a investigar, clasificar, redactar, resumir, priorizar y ejecutar acciones previamente autorizadas. El sistema no puede autootorgarse permisos, alterar políticas, omitir REPEP, inventar consentimiento, aplicar descuentos sensibles, comprometer términos contractuales ni enviar pagos sin controles.

## Problema

Los componentes propuestos resuelven partes distintas pero superpuestas del ciclo comercial. Integrarlos directamente crearía duplicidad de CRM, envíos fuera de control, estados inconsistentes, exposición de datos y poca trazabilidad. Se necesita un plano de control único con contratos estables y adaptadores reemplazables.

## Objetivos

- Reducir tiempo de lista a primer contacto autorizado.
- Aumentar reuniones y oportunidades calificadas por campaña.
- Conservar evidencia completa de consentimiento, REPEP, aprobación, mensajes y decisiones.
- Permitir reemplazar Kimi K3 por DeepSeek —o viceversa— sin cambiar flujos ni datos.
- Sincronizar Marketia en ambos sentidos sin convertirlo en una vía de evasión de políticas.
- Escalar voz y WhatsApp mediante colas, idempotencia y reintentos controlados.
- Evitar que un componente de baja madurez o licencia incompatible se vuelva un punto crítico del producto.
- Preservar el núcleo propietario mediante límites de proceso, API, repositorio e imagen alrededor de Atlantis-Neobot, Marketia, Policy Gateway, CRM API y adaptadores.
- Bloquear cualquier entrega de appliance, VM, plantilla o ISO que no incluya evidencia completa de cumplimiento de licencias.

## Fuera de alcance

- Comprar, vender o comerciar criptoactivos de forma autónoma.
- Scraping que infrinja términos, robots, licencias o legislación.
- Contactar números o cuentas sin base jurídica/consentimiento aplicable.
- Cierre contractual sin reglas explícitas y, cuando corresponda, aprobación humana.
- Sustituir la asesoría jurídica; la configuración de cumplimiento debe validarse por jurisdicción.

## Resultados medibles

| Indicador | Meta de piloto |
|---|---:|
| Llamadas salientes sin autorización válida | 0 |
| WhatsApp promocional sin opt-in demostrable | 0 |
| Acciones duplicadas por reintento | 0 |
| Ejecuciones reconstruibles desde auditoría | 100% |
| PII cruda en trazas de modelos | 0 |
| Entrega de webhooks procesables | ≥ 99.9% |
| Aprobaciones de campaña con versión fija | 100% |
| Tiempo p95 de decisión local de contacto | < 300 ms |
| Recuperación automática de fallo transitorio de modelo/canal | ≥ 95% |

## Cambios de capacidades

- Se agrega inteligencia de leads con procedencia y puntuación explicable.
- Se agrega orquestación de campañas versionadas y aprobación humana.
- Se agrega motor conversacional con límites de acción.
- Se agrega gateway central de cumplimiento y autorización por acción.
- Se agregan adaptadores de voz, WhatsApp, Marketia y modelos.
- Se agrega CRM/memoria/auditoría en PostgreSQL.
- Se agrega observabilidad, seguridad multi-tenant y operaciones del piloto.

## Riesgos principales

| Riesgo | Tratamiento |
|---|---|
| REPEP sin API estable para automatización | Adaptador desacoplado; carga/consulta por mecanismo autorizado; evidencia con hash; bloqueo ante error o caducidad. |
| Bloqueo de números de WhatsApp por transporte no oficial | Evolution API como gateway, pero WhatsApp Cloud API oficial en producción; Baileys sólo laboratorio aislado. |
| Proyectos OSS con alcance/licencia cambiante | Fijar commit/versión, escanear SBOM/licencia y encapsular cada proyecto. |
| OpenOutreach GPLv3 | Aislarlo como proceso/servicio con contrato de datos; no copiar ni enlazar código al núcleo propietario sin dictamen. |
| Contaminación de límites propietarios | Construir Atlantis-Neobot, Marketia, Policy Gateway, CRM API y adaptadores como servicios propietarios separados; comunicar sólo por contratos de datos versionados. |
| n8n no OSI-permisivo | Excluir n8n y usar Node-RED core Apache-2.0, fijado por commit e imagen digest; revisar cada nodo adicional. |
| Appliance/VM/ISO incompleta | Release gate bloqueante: SBOM, avisos, textos de licencia y paquete de código fuente correspondiente antes de entregar. |
| Evolution API con condiciones adicionales/activación | Preferir adaptador directo a Meta Cloud API; Evolution es opcional y exige aprobación de versión/licencia. |
| VICIdial marca desde listas internas | Aplicar autorización en el punto real de originate/dial; importar un lead no equivale a autorizar su llamada. |
| Alucinación o promesa comercial indebida | Respuestas fundamentadas, catálogo de afirmaciones permitido, límites, aprobación sensible y auditoría. |
| Duplicidad por reintentos/webhooks | Idempotency key, inbox/outbox transaccional y claves únicas. |
| Fuga de PII a modelos | Minimización, tokenización, DLP, retención corta y proveedores aprobados. |
| Divergencia Marketia/CRM | Propiedad de campos, versionado, reconciliación y cola de errores. |

## Criterio de aprobación de la propuesta

Debe existir aceptación conjunta de Producto, Ventas, Seguridad, Operaciones y Legal/Privacidad sobre: alcance, matriz de aprobación, mecanismo REPEP, registros sectoriales, política de WhatsApp, grabación de llamadas, retención, transferencias internacionales, proveedores de modelos y dictamen de licencias.
