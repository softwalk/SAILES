# Fuentes técnicas de referencia

Consultadas el 22 de agosto de 2026. Las versiones, condiciones y términos deben fijarse y verificarse nuevamente durante la tarea 0.6 y antes de cada release.

- OpenSpec: https://github.com/Fission-AI/OpenSpec — estructura y flujo spec-driven.
- OpenOutreach: https://github.com/eracle/OpenOutreach — GPLv3 observada; usar sin modificar como proceso/CLI externo. No importarlo en código propietario. Si se distribuyen modificaciones, publicar el código fuente correspondiente bajo GPLv3.
- OpenSales: https://github.com/siddartha19/OpenSales — MIT y baja madurez observada; incluye SendGrid, Google Sheets y fuentes externas. Usar como referencia o adaptador sin envío.
- SalesGPT: https://github.com/filip-michalsky/SalesGPT — MIT; su referencia incluye herramientas de pago. Deshabilitarlas y evaluar la política conversacional.
- LangGraph: https://docs.langchain.com/oss/python/langgraph/overview — persistencia, durable execution e interrupciones humanas.
- VICIdial Agent API: https://vicidial.org/docs/AGENT_API.txt
- VICIdial Non-Agent API: https://vicidial.org/docs/NON-AGENT_API.txt
- Evolution API: https://github.com/EvolutionAPI/evolution-api
- WhatsApp Business Platform: https://developers.facebook.com/documentation/business-messaging/whatsapp/about-the-platform
- REPEP Profeco: https://repep.profeco.gob.mx/
- REPEP para proveedores: https://repep.profeco.gob.mx/infogeneral.jsp — acceso previo registro/pago; no se presupone API pública.
- Ley Federal de Protección al Consumidor vigente: https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPC.pdf
- Ley Federal de Protección de Datos Personales en Posesión de los Particulares vigente: https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf
- Kimi API / modelos: https://platform.moonshot.ai/docs/models
- DeepSeek API: https://api-docs.deepseek.com/

## Notas de diligencia

- “Open source” no significa que toda fuente de datos o servicio integrado pueda usarse libremente; revisar TOS, licencia, procedencia y permisos.
- Node-RED core: https://github.com/node-red/node-red y https://github.com/node-red/node-red/blob/main/LICENSE — Apache-2.0. Cada nodo de terceros se inventaría y revisa por separado; la licencia del core no cubre automáticamente el catálogo de nodos.
- n8n: excluido de la arquitectura distribuible. No se permite incorporarlo como dependencia ni sustituir Node-RED sin un nuevo dictamen y cambio OpenSpec aprobado.
- Evolution API admite alternativas técnicas, pero esta especificación obliga WhatsApp Cloud API oficial en producción. Su licencia 2026 agrega condiciones de notificación y ciertas versiones exigen activación; revisar la versión exacta. La opción preferida es un adaptador directo a Meta.
- REPEP pertenece a Profeco. El mecanismo de consulta empresarial debe acordarse/autorizarse; la especificación no presupone una API pública ni autoriza scraping.
- Kimi K3 y los modelos DeepSeek cambian con frecuencia; los IDs quedan en configuración y el dominio usa alias de capacidad. Antes de enviar datos se validan residencia, retención, entrenamiento, transferencias y subprocesadores.
