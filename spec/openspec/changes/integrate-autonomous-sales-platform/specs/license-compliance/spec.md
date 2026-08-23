# License compliance and distribution

## ADDED Requirements

### Requirement: Manifiesto inmutable de componentes y modelos
Cada release SHALL materializar `compliance/component-lock.yaml` sin valores pendientes. Cada componente SHALL declarar `name`, `kind`, `repository`, `tag_or_revision`, `commit`, `artifact_or_model_id`, `digest`, `license_spdx`, `license_text_sha256`, `owner`, `distribution_mode` y `source_obligation`.

#### Scenario: Componente no fijado
- **GIVEN** un manifiesto con commit vacío, imagen sin digest o modelo por alias mutable
- **WHEN** se ejecuta el release gate
- **THEN** la release falla antes de construir cualquier artefacto para cliente

### Requirement: OpenOutreach como programa externo
OpenOutreach SHALL ejecutarse sin modificar como proceso/CLI externo y SHALL intercambiar únicamente datos mediante un contrato versionado. El código propietario SHALL NOT importarlo, enlazarlo, copiarlo ni cargarlo como plugin.

#### Scenario: Import accidental
- **GIVEN** un paquete propietario
- **WHEN** el análisis de dependencias detecta una importación desde OpenOutreach
- **THEN** CI bloquea el merge y exige usar el runner externo

### Requirement: Evidencia de obligaciones de fuente
Para cada artefacto distribuido, el sistema SHALL calcular las obligaciones según la versión fijada y SHALL preparar el código fuente correspondiente, modificaciones, avisos, licencias y scripts necesarios durante el plazo aplicable.

#### Scenario: Componente copyleft modificado
- **GIVEN** una modificación distribuida de OpenOutreach u otro componente copyleft
- **WHEN** se ensambla el bundle de cliente
- **THEN** el bundle incluye la fuente correspondiente bajo su licencia y evidencia de correspondencia binario-fuente

### Requirement: Prohibición de n8n
n8n SHALL NOT formar parte de las dependencias, imágenes, charts, flows o artefactos de Atlantis. Node-RED core Apache-2.0 MAY cubrir automatización visual únicamente con nodos adicionales aprobados individualmente.

#### Scenario: Dependencia n8n detectada
- **GIVEN** un lockfile, contenedor, SBOM o manifiesto de despliegue
- **WHEN** CI detecta `n8n` o una imagen asociada
- **THEN** la build falla y exige migrar el flujo a LangGraph, código propietario o Node-RED aprobado

### Requirement: Prohibición técnica de entrega incompleta
El pipeline SHALL impedir por política y permisos que una persona exporte o publique una appliance/VM/ISO sin un `distribution-compliance-attestation.json` firmado y ligado al digest exacto del artefacto.

#### Scenario: Exportación manual fuera de CI
- **GIVEN** una plantilla Proxmox marcada como candidata a cliente
- **WHEN** no existe attestation válida para su digest
- **THEN** el repositorio de entregas rechaza la carga y alerta a Release Manager y Legal
