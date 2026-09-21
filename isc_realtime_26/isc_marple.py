"""
isc_marple.py
Módulo para gestionar la subida de archivos CSV a Marple Data.
Usa la API correcta del SDK v3: db.get_stream() → stream.push_file() → wait_for_import()
"""
import os
import math
import logging
from pathlib import Path
from marple import DB

# ================= CONFIGURACIÓN =================
def get_secret(key: str, default: str) -> str:
    # 1. Try environment variable
    val = os.environ.get(key)
    if val:
        return val
    # 2. Try local .env file in workspace root
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == key:
                            return v.strip().strip("'").strip('"')
        except Exception:
            pass
    # 3. Fallback to default
    return default

MARPLE_API_TOKEN = get_secret("MARPLE_API_TOKEN", "mdb_Le69BDaNdgn1SJ4DqWX6N6btH-a8Dx8Ou96aBbLA4v8")


# Nombre del stream en Marple (debe existir en tu workspace)
DATASTREAM_NAME  = "ISC_Telemetry"

# Tiempo máximo de espera para que Marple procese el archivo (segundos)
IMPORT_TIMEOUT_S = 120
# =================================================

logger = logging.getLogger("ISC_MARPLE")


def upload_session_csv(file_path: str, metadata: dict) -> None:
    """
    Sube un archivo CSV a Marple Data usando el SDK de marple.
    """
    if not os.path.exists(file_path):
        logger.error(f"Archivo no encontrado: {file_path}")
        return

    try:
        logger.info("Conectando a Marple DB…")
        db = DB(MARPLE_API_TOKEN)

        logger.info(f"Subiendo archivo '{os.path.basename(file_path)}' al stream '{DATASTREAM_NAME}'…")
        dataset_id = db.push_file(DATASTREAM_NAME, file_path, metadata=metadata or {})

        logger.info(f"¡Subida completada! ID de Dataset en Marple: {dataset_id}")

    except Exception as e:
        logger.error(f"Error crítico subiendo a Marple: {e}")


# ==============================================================================
# MARPLE SIGNAL EXPORT MAPPING & METADATA DICTIONARY
# Standardized telemetry hierarchy for IFS-08 trackside analytics
# ==============================================================================

MARPLE_SIGNAL_MAP = {
    # ── Powertrain Torque Metrics [bytes 96-99] ──────────────────────────────
    'inv_torque_est_nm': {
        'path': 'Powertrain/Torque/Estimate_Nm',
        'unit': 'Nm',
        'desc': 'Inverter FOC estimated shaft torque (CAN 0x468 EMC_TX_STATE_9)',
    },
    'inv_torque_max_feas': {
        'path': 'Powertrain/Torque/Limit_Nm',
        'unit': 'Nm',
        'desc': 'Inverter maximum feasible torque limit (CAN 0x467 EMC_TX_STATE_8)',
    },
    # ── Powertrain Diagnostics & Subfault Bits [bytes 100-101] ────────────────
    'inv_subfault_bits': {
        'path': 'Powertrain/Diagnostics/Subfault_Bits',
        'unit': 'bitfield',
        'desc': 'Packed inverter subfault bitfield (PwrStg | EMCtrl_FOC | DEM_Active)',
    },
    'pwrstg_bitstate': {
        'path': 'Powertrain/Diagnostics/PwrStg_Fault',
        'unit': 'bitfield',
        'desc': 'Inverter power stage fault bits (0x461 EMC_TX_STATE_2)',
    },
    'emctrl_foc': {
        'path': 'Powertrain/Diagnostics/EMCtrl_FOC',
        'unit': 'bitfield',
        'desc': 'Inverter EMCtrl FOC status bits (0x466 EMC_TX_STATE_7)',
    },
    'emctrl_foc_bitstate': {
        'path': 'Powertrain/Diagnostics/EMCtrl_FOC',
        'unit': 'bitfield',
        'desc': 'Inverter EMCtrl FOC status bits (alias)',
    },
    'dem_active': {
        'path': 'Powertrain/Diagnostics/DEM_Active',
        'unit': 'bool',
        'desc': 'Diagnostic Event Manager active fault flag',
    },
    # ── Safety / AMS Active Fault Latch [CAN 0x4A3] ───────────────────────────
    'ams_fault_reason': {
        'path': 'Safety/AMS/ActiveFault/Reason_Code',
        'unit': 'enum',
        'desc': 'AMS active tripped fault reason code (0..12)',
    },
    'ams_fault_name': {
        'path': 'Safety/AMS/ActiveFault/Reason_Name',
        'unit': 'str',
        'desc': 'AMS active tripped fault textual name',
    },
    'ams_fault_module': {
        'path': 'Safety/AMS/ActiveFault/Offending_Module',
        'unit': 'id',
        'desc': 'Offending battery module index (0..4, 0xFF=none)',
    },
    'ams_fault_cell_ntc': {
        'path': 'Safety/AMS/ActiveFault/Offending_Index',
        'unit': 'id',
        'desc': 'Offending cell (0..18) or NTC (0..37) index',
    },
    'ams_tripped_val': {
        'path': 'Safety/AMS/ActiveFault/Tripped_Value',
        'unit': 'mV_or_degC',
        'desc': 'Offending reading at moment of error latch trip',
    },
    'ams_latch_active': {
        'path': 'Safety/AMS/ActiveFault/Latch_Active',
        'unit': 'bool',
        'desc': 'AMS hardware shutdown error latch state (1=TRIPPED)',
    },
}

# Add all 95 cell voltage channels: Accumulator/Voltage/Module_X/Cell_YY [mV]
for m in range(5):
    for c in range(19):
        path = f"Accumulator/Voltage/Module_{m}/Cell_{c:02d}"
        MARPLE_SIGNAL_MAP[f"cell_v_m{m}_c{c}"] = {
            'path': path,
            'unit': 'mV',
            'desc': f"Battery Module {m} Cell {c:02d} Voltage",
        }
        MARPLE_SIGNAL_MAP[f"ams_v_mod{m}_cell{c}"] = {
            'path': path,
            'unit': 'mV',
            'desc': f"Battery Module {m} Cell {c:02d} Voltage (SD alias)",
        }

# Add all 190 NTC thermal channels: Accumulator/Thermal/Module_X/NTC_YY [°C]
for m in range(5):
    for n in range(38):
        path = f"Accumulator/Thermal/Module_{m}/NTC_{n:02d}"
        MARPLE_SIGNAL_MAP[f"cell_t_m{m}_n{n}"] = {
            'path': path,
            'unit': '°C',
            'desc': f"Battery Module {m} NTC {n:02d} Temperature",
        }
        MARPLE_SIGNAL_MAP[f"ams_t_mod{m}_cell{n}"] = {
            'path': path,
            'unit': '°C',
            'desc': f"Battery Module {m} NTC {n:02d} Temperature (SD alias)",
        }


def get_marple_signal_map() -> dict:
    """Return the global Marple signal hierarchy mapping dictionary."""
    return MARPLE_SIGNAL_MAP


def build_marple_metadata(session_meta: dict = None, acu_summary: dict = None) -> dict:
    """
    Constructs a metadata payload adhering to Marple's expected session schema.
    """
    meta = {
        "vehicle":         "IFS-08",
        "system":          "ISCmetrics Telemetry",
        "version":         "2.10.0",
        "datastream":      DATASTREAM_NAME,
        "cell_count":      95,
        "ntc_sensor_count": 190,
        "torque_channel":  "Powertrain/Torque/Estimate_Nm",
        "fault_channel":   "Safety/AMS/ActiveFault",
    }
    if session_meta:
        meta.update(session_meta)
    if acu_summary:
        meta["acu_summary"] = acu_summary
    return meta


def export_acu_matrix_to_marple_csv(acu_matrix: dict, out_path: str) -> bool:
    """
    Exports the complete 95-cell voltage matrix and 190-sensor thermal matrix
    from latest_data_dict['acu_matrix'] into a Marple-compliant CSV file.
    """
    import csv
    from datetime import datetime

    voltages = acu_matrix.get('voltages_mv', [[0] * 19 for _ in range(5)])
    temps = acu_matrix.get('temps_c', [[float('nan')] * 38 for _ in range(5)])
    fault = acu_matrix.get('fault_status', {})

    headers = ["timestamp", "time_elapsed_s"]
    row_val = [datetime.now().isoformat(), "0.000"]

    # 95 Voltages
    for m in range(5):
        for c in range(19):
            headers.append(f"Accumulator/Voltage/Module_{m}/Cell_{c:02d} [mV]")
            v = voltages[m][c] if m < len(voltages) and c < len(voltages[m]) else 0
            row_val.append(v)

    # 190 Temperatures
    for m in range(5):
        for n in range(38):
            headers.append(f"Accumulator/Thermal/Module_{m}/NTC_{n:02d} [°C]")
            t = temps[m][n] if m < len(temps) and n < len(temps[m]) else float('nan')
            row_val.append(t if not math.isnan(t) else "")

    # Fault registers
    headers.extend([
        "Safety/AMS/ActiveFault/Reason_Code",
        "Safety/AMS/ActiveFault/Reason_Name",
        "Safety/AMS/ActiveFault/Offending_Module",
        "Safety/AMS/ActiveFault/Offending_Index",
        "Safety/AMS/ActiveFault/Tripped_Value",
        "Safety/AMS/ActiveFault/Latch_Active",
    ])
    row_val.extend([
        fault.get('fault_reason', 0),
        fault.get('fault_name', 'No Fault'),
        fault.get('offending_module', 0xFF),
        fault.get('offending_cell_ntc', 0xFF),
        fault.get('tripped_val', 0),
        1 if fault.get('latch_active', False) else 0,
    ])

    try:
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerow(row_val)
        return True
    except Exception as exc:
        logger.error(f"Error exporting ACU matrix to Marple CSV: {exc}")
        return False