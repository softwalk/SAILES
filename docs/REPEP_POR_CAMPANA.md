# Configuración REPEP por campaña

## Regla funcional

`repep.enabled` inicia en `false` para cada nueva campaña.

Para voz promocional existen dos rutas:

1. **REPEP activado:** requiere snapshot vigente y resultado `NOT_LISTED`.
2. **REPEP desactivado:** sólo permite continuar si la versión aprobada contiene:
   - `exemption_type: B2B`
   - `exemption_approved: true`
   - `exemption_evidence_ref` no vacío

Si falta cualquiera de esos elementos, Policy Gateway devuelve `DENY`. La
excepción, su referencia y el interruptor forman parte del artefacto inmutable;
cambiarlos invalida la aprobación.

```json
{
  "repep": {
    "enabled": false,
    "exemption_type": "B2B",
    "exemption_approved": true,
    "exemption_evidence_ref": "legal/b2b/campaign-2026-08.pdf"
  }
}
```

## Controles

- En producción, Policy Gateway toma estos valores del CRM y no confía en los
  flags enviados por el caller.
- B2C no puede usar la excepción.
- Supresiones internas/globales, horario, frecuencia, aprobación y kill switch
  siguen aplicando aunque REPEP esté desactivado.
- Debe existir dictamen interno que documente por qué la audiencia no tiene el
  carácter de consumidor y si existen registros sectoriales adicionales.

## Fundamento de alcance

Las fuentes oficiales describen REPEP como un mecanismo para proteger a
**consumidores** frente a publicidad no deseada. Esa descripción respalda que la
clasificación consumidor/B2B sea parte de la matriz jurídica, pero no sustituye
un dictamen para cada producto, audiencia y canal:

- https://repep.profeco.gob.mx/preguntasfrecuentes.jsp
- https://www.gob.mx/profeco/documentos/registro-publico-para-evitar-publicidad-repep
- https://repep.profeco.gob.mx/Sanciones.jsp
