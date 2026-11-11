"""
observation.py — Construccion de recursos FHIR Observation (resultados atomicos).

Las Observation son los resultados individuales de un estudio: un analito, un
valor, una unidad. El DiagnosticReport NO guarda los valores: los agrupa por
referencia a traves de su elemento `result`. Esta division de
responsabilidades es la clave del modelo de diagnosticos de FHIR:

    Observation    = el dato atomico   ("Hemoglobina = 10.2 g/dL")
    DiagnosticReport = el informe       ("Hemograma del 10/11/2026, firmado
                                          por el bioquimico X, conclusion: anemia")

Se usan codigos LOINC para identificar cada analito (asi dos laboratorios
distintos pueden decir "hemoglobina" de la misma manera) y unidades UCUM
para que el valor sea comparable sin ambiguedad.

TP6 - Interoperabilidad | Grupo 8 (DiagnosticReport)
Bioingenieria - 16.22 Informatica Medica
"""

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.observation import Observation, ObservationReferenceRange
from fhir.resources.quantity import Quantity
from fhir.resources.reference import Reference

SYSTEM_LOINC = "http://loinc.org"
SYSTEM_UCUM = "http://unitsofmeasure.org"
SYSTEM_CATEGORIA_OBS = "http://terminology.hl7.org/CodeSystem/observation-category"
SYSTEM_INTERPRETACION = "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"


def _codeable(system, code, display, texto=None):
    """Arma un CodeableConcept de un solo Coding."""
    cc = CodeableConcept()
    coding = Coding()
    coding.system = system
    coding.code = code
    coding.display = display
    cc.coding = [coding]
    cc.text = texto or display
    return cc


def crear_observation(
    codigo_loinc,
    nombre_analito,
    valor,
    unidad_ucum,
    unidad_legible,
    paciente_id,
    fecha_efectiva,
    rango_min=None,
    rango_max=None,
    interpretacion=None,
):
    """
    Crea una Observation de laboratorio lista para enviar al servidor.

    Parametros
    ----------
    codigo_loinc    : str   codigo LOINC del analito      -> Observation.code
    valor           : float resultado numerico            -> valueQuantity.value
    unidad_ucum     : str   unidad en sintaxis UCUM        -> valueQuantity.code
    paciente_id     : str   ID logico del Patient          -> Observation.subject
    interpretacion  : str   'N' normal | 'L' bajo | 'H' alto
    """
    # status y code son obligatorios (1..1) en Observation, por lo que
    # fhir.resources los exige en el constructor: si se intentara crear un
    # Observation() vacio y asignarlos despues, pydantic lanza
    # ValidationError 'field required'. Esta validacion local es util: atrapa
    # el error antes de mandar un recurso invalido al servidor.
    #
    #   status : 'final' = resultado validado y definitivo
    #   code   : QUE se midio, codificado en LOINC
    obs = Observation(
        status="final",
        code=_codeable(SYSTEM_LOINC, codigo_loinc, nombre_analito),
    )

    # category: clasifica la observacion a alto nivel (de laboratorio)
    obs.category = [
        _codeable(SYSTEM_CATEGORIA_OBS, "laboratory", "Laboratory", "Laboratorio")
    ]

    # subject: sobre QUIEN. Referencia al recurso Patient por su URL relativa.
    sujeto = Reference()
    sujeto.reference = f"Patient/{paciente_id}"
    obs.subject = sujeto

    # effectiveDateTime: cuando fue clinicamente relevante (toma de muestra)
    obs.effectiveDateTime = fecha_efectiva

    # valueQuantity: el resultado, con valor + unidad codificada en UCUM
    cantidad = Quantity()
    cantidad.value = valor
    cantidad.unit = unidad_legible
    cantidad.system = SYSTEM_UCUM
    cantidad.code = unidad_ucum
    obs.valueQuantity = cantidad

    # referenceRange: rango de referencia del laboratorio para interpretar
    if rango_min is not None or rango_max is not None:
        rango = ObservationReferenceRange()
        if rango_min is not None:
            q_min = Quantity()
            q_min.value = rango_min
            q_min.unit = unidad_legible
            q_min.system = SYSTEM_UCUM
            q_min.code = unidad_ucum
            rango.low = q_min
        if rango_max is not None:
            q_max = Quantity()
            q_max.value = rango_max
            q_max.unit = unidad_legible
            q_max.system = SYSTEM_UCUM
            q_max.code = unidad_ucum
            rango.high = q_max
        obs.referenceRange = [rango]

    # interpretation: lectura codificada del resultado (normal, bajo, alto)
    if interpretacion:
        etiquetas = {"N": "Normal", "L": "Low", "H": "High"}
        obs.interpretation = [
            _codeable(
                SYSTEM_INTERPRETACION,
                interpretacion,
                etiquetas.get(interpretacion, interpretacion),
            )
        ]

    return obs


# ---------------------------------------------------------------------------
# Caso clinico de ejemplo: hemograma con anemia leve
# ---------------------------------------------------------------------------
# Cada tupla define un analito del hemograma:
#   (LOINC, nombre, valor, unidad UCUM, unidad legible, min, max, interpretacion)
# Los codigos LOINC son los componentes del panel 58410-2 (CBC panel - Blood
# by Automated count) y las unidades son las que LOINC sugiere para cada uno.
ANALITOS_HEMOGRAMA = [
    (
        "718-7",
        "Hemoglobin [Mass/volume] in Blood",
        10.2,
        "g/dL",
        "g/dL",
        12.0,
        16.0,
        "L",  # por debajo del rango -> hallazgo que sustenta la conclusion
    ),
    (
        "4544-3",
        "Hematocrit [Volume Fraction] of Blood by Automated count",
        31.0,
        "%",
        "%",
        36.0,
        46.0,
        "L",
    ),
    (
        "6690-2",
        "Leukocytes [#/volume] in Blood by Automated count",
        7.5,
        "10*3/uL",
        "10^3/uL",
        4.5,
        11.0,
        "N",
    ),
    (
        "777-3",
        "Platelets [#/volume] in Blood by Automated count",
        250.0,
        "10*3/uL",
        "10^3/uL",
        150.0,
        450.0,
        "N",
    ),
]


def crear_observations_hemograma(paciente_id, fecha_efectiva):
    """Crea las cuatro Observation del hemograma de ejemplo."""
    observaciones = []
    for (
        loinc,
        nombre,
        valor,
        ucum,
        legible,
        minimo,
        maximo,
        interp,
    ) in ANALITOS_HEMOGRAMA:
        observaciones.append(
            crear_observation(
                codigo_loinc=loinc,
                nombre_analito=nombre,
                valor=valor,
                unidad_ucum=ucum,
                unidad_legible=legible,
                paciente_id=paciente_id,
                fecha_efectiva=fecha_efectiva,
                rango_min=minimo,
                rango_max=maximo,
                interpretacion=interp,
            )
        )
    return observaciones
