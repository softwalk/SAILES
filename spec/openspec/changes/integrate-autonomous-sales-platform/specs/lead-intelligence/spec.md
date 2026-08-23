# Lead intelligence

## ADDED Requirements

### Requirement: Descubrimiento con procedencia
El sistema SHALL invocar OpenOutreach sin modificar como proceso/CLI externo que entregue candidatos normalizados sin ejecutar contacto. El código propietario SHALL NOT importarlo, enlazarlo ni cargarlo como plugin, y SHALL registrar proveedor, URL/identificador de fuente, licencia/permiso, instante de obtención y confianza por dato.

#### Scenario: Lead aceptado
- **GIVEN** una campaña aprobada para investigación y una fuente permitida
- **WHEN** OpenOutreach devuelve una organización y posibles contactos
- **THEN** el sistema crea o fusiona registros por reglas deterministas, conserva procedencia por campo y no agenda ningún envío

#### Scenario: Fuente prohibida o sin procedencia
- **GIVEN** un resultado sin fuente suficiente o proveniente de una fuente denegada
- **WHEN** se intenta incorporarlo
- **THEN** se lo pone en cuarentena y se crea una revisión de datos

### Requirement: Modificaciones GPLv3 distribuibles
Si Atlantis distribuye una versión modificada de OpenOutreach, el pipeline SHALL generar y entregar el código fuente correspondiente de esas modificaciones bajo GPLv3, junto con licencia, avisos y scripts necesarios. Si el componente permanece sin modificar, el runner SHALL verificar el hash del artefacto aprobado.

#### Scenario: Fork modificado sin paquete de fuentes
- **GIVEN** una imagen de OpenOutreach cuyo commit difiere del upstream aprobado
- **WHEN** se intenta incluirla en una appliance, VM, plantilla o ISO
- **THEN** el release gate bloquea la entrega hasta adjuntar fuente GPLv3, avisos, licencia y evidencia de build

### Requirement: Calificación explicable
El sistema SHALL calcular ajuste de cuenta, ajuste de contacto, intención, oportunidad temporal y calidad de datos por separado; SHALL conservar versión de reglas/modelo y SHALL exponer razones positivas y negativas.

#### Scenario: Umbral insuficiente
- **GIVEN** un lead con puntuación menor al umbral de campaña
- **WHEN** finaliza la calificación
- **THEN** queda como `NURTURE` o `DISQUALIFIED` y no pasa a preflight de contacto

### Requirement: Deduplicación y fusión segura
El sistema SHALL comparar dominio, identificadores de fuente, teléfono normalizado y correo; SHALL evitar fusión automática cuando la confianza sea ambigua.

#### Scenario: Posible homónimo
- **GIVEN** dos contactos con mismo nombre pero empresas o teléfonos distintos
- **WHEN** la confianza de coincidencia está en zona gris
- **THEN** el sistema mantiene ambos registros y solicita revisión en lugar de fusionarlos
