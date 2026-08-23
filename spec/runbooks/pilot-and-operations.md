# Runbook de piloto y operación

## Promoción de ambientes

1. **Local:** proveedores falsos, datos sintéticos, sin egress a canales.
2. **Integración:** sandboxes; números/cuentas allowlist; REPEP simulado sólo para pruebas técnicas.
3. **Shadow:** datos reales minimizados; se calculan decisiones pero no se contacta.
4. **Piloto supervisado:** campaña y lista pequeñas; aprobación del 100% de acciones; límites diarios bajos.
5. **Producción limitada:** autonomía gradual por segmento y tipo de acción; sensibilidad siempre humana.

No se promociona si hay hallazgos críticos, decisiones no reconstruibles, duplicados, acciones sin autorización, pruebas de restore fallidas o configuración jurídica incompleta.

## Checklist previo a una campaña

- Versión exacta aprobada por un usuario distinto del creador cuando aplica.
- Segmento, propósito, base jurídica/consentimiento, horario y frecuencia validados.
- Por campaña, REPEP activado con evidencia vigente, o excepción B2B aprobada y
  evidenciada. El interruptor inicia desactivado, pero una campaña sin excepción
  B2B completa permanece bloqueada.
- Opt-in y plantilla/ventana válidos para WhatsApp.
- Claims, oferta, guion, idioma, transferencias y opt-out aprobados.
- Presupuesto, límites de volumen, quality rating y umbrales de pausa configurados.
- On-call y compliance reviewer asignados.
- Kill switch probado; dashboard y alertas verdes.

## Operación diaria

- Revisar salud de fuentes, REPEP, modelos, Marketia, VICIdial/Neobot y WhatsApp.
- Revisar atraso de outbox/inbox/DLQ y discrepancias de reconciliación.
- Muestrear conversaciones y revisar veracidad, tono, opt-out y handoff.
- Comparar costo, reuniones, oportunidades, quejas y denegaciones por variante.
- Aprobar o rechazar cambios de campaña; nunca editar una versión aprobada.

## Kill switch

1. Compliance reviewer o incident commander pausa tenant/campaña/canal/global.
2. Policy Gateway deja de emitir autorizaciones y revoca las no consumidas.
3. Workers dejan de sacar nuevas acciones; adaptadores rechazan tokens revocados.
4. Se preservan llamadas activas según política de terminación segura.
5. Se captura snapshot de configuración, métricas, decisiones y eventos.
6. Reanudación requiere nueva aprobación si cambió contenido, audiencia o política.

## Incidentes

| Señal | Acción inmediata |
|---|---|
| Llamada sin evidencia REPEP | Pausa global de voz, preservar evidencia, notificar Legal/Seguridad, analizar bypass. |
| WhatsApp sin opt-in | Pausa del tenant/número, invalidar colas, revisar fuente de consentimiento. |
| Mensajes duplicados | Pausar consumidor, revisar inbox/idempotency, no borrar evidencia. |
| Prompt injection/exfiltración | Revocar herramienta/secretos afectados, aislar run, preservar trazas redactadas. |
| Discrepancia Marketia/CRM | CRM prevalece en campos gobernados; pausar sync conflictivo y reconciliar. |
| Proveedor de modelo degradado | Abrir breaker, usar fallback permitido o bloquear; nunca relajar clasificación de datos. |
| Cuenta/número de WhatsApp restringido | Pausar envíos, no rotar evasivamente números, revisar calidad/política con Meta. |

## Rollback

- Revertir despliegue de servicios; no revertir eventos ya publicados.
- Pausar campañas y revocar autorizaciones antes del rollback.
- Migraciones de datos usan expand/contract; toda migración destructiva exige backup verificado.
- Reprocesar desde outbox/checkpoint sólo con consumidores idempotentes.
- Después del rollback, reconciliar canales, CRM y Marketia antes de reanudar.

## Evidencia de auditoría mínima

Para cada acción externa: tenant, contacto tokenizado, campaña/versión/hash, aprobación, propósito, decisión de política, evidencia (REPEP u opt-in), autorización/TTL, proveedor, payload hash, estado, disposición, modelo/prompt cuando corresponda, correlation ID y actores humanos.

## Pruebas de juego de desastre trimestral

- Caída total del modelo primario.
- REPEP inaccesible con cola de llamadas pendiente.
- Webhook duplicado y fuera de orden.
- Credencial de canal comprometida.
- Restauración PostgreSQL a punto en el tiempo.
- Marketia fuera de línea 24 horas y reconciliación posterior.
- Revocación masiva y verificación de cancelación en menos de 60 segundos.
