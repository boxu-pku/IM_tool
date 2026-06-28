"""
File validation dialog - Validate Hugoniot data file format
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFileDialog, QGroupBox,
    QFormLayout, QLineEdit, QCheckBox, QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor, QFont

from im_app.tools.validate_hugoniot import validate_file, ValidationResult


class ValidationThread(QThread):
    """Background thread for file validation"""

    finished = pyqtSignal(object)  # ValidationResult

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath

    def run(self):
        """Run validation in background"""
        result = validate_file(self.filepath)
        self.finished.emit(result)


class FileValidationDialog(QDialog):
    """Dialog for validating Hugoniot data files"""

    def __init__(self, lib_dir: str, parent=None):
        super().__init__(parent)
        self.lib_dir = lib_dir
        self.setWindowTitle("Validate Hugoniot File")
        self.setMinimumSize(1800, 1200)  # 放大一倍

        # 设置更大的字体
        font = self.font()
        font.setPointSize(11)
        self.setFont(font)

        # 结果文本框使用等宽字体
        result_font = QFont("Consolas, Monaco, Courier New")
        result_font.setPointSize(10)

        layout = QVBoxLayout(self)

        # File selection
        file_group = QGroupBox("File Selection")
        file_layout = QFormLayout(file_group)

        self.filepath_edit = QLineEdit()
        self.filepath_edit.setPlaceholderText("Select a file to validate...")
        self.filepath_edit.setFont(font)
        file_layout.addRow("File Path:", self.filepath_edit)

        btn_row = QHBoxLayout()
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._on_browse)
        self.browse_btn.setFont(font)
        btn_row.addWidget(self.browse_btn)

        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self._on_validate)
        self.validate_btn.setFont(font)
        btn_row.addWidget(self.validate_btn)

        file_layout.addRow(btn_row)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Validation options
        options_group = QGroupBox("Validation Options")
        options_layout = QVBoxLayout(options_group)

        self.check_encoding = QCheckBox("Check file encoding (UTF-8)")
        self.check_encoding.setChecked(True)
        self.check_encoding.setFont(font)
        options_layout.addWidget(self.check_encoding)

        self.check_line_endings = QCheckBox("Check line endings (LF vs CRLF)")
        self.check_line_endings.setChecked(True)
        self.check_line_endings.setFont(font)
        options_layout.addWidget(self.check_line_endings)

        self.check_data_format = QCheckBox("Check data format and values")
        self.check_data_format.setChecked(True)
        self.check_data_format.setFont(font)
        options_layout.addWidget(self.check_data_format)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Results
        results_group = QGroupBox("Validation Results")
        results_layout = QVBoxLayout(results_group)

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setFont(result_font)
        results_layout.addWidget(self.results_text)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setFont(font)
        layout.addWidget(close_btn)

        self.validation_thread = None

    def _on_browse(self):
        """Browse for file to validate"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Hugoniot File",
            str(self.lib_dir),
            "TXT Files (*.txt);;CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            self.filepath_edit.setText(file_path)

    def _on_validate(self):
        """Start validation"""
        filepath = self.filepath_edit.text().strip()
        if not filepath:
            QMessageBox.warning(self, "No File", "Please select a file to validate.")
            return

        if not os.path.isfile(filepath):
            QMessageBox.warning(self, "File Not Found", f"File not found:\n{filepath}")
            return

        # Disable controls
        self.validate_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.results_text.clear()
        self.results_text.append("Validating file...\n")

        # Start background validation
        self.validation_thread = ValidationThread(filepath)
        self.validation_thread.finished.connect(self._on_validation_finished)
        self.validation_thread.start()

    def _on_validation_finished(self, result: ValidationResult):
        """Handle validation completion"""
        # Re-enable controls
        self.validate_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)

        # Display results
        self.results_text.clear()

        # Build report
        report = []
        report.append("=" * 60)
        report.append(f"File: {result.filepath}")
        report.append("=" * 60)
        report.append("")

        if result.valid:
            report.append("[OK] Format validation passed")
        else:
            report.append("[FAIL] Format validation failed")

        report.append("")

        # File info
        if result.info:
            report.append("File Info:")
            for key, value in result.info.items():
                report.append(f"  {key}: {value}")
            report.append("")

        # Warnings
        if result.warnings:
            report.append("Warnings:")
            for warning in result.warnings:
                report.append(f"  [WARN] {warning}")
            report.append("")

        # Errors
        if result.errors:
            report.append("Errors:")
            for error in result.errors:
                report.append(f"  [ERROR] {error}")
            report.append("")

        report.append("=" * 60)

        self.results_text.append("\n".join(report))

        # Scroll to top
        cursor = self.results_text.textCursor()
        cursor.setPosition(0)
        self.results_text.setTextCursor(cursor)

    def accept(self):
        """Close dialog"""
        # Stop any running validation
        if self.validation_thread and self.validation_thread.isRunning():
            self.validation_thread.terminate()
            self.validation_thread.wait(1000)
        super().accept()
