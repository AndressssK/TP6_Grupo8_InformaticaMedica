"""
base.py — Comunicacion con el servidor publico de HAPI FHIR via API REST.

Extiende el modulo `base.py` del repo de la catedra (euberrino/FHIR-basics)
agregando: busqueda por parametros (GET con query string), manejo de errores
mas robusto y guardado de las respuestas JSON en disco para el informe.

TP6 - Interoperabilidad | Grupo 8 (DiagnosticReport)
Bioingenieria - 16.22 Informatica Medica
"""

import json
import os

import requests

# Endpoint: ubicacion del servicio web donde corre el servidor FHIR.
# La identidad de un recurso FHIR es: BASE_URL / {tipo de recurso} / {id logico}
#
# IMPORTANTE: el esquema tiene que ser HTTPS, no HTTP.
# hapi.fhir.org responde a http:// con una redireccion 301 hacia https://.
# requests sigue esa redireccion, pero ante un 301 convierte el POST en GET y
# descarta el cuerpo del mensaje (es el comportamiento estandar, heredado de
# los navegadores). El resultado es que un POST contra http:// llega al
# servidor convertido en una busqueda: devuelve 200 con un Bundle en lugar de
# 201 con el recurso creado, y la creacion falla sin un error evidente.
# Los GET funcionan igual con los dos esquemas, lo que hace el sintoma
# todavia mas confuso: se puede leer y buscar, pero no crear.
BASE_URL = "https://hapi.fhir.org/baseR4"

HEADERS_POST = {
    "Content-Type": "application/fhir+json",
    "Accept": "application/fhir+json",
}
HEADERS_GET = {"Accept": "application/fhir+json"}

TIMEOUT = 60  # el servidor publico de HAPI a veces tarda
CARPETA_SALIDAS = "salidas"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _guardar_json(nombre_archivo, contenido):
    """Guarda un JSON en ./salidas/ para poder adjuntarlo al informe."""
    os.makedirs(CARPETA_SALIDAS, exist_ok=True)
    ruta = os.path.join(CARPETA_SALIDAS, nombre_archivo)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(contenido, f, indent=2, ensure_ascii=False)
    print(f"   [guardado] {ruta}")


def _a_json_dict(recurso):
    """
    Convierte un recurso de fhir.resources a dict.

    fhir.resources 6.1.0 esta construido sobre pydantic 1.x, donde el metodo
    es .dict(); se usa exclude_none=True para no enviar al servidor los
    elementos vacios (FHIR exige que todo elemento presente tenga valor).
    """
    return json.loads(recurso.json(exclude_none=True))


# ---------------------------------------------------------------------------
# CREATE  ->  POST [base]/{tipo}
# ---------------------------------------------------------------------------
def send_resource_to_hapi_fhir(resource, resource_type, guardar_como=None):
    """
    Crea (CREATE) un recurso en el servidor. El servidor asigna el ID logico.

    Devuelve el ID logico asignado, o None si fallo.
    """
    url = f"{BASE_URL}/{resource_type}"
    payload = resource.json(exclude_none=True)

    print(f"\n>> POST {url}")
    try:
        response = requests.post(
            url, headers=HEADERS_POST, data=payload.encode("utf-8"), timeout=TIMEOUT
        )
    except requests.exceptions.RequestException as e:
        print(f"   ERROR de conexion: {e}")
        return None

    if response.status_code == 201:
        cuerpo = response.json()
        resource_id = cuerpo["id"]
        print(f"   OK 201 Created -> {resource_type}/{resource_id}")
        print(f"   URL del recurso: {BASE_URL}/{resource_type}/{resource_id}")
        if guardar_como:
            _guardar_json(guardar_como, cuerpo)
        return resource_id

    # Diagnostico de la redireccion descrita arriba: si la respuesta pasa por
    # un 301/302, el POST llego al servidor convertido en GET y el cuerpo se
    # perdio. Sin este aviso el sintoma es un 200 inexplicable.
    if response.history:
        saltos = " -> ".join(str(r.status_code) for r in response.history)
        print(f"   ERROR: la peticion fue redirigida ({saltos}) y el POST se "
              "convirtio en GET, por lo que el recurso NO se creo.")
        print(f"   URL pedida:  {url}")
        print(f"   URL final:   {response.url}")
        print("   Causa probable: BASE_URL usa http:// en lugar de https://")
        return None

    print(f"   ERROR al crear el recurso: HTTP {response.status_code}")
    print(_texto_de_error(response))
    return None


# ---------------------------------------------------------------------------
# READ  ->  GET [base]/{tipo}/{id}
# ---------------------------------------------------------------------------
def get_resource_from_hapi_fhir(resource_id, resource_type, guardar_como=None):
    """
    Lee (READ) un recurso por su ID logico y lo imprime formateado.

    Devuelve el recurso como dict, o None si fallo.
    """
    url = f"{BASE_URL}/{resource_type}/{resource_id}"

    print(f"\n>> GET {url}")
    try:
        response = requests.get(url, headers=HEADERS_GET, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"   ERROR de conexion: {e}")
        return None

    if response.status_code == 200:
        recurso = response.json()
        print("   OK 200 -> recurso leido:")
        print(json.dumps(recurso, indent=2, ensure_ascii=False))
        if guardar_como:
            _guardar_json(guardar_como, recurso)
        return recurso

    print(f"   ERROR al obtener el recurso: HTTP {response.status_code}")
    print(_texto_de_error(response))
    return None


# ---------------------------------------------------------------------------
# SEARCH  ->  GET [base]/{tipo}?parametro=valor
# ---------------------------------------------------------------------------
def search_resource_in_hapi_fhir(resource_type, parametros, guardar_como=None):
    """
    Busca (SEARCH) recursos de un tipo segun parametros de busqueda FHIR.

    El servidor responde con un Bundle de tipo 'searchset': una coleccion
    donde cada entry.resource es un recurso que cumple el criterio.

    Ejemplo:
        search_resource_in_hapi_fhir("Patient", {"identifier": "12345678"})

    Devuelve el Bundle como dict, o None si fallo.
    """
    url = f"{BASE_URL}/{resource_type}"

    print(f"\n>> GET {url} | parametros = {parametros}")
    try:
        response = requests.get(
            url, headers=HEADERS_GET, params=parametros, timeout=TIMEOUT
        )
    except requests.exceptions.RequestException as e:
        print(f"   ERROR de conexion: {e}")
        return None

    if response.status_code == 200:
        bundle = response.json()
        print(f"   OK 200 -> URL efectiva: {response.url}")
        print(f"   Bundle.type = {bundle.get('type')}")
        print(f"   Bundle.total = {bundle.get('total', 'no informado')}")
        if guardar_como:
            _guardar_json(guardar_como, bundle)
        return bundle

    print(f"   ERROR en la busqueda: HTTP {response.status_code}")
    print(_texto_de_error(response))
    return None


def _texto_de_error(response):
    """
    Extrae el detalle de un OperationOutcome, el recurso que FHIR usa para
    comunicar errores de validacion o de procesamiento.
    """
    try:
        cuerpo = response.json()
    except ValueError:
        return response.text[:1000]

    if cuerpo.get("resourceType") == "OperationOutcome":
        lineas = []
        for issue in cuerpo.get("issue", []):
            severidad = issue.get("severity", "?")
            codigo = issue.get("code", "?")
            detalle = issue.get("diagnostics") or issue.get("details", {}).get("text", "")
            lineas.append(f"   [{severidad}/{codigo}] {detalle}")
        return "\n".join(lineas) if lineas else json.dumps(cuerpo, indent=2)

    return json.dumps(cuerpo, indent=2, ensure_ascii=False)[:1000]
