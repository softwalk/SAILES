# Supply-chain governance

## ADDED Requirements

### Requirement: Admisión de componentes OSS
Todo componente, imagen y modelo SHALL tener repositorio/fuente, tag o revisión, commit inmutable, imagen por digest cuando aplique, licencia verificada, hash de licencia, SBOM/procedencia, análisis de vulnerabilidades, plan de actualización y propietario antes de build de entrega o producción.

#### Scenario: Dependencia sin licencia compatible
- **GIVEN** un componente cuya licencia no fue aprobada para el producto propietario
- **WHEN** una build intenta enlazarlo o incorporarlo al artefacto principal
- **THEN** CI bloquea la build y ofrece aislamiento por proceso sólo si Legal lo autoriza

#### Scenario: Alias mutable o campo pendiente
- **GIVEN** un componente con imagen `latest`, modelo por alias mutable, commit ausente, licencia `UNKNOWN` o valor `TBD`
- **WHEN** se solicita promoción o empaquetado
- **THEN** CI bloquea la operación y lista los campos que deben resolverse

### Requirement: Separación de servicios propietarios
Atlantis-Neobot, Marketia, Policy Gateway, CRM API y adaptadores SHALL mantenerse como servicios propietarios separados, con repositorio, proceso, imagen, dependencias, SBOM y pipeline propios. SHALL comunicarse con componentes copyleft exclusivamente mediante contratos de datos o APIs versionadas y SHALL NOT importar, enlazar o cargar módulos GPL/AGPL en su proceso.

#### Scenario: Importación copyleft en servicio propietario
- **GIVEN** un servicio propietario Atlantis
- **WHEN** SCA detecta importación, enlace, copia o plugin GPL/AGPL no exceptuado
- **THEN** CI bloquea la build hasta aislar el componente o aprobar y cumplir la licencia aplicable

### Requirement: Gate de distribución de appliance
El sistema SHALL NOT publicar ni entregar una appliance, VM, plantilla, snapshot, ISO o imagen de cliente hasta generar y validar: SBOM CycloneDX/SPDX, `THIRD_PARTY_NOTICES`, textos completos de licencias, manifiesto fijado, paquete/oferta de código fuente correspondiente, scripts de build/instalación y hashes del bundle.

#### Scenario: VM lista sin fuentes correspondientes
- **GIVEN** una VM funcional que contiene componentes GPL/AGPL o modificaciones cubiertas
- **WHEN** Release Manager solicita exportarla al cliente
- **THEN** el gate `distribution-compliance` deniega la entrega y no genera URL ni medio descargable

### Requirement: Herramientas peligrosas deshabilitadas
Adapters de OpenSales y SalesGPT SHALL exponer únicamente funciones permitidas. Herramientas heredadas de envío, pago, firma, descuentos o acceso directo a CRM SHALL permanecer ausentes o deshabilitadas por construcción.

#### Scenario: SalesGPT propone un pago
- **GIVEN** una configuración upstream que incluye creación de enlaces de pago
- **WHEN** se carga en el runtime Atlantis
- **THEN** la validación de capacidades rechaza la herramienta y crea un hallazgo de configuración

### Requirement: Compatibilidad de Evolution API
Si Evolution API se utiliza, su versión, licencia, requisitos de activación y telemetría SHALL estar aprobados. El despliegue SHALL permitir sustituirlo por el adaptador directo a Meta sin cambiar el dominio.

#### Scenario: Cambio de licencia
- **GIVEN** una nueva versión de Evolution API con condiciones diferentes
- **WHEN** Renovate o un operador propone actualizarla
- **THEN** la promoción queda bloqueada hasta un nuevo dictamen y pruebas de contrato
