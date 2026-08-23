# Cambios: REPEP configurable por campaña

- Se agregó `repep_enabled`, con valor inicial `false`.
- REPEP activo conserva la validación fail-closed de snapshot y listado.
- REPEP inactivo sólo permite voz promocional con excepción B2B aprobada y
  referencia de evidencia jurídica.
- CRM es la autoridad de la configuración; EvidenceClient sobrescribe flags del caller.
- Policy Gateway se versionó como `mx-contactability@2`.
- Se actualizaron OpenAPI, OpenSpec, runbook, README y documentación de usuario.
- Se añadieron pruebas de default, excepción B2B válida, rechazo B2C y protección
  contra manipulación de flags.

Este cambio no habilita producción ni cierra los bloqueos existentes de la RC.
