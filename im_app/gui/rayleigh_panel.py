"""
Rayleigh line management panel.

Lets the user create Rayleigh lines by specifying material, D, and rho0.
"""

from __future__ import annotations

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QDoubleSpinBox, QPushButton,
    QListWidget, QListWidgetItem, QHBoxLayout, QLabel,
)
from PyQt5.QtCore import pyqtSignal, Qt

from im_app.core.physics import RayleighLine, rayleigh_line


class RayleighPanel(QWidget):
    """Panel for adding/removing Rayleigh lines."""

    rayleigh_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: dict[str, RayleighLine] = {}
        self._counter = 0
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        grp = QGroupBox("Rayleigh Lines")
        vbox = QVBoxLayout(grp)

        # Input form
        form = QFormLayout()

        # Custom material name (optional)
        self.custom_name_edit = QComboBox()
        self.custom_name_edit.setEditable(True)
        form.addRow("Material name:", self.custom_name_edit)

        self.D_spin = QDoubleSpinBox()
        self.D_spin.setRange(0.01, 200)
        self.D_spin.setDecimals(3)
        self.D_spin.setValue(8.0)
        self.D_spin.setSingleStep(0.1)
        self.D_spin.setSuffix(" km/s")
        form.addRow("D (shock vel):", self.D_spin)

        self.rho0_spin = QDoubleSpinBox()
        self.rho0_spin.setRange(0.01, 100)
        self.rho0_spin.setDecimals(2)
        self.rho0_spin.setValue(2.65)
        self.rho0_spin.setSuffix(" g/cm³")
        form.addRow("ρ₀ (density):", self.rho0_spin)

        vbox.addLayout(form)

        # Store materials dict for rho0 lookup
        self._materials_dict = {}

        # Auto-fill rho0 when a preset material is selected.
        # 必须只连一次：PyQt5 的 connect 不幂等，update_materials 会被反复调用，
        # 每次 connect 都会新增一条连接，导致一次切换触发 N 次 _on_material_selected。
        self.custom_name_edit.currentIndexChanged.connect(self._on_material_selected)

        self.add_btn = QPushButton("Add Rayleigh Line")
        self.add_btn.clicked.connect(self._add_line)
        vbox.addWidget(self.add_btn)

        # List of added lines
        self.line_list = QListWidget()
        self.line_list.itemChanged.connect(self._on_visibility_changed)
        vbox.addWidget(self.line_list)

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self._remove_selected)
        vbox.addWidget(self.remove_btn)

        layout.addWidget(grp)
        layout.addStretch()

    def update_materials(self, materials: dict):
        """Update the material combo box with available materials."""
        self._materials_dict = materials
        current_text = self.custom_name_edit.currentText()

        self.custom_name_edit.clear()
        for mid, mat in materials.items():
            self.custom_name_edit.addItem(f"{mat.name} ({mat.id})", mid)

        # Restore custom text if it was not a preset material
        if current_text and not any(current_text in self.custom_name_edit.itemText(i) for i in range(self.custom_name_edit.count())):
            self.custom_name_edit.setEditText(current_text)

    def _on_material_selected(self, index):
        """Auto-fill rho0 when a material is selected from the dropdown."""
        mat_id = self.custom_name_edit.currentData()
        if mat_id and mat_id in self._materials_dict:
            mat = self._materials_dict[mat_id]
            self.rho0_spin.setValue(mat.rho0)

    def _add_line(self):
        # For editable combo boxes, use lineEdit().text() instead of currentText()
        # to reliably get the custom text, especially when setEditText() is called
        # programmatically (e.g., during workflow loading).
        custom_name = self.custom_name_edit.lineEdit().text().strip()

        if not custom_name:
            return

        # 不能用 currentData() 判断是否选了预设材料：editable combo 中手动键入
        # 自定义文字时 currentIndex 不会变，currentData() 仍返回先前选中项的
        # data，会把 Rayleigh 线错误地关联到库里某个材料（导致 legend 显示成
        # 别的材料的名字）。必须用 findText 精确匹配判断 typed text 是否真的
        # 对应一个预设项。
        matched_idx = self.custom_name_edit.findText(custom_name, Qt.MatchExactly)
        mat_id = self.custom_name_edit.itemData(matched_idx) if matched_idx >= 0 else None

        D = self.D_spin.value()
        rho0 = self.rho0_spin.value()

        self._counter += 1
        rl_id = f"rl_{self._counter}"

        up = np.linspace(0, 40, 500)
        p = rayleigh_line(up, rho0, D)

        # Use custom name as material_id if no preset material selected
        material_id = mat_id if mat_id else custom_name

        rl = RayleighLine(
            id=rl_id,
            material_id=material_id,
            D=D,
            rho0=rho0,
            up=up,
            p=p,
        )
        self._lines[rl_id] = rl

        # Add to list widget - show custom name
        item = QListWidgetItem(f"{custom_name}: D={D:.2f} km/s, rho0={rho0:.2f}")
        item.setData(Qt.UserRole, rl_id)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self.line_list.addItem(item)

        self.rayleigh_changed.emit()

    def _remove_selected(self):
        current = self.line_list.currentItem()
        if current is None:
            return
        rl_id = current.data(Qt.UserRole)
        self._lines.pop(rl_id, None)
        self.line_list.takeItem(self.line_list.row(current))
        self.rayleigh_changed.emit()

    def _on_visibility_changed(self, item: QListWidgetItem):
        self.rayleigh_changed.emit()

    def get_visible_rayleigh_lines(self) -> dict[str, RayleighLine]:
        result = {}
        for i in range(self.line_list.count()):
            item = self.line_list.item(i)
            rl_id = item.data(Qt.UserRole)
            if item.checkState() == Qt.Checked and rl_id in self._lines:
                result[rl_id] = self._lines[rl_id]
        return result

    def get_all_rayleigh_lines(self) -> dict[str, RayleighLine]:
        return dict(self._lines)

    def remove_rayleigh(self, rl_id: str):
        """Remove a Rayleigh line by ID (called from plot context menu)."""
        if rl_id not in self._lines:
            return

        # Remove from storage
        self._lines.pop(rl_id, None)

        # Remove from list widget
        for i in range(self.line_list.count()):
            item = self.line_list.item(i)
            if item.data(Qt.UserRole) == rl_id:
                self.line_list.takeItem(i)
                break

        self.rayleigh_changed.emit()

    def clear(self):
        """清空所有 Rayleigh 线（用于 material refresh 全局重置）。"""
        self._lines.clear()
        self.line_list.clear()
        self._counter = 0
