"""
diagnostic_report.py — Consigna 3.c | GRUPO 8: recurso DiagnosticReport.

QUE ES Y PARA QUE SE USA
------------------------
DiagnosticReport representa los hallazgos y la interpretacion de estudios
diagnosticos realizados sobre un paciente, un grupo de pacientes, dispositivos
o lugares, y/o sobre muestras derivadas de estos. Es el recurso con el que se
modelan los informes de laboratorio, anatomia patologica e imagenes.

Su razon de ser es que un informe diagnostico NO es solo una lista de valores:
es el conjunto de informacion que un servicio diagnostico entrega cuando
termina el estudio, e incluye contexto clinico (quien lo pidio, quien lo hizo,
sobre que muestra) junto con una mezcla de resultados atomicos, imagenes,
interpretaciones textuales y codificadas, y el informe formateado tal como
fue emitido.

Por eso el recurso cumple el rol de "organizador": agrupa por referencia los
resultados individuales (Observation), les agrega el contexto y la firma
clinica, y los presenta como una unidad entregable.

DONDE TERMINA SU ALCANCE
------------------------
  - Observation      -> el dato atomico individual. DiagnosticReport lo
                        referencia; no lo reemplaza.
  - Composition      -> informes mas narrativos y con menos workflow. Si el
                        informe es altamente estructurado, corresponde
                        DiagnosticReport, que tiene soporte de datos y de
                        workflow.
  - ServiceRequest   -> la solicitud del estudio (la orden). Se referencia
                        desde DiagnosticReport.basedOn.
  - Procedure        -> el procedimiento que genero las observaciones, cuando
                        interesa documentar como se realizo.
  - DocumentReference-> un objeto no-FHIR (un PDF escaneado, un CDA). Si hay
                        datos discretos, va DiagnosticReport con el PDF
                        adjunto en presentedForm.

EJEMPLO IMPLEMENTADO
--------------------
Un hemograma completo (LOINC 58410-2) con cuatro resultados, de los cuales dos
estan por debajo del rango de referencia, y una conclusion codificada en
SNOMED CT.

TP6 - Interoperabilidad | Grupo 8
Bioingenieria - 16.22 Informatica Medica
"""

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.identifier import Identifier
from fhir.resources.reference import Reference

SYSTEM_LOINC = "http://loinc.org"
SYSTEM_SNOMED = "http://snomed.info/sct"
# Secciones del servicio diagnostico (tabla v2-0074 de HL7)
SYSTEM_SECCION_SERVICIO = "http://terminology.hl7.org/CodeSystem/v2-0074"

# LOINC del panel: hemograma completo automatizado
LOINC_HEMOGRAMA = "58410-2"
NOMBRE_HEMOGRAMA = "CBC panel - Blood by Automated count"


def _codeable(system, code, display, texto=None):
    cc = CodeableConcept()
    coding = Coding()
    coding.system = system
    coding.code = code
    coding.display = display
    cc.coding = [coding]
    cc.text = texto or display
    return cc


def create_diagnostic_report_resource(
    paciente_id,
    observation_ids,
    fecha_efectiva,
    fecha_emision,
    nro_protocolo=None,
    conclusion=None,
    codigo_conclusion_snomed=None,
    display_conclusion_snomed=None,
    status="final",
    especimen_ids=None,
    performer_display="Laboratorio Central - Hospital Escuela",
):
    """
    Construye el recurso DiagnosticReport del Grupo 8.

    Parametros
    ----------
    paciente_id       : str  ID logico del Patient (sujeto del informe)
    observation_ids   : list IDs logicos de las Observation a agrupar
    fecha_efectiva    : str  datetime clinicamente relevante (toma de muestra)
    fecha_emision     : str  instant en que el informe fue emitido
    nro_protocolo     : str  numero de protocolo del laboratorio (identifier)
    conclusion        : str  interpretacion clinica en texto libre
    codigo_conclusion_snomed : str  la misma conclusion, codificada
    status            : str  registered|partial|preliminary|final|amended|...
    """
    # -----------------------------------------------------------------
    # status y code son los dos elementos OBLIGATORIOS (1..1) del recurso,
    # por lo que fhir.resources los exige en el constructor: no se puede
    # crear un DiagnosticReport() vacio y asignarlos despues (pydantic lanza
    # ValidationError 'field required'). Esa validacion local es deseable:
    # evita enviar al servidor un recurso que no cumple el estandar.
    #
    #   status (1..1, code)            — estado del informe como un todo.
    #     Binding REQUERIDO al value set DiagnosticReportStatus: los codigos
    #     SHALL tomarse de ahi (registered | partial | preliminary | final,
    #     y ademas amended, corrected, appended, cancelled,
    #     entered-in-error, unknown). Es un elemento MODIFICADOR: el valor
    #     'entered-in-error' invierte el significado clinico de todo el
    #     recurso, por eso un receptor no puede ignorarlo.
    #
    #   code (1..1, CodeableConcept)   — QUE informe es.
    #     Binding 'preferred' a LOINCDiagnosticReportCodes: se recomienda
    #     LOINC. Sin este codigo el receptor recibe un informe que no sabe
    #     clasificar.
    # -----------------------------------------------------------------
    reporte = DiagnosticReport(
        status=status,
        code=_codeable(
            SYSTEM_LOINC, LOINC_HEMOGRAMA, NOMBRE_HEMOGRAMA, "Hemograma completo"
        ),
    )

    # -----------------------------------------------------------------
    # identifier (0..*) — identificador de negocio del informe.
    # Es el numero de protocolo con el que el laboratorio conoce al informe,
    # distinto del ID logico que asigna el servidor FHIR.
    # -----------------------------------------------------------------
    if nro_protocolo:
        ident = Identifier()
        ident.use = "official"
        ident.system = "http://hospital-escuela.example.org/protocolos"
        ident.value = str(nro_protocolo)
        reporte.identifier = [ident]

    # -----------------------------------------------------------------
    # category (0..*) — seccion del servicio diagnostico que lo produjo.
    # Binding de tipo 'example' a DiagnosticServiceSectionCodes.
    # Sirve para filtrar: "traeme los informes de hematologia del paciente".
    # -----------------------------------------------------------------
    reporte.category = [
        _codeable(SYSTEM_SECCION_SERVICIO, "HM", "Hematology", "Hematologia"),
        _codeable(SYSTEM_SECCION_SERVICIO, "LAB", "Laboratory", "Laboratorio"),
    ]

    # -----------------------------------------------------------------
    # subject (0..1) — DE QUIEN es el informe. En la practica, siempre
    # presente: un informe sin paciente no es utilizable clinicamente.
    # -----------------------------------------------------------------
    sujeto = Reference()
    sujeto.reference = f"Patient/{paciente_id}"
    reporte.subject = sujeto

    # -----------------------------------------------------------------
    # effectiveDateTime (0..1) — momento clinicamente relevante: cuando se
    # tomo la muestra, NO cuando se emitio el informe. Es el dato que importa
    # para interpretar el resultado.
    # -----------------------------------------------------------------
    reporte.effectiveDateTime = fecha_efectiva

    # -----------------------------------------------------------------
    # issued (0..1) — cuando esta version del informe se puso a disposicion.
    # Tipo de dato 'instant': exige precision de segundos y zona horaria.
    # -----------------------------------------------------------------
    reporte.issued = fecha_emision

    # -----------------------------------------------------------------
    # performer (0..*) — quien es responsable del informe.
    # Se distingue de resultsInterpreter, que es quien interpreto los
    # resultados clinicamente (puede ser otra persona).
    # -----------------------------------------------------------------
    ejecutor = Reference()
    ejecutor.display = performer_display
    reporte.performer = [ejecutor]

    # -----------------------------------------------------------------
    # specimen (0..*) — muestras sobre las que se hizo el estudio.
    # -----------------------------------------------------------------
    if especimen_ids:
        reporte.specimen = [
            _referencia(f"Specimen/{sid}") for sid in especimen_ids
        ]

    # -----------------------------------------------------------------
    # result (0..*) — EL ELEMENTO CENTRAL. Referencias a las Observation
    # con los resultados atomicos. Aca se ve el rol de organizador del
    # recurso: el informe no copia los valores, los agrupa por referencia.
    # -----------------------------------------------------------------
    if observation_ids:
        reporte.result = [
            _referencia(f"Observation/{oid}") for oid in observation_ids
        ]

    # -----------------------------------------------------------------
    # conclusion (0..1) — interpretacion clinica en texto libre.
    # -----------------------------------------------------------------
    if conclusion:
        reporte.conclusion = conclusion

    # -----------------------------------------------------------------
    # conclusionCode (0..*) — la misma conclusion, pero codificada.
    # Esto es lo que hace la diferencia entre un informe legible y un
    # informe procesable: con SNOMED CT un sistema puede detectar
    # automaticamente que este paciente tiene anemia, sin leer el texto.
    # -----------------------------------------------------------------
    if codigo_conclusion_snomed:
        reporte.conclusionCode = [
            _codeable(
                SYSTEM_SNOMED,
                codigo_conclusion_snomed,
                display_conclusion_snomed or "",
            )
        ]

    return reporte


def _referencia(url_relativa, display=None):
    """Crea un tipo de dato Reference a partir de una URL relativa."""
    ref = Reference()
    ref.reference = url_relativa
    if display:
        ref.display = display
    return ref


# ---------------------------------------------------------------------------
# Resumen de los elementos del recurso, para el informe y la presentacion
# ---------------------------------------------------------------------------
ELEMENTOS_DIAGNOSTICREPORT = [
    ("identifier", "0..*", "Identifier", "Nro. de protocolo del laboratorio"),
    ("basedOn", "0..*", "Reference", "La orden que origino el estudio (ServiceRequest)"),
    ("status", "1..1", "code", "OBLIGATORIO. Estado del informe. Modificador"),
    ("category", "0..*", "CodeableConcept", "Seccion del servicio (hematologia, etc.)"),
    ("code", "1..1", "CodeableConcept", "OBLIGATORIO. Que informe es (LOINC)"),
    ("subject", "0..1", "Reference", "Paciente / grupo / dispositivo / lugar"),
    ("encounter", "0..1", "Reference", "Contacto asistencial en que se genero"),
    ("effective[x]", "0..1", "dateTime | Period", "Momento clinicamente relevante"),
    ("issued", "0..1", "instant", "Cuando se emitio esta version"),
    ("performer", "0..*", "Reference", "Responsable del informe"),
    ("resultsInterpreter", "0..*", "Reference", "Quien interpreto los resultados"),
    ("specimen", "0..*", "Reference", "Muestras analizadas"),
    ("result", "0..*", "Reference", "Observation con los resultados atomicos"),
    ("imagingStudy", "0..*", "Reference", "Estudios de imagenes DICOM asociados"),
    ("media", "0..*", "BackboneElement", "Imagenes clave del informe"),
    ("conclusion", "0..1", "string", "Interpretacion clinica en texto"),
    ("conclusionCode", "0..*", "CodeableConcept", "Interpretacion codificada (SNOMED)"),
    ("presentedForm", "0..*", "Attachment", "El informe completo tal como se emitio"),
]


def imprimir_tabla_elementos():
    """Imprime la tabla de elementos del recurso (util para el informe)."""
    print("\n" + "=" * 78)
    print("ELEMENTOS DEL RECURSO DiagnosticReport (FHIR R4)")
    print("=" * 78)
    print(f"{'Elemento':<20}{'Card.':<8}{'Tipo':<22}{'Para que sirve'}")
    print("-" * 78)
    for nombre, card, tipo, descripcion in ELEMENTOS_DIAGNOSTICREPORT:
        print(f"{nombre:<20}{card:<8}{tipo:<22}{descripcion}")
    print("=" * 78)
