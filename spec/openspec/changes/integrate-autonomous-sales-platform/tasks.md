# Plan de implementación

Cada tarea se cierra con código, pruebas, observabilidad, documentación y evidencia. Los ítems `[GATE]` requieren aceptación humana antes de continuar.

## 0. Descubrimiento y gobierno

- [ ] 0.1 [GATE] Confirmar procesos, API, autenticación, webhooks y propiedad de campos de Marketia.
- [ ] 0.2 [GATE] Confirmar contrato técnico de Atlantis-Neobot y responsabilidades frente a VICIdial.
- [ ] 0.3 [GATE] Validar con Legal/Privacidad el mecanismo autorizado de REPEP, vigencia de evidencia, horarios, grabación, avisos y retención.
- [ ] 0.4 [GATE] Definir matriz por jurisdicción, producto, propósito y canal.
- [ ] 0.5 [GATE] Documentar opt-in de WhatsApp y aprobar plantillas iniciales.
- [ ] 0.6 [GATE] Completar `compliance/component-lock.yaml` para cada componente, imagen y modelo con repositorio, tag/revisión, commit, artefacto/model ID, digest, SPDX/LicenseRef y hash del texto de licencia; ningún `TBD`, `UNKNOWN`, `latest` o alias mutable puede promoverse.
- [ ] 0.7 Generar SBOM CycloneDX y SPDX, dictamen de compatibilidad, avisos y matriz de obligaciones; prohibir incorporación hasta aprobación.
- [ ] 0.8 Definir SLO, volumen, presupuesto de modelos y criterios de éxito del piloto.
- [ ] 0.9 [GATE] Definir B2B/B2C, sectores y registros de exclusión aplicables además de REPEP.
- [ ] 0.10 [GATE] Aprobar evaluación DPIA/transferencias internacionales para Kimi y DeepSeek.
- [ ] 0.11 [GATE] Aprobar ADR de separación: Atlantis-Neobot, Marketia, Policy Gateway, CRM API y cada adaptador como servicio propietario, repositorio/imagen/pipeline y SBOM independientes.
- [ ] 0.12 [GATE] Excluir n8n y aprobar Node-RED core Apache-2.0; inventariar y aprobar individualmente cada nodo adicional.

## 1. Fundación de plataforma

- [ ] 1.1 Crear repos coordinados o monorepo con límites de build obligatorios: cada servicio propietario produce una imagen independiente y no comparte proceso con componentes copyleft.
- [ ] 1.2 Implementar OIDC, roles, segregación de funciones y contexto de tenant.
- [ ] 1.3 Crear migraciones PostgreSQL, RLS, índices, particiones y backups.
- [ ] 1.4 Implementar cifrado de aplicación para campos sensibles y gestor de secretos.
- [ ] 1.5 Desplegar RabbitMQ, outbox/inbox, DLQ y contratos de eventos versionados.
- [ ] 1.6 Implementar API Gateway, rate limiting, idempotency keys y error model.
- [ ] 1.7 Instrumentar OpenTelemetry, métricas, logs redactados y correlation IDs.
- [ ] 1.8 Crear consola mínima de auditoría, campañas, aprobaciones y kill switch.
- [ ] 1.9 Probar aislamiento tenant, restore de backup y rotación de secretos.
- [ ] 1.10 Ejecutar migraciones en PostgreSQL real y probar FKs compuestas, RLS `FORCE`, usuario no propietario y acceso administrativo de emergencia.
- [ ] 1.11 Implementar cadena de auditoría serializada por tenant y exportación WORM verificable.

## 2. Policy & Compliance Gateway

- [ ] 2.1 Implementar motor determinista de reglas versionadas y explainability.
- [ ] 2.2 Crear consent ledger y exclusión global/tenant/canal/propósito.
- [ ] 2.3 Implementar normalización/tokenización de teléfonos E.164.
- [ ] 2.4 Crear `RepepProvider` con importación/consulta autorizada, evidencia, hash y vigencia.
- [ ] 2.5 Aplicar `fail closed` para llamadas ante evidencia ausente, vencida o ambigua.
- [ ] 2.6 Implementar horario, frecuencia, quiet hours y límites por campaña/contacto.
- [ ] 2.7 Emitir tokens firmados de un solo uso con TTL y revocación.
- [ ] 2.8 Implementar aprobación de campaña ligada a hash y versión.
- [ ] 2.9 Implementar matriz de oportunidades sensibles y SLA de revisión.
- [ ] 2.10 Crear pruebas de mutación que demuestren que ninguna ruta omite políticas.
- [ ] 2.11 Emitir autorización sólo después de retirar la acción de la cola y repetir preflight justo antes del efecto.
- [ ] 2.12 Guardar snapshot REPEP con lote, fecha efectiva, contrato/recibo, hash y vigencia jurídica.

## 3. Inteligencia de leads

- [ ] 3.1 Implementar `OpenOutreachExternalRunner` que ejecute el upstream sin modificar por proceso/CLI; el código propietario no puede importarlo, enlazarlo ni cargarlo como plugin.
- [ ] 3.2 Normalizar empresa/contacto y procedencia por campo.
- [ ] 3.3 Implementar deduplicación, zona gris y revisión de merge.
- [ ] 3.4 Implementar scoring por componentes con razones y versión.
- [ ] 3.5 Incorporar control de fuentes, licencias, robots/TOS y minimización.
- [ ] 3.6 Crear datasets de evaluación y pruebas de precisión/recall de calificación.
- [ ] 3.7 Verificar el hash del upstream OpenOutreach sin modificar; si se mantiene un fork distribuible, generar automáticamente el paquete de fuente GPLv3 y evidencia binario-fuente.

## 4. Campañas, OpenSales y Marketia

- [ ] 4.1 Implementar dominio campaña/versión/segmento/secuencia/variante.
- [ ] 4.2 Encapsular agentes OpenSales como generadores sin herramientas de canal.
- [ ] 4.3 Crear validación de claims contra knowledge base aprobada.
- [ ] 4.4 Implementar preview exacto y diff material previo a aprobación.
- [ ] 4.5 Crear `MarketiaAdapter` y registrar versión de contrato.
- [ ] 4.6 Definir ownership por campo y resolución de conflictos.
- [ ] 4.7 Implementar sync incremental, reconciliación diaria, outbox y DLQ.
- [ ] 4.8 Propagar UTM/correlation IDs y validar atribución de extremo a extremo.
- [ ] 4.9 Probar que Marketia no puede habilitar un contacto suprimido.
- [ ] 4.10 Reemplazar herramientas nativas de envío/Sheets de OpenSales por puertos internos sin credenciales de canal.

## 5. Orquestación LangGraph

- [ ] 5.1 Definir `SalesRunState` versionado y migraciones de checkpoint.
- [ ] 5.2 Implementar nodos puros y side effects sólo por outbox.
- [ ] 5.3 Implementar retry con backoff/jitter, circuit breakers y DLQ.
- [ ] 5.4 Implementar interrupts humanos, expiración, reasignación y escalamiento.
- [ ] 5.5 Implementar compensación/cancelación de acciones pendientes.
- [ ] 5.6 Crear simulador determinista y replay desde eventos.
- [ ] 5.7 Probar crash/restart en cada transición sin duplicar efectos.
- [ ] 5.8 Fijar `workflow_version` por run y probar reanudación durante despliegues y migraciones de checkpoint.
- [ ] 5.9 Desplegar Node-RED en contenedor independiente sólo para automatización auxiliar; negar DB/canales directos y exigir Policy Gateway para todo efecto externo.
- [ ] 5.10 Añadir regla CI/SBOM que falle ante n8n o nodos Node-RED no registrados/licenciados.

## 6. Gateway de modelos y SalesGPT

- [ ] 6.1 Implementar interfaz `ModelGateway` y catálogo de capacidades.
- [ ] 6.2 Crear adapters Kimi y DeepSeek con secretos separados.
- [ ] 6.3 Implementar router por datos, región, calidad, costo, latencia y salud.
- [ ] 6.4 Implementar JSON Schema, reparación única, fallback y handoff.
- [ ] 6.5 Versionar prompts, knowledge packs y evaluaciones.
- [ ] 6.6 Integrar SalesGPT como política conversacional sin acceso directo a canales.
- [ ] 6.7 Añadir detector de intención, objeción, opt-out y sensibilidad.
- [ ] 6.8 Añadir grounding de afirmaciones y umbrales de confianza.
- [ ] 6.9 Implementar presupuestos por tenant/campaña y degradación segura.
- [ ] 6.10 Ejecutar evals offline de veracidad, tono, rechazo, handoff y costo.
- [ ] 6.11 Probar canary, rollback de modelo y fallback dentro de conversación sin pérdida de políticas ni contexto.
- [ ] 6.12 Eliminar/deshabilitar herramientas de pago, firma y envío heredadas de SalesGPT.

## 7. Canal de voz

- [ ] 7.1 Definir `VoiceProvider` y mapeo de disposiciones.
- [ ] 7.2 Implementar VICIdial adapter sobre Agent/Non-Agent API vía HTTPS.
- [ ] 7.3 Implementar Atlantis-Neobot adapter según contrato confirmado.
- [ ] 7.4 Exigir validación local del token antes de importar/marcar.
- [ ] 7.5 Implementar eventos, transferencia humana, timeout y cancelación.
- [ ] 7.6 Configurar grabación/aviso por política y almacenamiento de objetos.
- [ ] 7.7 Implementar kill switch con propagación menor a 60 segundos.
- [ ] 7.8 Probar REPEP inscrito, fuente caída, token vencido/replay y cambio horario.
- [ ] 7.9 [GATE] Demostrar con prueba end-to-end que Asterisk/VICIdial no puede originar una llamada por ninguna ruta sin token válido.

## 8. Canal WhatsApp

- [ ] 8.1 Implementar `WhatsAppProvider` directo a Meta Cloud API como ruta productiva preferida.
- [ ] 8.2 Si se usa Evolution API, fijar versión/licencia, activar sólo transporte Cloud API oficial, deshabilitar Baileys y validar hardening.
- [ ] 8.3 Implementar opt-in ledger, plantillas, idiomas y ventana conversacional.
- [ ] 8.4 Verificar firma, timestamp, deduplicación y orden de webhooks.
- [ ] 8.5 Implementar opt-out inmediato y cancelación de cola.
- [ ] 8.6 Implementar control de calidad, rate/quality limits y pausas.
- [ ] 8.7 Probar plantilla rechazada, opt-in ausente, webhook duplicado y revocación.
- [ ] 8.8 Verificar firma Meta con cuerpo crudo, challenge de suscripción, timestamp, reentrega y eventos fuera de orden.

## 9. CRM, memoria y analítica

- [ ] 9.1 Implementar API de contactos, cuentas, interacciones y oportunidades.
- [ ] 9.2 Implementar memoria factual con procedencia, confianza y caducidad.
- [ ] 9.3 Separar transcripción, resumen y hechos extraídos.
- [ ] 9.4 Implementar exportación, rectificación, supresión y legal hold.
- [ ] 9.5 Crear embudo, atribución, métricas de contacto y costo por resultado.
- [ ] 9.6 Validar que métricas no reidentifiquen contactos fuera de permisos.
- [ ] 9.7 Implementar solicitudes ARCO, borrado propagado, excepciones legales y evidencia mínima de supresión.

## 10. Seguridad, rendimiento y piloto

- [ ] 10.1 Ejecutar threat model (STRIDE/LINDDUN) y cerrar riesgos críticos.
- [ ] 10.2 Realizar pruebas de prompt injection, SSRF, exfiltración y tool abuse.
- [ ] 10.3 Ejecutar SAST/DAST/SCA, pentest y revisión de configuración.
- [ ] 10.4 Ejecutar carga a 100 grafos concurrentes y 100 webhooks/s.
- [ ] 10.5 Ejecutar disaster recovery y demostrar RPO/RTO.
- [ ] 10.6 [GATE] Lanzar shadow mode sin contacto; comparar decisiones humanas.
- [ ] 10.7 [GATE] Piloto interno/allowlist con límites diarios y revisión del 100%.
- [ ] 10.8 [GATE] Piloto productivo pequeño con comité diario y rollback.
- [ ] 10.9 Promover autonomía gradual sólo si métricas y cero incidentes lo permiten.
- [ ] 10.10 Ejecutar pruebas contractuales del OpenAPI y eventos contra todos los adaptadores.
- [ ] 10.11 [GATE] Ejecutar `distribution-compliance`: generar SBOMs, `THIRD_PARTY_NOTICES`, licencias, fuentes correspondientes, scripts, hashes y attestation ligada al digest final.
- [ ] 10.12 [GATE] Probar que ninguna cuenta humana puede exportar/publicar appliance, VM, plantilla, snapshot o ISO sin attestation válida.

## Criterios finales de Done

- [ ] Evidencia automatizada de que 100% de llamadas requieren REPEP vigente y token válido.
- [ ] Evidencia automatizada de que 100% de WhatsApp iniciado requiere opt-in y reglas de plantilla/ventana.
- [ ] Cero duplicados en pruebas de reentrega y crash.
- [ ] Auditor reconstruye una muestra aleatoria de acciones sin acceso privilegiado a producción.
- [ ] Fallo de cada proveedor resulta en fallback permitido o bloqueo seguro.
- [ ] Runbooks, responsables, alertas y rollback ensayados.
- [ ] Aprobación final de Producto, Ventas, Seguridad, Operaciones y Legal/Privacidad.
- [ ] Cero dependencias n8n y cero imports/enlaces GPL/AGPL dentro de servicios propietarios.
- [ ] Todo componente/modelo está fijado y el bundle de distribución contiene SBOM, avisos, licencias y fuentes correspondientes.

## 11. Alineación con infraestructura Proxmox instalada

- [x] 11.1 Inventariar VM 110, VM 102, invitados protegidos, redes Docker, puertos y rutas `/opt/atlantis` sin incluir secretos.
- [x] 11.2 Crear overlay application-only que preserve PostgreSQL, RabbitMQ, Valkey, LiteLLM, Node-RED, Caddy y observabilidad existentes.
- [x] 11.3 Limitar recursos de los servicios propietarios para el techo de 4 GiB y prohibir modelos locales en VM 110.
- [x] 11.4 Aceptar credenciales mediante archivos secretos y construir el DSN PostgreSQL sólo en memoria.
- [x] 11.5 Añadir preflight no destructivo para host/IP/rutas/redes/permisos/bindings y credencial bootstrap conocida.
- [ ] 11.6 [GATE] Rotar LiteLLM/Grafana bootstrap y comprobar que 1880/3001/9090/15672 sólo sean accesibles desde VPN/CIDR administrativo.
- [ ] 11.7 [GATE] Confirmar nombres DNS de contenedores, dependencias runtime e imágenes propietarias con digest/attestation.
- [ ] 11.8 [GATE] Desplegar RC2 en VM 110, ejecutar shadow E2E y ensayar rollback con snapshot/dump.
