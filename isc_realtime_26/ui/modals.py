"""
ui/modals.py — Post-Merge Confirmation Modal & Manual Marple Export Dialog

Styled to match the high-contrast F1 dark theme:
  • PostMergeConfirmationModal: Displays synchronization statistics (drift, records, correlation)
    with [Upload to Marple], [Save Locally], and [Cancel] action buttons.
  • ManualMarpleExportDialog: Standalone dialog for manual session export to Marple Data.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.marple_exporter import MarpleExportWorker, get_marple_api_token
from core.sync import SyncSummary

# Theme color constants matching ui.py
ISC_GREEN = "#008000"
F1_DARK_BG = "#111111"
F1_MID_BG = "#1a1a1a"
F1_PANEL_BG = "#222222"
F1_TEXT = "#f1f5f9"
F1_MUTED = "#94a3b8"
F1_WARNING = "#f59e0b"
F1_ERROR = "#ef4444"
F1_BLUE = "#38bdf8"
_MARPLE_PASSWORD_HASH = hashlib.sha256(b"ISC_telemetry_2026").hexdigest()


# ==============================================================================
# POST-MERGE CONFIRMATION MODAL
# ==============================================================================

class PostMergeConfirmationModal(QDialog):
    """
    Modal opened after multi-log synchronization completes.
    Displays alignment statistics, offsets, correlation, and actions:
      [Upload to Marple], [Save Locally], [Cancel].
    """

    def __init__(self, summary: SyncSummary, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.summary = summary
        self._worker: Optional[MarpleExportWorker] = None
        self.setWindowTitle("ISCmetrics — Synchronization Summary & Export")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(720, 520)
        self.setStyleSheet(f"""
            QDialog {{ background: {F1_DARK_BG}; color: {F1_TEXT}; }}
            QLabel {{ color: {F1_TEXT}; }}
            QGroupBox {{ color: {ISC_GREEN}; font-weight: bold; border: 1px solid #333; margin-top: 8px; font-size: 11px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 4px; background: {F1_DARK_BG}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header Title
        title_lbl = QLabel("MULTI-LOG SYNCHRONIZATION COMPLETE")
        title_lbl.setStyleSheet(f"color: {ISC_GREEN}; font-size: 14px; font-weight: bold;")
        root.addWidget(title_lbl)

        # Summary Info Bar
        info_box = QGroupBox("SESSION METRICS")
        info_lay = QGridLayout(info_box)
        info_lay.setContentsMargins(10, 12, 10, 10)
        info_lay.setSpacing(8)

        info_lay.addWidget(self._stat_label("Base Session:"), 0, 0)
        info_lay.addWidget(self._val_label(self.summary.session_file, F1_BLUE), 0, 1)

        info_lay.addWidget(self._stat_label("Total Records:"), 0, 2)
        info_lay.addWidget(self._val_label(f"{self.summary.total_rows:,} rows", F1_TEXT), 0, 3)

        info_lay.addWidget(self._stat_label("Output File:"), 1, 0)
        info_lay.addWidget(self._val_label(Path(self.summary.output_file).name, F1_MUTED), 1, 1)

        info_lay.addWidget(self._stat_label("Time Span:"), 1, 2)
        info_lay.addWidget(self._val_label(f"{self.summary.duration_s:.1f} seconds", F1_TEXT), 1, 3)

        root.addWidget(info_box)

        # Stream Synchronization Table
        tbl_box = QGroupBox("SYNCHRONIZED STREAMS")
        tbl_lay = QVBoxLayout(tbl_box)
        tbl_lay.setContentsMargins(8, 12, 8, 8)

        self._tbl = QTableWidget(len(self.summary.streams), 6)
        self._tbl.setHorizontalHeaderLabels([
            "Stream", "Status", "Detected Offset", "Correlation (r)", "Matched Rows", "Details"
        ])
        self._tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._tbl.horizontalHeader().setStretchLastSection(True)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self._tbl.setStyleSheet(f"""
            QTableWidget {{ background: {F1_MID_BG}; color: {F1_TEXT}; border: 1px solid #333; gridline-color: #222; font-size: 10px; }}
            QHeaderView::section {{ background: {F1_PANEL_BG}; color: {ISC_GREEN}; font-weight: bold; border: none; padding: 4px; }}
            QTableWidget::item:selected {{ background: #264a26; }}
        """)

        for row, (name, stream) in enumerate(self.summary.streams.items()):
            # Stream Name
            self._tbl.setItem(row, 0, QTableWidgetItem(name))

            # Status
            status_item = QTableWidgetItem("✓ Aligned" if stream.success else "✗ Failed")
            status_item.setForeground(QColor(ISC_GREEN if stream.success else F1_ERROR))
            self._tbl.setItem(row, 1, status_item)

            # Offset
            off_str = f"{stream.offset_ms:+.1f} ms" if stream.success else "—"
            self._tbl.setItem(row, 2, QTableWidgetItem(off_str))

            # Correlation
            corr_str = f"{stream.correlation_score:.3f}" if stream.success and stream.correlation_score > 0 else "—"
            self._tbl.setItem(row, 3, QTableWidgetItem(corr_str))

            # Matched rows
            matched_str = f"{stream.matched_records:,} / {stream.total_records:,}"
            self._tbl.setItem(row, 4, QTableWidgetItem(matched_str))

            # Message
            self._tbl.setItem(row, 5, QTableWidgetItem(stream.message))

        tbl_lay.addWidget(self._tbl)
        root.addWidget(tbl_box)

        # Added Channels list
        if self.summary.added_columns:
            chans_lbl = QLabel(f"Added Channels ({len(self.summary.added_columns)}): " + ", ".join(self.summary.added_columns[:10]) + ("..." if len(self.summary.added_columns) > 10 else ""))
            chans_lbl.setStyleSheet(f"color: {F1_MUTED}; font-size: 9px; font-family: 'Courier New';")
            root.addWidget(chans_lbl)

        # Upload Progress Area (hidden by default)
        self._prog_box = QWidget()
        prog_lay = QVBoxLayout(self._prog_box)
        prog_lay.setContentsMargins(0, 0, 0, 0)
        self._prog_status = QLabel("Ready to export.")
        self._prog_status.setStyleSheet("font-size: 10px; color: #aaa;")
        prog_lay.addWidget(self._prog_status)

        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 100)
        self._prog_bar.setValue(0)
        self._prog_bar.setStyleSheet(f"""
            QProgressBar {{ background: {F1_MID_BG}; border: 1px solid #444; border-radius: 3px; height: 10px; text-align: center; font-size: 8px; }}
            QProgressBar::chunk {{ background: {ISC_GREEN}; }}
        """)
        prog_lay.addWidget(self._prog_bar)
        self._prog_box.hide()
        root.addWidget(self._prog_box)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_upload = QPushButton("🚀  Upload to Marple")
        self._btn_upload.setStyleSheet(f"""
            QPushButton {{ background: {ISC_GREEN}; color: {F1_DARK_BG}; font-weight: bold; border: none; border-radius: 3px; padding: 7px 16px; font-size: 11px; }}
            QPushButton:hover {{ background: #00a000; }}
            QPushButton:disabled {{ background: #222; color: #555; }}
        """)
        self._btn_upload.clicked.connect(self._start_marple_upload)
        btn_row.addWidget(self._btn_upload)

        self._btn_save = QPushButton("💾  Save Locally")
        self._btn_save.setStyleSheet(f"""
            QPushButton {{ background: {F1_PANEL_BG}; color: {F1_TEXT}; border: 1px solid #444; border-radius: 3px; padding: 7px 16px; font-size: 11px; font-weight: bold; }}
            QPushButton:hover {{ border-color: {ISC_GREEN}; color: {ISC_GREEN}; }}
        """)
        self._btn_save.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_save)

        btn_row.addStretch()

        self._btn_cancel = QPushButton("✖  Cancel")
        self._btn_cancel.setStyleSheet(f"""
            QPushButton {{ background: {F1_PANEL_BG}; color: {F1_MUTED}; border: 1px solid #333; border-radius: 3px; padding: 7px 14px; font-size: 11px; }}
            QPushButton:hover {{ border-color: {F1_ERROR}; color: {F1_ERROR}; }}
        """)
        self._btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_cancel)

        root.addLayout(btn_row)

    def _start_marple_upload(self):
        """Trigger background upload of the merged file to Marple Data."""
        out_path = Path(self.summary.output_file)
        if not out_path.exists():
            QMessageBox.critical(self, "Missing File", f"Merged output file not found:\n{out_path}")
            return

        self._prog_box.show()
        self._prog_bar.setValue(5)
        self._prog_status.setText("Preparing Marple upload worker...")
        self._btn_upload.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._btn_cancel.setText("Close")

        meta = {
            "source_session": self.summary.session_file,
            "merged_channels": len(self.summary.added_columns),
            "rows": self.summary.total_rows,
            "duration_s": round(self.summary.duration_s, 2),
        }

        self._worker = MarpleExportWorker(
            file_path=out_path,
            metadata=meta,
            parent=self,
        )
        self._worker.progress.connect(self._on_upload_progress)
        self._worker.finished.connect(self._on_upload_finished)
        self._worker.start()

    def _on_upload_progress(self, pct: int, msg: str):
        self._prog_bar.setValue(pct)
        self._prog_status.setText(msg)

    def _on_upload_finished(self, success: bool, msg: str, dataset_id: str):
        self._btn_save.setEnabled(True)
        if success:
            self._prog_bar.setValue(100)
            self._prog_status.setText(f"✓ {msg}")
            self._prog_status.setStyleSheet(f"color: {ISC_GREEN}; font-weight: bold;")
            QMessageBox.information(
                self,
                "Marple Export Successful",
                f"Dataset uploaded successfully to Marple Data!\n\nDataset ID: {dataset_id}\nTarget: {Path(self.summary.output_file).name}",
            )
        else:
            self._btn_upload.setEnabled(True)
            self._prog_status.setText(f"✗ {msg}")
            self._prog_status.setStyleSheet(f"color: {F1_ERROR}; font-weight: bold;")
            QMessageBox.warning(
                self,
                "Marple Export Failed",
                f"Upload could not be completed:\n\n{msg}\n\nThe merged session remains safely saved on disk.",
            )

    @staticmethod
    def _stat_label(text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color: {F1_MUTED}; font-size: 10px; font-weight: bold;")
        return l

    @staticmethod
    def _val_label(text: str, color: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color: {color}; font-size: 10px; font-family: 'Courier New'; font-weight: bold;")
        return l


# ==============================================================================
# MANUAL MARPLE EXPORT DIALOG
# ==============================================================================

class ManualMarpleExportDialog(QDialog):
    """
    Dedicated dialog for manually pushing any historical session CSV to Marple Data.
    Can be launched directly from the Session Viewer or Main Window.
    """

    def __init__(self, session_path: Union[str, Path], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.session_path = Path(session_path)
        self._worker: Optional[MarpleExportWorker] = None
        self.setWindowTitle("ISCmetrics — Export Session to Marple Data")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(520, 380)
        self.setStyleSheet(f"""
            QDialog {{ background: {F1_DARK_BG}; color: {F1_TEXT}; }}
            QLabel {{ color: {F1_TEXT}; font-size: 11px; }}
            QLineEdit {{ background: {F1_MID_BG}; color: {F1_TEXT}; border: 1px solid #444; border-radius: 3px; padding: 4px; font-size: 11px; }}
            QLineEdit:focus {{ border-color: {ISC_GREEN}; }}
        """)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # Title
        title = QLabel("EXPORT SESSION TO MARPLE CLOUD")
        title.setStyleSheet(f"color: {ISC_GREEN}; font-size: 13px; font-weight: bold;")
        root.addWidget(title)

        # File Info
        f_lbl = QLabel(f"File: {self.session_path.name}")
        f_lbl.setStyleSheet(f"color: {F1_BLUE}; font-family: 'Courier New'; font-size: 10px;")
        root.addWidget(f_lbl)

        # Fields
        g = QGridLayout()
        g.setSpacing(8)

        g.addWidget(QLabel("Datastream Name:"), 0, 0)
        self._inp_stream = QLineEdit("ISC_Telemetry")
        g.addWidget(self._inp_stream, 0, 1)

        g.addWidget(QLabel("Driver / Pilot:"), 1, 0)
        self._inp_pilot = QLineEdit("")
        self._inp_pilot.setPlaceholderText("Optional (e.g. Andres)")
        g.addWidget(self._inp_pilot, 1, 1)

        g.addWidget(QLabel("Circuit / Event:"), 2, 0)
        self._inp_circuit = QLineEdit("")
        self._inp_circuit.setPlaceholderText("Optional (e.g. Montmelo Acceleration)")
        g.addWidget(self._inp_circuit, 2, 1)

        g.addWidget(QLabel("Notes:"), 3, 0)
        self._inp_notes = QLineEdit("")
        self._inp_notes.setPlaceholderText("Optional run comments")
        g.addWidget(self._inp_notes, 3, 1)

        root.addLayout(g)

        # Progress indicator
        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 100)
        self._prog_bar.setValue(0)
        self._prog_bar.setStyleSheet(f"""
            QProgressBar {{ background: {F1_MID_BG}; border: 1px solid #444; border-radius: 3px; height: 10px; text-align: center; font-size: 8px; }}
            QProgressBar::chunk {{ background: {ISC_GREEN}; }}
        """)
        self._prog_bar.hide()
        root.addWidget(self._prog_bar)

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("font-size: 10px; color: #888;")
        root.addWidget(self._lbl_status)

        root.addStretch()

        # Buttons
        btns = QHBoxLayout()
        self._btn_upload = QPushButton("🚀  Start Export")
        self._btn_upload.setStyleSheet(f"""
            QPushButton {{ background: {ISC_GREEN}; color: {F1_DARK_BG}; font-weight: bold; border: none; border-radius: 3px; padding: 7px 18px; }}
            QPushButton:hover {{ background: #00a000; }}
            QPushButton:disabled {{ background: #222; color: #555; }}
        """)
        self._btn_upload.clicked.connect(self._do_upload)
        btns.addWidget(self._btn_upload)

        self._btn_close = QPushButton("Cancel")
        self._btn_close.setStyleSheet(f"""
            QPushButton {{ background: {F1_PANEL_BG}; color: {F1_TEXT}; border: 1px solid #444; border-radius: 3px; padding: 7px 14px; }}
        """)
        self._btn_close.clicked.connect(self.reject)
        btns.addWidget(self._btn_close)

        root.addLayout(btns)

    def _do_upload(self):
        stream = self._inp_stream.text().strip() or "ISC_Telemetry"
        meta = {
            "pilot": self._inp_pilot.text().strip(),
            "circuit": self._inp_circuit.text().strip(),
            "notes": self._inp_notes.text().strip(),
        }

        self._prog_bar.show()
        self._prog_bar.setValue(5)
        self._lbl_status.setText("Initiating non-blocking Marple worker...")
        self._btn_upload.setEnabled(False)

        self._worker = MarpleExportWorker(
            file_path=self.session_path,
            datastream=stream,
            metadata=meta,
            parent=self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self._prog_bar.setValue(pct)
        self._lbl_status.setText(msg)

    def _on_finished(self, success: bool, msg: str, dataset_id: str):
        self._btn_upload.setEnabled(True)
        if success:
            self._prog_bar.setValue(100)
            self._lbl_status.setText(f"✓ {msg}")
            self._lbl_status.setStyleSheet(f"color: {ISC_GREEN}; font-weight: bold;")
            QMessageBox.information(
                self, "Export Successful", f"Session uploaded to Marple!\nDataset ID: {dataset_id}"
            )
            self.accept()
        else:
            self._lbl_status.setText(f"✗ {msg}")
            self._lbl_status.setStyleSheet(f"color: {F1_ERROR}; font-weight: bold;")
            QMessageBox.warning(self, "Export Failed", f"Could not upload:\n{msg}")
