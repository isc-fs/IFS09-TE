"""
core/marple_exporter.py — Non-Blocking Marple Export Client & Background Worker for ISCmetrics

Provides:
  • MarpleClient: Headless API client with token resolution, metadata injection, and exponential backoff retry.
  • MarpleExportWorker: PyQt5 QThread background worker emitting progress and status signals without GUI freezes.
  • Asynchronous export entrypoints for single sessions and merged multi-log datasets.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    # Minimal fallback dummy classes if running headless without PyQt5
    class QObject:  # type: ignore
        pass
    class QThread:  # type: ignore
        def __init__(self, parent=None):
            pass
        def start(self):
            self.run()
    def pyqtSignal(*args):  # type: ignore
        class Signal:
            def emit(self, *a, **kw): pass
            def connect(self, f): pass
        return Signal()

logger = logging.getLogger("ISC_MARPLE_EXP")

DEFAULT_API_TOKEN = "mdb_Le69BDaNdgn1SJ4DqWX6N6btH-a8Dx8Ou96aBbLA4v8"
DEFAULT_DATASTREAM = "ISC_Telemetry"


# ==============================================================================
# TOKEN & CONFIG RESOLUTION
# ==============================================================================

def get_marple_api_token(explicit_token: Optional[str] = None) -> str:
    """
    Resolve Marple API token with priority:
      1. Explicitly passed parameter
      2. Environment variable MARPLE_API_TOKEN
      3. .env file in workspace
      4. Hardcoded fallback token
    """
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()

    env_val = os.environ.get("MARPLE_API_TOKEN")
    if env_val and env_val.strip():
        return env_val.strip()

    # Search common .env locations
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent / ".env",
    ]
    for env_path in candidates:
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() == "MARPLE_API_TOKEN":
                                return v.strip().strip("'").strip('"')
            except Exception:
                pass

    return DEFAULT_API_TOKEN


# ==============================================================================
# MARPLE CLIENT
# ==============================================================================

class MarpleClient:
    """
    Synchronous / headless client communicating with Marple Data.
    Handles token management, metadata construction, and retry loops.
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        datastream: str = DEFAULT_DATASTREAM,
        max_retries: int = 3,
        base_backoff_s: float = 2.0,
    ):
        self.api_token = get_marple_api_token(api_token)
        self.datastream = datastream
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s

    def build_metadata(
        self,
        session_path: Union[str, Path],
        pilot: Optional[str] = None,
        circuit: Optional[str] = None,
        extra_tags: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build standard telemetry metadata payload."""
        p = Path(session_path)
        meta = {
            "vehicle": "IFS-08",
            "car": "Formula Student Electric",
            "software": "ISCmetrics",
            "file_name": p.name,
            "datastream": self.datastream,
            "export_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if pilot:
            meta["pilot"] = pilot
        if circuit:
            meta["circuit"] = circuit
        if extra_tags:
            meta.update(extra_tags)
        return meta

    def upload_file(
        self,
        file_path: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
        progress_cb: Optional[callable] = None,
    ) -> Tuple[bool, str, str]:
        """
        Uploads a session CSV file to Marple Data with automatic retries.

        Returns:
          (success: bool, status_message: str, dataset_id_or_url: str)
        """
        path = Path(file_path)
        if not path.exists():
            return False, f"File not found: {path}", ""

        meta = metadata or self.build_metadata(path)
        if progress_cb:
            progress_cb(10, f"Initializing Marple DB connection for {path.name}...")

        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                if progress_cb:
                    progress_cb(
                        20 + attempt * 15,
                        f"Connecting to Marple (Attempt {attempt}/{self.max_retries})...",
                    )

                # Attempt upload via marple SDK
                import marple
                db = marple.DB(self.api_token)

                if progress_cb:
                    progress_cb(70, f"Streaming {path.name} to datastream '{self.datastream}'...")

                dataset_id = db.push_file(self.datastream, str(path), metadata=meta)

                if progress_cb:
                    progress_cb(100, f"Upload complete! Dataset ID: {dataset_id}")

                dataset_url = f"https://app.marpledata.com"
                return True, f"Successfully uploaded to Marple (Dataset: {dataset_id})", str(dataset_id)

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    f"Marple upload attempt {attempt}/{self.max_retries} failed: {exc}"
                )
                if attempt < self.max_retries:
                    sleep_time = self.base_backoff_s * (2 ** (attempt - 1))
                    if progress_cb:
                        progress_cb(
                            20 + attempt * 15,
                            f"Network glitch, retrying in {sleep_time:.1f}s: {exc}",
                        )
                    time.sleep(sleep_time)

        return False, f"Upload failed after {self.max_retries} attempts: {last_error}", ""


# ==============================================================================
# ASYNC QTHREAD BACKGROUND WORKER
# ==============================================================================

class MarpleExportWorker(QThread):
    """
    Asynchronous background thread worker for Marple Data upload.
    Emits progress and result signals safely to the Qt GUI thread.
    """

    # Signals
    started_upload = pyqtSignal(str)              # filename
    progress = pyqtSignal(int, str)               # percent (0..100), message
    finished = pyqtSignal(bool, str, str)         # success, message, dataset_id

    def __init__(
        self,
        file_path: Union[str, Path],
        api_token: Optional[str] = None,
        datastream: str = DEFAULT_DATASTREAM,
        metadata: Optional[Dict[str, Any]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.file_path = Path(file_path)
        self.api_token = api_token
        self.datastream = datastream
        self.metadata = metadata
        self._is_cancelled = False

    def cancel(self):
        """Request worker termination."""
        self._is_cancelled = True

    def run(self):
        """Thread execution payload."""
        try:
            self.started_upload.emit(self.file_path.name)
            self.progress.emit(5, "Starting Marple exporter worker...")

            client = MarpleClient(
                api_token=self.api_token,
                datastream=self.datastream,
            )

            def _on_progress(pct: int, msg: str):
                if not self._is_cancelled:
                    self.progress.emit(pct, msg)

            success, msg, dataset_id = client.upload_file(
                self.file_path,
                metadata=self.metadata,
                progress_cb=_on_progress,
            )

            if self._is_cancelled:
                self.finished.emit(False, "Upload cancelled by user.", "")
            else:
                self.finished.emit(success, msg, dataset_id)

        except Exception as exc:
            logger.exception("Unexpected error in MarpleExportWorker")
            self.finished.emit(False, f"Unexpected export error: {exc}", "")


# ==============================================================================
# CONVENIENCE HELPERS
# ==============================================================================

def export_session_to_marple_async(
    file_path: Union[str, Path],
    on_finished: Optional[callable] = None,
    on_progress: Optional[callable] = None,
    api_token: Optional[str] = None,
    datastream: str = DEFAULT_DATASTREAM,
    metadata: Optional[Dict[str, Any]] = None,
) -> MarpleExportWorker:
    """
    Launch a background export worker and connect optional callbacks.
    Returns the running worker instance.
    """
    worker = MarpleExportWorker(
        file_path=file_path,
        api_token=api_token,
        datastream=datastream,
        metadata=metadata,
    )
    if on_finished:
        worker.finished.connect(on_finished)
    if on_progress:
        worker.progress.connect(on_progress)
    worker.start()
    return worker
