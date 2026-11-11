"""
validar_local.py — Valida la construccion de los recursos SIN tocar la red.

Sirve para verificar que los recursos cumplen la estructura FHIR R4 (elementos
obligatorios, tipos de dato, cardinalidades) antes de hacer el POST al
servidor. Util para desarrollar sin depender de hapi.fhir.org.

    python validar_local.py
"""

import json

from diagnostic_report import create_diagnostic_report_resource
from observation import crear_observations_hemograma
from patient import create_patient_resource

PACIENTE_FALSO = "ejemplo-123"
FECHA = "2026-11-10T10:30:00-03:00"

ok = True


def chequear(nombre, funcion):
    global ok
    try:
        recurso = funcion()
        cuerpo = json.loads(recurso.json(exclude_none=True))
        assert cuerpo.get("resourceType"), "falta resourceType"
        print(f"  [OK]    {nombre:<34} resourceType={cuerpo['resourceType']}")
        return cuerpo
    except Exception as e:
        ok = False
        print(f"  [FALLA] {nombre:<34} {type(e).__name__}: {e}")
        return None


print("\n=== Validacion local de los recursos (sin red) ===\n")

patient = chequear(
    "Patient con identifier (DNI)",
    lambda: create_patient_resource(
        family_name="Gomez",
        given_name="Lucia",
        birth_date="1995-03-22",
        gender="female",
        phone="+5491133445566",
        documento="38765434",
    ),
)

observaciones = crear_observations_hemograma(PACIENTE_FALSO, FECHA)
for i, obs in enumerate(observaciones, start=1):
    chequear(f"Observation {i} ({obs.code.coding[0].code})", lambda o=obs: o)

reporte = chequear(
    "DiagnosticReport (Grupo 8)",
    lambda: create_diagnostic_report_resource(
        paciente_id=PACIENTE_FALSO,
        observation_ids=["obs-1", "obs-2", "obs-3", "obs-4"],
        fecha_efectiva=FECHA,
        fecha_emision="2026-11-10T11:05:00-03:00",
        nro_protocolo="LAB-2026-004821",
        conclusion="Anemia leve.",
        codigo_conclusion_snomed="271737000",
        display_conclusion_snomed="Anemia",
    ),
)

# ---------------------------------------------------------------------------
# Chequeos explicitos de los elementos obligatorios del recurso asignado
# ---------------------------------------------------------------------------
print("\n--- Elementos obligatorios de DiagnosticReport (R4) ---")
if reporte:
    for elemento in ("status", "code"):
        presente = elemento in reporte
        print(f"  {'[OK]   ' if presente else '[FALLA]'} {elemento} (1..1)")
        ok = ok and presente

    estados_validos = {
        "registered", "partial", "preliminary", "final", "amended",
        "corrected", "appended", "cancelled", "entered-in-error", "unknown",
    }
    estado = reporte.get("status")
    valido = estado in estados_validos
    print(f"  {'[OK]   ' if valido else '[FALLA]'} status='{estado}' pertenece "
          "al value set DiagnosticReportStatus")
    ok = ok and valido

    n_result = len(reporte.get("result", []))
    print(f"  [info]  result -> {n_result} referencias a Observation")

    print("\n--- DiagnosticReport generado ---")
    print(json.dumps(reporte, indent=2, ensure_ascii=False))

print("\n" + ("=== TODO OK ===" if ok else "=== HAY FALLAS ==="))
raise SystemExit(0 if ok else 1)
