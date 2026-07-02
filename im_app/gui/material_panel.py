"""
Material selection panel.

Loads available materials from the standard library and lets the user
toggle them on/off for plotting.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QLabel, QFileDialog, QMessageBox,
    QDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt

from im_app.core.data_loader import list_available_materials, load_material_by_id, compute_material_error_bands
from im_app.core.physics import MaterialData

import numpy as np
import json
import os
from datetime import datetime


class MaterialPanel(QWidget):
    """Left panel: material selection with checkboxes."""

    materials_changed = pyqtSignal()   # emitted when selection changes
    material_added = pyqtSignal(str)      # emitted when new material is added
    reset_all_requested = pyqtSignal()   # emitted when refresh_library is called

    def __init__(self, lib_dir: str, parent=None):
        super().__init__(parent)
        self.lib_dir = lib_dir
        self._loaded: dict[str, MaterialData] = {}  # id -> MaterialData
        self._in_memory_materials: dict[str, MaterialData] = {}  # 内存材料（非文件）
        self._init_ui()
        # Auto-refresh removed - main_window will explicitly call refresh_library after connecting signals

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Material management group
        grp = QGroupBox("Material Library")
        vbox = QVBoxLayout(grp)

        # Action buttons
        action_row = QHBoxLayout()
        self.add_material_btn = QPushButton("Add New Material")
        self.add_material_btn.setToolTip("Create a new Hugoniot material file")
        self.add_material_btn.clicked.connect(self._on_add_material)
        action_row.addWidget(self.add_material_btn)

        self.ideal_plasma_btn = QPushButton("Ideal Plasma")
        self.ideal_plasma_btn.setToolTip("Create ideal plasma Hugoniot from γ-law gas model")
        self.ideal_plasma_btn.clicked.connect(self._on_ideal_plasma)
        action_row.addWidget(self.ideal_plasma_btn)

        self.validate_btn = QPushButton("Validate File")
        self.validate_btn.setToolTip("Validate a Hugoniot data file format")
        self.validate_btn.clicked.connect(self._on_validate_file)
        action_row.addWidget(self.validate_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Reset all state and reload material library")
        self.refresh_btn.clicked.connect(self.refresh_library)
        action_row.addWidget(self.refresh_btn)

        vbox.addLayout(action_row)

        # Material list
        self.material_list = QListWidget()
        self.material_list.itemChanged.connect(self._on_item_changed)
        self.material_list.setMinimumHeight(300)
        vbox.addWidget(self.material_list)

        # Selection buttons
        btn_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.deselect_all_btn = QPushButton("Deselect All")
        self.select_all_btn.clicked.connect(self._select_all)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        btn_row.addWidget(self.select_all_btn)
        btn_row.addWidget(self.deselect_all_btn)
        vbox.addLayout(btn_row)

        # Info label
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("font-size: 24px; color: gray;")
        vbox.addWidget(self.info_label)

        layout.addWidget(grp)
        layout.addStretch()

    def _populate(self):
        self.material_list.clear()
        try:
            entries = list_available_materials(self.lib_dir)
        except FileNotFoundError:
            self.info_label.setText("Library not found")
            return

        # Sort entries alphabetically by name (case-insensitive)
        entries = sorted(entries, key=lambda x: x['name'].lower())

        for entry in entries:
            item = QListWidgetItem(
                f"{entry['name']} ({entry['source']})"
            )
            item.setData(Qt.UserRole, entry["id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.material_list.addItem(item)

        self.info_label.setText(f"{len(entries)} materials available")

        # 追加内存中的理想等离子体材料
        existing_ids = {e["id"] for e in entries}
        for mat_id, mat in self._in_memory_materials.items():
            if mat_id in existing_ids:
                continue
            item = QListWidgetItem(f"{mat.name} (Ideal Plasma)")
            item.setData(Qt.UserRole, mat_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if mat_id in self._loaded else Qt.Unchecked)
            self.material_list.addItem(item)

    def _on_item_changed(self, item: QListWidgetItem):
        mat_id = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self._load_material(mat_id)
        else:
            self._loaded.pop(mat_id, None)
        self.materials_changed.emit()

    def _load_material(self, mat_id: str):
        if mat_id in self._loaded:
            return
        # 内存材料（理想等离子体等非文件来源）
        if mat_id in self._in_memory_materials:
            self._loaded[mat_id] = self._in_memory_materials[mat_id]
            return
        try:
            df, fit_params = load_material_by_id(self.lib_dir, mat_id)
        except Exception:
            return
        entries = list_available_materials(self.lib_dir)
        meta = next((e for e in entries if e["id"] == mat_id), {})

        # Get rho0, handle None case
        rho0 = meta.get("rho0")
        if rho0 is None:
            rho0 = 2.7  # Default fallback value

        mat = MaterialData(
            id=mat_id,
            name=meta.get("name", mat_id),
            rho0=rho0,
            up=df["Up(km/s)"].values,
            p=df["P(Mbar)"].values,
            us=df["Us(km/s)"].values if "Us(km/s)" in df.columns else None,
            compression=df["compression"].values if "compression" in df.columns else None,
            rho=df["rho(g/cm3)"].values if "rho(g/cm3)" in df.columns else None,
            temperature=df["T(eV)"].values if "T(eV)" in df.columns else None,
            energy=df["E(MJ/g)"].values if "E(MJ/g)" in df.columns else None,
            fit_params=fit_params,
        )
        # 计算误差带（如果有拟合参数元数据）
        mat = compute_material_error_bands(mat)
        self._loaded[mat_id] = mat

    def _select_all(self):
        for i in range(self.material_list.count()):
            self.material_list.item(i).setCheckState(Qt.Checked)

    def _deselect_all(self):
        for i in range(self.material_list.count()):
            self.material_list.item(i).setCheckState(Qt.Unchecked)

    def get_selected_materials(self) -> dict[str, MaterialData]:
        return dict(self._loaded)

    def set_material_checked(self, mat_id: str, checked: bool):
        """Set the checked state of a material by ID."""
        for i in range(self.material_list.count()):
            item = self.material_list.item(i)
            if item.data(Qt.UserRole) == mat_id:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                break

    def refresh_library(self):
        """Refresh material list from library and sync with metadata.json"""
        was_loaded = set(self._loaded.keys())
        self._loaded.clear()
        # 恢复之前已加载的内存材料
        for mat_id, mat in self._in_memory_materials.items():
            if mat_id in was_loaded:
                self._loaded[mat_id] = mat

        # Load metadata
        try:
            meta_path = os.path.join(self.lib_dir, "metadata.json")
            with open(meta_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            self.info_label.setText("Library not found")
            return

        # Get existing material IDs
        existing_ids = {m['id'] for m in metadata.get('materials', [])}

        # Scan materials folder for new files
        materials_dir = os.path.join(self.lib_dir, "materials")
        if os.path.isdir(materials_dir):
            for filename in os.listdir(materials_dir):
                # 支持 .txt 和 .hug 文件
                if not (filename.endswith('.txt') or filename.endswith('.hug')):
                    continue

                # Extract material ID from filename
                if filename.endswith('.txt'):
                    material_id = filename.replace('.txt', '')
                else:  # .hug
                    material_id = filename.replace('.hug', '')

                # Skip if already in metadata
                if material_id in existing_ids:
                    continue

                # Try to read the file to get metadata
                file_path = os.path.join(materials_dir, filename)
                try:
                    # 根据文件扩展名选择加载方法
                    if filename.endswith('.hug'):
                        # FEOS .hug 格式
                        from im_app.core.data_loader import load_feos_hug
                        df = load_feos_hug(file_path)

                        # 从文件名提取材料名（去掉扩展名）
                        material_name = material_id
                        reference = "FEOS"
                        rho0 = 2.7
                        if 'rho(g/cm3)' in df.columns and len(df) > 0:
                            rho0 = float(df['rho(g/cm3)'].iloc[0])
                        data_source = "FEOS Calculation"
                    else:
                        # 标准 TXT/CSV 格式
                        import pandas as pd
                        df = pd.read_csv(file_path, sep='\t', comment='#', encoding='utf-8')

                        # Read metadata from comments
                        material_name = "Unknown"
                        reference = ""
                        rho0 = 2.7
                        data_source = ""

                        with open(file_path, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith('# Material:'):
                                    material_name = line.split(':', 1)[1].strip()
                                elif line.startswith('# Reference:'):
                                    reference = line.split(':', 1)[1].strip()
                                elif line.startswith('# Initial Density:'):
                                    try:
                                        rho0_str = line.split(':', 1)[1].strip().split()[0]
                                        rho0 = float(rho0_str)
                                    except:
                                        pass
                                elif line.startswith('# Data Source:'):
                                    data_source = line.split(':', 1)[1].strip()

                    # Calculate ranges
                    up_col = None
                    for col in df.columns:
                        if 'up' in col.lower() and 'km/s' in col.lower():
                            up_col = col
                            break
                        if col == 'Up(km/s)':
                            up_col = col
                            break

                    p_col = None
                    for col in df.columns:
                        if 'p(' in col.lower() and 'mbar' in col.lower():
                            p_col = col
                            break
                        if col == 'P(Mbar)':
                            p_col = col
                            break

                    if up_col and p_col:
                        up_range = [float(df[up_col].min()), float(df[up_col].max())]
                        p_range = [float(df[p_col].min()), float(df[p_col].max())]
                    else:
                        up_range = [0.0, 1.0]
                        p_range = [0.0, 1.0]

                    compression_range = None
                    compression_col = None
                    for col in df.columns:
                        if 'compression' in col.lower():
                            compression_col = col
                            break
                        if col == 'compression':
                            compression_col = col
                            break

                    if compression_col and compression_col in df.columns:
                        compression_range = [
                            float(df[compression_col].min()),
                            float(df[compression_col].max())
                        ]

                    # Add new material to metadata
                    new_material = {
                        'id': material_id,
                        'name': material_name,
                        'source': reference,
                        'rho0': rho0,
                        'file': f'materials/{filename}',
                        'tags': [],
                        'points': len(df),
                        'up_range': up_range,
                        'p_range': p_range,
                    }
                    if compression_range:
                        new_material['compression_range'] = compression_range

                    metadata['materials'].append(new_material)

                except Exception as e:
                    # Skip files that can't be parsed
                    continue

        # Check each material file and remove if not exists
        materials_to_keep = []
        for material in metadata.get('materials', []):
            file_path = os.path.join(self.lib_dir, material.get('file', ''))
            if os.path.isfile(file_path):
                materials_to_keep.append(material)

        # Update metadata
        metadata['materials'] = materials_to_keep
        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

        # Populate the list
        self._populate()

        # Emit signal to notify main_window to reset all state
        self.reset_all_requested.emit()

    def _on_ideal_plasma(self):
        """打开理想等离子体 Hugoniot 创建对话框。"""
        from im_app.gui.ideal_plasma_dialog import IdealPlasmaDialog

        dialog = IdealPlasmaDialog(self.lib_dir, self)
        if dialog.exec_() == QDialog.Accepted:
            mat = dialog.get_material()
            mat_id = mat.id
            gamma = dialog.gamma_spin.value()

            if dialog.save_to_library():
                # 已写入文件，刷新库并勾选（不入 _in_memory_materials）
                self.refresh_library()
                self.set_material_checked(mat_id, True)
            else:
                # 纯内存：注册到 _in_memory_materials
                self._in_memory_materials[mat_id] = mat
                # 添加列表项并自动勾选
                item = QListWidgetItem(f"{mat.name} (Ideal Plasma, γ={gamma:.3f})")
                item.setData(Qt.UserRole, mat_id)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                self.material_list.addItem(item)
                self._loaded[mat_id] = mat
                item.setCheckState(Qt.Checked)
                self.materials_changed.emit()

            self.material_added.emit(mat_id)

    def _on_add_material(self):
        """Open material creation wizard"""
        from im_app.gui.material_wizard import MaterialWizard

        wizard = MaterialWizard(self.lib_dir, self)
        if wizard.exec() == QDialog.Accepted:
            # Check if file was created successfully
            if not wizard.is_creation_successful():
                # File creation failed, don't show success message
                return

            # Get the created file info
            material_info = wizard.get_material_info()
            filename = wizard.get_filename()
            save_to_stdlib = wizard.save_to_stdlib()

            if save_to_stdlib:
                # File was saved to standard library
                QMessageBox.information(
                    self, "Material Created",
                    f"Material '{material_info['material']}' has been created successfully!\n\n"
                    f"File: {filename}\n"
                    f"Points: {len(wizard.get_data())}"
                )
                # Refresh library to show new material
                self.refresh_library()
                self.material_added.emit(filename)
            else:
                QMessageBox.information(
                    self, "Material Created",
                    f"Material '{material_info['material']}' has been created!\n\n"
                    f"File saved to: {filename}"
                )

    def _on_validate_file(self):
        """Open file validation dialog"""
        from im_app.gui.validation_dialog import FileValidationDialog

        dialog = FileValidationDialog(self.lib_dir, self)
        dialog.exec()
