# TP6 — Interoperabilidad (FHIR) · Grupo 8: DiagnosticReport

**Bioingeniería – 16.22 Informática Médica**

Resolución de la **Actividad 3 (Python)** del TP6. Basado en el repositorio
de la cátedra [euberrino/FHIR-basics](https://github.com/euberrino/FHIR-basics),
extendido con el recurso asignado al grupo.

Servidor utilizado: `https://hapi.fhir.org/baseR4` (instancia pública de HAPI FHIR).

---

## Instalación

```bash
python -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> **Atención con pydantic.** `fhir.resources==6.1.0` está construido sobre
> pydantic 1.x. Si se instala sobre un entorno que ya tiene pydantic 2, el
> import falla con
> `ImportError: cannot import name 'ROOT_VALIDATOR_CONFIG_KEY'`.
> Por eso `requirements.txt` pinea `pydantic==1.10.13`.

## Uso

```bash
python workflow.py          # corre las tres consignas (3.a, 3.b, 3.c)
python workflow.py 3a       # solo crear y leer el Patient
python workflow.py 3b       # solo la búsqueda por documento
python workflow.py 3c       # solo el DiagnosticReport

python validar_local.py     # valida la estructura de los recursos sin usar red
```

Los JSON de todas las respuestas del servidor se guardan en `salidas/`.

---

## Estructura

| Archivo | Contenido |
|---|---|
| `base.py` | Comunicación REST con el servidor: CREATE (POST), READ (GET por id) y SEARCH (GET con parámetros). Maneja `OperationOutcome` para mostrar los errores de validación del servidor. |
| `patient.py` | Construcción del `Patient` con `identifier` (DNI) y el método de búsqueda por documento (**3.b**). |
| `observation.py` | Construcción de las `Observation` con los resultados atómicos del hemograma (LOINC + unidades UCUM). |
| `diagnostic_report.py` | **Consigna 3.c** — construcción del `DiagnosticReport` y documentación de sus elementos. |
| `workflow.py` | Orquesta las tres consignas. Punto de entrada. |
| `validar_local.py` | Valida los recursos contra los modelos FHIR sin salir a la red. |

---

## Consigna 3.a — Patient con documento como identifier

Se crea el `Patient` agregando el DNI en `Patient.identifier`. El punto
importante es que un `Identifier` en FHIR **no es un número suelto**: es el par
`(system, value)`. El `system` declara el dominio de identificación, y por eso
el mismo número en dos `system` distintos identifica a dos cosas distintas.

Se usa el namespace que la guía de implementación argentina define para el DNI
emitido por RENAPER:

```json
"identifier": [{
  "use": "official",
  "system": "http://www.renaper.gob.ar/dni",
  "type": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
      "code": "NI",
      "display": "National unique individual identifier"
    }],
    "text": "DNI"
  },
  "value": "38765434"
}]
```

Esto es lo que permite que cualquier nodo de la Red Nacional de Salud Digital
interprete el identificador sin ambigüedad: dos sistemas distintos pueden saber
que ese número es un DNI argentino, y no un número de afiliado ni una historia
clínica interna.

### ID lógico vs. identifier

| | ID lógico | identifier |
|---|---|---|
| Quién lo asigna | El servidor FHIR | El sistema de origen (RENAPER, el laboratorio) |
| Alcance | Único **dentro de ese servidor** | Único dentro de su `system` |
| Al migrar de servidor | Cambia | Se mantiene |
| Dónde aparece | En la URL del recurso | En el cuerpo del recurso |

## Consigna 3.b — Búsqueda por documento

```
GET https://hapi.fhir.org/baseR4/Patient?identifier=http://www.renaper.gob.ar/dni|38765434
```

El parámetro de búsqueda `identifier` acepta dos formas: solo el valor
(`identifier=38765434`) o `system|valor`. **Se usa la segunda**, porque sin el
`system` se podrían traer pacientes de otro dominio de identificación que
casualmente tengan el mismo número — algo muy probable en un servidor público
de pruebas donde escriben cientos de usuarios.

El servidor responde un `Bundle` de tipo `searchset`, y los recursos vienen en
`entry[].resource`.

---

## Consigna 3.c — DiagnosticReport (recurso del Grupo 8)

### Qué es y para qué se usa

`DiagnosticReport` representa **los hallazgos y la interpretación de estudios
diagnósticos** realizados sobre un paciente, un grupo de pacientes,
dispositivos o lugares, y/o sobre muestras derivadas de estos. Es el recurso
con el que se modelan los informes de **laboratorio, anatomía patológica e
imágenes**.

Su razón de ser es que un informe diagnóstico **no es solo una lista de
valores**: es el conjunto de información que un servicio diagnóstico entrega
cuando termina el estudio, e incluye contexto clínico (quién lo pidió, quién lo
realizó, sobre qué muestra) junto con una mezcla de resultados atómicos,
imágenes, interpretaciones textuales y codificadas, y el informe formateado tal
como fue emitido.

Por eso el recurso cumple el rol de **organizador**: agrupa por referencia los
resultados individuales (`Observation`), les agrega el contexto y la firma
clínica, y los presenta como una unidad entregable.

```
                    DiagnosticReport  (el informe: contexto + firma + conclusión)
                            │
                     result │ 0..*
                            ▼
      Observation   Observation   Observation   Observation
      Hemoglobina   Hematocrito   Leucocitos    Plaquetas
         (el dato atómico: analito + valor + unidad)
```

### Dónde termina su alcance

| Recurso | Cuándo corresponde ese y no DiagnosticReport |
|---|---|
| `Observation` | El dato atómico individual. `DiagnosticReport` lo **referencia**, no lo reemplaza. |
| `Composition` | Informes más narrativos y con menos workflow. Si el informe es altamente estructurado, corresponde `DiagnosticReport`, que tiene soporte de datos y de workflow. |
| `ServiceRequest` | La **solicitud** del estudio (la orden). Se referencia desde `DiagnosticReport.basedOn`. |
| `Procedure` | El procedimiento que generó las observaciones, cuando interesa documentar *cómo* se realizó. |
| `DocumentReference` | Un objeto no-FHIR (un PDF escaneado, un CDA). Si hay datos discretos, va `DiagnosticReport` con el PDF adjunto en `presentedForm`. |

### Elementos del recurso

| Elemento | Card. | Tipo | Para qué sirve |
|---|---|---|---|
| `identifier` | 0..* | Identifier | Nro. de protocolo del laboratorio |
| `basedOn` | 0..* | Reference | La orden que originó el estudio (`ServiceRequest`) |
| **`status`** | **1..1** | code | **Obligatorio.** Estado del informe. Elemento *modificador* |
| `category` | 0..* | CodeableConcept | Sección del servicio diagnóstico (hematología, etc.) |
| **`code`** | **1..1** | CodeableConcept | **Obligatorio.** Qué informe es (LOINC) |
| `subject` | 0..1 | Reference | Paciente / grupo / dispositivo / lugar |
| `encounter` | 0..1 | Reference | Contacto asistencial en que se generó |
| `effective[x]` | 0..1 | dateTime \| Period | Momento clínicamente relevante (toma de muestra) |
| `issued` | 0..1 | instant | Cuándo se emitió esta versión |
| `performer` | 0..* | Reference | Responsable del informe |
| `resultsInterpreter` | 0..* | Reference | Quién interpretó los resultados clínicamente |
| `specimen` | 0..* | Reference | Muestras analizadas |
| `result` | 0..* | Reference | **`Observation` con los resultados atómicos** |
| `imagingStudy` | 0..* | Reference | Estudios DICOM asociados |
| `media` | 0..* | BackboneElement | Imágenes clave del informe |
| `conclusion` | 0..1 | string | Interpretación clínica en texto libre |
| `conclusionCode` | 0..* | CodeableConcept | La misma interpretación, codificada (SNOMED CT) |
| `presentedForm` | 0..* | Attachment | El informe completo tal como fue emitido (PDF) |

Dos observaciones sobre elementos que suelen confundirse:

- **`effective[x]` vs. `issued`.** El primero es cuándo se tomó la muestra —
  el dato que importa para interpretar el resultado. El segundo es cuándo se
  publicó el informe. Pueden diferir en días.
- **`performer` vs. `resultsInterpreter`.** `performer` es quien realizó o fue
  responsable del procedimiento diagnóstico; `resultsInterpreter` es quien fue
  responsable de la interpretación clínica de los resultados. Pueden ser
  personas distintas.

### `status`: valores posibles

Binding **requerido** al value set `DiagnosticReportStatus` (los códigos
*SHALL* tomarse de ahí):

`registered` · `partial` · `preliminary` · `final` · `amended` · `corrected` ·
`appended` · `cancelled` · `entered-in-error` · `unknown`

Es un **elemento modificador**: el valor `entered-in-error` invierte el
significado clínico de todo el recurso, así que un sistema receptor no puede
ignorarlo.

### Terminologías usadas en el ejemplo

| Elemento | Sistema | Código |
|---|---|---|
| `code` | LOINC | `58410-2` — CBC panel - Blood by Automated count |
| `category` | HL7 v2-0074 | `HM` (Hematology), `LAB` (Laboratory) |
| `conclusionCode` | SNOMED CT | `271737000` — Anemia |
| `Observation.code` | LOINC | `718-7`, `4544-3`, `6690-2`, `777-3` |
| `Observation.valueQuantity` | UCUM | `g/dL`, `%`, `10*3/uL` |
| `Observation.interpretation` | HL7 v3-ObservationInterpretation | `L` (Low), `N` (Normal) |

El `conclusionCode` es lo que marca la diferencia entre un informe **legible** y
un informe **procesable**: con la conclusión codificada en SNOMED CT, un sistema
puede detectar automáticamente que el paciente tiene anemia sin tener que
interpretar el texto libre.

### Caso implementado

Un hemograma completo con cuatro resultados, dos de ellos por debajo del rango
de referencia:

| Analito | LOINC | Valor | Ref. | Interp. |
|---|---|---|---|---|
| Hemoglobina | 718-7 | 10,2 g/dL | 12–16 | `L` |
| Hematocrito | 4544-3 | 31 % | 36–46 | `L` |
| Leucocitos | 6690-2 | 7,5 ×10³/µL | 4,5–11 | `N` |
| Plaquetas | 777-3 | 250 ×10³/µL | 150–450 | `N` |

**Orden de creación.** Como `DiagnosticReport.result` guarda *referencias*, las
`Observation` tienen que existir en el servidor **antes** del informe, para
poder referenciarlas por su ID lógico. El script hace:

1. `POST /Observation` × 4 → guarda los IDs lógicos devueltos
2. `POST /DiagnosticReport` con `result` apuntando a esos IDs
3. `GET /DiagnosticReport/{id}` → lee el informe
4. `GET /DiagnosticReport?_id={id}&_include=DiagnosticReport:result` → lee el
   informe **con sus `Observation` resueltas en el mismo Bundle**, en lugar de
   hacer un GET por cada una

El paso 4 muestra una de las ventajas de la API REST de FHIR: `_include` le pide
al servidor que traiga los recursos referenciados en la misma respuesta.

---

## Referencias

- [HL7 FHIR R4 — DiagnosticReport](https://hl7.org/fhir/R4/diagnosticreport.html)
- [HL7 FHIR R4 — Lista de recursos](https://hl7.org/fhir/resourcelist.html)
- [HAPI FHIR](https://hapifhir.io/hapi-fhir/)
- [Ministerio de Salud — Estándares de la Red Nacional de Salud Digital](https://www.argentina.gob.ar/salud/digital/estandares)
- [Guías de implementación FHIR de la Red (openRSD)](https://openrsd.msal.gov.ar/)
- [LOINC 58410-2](https://loinc.org/58410-2)
- Repositorio base de la cátedra: [euberrino/FHIR-basics](https://github.com/euberrino/FHIR-basics)
