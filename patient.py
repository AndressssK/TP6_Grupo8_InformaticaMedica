"""
patient.py — Construccion del recurso FHIR Patient.

Extiende el modulo `patient.py` del repo de la catedra agregando el elemento
`identifier` con el numero de documento (DNI), requerido por la consigna 3.a.

El `system` del identifier usa el namespace que la guia de implementacion
argentina define para el DNI emitido por RENAPER
(http://www.renaper.gob.ar/dni), con el tipo de identificador 'NI'
(National unique individual identifier) del code system v2-0203 de HL7.
De esta forma el identificador queda univocamente interpretable por
cualquier nodo de la Red Nacional de Salud Digital: dos sistemas distintos
pueden saber que '30123456' es un DNI argentino y no un numero de afiliado
o una historia clinica interna.

TP6 - Interoperabilidad | Grupo 8 (DiagnosticReport)
Bioingenieria - 16.22 Informatica Medica
"""

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.contactpoint import ContactPoint
from fhir.resources.humanname import HumanName
from fhir.resources.identifier import Identifier
from fhir.resources.patient import Patient

# Namespace del DNI argentino (RENAPER) segun la guia de implementacion nacional
SYSTEM_DNI_ARG = "http://www.renaper.gob.ar/dni"
# Code system de tipos de identificador de HL7 (tabla v2-0203)
SYSTEM_TIPO_ID = "http://terminology.hl7.org/CodeSystem/v2-0203"


def crear_identifier_dni(numero_documento):
    """
    Construye el tipo de dato Identifier para un DNI argentino.

    Un Identifier no es solo un numero: es el par (system, value). El `system`
    declara el dominio de identificacion, y por eso el mismo numero en dos
    `system` distintos identifica a dos cosas distintas.
    """
    identifier = Identifier()
    identifier.use = "official"
    identifier.system = SYSTEM_DNI_ARG
    identifier.value = str(numero_documento)

    # type: describe QUE clase de identificador es, de forma codificada
    tipo = CodeableConcept()
    coding = Coding()
    coding.system = SYSTEM_TIPO_ID
    coding.code = "NI"  # National unique individual identifier
    coding.display = "National unique individual identifier"
    tipo.coding = [coding]
    tipo.text = "DNI"
    identifier.type = tipo

    return identifier


def create_patient_resource(
    family_name=None,
    given_name=None,
    birth_date=None,
    gender=None,
    phone=None,
    documento=None,
):
    """
    Crea el recurso FHIR Patient con parametros opcionales.

    Parametros
    ----------
    family_name : str   apellido          -> Patient.name.family
    given_name  : str   nombre            -> Patient.name.given
    birth_date  : str   'YYYY-MM-DD'      -> Patient.birthDate (tipo date)
    gender      : str   male|female|other|unknown -> Patient.gender (tipo code)
    phone       : str   telefono          -> Patient.telecom (tipo ContactPoint)
    documento   : str   DNI               -> Patient.identifier (tipo Identifier)
    """
    patient = Patient()

    # identifier: identificador de negocio del paciente (DNI).
    # A diferencia del ID logico, que lo asigna el servidor, este viaja con el
    # recurso y es el que permite buscar al paciente entre sistemas distintos.
    if documento:
        patient.identifier = [crear_identifier_dni(documento)]

    # name: tipo de dato HumanName (apellido + nombres de pila)
    if family_name or given_name:
        name = HumanName()
        name.use = "official"
        if family_name:
            name.family = family_name
        if given_name:
            name.given = [given_name]
        patient.name = [name]

    # birthDate: tipo de dato date
    if birth_date:
        patient.birthDate = birth_date

    # gender: tipo de dato code, con binding requerido a AdministrativeGender
    if gender:
        patient.gender = gender

    # telecom: tipo de dato ContactPoint
    if phone:
        contact = ContactPoint()
        contact.system = "phone"
        contact.value = phone
        contact.use = "mobile"
        patient.telecom = [contact]

    # active: indica si el registro del paciente esta en uso
    patient.active = True

    return patient


def buscar_paciente_por_documento(numero_documento, incluir_system=True):
    """
    Consigna 3.b — Metodo que permite buscar pacientes por documento.

    Arma los parametros del search FHIR y delega el GET en base.py. El
    parametro de busqueda estandar para Patient.identifier se llama
    'identifier' y acepta dos formas:

        identifier=30123456                     -> busca por valor solo
        identifier=<system>|30123456            -> busca por system + valor

    La segunda es la correcta: sin el `system` se podrian traer pacientes de
    otro dominio de identificacion que casualmente tengan el mismo numero
    (algo muy probable en un servidor publico de pruebas como el de HAPI,
    donde escriben cientos de usuarios).

    Devuelve una lista de recursos Patient que cumplen el criterio.
    """
    from base import search_resource_in_hapi_fhir

    if incluir_system:
        valor_busqueda = f"{SYSTEM_DNI_ARG}|{numero_documento}"
    else:
        valor_busqueda = str(numero_documento)

    bundle = search_resource_in_hapi_fhir(
        "Patient",
        {"identifier": valor_busqueda},
        guardar_como=f"3b_busqueda_dni_{numero_documento}.json",
    )

    if not bundle:
        return []

    # El servidor responde un Bundle searchset; los recursos vienen en entry[]
    encontrados = [
        entry["resource"]
        for entry in bundle.get("entry", [])
        if entry.get("resource", {}).get("resourceType") == "Patient"
    ]

    print(f"\n   Pacientes encontrados con DNI {numero_documento}: {len(encontrados)}")
    for p in encontrados:
        nombres = p.get("name", [{}])[0]
        nombre_completo = " ".join(
            nombres.get("given", []) + [nombres.get("family", "")]
        ).strip()
        print(f"     - Patient/{p.get('id')} | {nombre_completo or '(sin nombre)'}")

    return encontrados
