"""
isc_marple.py
Gestión y exportación de telemetría ISCmetrics → Marple DB (SDK oficial `marpledata`).

Flujo (SDK v3):  DB(token) → db.get_stream(name) → stream.push_file(csv, metadata) → dataset.wait_for_import()

Configuración (por orden de prioridad):
  1. Variables de entorno  MARPLE_API_TOKEN / MARPLE_API_URL / MARPLE_STREAM
  2. Fichero `.env` junto a este módulo (NO se sube a git, ver .gitignore)

El token ya NO está en el código fuente. Copia `.env.example` a `.env` y rellénalo.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("ISC_MARPLE")

try:  # el import es lento la primera vez (pandas/pyarrow); no bloquea si falta el SDK
    from marple import DB
    MARPLE_AVAILABLE = True
except Exception as _imp_err:  # pragma: no cover
    DB = None  # type: ignore[assignment]
    MARPLE_AVAILABLE = False
    logger.warning("SDK de Marple no disponible (%s). Instala con: pip install marpledata", _imp_err)


# ================= CONFIGURACIÓN =================
def get_secret(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val:
        return val
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == key:
                        return v.strip().strip("'").strip('"')
        except Exception:
            pass
    return default


def _token() -> str:
    return get_secret("MARPLE_API_TOKEN")


def _api_url() -> str:
    return get_secret("MARPLE_API_URL", "https://db.marpledata.com/api/v1")


# Nombre del stream en Marple (debe existir en tu workspace)
DATASTREAM_NAME = get_secret("MARPLE_STREAM", "ISC_Telemetry")

# Tiempo máximo de espera para que Marple procese el archivo (segundos)
IMPORT_TIMEOUT_S = 120
UPLOAD_RETRIES   = 3
# =================================================

_db_lock = threading.Lock()
_db = None


def is_configured() -> bool:
    """True si hay SDK y token disponibles."""
    return MARPLE_AVAILABLE and bool(_token())


def _get_db():
    global _db
    with _db_lock:
        if _db is None:
            if not MARPLE_AVAILABLE:
                raise RuntimeError("SDK de Marple no instalado (pip install marpledata)")
            if not _token():
                raise RuntimeError("Falta MARPLE_API_TOKEN (variable de entorno o .env)")
            _db = DB(_token(), _api_url())
        return _db


def check_connection() -> Tuple[bool, str]:
    """Comprueba token + red. Devuelve (ok, mensaje)."""
    try:
        db = _get_db()
        db.check_connection()
        return True, f"Conectado a Marple DB ({_api_url()})"
    except Exception as exc:
        return False, str(exc)


def list_local_sessions(limit: int = 50) -> List[Path]:
    """CSV de sesión más recientes en la carpeta de logs de ISCmetrics."""
    try:
        from ISC_RTT_serial import LOG_DIR
    except Exception:
        return []
    files = [p for p in Path(LOG_DIR).glob("*.csv") if p.is_file()]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def upload_session_csv(file_path: str, metadata: Optional[dict] = None,
                       wait: bool = True) -> Optional[object]:
    """
    Sube un CSV a Marple Data (con reintentos). Devuelve el dataset o None si falla.
    Seguro para llamar desde un hilo en segundo plano.
    """
    if not os.path.exists(file_path):
        logger.error(f"Archivo no encontrado: {file_path}")
        return None

    last_exc: Optional[Exception] = None
    for attempt in range(1, UPLOAD_RETRIES + 1):
        try:
            logger.info("Conectando a Marple DB… (intento %d/%d)", attempt, UPLOAD_RETRIES)
            stream = _get_db().get_stream(DATASTREAM_NAME)
            logger.info("Subiendo '%s' al stream '%s'…", os.path.basename(file_path), DATASTREAM_NAME)
            dataset = stream.push_file(file_path, metadata=metadata or {})
            if wait and hasattr(dataset, "wait_for_import"):
                dataset = dataset.wait_for_import(timeout=IMPORT_TIMEOUT_S)
            logger.info("¡Subida completada a Marple! (%s)", getattr(dataset, "dataset_id", dataset))
            return dataset
        except Exception as exc:
            last_exc = exc
            logger.warning("Fallo subiendo a Marple (intento %d): %s", attempt, exc)
            time.sleep(min(2 ** attempt, 10))
    logger.error("Error crítico subiendo a Marple: %s", last_exc)
    return None


def upload_session_csv_async(file_path: str, metadata: Optional[dict] = None,
                             on_done: Optional[Callable[[bool, str], None]] = None) -> threading.Thread:
    """Sube en un hilo daemon (no bloquea la UI). `on_done(ok, mensaje)` se llama al terminar."""
    def _run():
        ds = upload_session_csv(file_path, metadata)
        if on_done:
            try:
                on_done(ds is not None, os.path.basename(file_path))
            except Exception:
                logger.exception("on_done callback falló")
    th = threading.Thread(target=_run, name="marple-upload", daemon=True)
    th.start()
    return th
