"""
tests/test_marple_exporter.py — Test Suite for Marple Export Engine
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt5.QtWidgets import QApplication

from core.marple_exporter import (
    DEFAULT_API_TOKEN,
    DEFAULT_DATASTREAM,
    MarpleClient,
    MarpleExportWorker,
    get_marple_api_token,
)

# Ensure a QApplication exists for QThread / QObject tests
_app = QApplication.instance() or QApplication([])


def test_token_resolution_explicit():
    token = get_marple_api_token("custom_token_123")
    assert token == "custom_token_123"


def test_token_resolution_fallback():
    token = get_marple_api_token(None)
    assert token is not None
    assert len(token) > 0


def test_metadata_construction(tmp_path):
    dummy_csv = tmp_path / "test_session.csv"
    dummy_csv.write_text("time,tick_ms\n0,1000\n", encoding="utf-8")

    client = MarpleClient()
    meta = client.build_metadata(
        dummy_csv,
        pilot="Andres",
        circuit="Montmelo",
        extra_tags={"event": "Acceleration", "laps": 4},
    )

    assert meta["pilot"] == "Andres"
    assert meta["circuit"] == "Montmelo"
    assert meta["event"] == "Acceleration"
    assert meta["file_name"] == "test_session.csv"
    assert meta["datastream"] == DEFAULT_DATASTREAM


def test_upload_missing_file():
    client = MarpleClient()
    ok, msg, dataset_id = client.upload_file("non_existent_file_xyz.csv")
    assert ok is False
    assert "File not found" in msg


@patch("marple.DB")
def test_upload_success_mock(mock_db_cls, tmp_path):
    mock_db = MagicMock()
    mock_db.push_file.return_value = "dataset_mock_999"
    mock_db_cls.return_value = mock_db

    dummy_csv = tmp_path / "test_run.csv"
    dummy_csv.write_text("time,tick_ms\n0,1000\n", encoding="utf-8")

    progress_reports = []
    def _prog(pct, msg):
        progress_reports.append((pct, msg))

    client = MarpleClient()
    ok, msg, dataset_id = client.upload_file(dummy_csv, progress_cb=_prog)

    assert ok is True
    assert dataset_id == "dataset_mock_999"
    assert "Successfully uploaded" in msg
    assert len(progress_reports) >= 3


def test_marple_export_worker_signals(tmp_path):
    dummy_csv = tmp_path / "worker_test.csv"
    dummy_csv.write_text("time,tick_ms\n0,1000\n", encoding="utf-8")

    with patch("marple.DB") as mock_db_cls:
        mock_db = MagicMock()
        mock_db.push_file.return_value = "ds_worker_123"
        mock_db_cls.return_value = mock_db

        worker = MarpleExportWorker(file_path=dummy_csv)

        finished_results = []
        def _on_finished(success, msg, ds_id):
            finished_results.append((success, msg, ds_id))

        worker.finished.connect(_on_finished)
        worker.run()  # synchronous run for testing

        assert len(finished_results) == 1
        success, msg, ds_id = finished_results[0]
        assert success is True
        assert ds_id == "ds_worker_123"
