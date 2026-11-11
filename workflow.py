"""
workflow.py — Punto de entrada. Resuelve la ACTIVIDAD 3 completa del TP6.

    3.a  Crear un Patient con numero de documento como identifier, y leerlo.
    3.b  Buscar pacientes por documento y encontrar el creado.
    3.c  Crear el recurso DiagnosticReport (recurso asignado al Grupo 8).

Uso:
    python workflow.py            # corre las tres consignas
    python workflow.py 3a         # corre solo una consigna
    python workflow.py 3c

Los JSON de todas las respuestas del servidor quedan en ./salidas/ para
adjuntarlos al informe.

TP6 - Interoperabilidad | Grupo 8 (DiagnosticReport)
Bioingenieria - 16.22 Informatica Medica
"""

import os
import sys
from datetime import datetime, timezone

from base import (
    BASE_URL,
    CARPETA_SALIDAS,
    get_resource_from_hapi_fhir,
    send_resource_to_hapi_fhir,
)
from diagnostic_report import (
    create_diagnostic_report_resource,
    imprimir_tabla_elementos,
)
from observation import crear_observations_hemograma
from patient import buscar_paciente_por_documento, create_patient_resource

# ---------------------------------------------------------------------------
# DATOS DEL CASO DE PRUEBA
# ---------------------------------------------------------------------------
# hapi.fhir.org es un servidor publico de pruebas: cualquiera escribe en el y
# los recursos se pueden purgar. Dos consecuencias practicas:
#   1) Si se corre el script varias veces, van quedando varios Patient con el
#      mismo DNI. Eso NO es un error: el search de 3.b los va a devolver a
#      todos, y es justamente lo que permite mostrar que la busqueda por
#      identifier funciona sobre el dominio de identificacion y no sobre el
#      ID logico.
#   2) Conviene correr 3.c en la misma corrida que 3.a, para que el Patient
#      referenciado por el informe exista con seguridad.
#   3) Los datos del paciente son FICTICIOS a proposito: el servidor advierte
#      en su pagina principal que no deben cargarse datos personales reales.
#      Es la misma paciente de las actividades 1 y 2, con un DNI distinto por
#      actividad para poder distinguir que herramienta creo cada registro:
#      actividad 1 -> 38765432, actividad 2 -> 38765433, actividad 3 -> 38765434.
APELLIDO = "Gomez"
NOMBRE = "Lucia"
FECHA_NACIMIENTO = "1995-03-22"
GENERO = "female"
TELEFONO = "+5491133445566"
DOCUMENTO = "38765434"

NRO_PROTOCOLO = "LAB-2026-004821"
CONCLUSION_TEXTO = (
    "Hemograma con hemoglobina y hematocrito por debajo del rango de "
    "referencia, con recuento leucocitario y plaquetario normales. "
    "Hallazgos compatibles con anemia leve. Se sugiere completar estudio "
    "con perfil de hierro."
)
# SNOMED CT 271737000 = Anemia (disorder)
SNOMED_CONCLUSION = "271737000"
SNOMED_CONCLUSION_DISPLAY = "Anemia"


def _ahora_iso():
    """Devuelve el instante actual con zona horaria, como exige el tipo instant."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Control de la corrida: limpieza previa y resumen final
# ---------------------------------------------------------------------------
# Sin esto, una corrida que falla a la mitad deja archivos mezclados con los de
# la corrida anterior y no hay forma de saber cual es de cual.
RECURSOS_CREADOS = []


def _limpiar_salidas():
    """
    Borra los JSON de corridas anteriores antes de empezar.

    Solo toca los .json y el RESUMEN.md que genera este script. No toca
    ningun otro archivo de la carpeta (por ejemplo consola.txt, que puede
    estar escribiendose en este momento).
    """
    if not os.path.isdir(CARPETA_SALIDAS):
        return

    borrados = 0
    for nombre in sorted(os.listdir(CARPETA_SALIDAS)):
        if nombre.endswith(".json") or nombre == "RESUMEN.md":
            os.remove(os.path.join(CARPETA_SALIDAS, nombre))
            borrados += 1

    if borrados:
        print(f"\n[limpieza] Se borraron {borrados} archivo(s) de corridas "
              f"anteriores en ./{CARPETA_SALIDAS}/")


def _registrar(tipo, recurso_id):
    """Anota un recurso creado, para el resumen final."""
    if recurso_id:
        RECURSOS_CREADOS.append((tipo, recurso_id))


def _escribir_resumen(inicio):
    """
    Escribe salidas/RESUMEN.md con los recursos creados en ESTA corrida.

    Es el archivo que se adjunta al informe: dice cuando se corrio, que se
    creo y con que URL se puede verificar cada recurso en el servidor.
    """
    os.makedirs(CARPETA_SALIDAS, exist_ok=True)
    ruta = os.path.join(CARPETA_SALIDAS, "RESUMEN.md")

    lineas = [
        "# Resumen de la corrida",
        "",
        f"- **Fecha y hora:** {inicio}",
        f"- **Servidor:** {BASE_URL}",
        f"- **Paciente de prueba:** {NOMBRE} {APELLIDO}, DNI {DOCUMENTO}",
        f"- **Recursos creados:** {len(RECURSOS_CREADOS)}",
        "",
        "| # | Tipo de recurso | ID logico | URL |",
        "| --- | --- | --- | --- |",
    ]
    for i, (tipo, rid) in enumerate(RECURSOS_CREADOS, start=1):
        lineas.append(f"| {i} | `{tipo}` | `{rid}` | {BASE_URL}/{tipo}/{rid} |")

    if not RECURSOS_CREADOS:
        lineas.append("| — | — | — | No se creo ningun recurso en esta corrida |")

    lineas.append("")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))

    print(f"\n[resumen] {ruta}")


def _titulo(texto):
    print("\n" + "#" * 78)
    print(f"# {texto}")
    print("#" * 78)


# ===========================================================================
# 3.a — Crear un Patient con documento como identifier, y leerlo
# ===========================================================================
def consigna_3a():
    _titulo("CONSIGNA 3.a — Crear un recurso Patient con identifier (DNI) y leerlo")

    paciente = create_patient_resource(
        family_name=APELLIDO,
        given_name=NOMBRE,
        birth_date=FECHA_NACIMIENTO,
        gender=GENERO,
        phone=TELEFONO,
        documento=DOCUMENTO,
    )

    print("\nRecurso Patient armado localmente (antes del POST):")
    print(paciente.json(indent=2, exclude_none=True))

    # CREATE
    paciente_id = send_resource_to_hapi_fhir(
        paciente, "Patient", guardar_como="3a_patient_creado.json"
    )
    if not paciente_id:
        print("\nNo se pudo crear el paciente. Se interrumpe la corrida.")
        return None
    _registrar("Patient", paciente_id)

    # READ
    get_resource_from_hapi_fhir(
        paciente_id, "Patient", guardar_como="3a_patient_leido.json"
    )

    print(f"\n>>> Patient creado: {BASE_URL}/Patient/{paciente_id}")
    print("    (esta URL se puede pegar en el navegador para ver el recurso)")
    return paciente_id


# ===========================================================================
# 3.b — Buscar pacientes por documento
# ===========================================================================
def consigna_3b(paciente_id_esperado=None):
    _titulo("CONSIGNA 3.b — Buscar pacientes por numero de documento")

    encontrados = buscar_paciente_por_documento(DOCUMENTO)

    if paciente_id_esperado:
        ids = [p.get("id") for p in encontrados]
        if paciente_id_esperado in ids:
            print(
                f"\n>>> OK: el paciente creado en 3.a (Patient/"
                f"{paciente_id_esperado}) fue encontrado por su DNI."
            )
        else:
            print(
                f"\n>>> ATENCION: Patient/{paciente_id_esperado} no aparecio en "
                "la busqueda. El servidor publico de HAPI puede tardar unos "
                "segundos en indexar el recurso; reintentar la busqueda."
            )
    return encontrados


# ===========================================================================
# 3.c — GRUPO 8: crear el recurso DiagnosticReport
# ===========================================================================
def consigna_3c(paciente_id):
    _titulo("CONSIGNA 3.c — GRUPO 8: recurso DiagnosticReport")

    imprimir_tabla_elementos()

    fecha_muestra = _ahora_iso()

    # PASO 1 — Crear las Observation con los resultados atomicos.
    # DiagnosticReport no guarda los valores: los referencia. Entonces las
    # Observation tienen que existir en el servidor ANTES del informe, para
    # poder referenciarlas por su ID logico.
    print("\n--- PASO 1: crear las Observation (resultados atomicos) ---")
    observaciones = crear_observations_hemograma(paciente_id, fecha_muestra)

    observation_ids = []
    for i, obs in enumerate(observaciones, start=1):
        analito = obs.code.text
        print(f"\n[{i}/{len(observaciones)}] {analito}")
        obs_id = send_resource_to_hapi_fhir(
            obs, "Observation", guardar_como=f"3c_observation_{i}.json"
        )
        if obs_id:
            observation_ids.append(obs_id)
            _registrar("Observation", obs_id)

    if not observation_ids:
        print("\nNo se creo ninguna Observation; el informe quedaria sin result.")

    # PASO 2 — Crear el DiagnosticReport que las agrupa.
    print("\n--- PASO 2: crear el DiagnosticReport que agrupa los resultados ---")
    reporte = create_diagnostic_report_resource(
        paciente_id=paciente_id,
        observation_ids=observation_ids,
        fecha_efectiva=fecha_muestra,
        fecha_emision=_ahora_iso(),
        nro_protocolo=NRO_PROTOCOLO,
        conclusion=CONCLUSION_TEXTO,
        codigo_conclusion_snomed=SNOMED_CONCLUSION,
        display_conclusion_snomed=SNOMED_CONCLUSION_DISPLAY,
        status="final",
    )

    print("\nRecurso DiagnosticReport armado localmente (antes del POST):")
    print(reporte.json(indent=2, exclude_none=True))

    reporte_id = send_resource_to_hapi_fhir(
        reporte, "DiagnosticReport", guardar_como="3c_diagnosticreport_creado.json"
    )
    if not reporte_id:
        return None
    _registrar("DiagnosticReport", reporte_id)

    # PASO 3 — Leer el informe creado.
    print("\n--- PASO 3: leer el DiagnosticReport creado ---")
    get_resource_from_hapi_fhir(
        reporte_id, "DiagnosticReport", guardar_como="3c_diagnosticreport_leido.json"
    )

    # PASO 4 — Leer el informe resolviendo las referencias en una sola
    # consulta. _include le pide al servidor que incluya en el Bundle los
    # recursos referenciados, para no hacer un GET por cada Observation.
    print("\n--- PASO 4: leer el informe con sus Observation resueltas (_include) ---")
    from base import search_resource_in_hapi_fhir

    search_resource_in_hapi_fhir(
        "DiagnosticReport",
        {"_id": reporte_id, "_include": "DiagnosticReport:result"},
        guardar_como="3c_diagnosticreport_con_include.json",
    )

    print(f"\n>>> DiagnosticReport creado: {BASE_URL}/DiagnosticReport/{reporte_id}")
    print(f"    Agrupa {len(observation_ids)} Observation del paciente "
          f"Patient/{paciente_id}")
    return reporte_id


# ===========================================================================
def main():
    consigna = sys.argv[1].lower() if len(sys.argv) > 1 else "todo"
    inicio = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M:%S (UTC%z)")

    print("=" * 78)
    print("TP6 - INTEROPERABILIDAD | Actividad 3 (Python)")
    print("Grupo 8 - Recurso asignado: DiagnosticReport")
    print(f"Servidor: {BASE_URL}")
    print(f"Corrida:  {inicio}")
    print("=" * 78)

    # Se borran las salidas anteriores para que no queden archivos de dos
    # corridas distintas mezclados si esta falla a la mitad.
    _limpiar_salidas()

    paciente_id = None

    if consigna in ("todo", "3a"):
        paciente_id = consigna_3a()

    if consigna in ("todo", "3b"):
        if paciente_id is None and consigna == "3b":
            print(
                "\nNota: se corre 3.b sin haber creado un paciente en esta "
                "corrida; se busca el DNI en el servidor igual."
            )
        consigna_3b(paciente_id)

    if consigna in ("todo", "3c"):
        if paciente_id is None:
            print(
                "\nPara 3.c hace falta un Patient como sujeto del informe. "
                "Se crea uno primero."
            )
            paciente_id = consigna_3a()
        if paciente_id:
            consigna_3c(paciente_id)

    _escribir_resumen(inicio)

    print("\n" + "=" * 78)
    print(f"Fin. Recursos creados en esta corrida: {len(RECURSOS_CREADOS)}")
    for tipo, rid in RECURSOS_CREADOS:
        print(f"   {tipo}/{rid}")
    print(f"Los JSON de las respuestas quedaron en ./{CARPETA_SALIDAS}/")
    print("=" * 78)


if __name__ == "__main__":
    main()
