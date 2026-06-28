"""
Material wizard dialog - Guide users to create new material files
"""

from __future__ import annotations

import os
import json
from datetime import datetime

import numpy as np
import pandas as pd

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QWizard, QWizardPage, QFileDialog,
    QMessageBox, QProgressBar, QGroupBox, QCheckBox,
    QComboBox, QSpinBox, QTabWidget, QWidget, QApplication,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDoubleValidator, QIntValidator, QFont

from im_app.core.data_converter import write_standard_txt

# Global font size for inputs
INPUT_FONT_SIZE = 11
TABLE_FONT_SIZE = 11


class MaterialInfoPage(QWizardPage):
    """Page 1: Material basic information"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Step 1: Material Information")
        self.setSubTitle("Enter basic material information")
        # Don't set CommitPage, let the wizard handle Next button automatically

        layout = QFormLayout(self)

        # Set larger font for labels and inputs
        font = QFont()
        font.setPointSize(INPUT_FONT_SIZE)

        # Material name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Aluminum, Copper")
        self.name_edit.setFont(font)
        layout.addRow("Material Name*:", self.name_edit)

        # Reference
        self.reference_edit = QLineEdit()
        self.reference_edit.setPlaceholderText("e.g., SESAME 3717, Smith et al. 2020")
        self.reference_edit.setFont(font)
        layout.addRow("Reference*:", self.reference_edit)

        # Initial density
        self.rho0_spin = QDoubleSpinBox()
        self.rho0_spin.setRange(0.1, 30.0)
        self.rho0_spin.setDecimals(3)
        self.rho0_spin.setSingleStep(0.1)
        self.rho0_spin.setSuffix(" g/cm³")
        self.rho0_spin.setValue(2.7)
        self.rho0_spin.setFont(font)
        layout.addRow("Initial Density (ρ₀)*:", self.rho0_spin)

        # Data source
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("e.g., LANL, Experimental data")
        self.source_edit.setFont(font)
        layout.addRow("Data Source:", self.source_edit)

        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Additional notes about the data...")
        self.notes_edit.setFont(font)
        layout.addRow("Notes:", self.notes_edit)

        # Register fields for wizard access
        self.registerField("material_name*", self.name_edit)
        self.registerField("reference*", self.reference_edit)
        # QDoubleSpinBox 在 PyQt5 下默认 property 解析不稳定，wizard.field("rho0")
        # 会返回 None（ReviewPage 摘要显示成 "Initial Density: None"）。必须显式指定
        # property="value" 并传入 valueChanged 信号（PyQt5 需要传 bound signal 对象，
        # 不能是字符串）。
        # 注意不能加 "*"（mandatory）：PyQt5 在 mandatory + 显式 changedSignal 组合下，
        # isComplete 会要求 valueChanged 至少触发一次才认为字段完成，spinbox 默认值
        # 2.7 不被识别，导致 Next 按钮始终禁用。rho0 > 0 的校验由 validatePage 保证。
        self.registerField("rho0", self.rho0_spin, "value", self.rho0_spin.valueChanged)

    def validatePage(self):
        """Validate input before proceeding"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing Field", "Please enter a material name.")
            return False
        if not self.reference_edit.text().strip():
            QMessageBox.warning(self, "Missing Field", "Please enter a reference.")
            return False
        if self.rho0_spin.value() <= 0:
            QMessageBox.warning(self, "Invalid Value", "Initial density must be positive.")
            return False
        return True


class DataInputPage(QWizardPage):
    """Page 2: Data input methods"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Step 2: Data Input")
        self.setSubTitle("Choose how to input your Hugoniot data")

        # Set font for this page
        font = QFont()
        font.setPointSize(INPUT_FONT_SIZE)
        self.setFont(font)

        layout = QVBoxLayout(self)

        # Instructions
        info = QLabel(
            "Choose how to input your Hugoniot data:\n\n"
            "• Paste from spreadsheet: Copy data from Excel/CSV and paste\n"
            "• Import from file: Load from CSV or TXT file\n"
            "• Manual entry: Type data directly into the table"
        )
        info.setWordWrap(True)
        info.setFont(font)
        layout.addWidget(info)

        # Input method selection
        method_group = QGroupBox("Input Method")
        method_layout = QVBoxLayout(method_group)

        self.paste_radio = QCheckBox("Paste from spreadsheet (recommended)")
        self.paste_radio.setChecked(True)
        self.paste_radio.setFont(font)
        method_layout.addWidget(self.paste_radio)

        self.import_radio = QCheckBox("Import from file")
        self.import_radio.setFont(font)
        method_layout.addWidget(self.import_radio)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

        # Data format info
        format_info = QLabel(
            "\nRequired columns:\n"
            "• Up (km/s) - Particle velocity\n"
            "• Us (km/s) - Shock velocity\n"
            "• P (Mbar) - Pressure\n"
            "• rho (g/cm³) - Density\n"
            "• compression - Compression ratio (rho/rho₀)\n\n"
            "Optional columns:\n"
            "• T (eV) - Temperature\n"
            "• E (MJ/g) - Internal energy\n"
            "• source - Data source identifier"
        )
        format_info.setWordWrap(True)
        format_info.setFont(font)
        layout.addWidget(format_info)

        layout.addStretch()


class DataTablePage(QWizardPage):
    """Page 3: Data table editor"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Step 3: Data Input")
        self.setSubTitle("Input or import your Hugoniot data")

        # Set font for this page
        font = QFont()
        font.setPointSize(INPUT_FONT_SIZE)
        self.setFont(font)

        table_font = QFont()
        table_font.setPointSize(TABLE_FONT_SIZE)

        layout = QVBoxLayout(self)

        # Control buttons
        control_layout = QHBoxLayout()

        self.paste_btn = QPushButton("Paste Data")
        self.paste_btn.clicked.connect(self._on_paste)
        self.paste_btn.setFont(font)
        control_layout.addWidget(self.paste_btn)

        self.import_btn = QPushButton("Import from File")
        self.import_btn.clicked.connect(self._on_import)
        self.import_btn.setFont(font)
        control_layout.addWidget(self.import_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._on_clear)
        self.clear_btn.setFont(font)
        control_layout.addWidget(self.clear_btn)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        # Data table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Up (km/s)", "Us (km/s)", "P (Mbar)",
            "rho (g/cm³)", "compression",
            "T (eV)", "E (MJ/g)", "source"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.table.setFont(table_font)
        layout.addWidget(self.table)

        # Add row button
        add_row_layout = QHBoxLayout()
        self.add_row_btn = QPushButton("Add Row")
        self.add_row_btn.clicked.connect(self._on_add_row)
        self.add_row_btn.setFont(font)
        add_row_layout.addWidget(self.add_row_btn)

        self.delete_row_btn = QPushButton("Delete Selected Row")
        self.delete_row_btn.clicked.connect(self._on_delete_row)
        self.delete_row_btn.setFont(font)
        add_row_layout.addWidget(self.delete_row_btn)

        add_row_layout.addStretch()
        layout.addLayout(add_row_layout)

        # Instructions
        hint = QLabel(
            "Tip: Double-click cells to edit. Required columns: Up, Us, P, rho, compression"
        )
        hint.setStyleSheet("color: gray; font-style: italic;")
        hint.setFont(font)
        layout.addWidget(hint)

    def _on_paste(self):
        """Paste data from clipboard"""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text.strip():
            return

        lines = text.split('\n')
        start_row = self.table.rowCount()
        pasted_count = 0

        # Column keywords to identify header rows
        column_keywords = ['up', 'us', 'p(mbar)', 'p(mbar)', 'rho', 'compression', 't(ev)', 'e(mj/g)', 'source', 'km/s']

        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue

            # Skip comment lines
            if line.strip().startswith('#'):
                continue

            parts = line.split('\t')
            if len(parts) < 5:  # 至少需要5列
                continue

            # Check if this is a header row (contains column names)
            line_lower = line.lower()
            is_header = any(keyword in line_lower for keyword in column_keywords)

            if is_header:
                # Skip header row
                continue

            # Try to parse first value as float to verify it's data
            try:
                first_val = parts[0].strip()
                if not first_val:  # Empty first cell
                    continue
                float(first_val)
            except (ValueError, IndexError):
                # First column is not a number, skip this row
                continue

            # Validate that first 5 columns are numeric (required columns)
            valid_row = True
            for j in range(min(5, len(parts))):
                val = parts[j].strip()
                if val and not self._is_numeric(val):
                    valid_row = False
                    break

            if not valid_row:
                continue

            self.table.insertRow(start_row + pasted_count)
            for j in range(8):
                if j < len(parts):
                    value = parts[j].strip()
                    # Store numeric values only, leave optional columns empty
                    if j < 5:  # Required columns
                        item = QTableWidgetItem(value)
                    else:  # Optional columns
                        if self._is_numeric(value):
                            item = QTableWidgetItem(value)
                        else:
                            item = QTableWidgetItem("")
                    self.table.setItem(start_row + pasted_count, j, item)
                else:
                    # Missing columns, add empty
                    item = QTableWidgetItem("")
                    self.table.setItem(start_row + pasted_count, j, item)
            pasted_count += 1

        if pasted_count > 0:
            QMessageBox.information(self, "Paste Complete",
                                   f"Pasted {pasted_count} valid rows into table.")
        else:
            QMessageBox.warning(self, "No Data Pasted",
                               "No valid data rows found. Make sure to copy numeric data rows.")

    def _is_numeric(self, value: str) -> bool:
        """Check if a string can be converted to float"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def _on_import(self):
        """Import data from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Data File", "",
            "All Files (*);;CSV Files (*.csv);;TXT Files (*.txt)"
        )
        if not file_path:
            return

        try:
            # Try to read as CSV/TXT
            df = pd.read_csv(file_path, sep='\t', comment='#', encoding='utf-8')

            # Clear existing data
            self.table.setRowCount(0)

            # Populate table
            for _, row in df.iterrows():
                row_pos = self.table.rowCount()
                self.table.insertRow(row_pos)

                for j, col in enumerate(df.columns):
                    if j >= 8:
                        break
                    value = str(row[col]) if pd.notna(row[col]) else ""
                    item = QTableWidgetItem(value)
                    self.table.setItem(row_pos, j, item)

            QMessageBox.information(self, "Import Successful",
                                   f"Imported {len(df)} rows from file.")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Failed to import file:\n{e}")

    def _on_clear(self):
        """Clear all data"""
        reply = QMessageBox.question(
            self, "Clear Data",
            "Are you sure you want to clear all data?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.table.setRowCount(0)

    def _on_add_row(self):
        """Add a new empty row"""
        self.table.insertRow(self.table.rowCount())

    def _on_delete_row(self):
        """Delete selected row"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def validatePage(self):
        """Validate data before proceeding"""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "Please input at least one data row.")
            return False

        # Check required columns have valid numeric data
        for row in range(self.table.rowCount()):
            has_valid_data = False
            for col in range(5):  # Check first 5 columns (required)
                item = self.table.item(row, col)
                if item and item.text().strip():
                    # Try to validate it's a number
                    try:
                        val = item.text().strip()
                        if val:  # Not empty
                            float(val)
                            has_valid_data = True
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Data",
                                           f"Row {row + 1}, Column {col + 1} contains invalid data '{item.text()}'. All required columns must contain numeric values.")
                        return False

            if not has_valid_data:
                QMessageBox.warning(self, "Incomplete Data",
                                   f"Row {row + 1} is incomplete. Please fill in at least one required column with numeric data.")
                return False

        return True

    def get_data(self):
        """Get data from table as DataFrame"""
        data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for col in range(8):
                item = self.table.item(row, col)
                value = item.text().strip() if item else ""
                row_data.append(value)

            # Skip rows where all required columns are empty
            required_values = [row_data[i] for i in range(5)]  # First 5 columns
            if all(not v for v in required_values):
                continue  # Skip this row

            data.append(row_data)

        # Check if we have any valid data
        if not data:
            raise ValueError("No valid data rows found in table")

        columns = [
            "Up(km/s)", "Us(km/s)", "P(Mbar)", "rho(g/cm3)", "compression",
            "T(eV)", "E(MJ/g)", "source"
        ]
        df = pd.DataFrame(data, columns=columns)

        # Convert numeric columns
        for col in ["Up(km/s)", "Us(km/s)", "P(Mbar)", "rho(g/cm3)", "compression"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # For optional columns T(eV) and E(MJ/g), also convert to numeric
        for col in ["T(eV)", "E(MJ/g)"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df


class ReviewPage(QWizardPage):
    """Page 4: Review and confirm"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Step 4: Review and Create")
        self.setSubTitle("Review your material and create the file")

        # Set font for this page
        font = QFont()
        font.setPointSize(INPUT_FONT_SIZE)
        self.setFont(font)

        table_font = QFont()
        table_font.setPointSize(TABLE_FONT_SIZE)

        layout = QVBoxLayout(self)

        # Summary
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setFont(font)
        layout.addWidget(self.summary_label)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QFormLayout(options_group)

        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("e.g., MyMaterial_Smith2020")
        self.filename_edit.setFont(font)
        options_layout.addRow("File Name (no extension):", self.filename_edit)

        # 必须在 __init__ 里 register：之前放在 initializePage 末尾，且顺序是
        # setText 在前、registerField 在后。wizard 的 mandatory-field 完成检测
        # 是在 registerField 时连接 widget 的 notify 信号；setText 早于连接，
        # 导致默认填好的 filename 不被识别为"已完成"，Finish 按钮被禁用，
        # 用户必须手动改一下名字才能保存。
        self.registerField("filename*", self.filename_edit)

        self.save_to_stdlib_check = QCheckBox("Save to standard library")
        self.save_to_stdlib_check.setChecked(True)
        self.save_to_stdlib_check.setFont(font)
        options_layout.addRow(self.save_to_stdlib_check)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Preview
        preview_group = QGroupBox("Data Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(5)
        self.preview_table.setHorizontalHeaderLabels([
            "Up (km/s)", "Us (km/s)", "P (Mbar)", "rho (g/cm³)", "compression"
        ])
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview_table.setMaximumHeight(200)
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.setFont(table_font)
        preview_layout.addWidget(self.preview_table)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        layout.addStretch()

    def initializePage(self):
        """Called when the page is shown"""
        wizard = self.wizard()
        if not wizard:
            return

        # Get material info
        name = wizard.field("material_name")
        reference = wizard.field("reference")
        rho0 = wizard.field("rho0")

        # Generate suggested filename
        suggested_name = f"{name.replace(' ', '_')}_{reference.replace(' ', '_')}"
        self.filename_edit.setText(suggested_name)

        # Update summary
        self.summary_label.setText(
            f"Material: {name}\n"
            f"Reference: {reference}\n"
            f"Initial Density: {rho0} g/cm³\n\n"
            f"Click 'Finish' to create the material file."
        )

        # Get data preview
        data_page = wizard.page(2)
        if isinstance(data_page, DataTablePage):
            df = data_page.get_data()

            self.preview_table.setRowCount(0)
            for i in range(min(len(df), 10)):  # Show first 10 rows
                self.preview_table.insertRow(i)
                for j, col in enumerate(["Up(km/s)", "Us(km/s)", "P(Mbar)", "rho(g/cm3)", "compression"]):
                    if col in df.columns:
                        value = df[col].iloc[i]
                        if pd.notna(value):
                            item = QTableWidgetItem(f"{value:.6g}")
                            self.preview_table.setItem(i, j, item)

    def validatePage(self):
        """Validate before creating file"""
        if not self.filename_edit.text().strip():
            QMessageBox.warning(self, "Missing Filename", "Please enter a file name.")
            return False
        return True


class MaterialWizard(QWizard):
    """Wizard for creating new Hugoniot material files"""

    file_created = pyqtSignal(str)  # emitted when file is created

    def __init__(self, lib_dir: str, parent=None):
        super().__init__(parent)
        self.lib_dir = lib_dir
        self._created_filepath = None
        self._creation_successful = False  # Track if file was created successfully

        self.setWindowTitle("New Material Wizard")
        self.setMinimumSize(2000, 1400)  # 放大一倍

        # 设置更大的字体
        font = self.font()
        font.setPointSize(11)
        self.setFont(font)

        # Add pages
        self.info_page = MaterialInfoPage(self)
        self.input_page = DataInputPage(self)
        self.data_page = DataTablePage(self)
        self.review_page = ReviewPage(self)

        self.addPage(self.info_page)
        self.addPage(self.input_page)
        self.addPage(self.data_page)
        self.addPage(self.review_page)

        # Set wizard style
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.HaveHelpButton, False)

        # 设置按钮样式
        self.setOption(QWizard.HaveCustomButton1, False)
        self.setOption(QWizard.HaveCustomButton2, False)
        self.setOption(QWizard.HaveCustomButton3, False)

        # Connect finish signal to create file
        self.finished.connect(self._on_finished)

    def get_material_info(self):
        """Get material information from page 1"""
        # Get rho0 value, ensuring it's not None
        rho0 = self.field("rho0")
        if rho0 is None:
            rho0 = self.info_page.rho0_spin.value()

        return {
            "material": self.field("material_name"),
            "reference": self.field("reference"),
            "rho0": rho0,
            "data_source": self.info_page.source_edit.text().strip(),
            "notes": self.info_page.notes_edit.toPlainText().strip(),
        }

    def get_filename(self):
        """Get the filename"""
        base_name = self.review_page.filename_edit.text().strip()
        return f"{base_name}.txt"

    def get_data(self):
        """Get data from page 3"""
        return self.data_page.get_data()

    def save_to_stdlib(self):
        """Should save to standard library"""
        return self.review_page.save_to_stdlib_check.isChecked()

    def create_material_file(self):
        """Create the material file and update metadata"""
        # Get information
        material_info = self.get_material_info()
        df = self.get_data()
        filename = self.get_filename()
        save_to_stdlib = self.save_to_stdlib()

        # Validate data before creating file
        if df is None or len(df) == 0:
            raise ValueError("No data to save")

        # Check required columns have valid data
        required_cols = ["Up(km/s)", "P(Mbar)"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
            if df[col].isna().all():
                raise ValueError(f"Column {col} has no valid data")

        # Validate numeric columns
        numeric_cols = ["Up(km/s)", "P(Mbar)", "rho(g/cm3)", "compression"]
        for col in numeric_cols:
            if col in df.columns:
                # Check if column has any valid numeric values
                valid_count = df[col].notna().sum()
                if valid_count == 0 and col in ["Up(km/s)", "P(Mbar)", "rho(g/cm3)"]:
                    raise ValueError(f"Column {col} has no valid numeric values")

        if save_to_stdlib:
            # Save to standard library
            output_path = os.path.join(self.lib_dir, "materials", filename)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Write file
            write_standard_txt(output_path, df, material_info)

            # Update metadata.json
            metadata_path = os.path.join(self.lib_dir, "metadata.json")
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # Create material ID from filename
            material_id = filename.replace('.txt', '')

            # Check if already exists
            existing = next((m for m in metadata['materials'] if m['id'] == material_id), None)
            if existing:
                # Update existing
                existing['name'] = material_info['material']
                existing['source'] = material_info['reference']
                existing['rho0'] = material_info['rho0']
                existing['file'] = f"materials/{filename}"
            else:
                # Add new material
                new_material = {
                    'id': material_id,
                    'name': material_info['material'],
                    'source': material_info['reference'],
                    'rho0': material_info['rho0'],
                    'file': f"materials/{filename}",
                    'tags': [],
                    'points': len(df),
                    'up_range': [float(df['Up(km/s)'].min()), float(df['Up(km/s)'].max())],
                    'p_range': [float(df['P(Mbar)'].min()), float(df['P(Mbar)'].max())],
                }
                if 'compression' in df.columns and df['compression'].notna().any():
                    new_material['compression_range'] = [
                        float(df['compression'].min()),
                        float(df['compression'].max())
                    ]
                metadata['materials'].append(new_material)

            # Save updated metadata
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)

            self._created_filepath = output_path
            return output_path
        else:
            # Save to custom location
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save Material File",
                filename.replace('.txt', '') + ".txt",
                "TXT Files (*.txt)"
            )
            if file_path:
                write_standard_txt(file_path, df, material_info)
                self._created_filepath = file_path
                return file_path
            return None

    def get_created_filepath(self):
        """Get the path of the created file"""
        return self._created_filepath

    def is_creation_successful(self):
        """Check if file was created successfully"""
        return self._creation_successful

    def _on_finished(self, result):
        """Handle wizard finish - create the file"""
        if result == QDialog.Accepted:
            # User clicked Finish, create the file
            try:
                filepath = self.create_material_file()
                if filepath:
                    self._creation_successful = True
                    self.file_created.emit(filepath)
                else:
                    self._creation_successful = False
                    QMessageBox.warning(self, "Not Saved",
                                     "Material was not saved to the library.")
            except Exception as e:
                self._creation_successful = False
                QMessageBox.critical(self, "Error Creating File",
                                     f"Failed to create material file:\n{e}")
