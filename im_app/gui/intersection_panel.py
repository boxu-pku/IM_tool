"""
Intersection and reflection management panel.

Shows detected intersections and lets the user choose one for reflection.
Supports precise intersection finding between specific curve pairs.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
    QComboBox, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QListWidgetItem,
    QCheckBox, QDoubleSpinBox,
    QDialog, QDialogButtonBox, QFormLayout,
)
from PyQt5.QtCore import pyqtSignal, Qt

import numpy as np

from im_app.core.physics import Intersection, RayleighLine
from im_app.core.data_loader import list_available_materials, load_material_by_id
from im_app.core.physics import MaterialData


class ReleaseEditDialog(QDialog):
    """双击 Release 列表项时弹出的小对话框，编辑锚定 Up。"""

    def __init__(self, source_name: str, up_value: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Release ({source_name})")

        form = QFormLayout(self)

        self.up_spin = QDoubleSpinBox()
        self.up_spin.setRange(0, 100)
        self.up_spin.setDecimals(3)
        self.up_spin.setValue(up_value)
        self.up_spin.setSuffix(" km/s")
        self.up_spin.setSingleStep(0.1)
        form.addRow("Anchor Up:", self.up_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addWidget(buttons)

    def up_value(self) -> float:
        return self.up_spin.value()


class IntersectionPanel(QWidget):
    """Panel for intersection selection and reflection with precise control."""

    reflect_requested = pyqtSignal(str, float)  # (source_material_id, center_up)
    release_requested = pyqtSignal(str, float)  # (source_material_id, up_value) 固定 Up 锚的 release 线
    release_edited = pyqtSignal(str, float)  # (reflected_curve_id, new_up) 双击编辑 release 锚点
    find_intersection = pyqtSignal(str, str, bool)  # (curve1_id, curve2_id, include_reflected)
    reverse_match_requested = pyqtSignal(float, float, str)  # (target_up, target_p, hugoniot_id)
    remove_reflected = pyqtSignal(str)  # (reflected_curve_id)
    remove_intersection = pyqtSignal(str)  # (intersection_id)
    show_errorbars_changed = pyqtSignal(bool)  # 交点误差棒显隐切换

    def __init__(self, parent=None):
        super().__init__(parent)
        self._intersections: list[Intersection] = []
        self._materials: dict = {}
        self._rayleigh_lines: dict = {}
        self._reflected_curves: list = []
        self._reflected_entries: dict = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Intersection finding controls
        find_grp = QGroupBox("Find Intersection")
        find_layout = QVBoxLayout(find_grp)

        # 自适应刷新开关：Rayleigh / 反射线变化时自动重算依赖它们的交点。
        self.auto_update_check = QCheckBox("Auto-update intersections when curves change")
        self.auto_update_check.setChecked(True)
        self.auto_update_check.setToolTip(
            "勾选时，修改 Rayleigh 线 D / ρ₀ 或删除曲线后，已有交点会自动重算。\n"
            "关闭则恢复旧行为：交点画上去后位置冻结，需手动 Find Intersection。"
        )
        find_layout.addWidget(self.auto_update_check)

        # Curve selection
        curve_row = QHBoxLayout()
        curve_row.addWidget(QLabel("Curve 1:"))
        self.curve1_combo = QComboBox()
        self.curve1_combo.setEditable(True)
        curve_row.addWidget(self.curve1_combo)

        curve_row.addWidget(QLabel("Curve 2:"))
        self.curve2_combo = QComboBox()
        self.curve2_combo.setEditable(True)
        curve_row.addWidget(self.curve2_combo)
        find_layout.addLayout(curve_row)

        # Options
        options_row = QHBoxLayout()
        self.ignore_first_check = QCheckBox("Ignore first intersection near zero")
        self.ignore_first_check.setChecked(True)
        options_row.addWidget(self.ignore_first_check)

        self.include_reflected_check = QCheckBox("Include reflected curves")
        self.include_reflected_check.setChecked(False)
        options_row.addWidget(self.include_reflected_check)
        find_layout.addLayout(options_row)

        # Find button
        self.find_btn = QPushButton("Find Intersection")
        self.find_btn.clicked.connect(self._on_find_intersection)
        find_layout.addWidget(self.find_btn)

        layout.addWidget(find_grp)

        # Intersections table
        ix_grp = QGroupBox("Intersections")
        ix_layout = QVBoxLayout(ix_grp)

        # 交点误差棒显隐开关
        self.show_errbar_check = QCheckBox("Show error bars on intersections")
        self.show_errbar_check.setChecked(True)
        self.show_errbar_check.toggled.connect(self._on_show_errorbars_toggled)
        ix_layout.addWidget(self.show_errbar_check)

        self.ix_table = QTableWidget(0, 10)
        self.ix_table.setHorizontalHeaderLabels(
            ["ID", "Curve 1", "Curve 2", "Up (km/s)", "P (Mbar)", "CR",
             "Up err (km/s)", "P err (Mbar)", "CR err", "Rho err (g/cm3)"]
        )
        self.ix_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ix_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ix_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ix_table.setMinimumHeight(200)
        self.ix_table.itemSelectionChanged.connect(self._on_selection)
        ix_layout.addWidget(self.ix_table)

        # Delete button
        btn_row = QHBoxLayout()
        self.delete_ix_btn = QPushButton("Delete Selected Intersection")
        self.delete_ix_btn.clicked.connect(self._on_delete_intersection)
        btn_row.addWidget(self.delete_ix_btn)
        ix_layout.addLayout(btn_row)

        layout.addWidget(ix_grp)

        # Reflection / Release controls
        refl_grp = QGroupBox("Reflect / Release")
        refl_layout = QVBoxLayout(refl_grp)

        # 第一行：交点锚定反射（原 Reflect 功能）
        refl_row1 = QHBoxLayout()
        refl_row1.addWidget(QLabel("Curve:"))
        self.reflect_curve_combo = QComboBox()
        refl_row1.addWidget(self.reflect_curve_combo)

        refl_row1.addWidget(QLabel("About intersection:"))
        self.reflect_center_combo = QComboBox()
        refl_row1.addWidget(self.reflect_center_combo)

        self.reflect_btn = QPushButton("Reflect")
        self.reflect_btn.clicked.connect(self._on_reflect)
        refl_row1.addWidget(self.reflect_btn)
        refl_layout.addLayout(refl_row1)

        # 第二行：固定 Up 锚的 release 线（反射 Hugoniot 近似）
        refl_row2 = QHBoxLayout()
        refl_row2.addWidget(QLabel("Release @ Up:"))
        self.release_up_spin = QDoubleSpinBox()
        self.release_up_spin.setRange(0, 1e6)
        self.release_up_spin.setDecimals(3)
        self.release_up_spin.setValue(5.0)
        self.release_up_spin.setSingleStep(0.1)
        self.release_up_spin.setSuffix(" km/s")
        refl_row2.addWidget(self.release_up_spin)

        self.release_btn = QPushButton("Add Release")
        self.release_btn.setToolTip(
            "在所选 Hugoniot 的指定 Up 点绘制 release 线（反射 Hugoniot 近似）。\n"
            "Release 线与 Reflect 线一样可参与找交点（阻抗匹配）。"
        )
        self.release_btn.clicked.connect(self._on_release_clicked)
        refl_row2.addWidget(self.release_btn)

        self.remove_refl_btn = QPushButton("Remove Reflection")
        self.remove_refl_btn.clicked.connect(self._on_remove_reflection)
        refl_row2.addWidget(self.remove_refl_btn)
        refl_layout.addLayout(refl_row2)

        layout.addWidget(refl_grp)

        # Reflected curves list
        self.refl_list = QListWidget()
        self.refl_list.setMinimumHeight(200)
        self.refl_list.setToolTip(
            "双击 Release 条目可编辑其锚定 Up，确认后自动重算镜像曲线与依赖交点。\n"
            "Reflected 条目锚定在交点上，跟随交点移动，不在此编辑。"
        )
        # 双击 Release 条目 → 编辑锚定 Up（与 Rayleigh 线双击编辑 D 的交互一致）
        self.refl_list.itemDoubleClicked.connect(self._on_refl_item_double_clicked)
        layout.addWidget(self.refl_list)

        # Reverse impedance matching
        rev_grp = QGroupBox("Reverse Impedance Match")
        rev_layout = QVBoxLayout(rev_grp)

        # Select intersection point
        rev_point_row = QHBoxLayout()
        rev_point_row.addWidget(QLabel("From intersection:"))
        self.reverse_ix_combo = QComboBox()
        rev_point_row.addWidget(self.reverse_ix_combo)
        rev_layout.addLayout(rev_point_row)

        # Or manual input
        rev_manual_row = QHBoxLayout()
        self.reverse_up_spin = QDoubleSpinBox()
        self.reverse_up_spin.setRange(0, 100)
        self.reverse_up_spin.setDecimals(4)
        self.reverse_up_spin.setSuffix(" km/s")
        self.reverse_p_spin = QDoubleSpinBox()
        self.reverse_p_spin.setRange(0, 100)
        self.reverse_p_spin.setDecimals(4)
        self.reverse_p_spin.setSuffix(" Mbar")
        rev_manual_row.addWidget(QLabel("Up:"))
        rev_manual_row.addWidget(self.reverse_up_spin)
        rev_manual_row.addWidget(QLabel("P:"))
        rev_manual_row.addWidget(self.reverse_p_spin)
        rev_layout.addLayout(rev_manual_row)

        # Hugoniot selection
        rev_hug_row = QHBoxLayout()
        rev_hug_row.addWidget(QLabel("Hugoniot curve:"))
        self.reverse_hugoniot_combo = QComboBox()
        rev_hug_row.addWidget(self.reverse_hugoniot_combo)

        self.reverse_match_btn = QPushButton("Reverse Match")
        self.reverse_match_btn.clicked.connect(self._on_reverse_match)
        rev_hug_row.addWidget(self.reverse_match_btn)
        rev_layout.addLayout(rev_hug_row)

        layout.addWidget(rev_grp)

    def update_materials(self, materials: dict):
        """材料勾选变化时同步面板（Reflect/Release 源曲线下拉 + reverse combo + curve1/curve2）。

        保留 reflect_curve_combo 的当前选择（若材料仍勾选），避免打断操作。
        """
        self._materials = materials

        cur = self.reflect_curve_combo.currentData()
        self.reflect_curve_combo.blockSignals(True)
        self.reflect_curve_combo.clear()
        for mid, mat in materials.items():
            self.reflect_curve_combo.addItem(mat.name, mid)
        if cur is not None:
            idx = self.reflect_curve_combo.findData(cur)
            if idx >= 0:
                self.reflect_curve_combo.setCurrentIndex(idx)
        elif self.reflect_curve_combo.count() > 0:
            self.reflect_curve_combo.setCurrentIndex(0)
        self.reflect_curve_combo.blockSignals(False)

        self.reverse_hugoniot_combo.clear()
        for mid, mat in materials.items():
            self.reverse_hugoniot_combo.addItem(mat.name, mid)

        self._update_curve_combos()

    def set_intersections(self, intersections: list[Intersection], materials: dict):
        self._intersections = intersections
        self._materials = materials

        # Update table
        self.ix_table.setRowCount(len(intersections))
        for row, ix in enumerate(intersections):
            self.ix_table.setItem(row, 0, QTableWidgetItem(ix.id))
            self.ix_table.setItem(row, 1, QTableWidgetItem(ix.curve1_id))
            self.ix_table.setItem(row, 2, QTableWidgetItem(ix.curve2_id))
            self.ix_table.setItem(row, 3, QTableWidgetItem(f"{ix.up:.4f}"))
            self.ix_table.setItem(row, 4, QTableWidgetItem(f"{ix.p:.4f}"))
            # Calculate compression ratio if possible
            cr_str = "-"
            if getattr(ix, 'compression_ratio', None) is not None:
                cr_str = f"{ix.compression_ratio:.3f}"
            self.ix_table.setItem(row, 5, QTableWidgetItem(cr_str))
            # 误差列
            up_err_str = "—"
            p_err_str = "—"
            if getattr(ix, 'up_err', None) is not None and np.isfinite(ix.up_err):
                up_err_str = f"{ix.up_err:.4f}"
            if getattr(ix, 'p_err', None) is not None and np.isfinite(ix.p_err):
                p_err_str = f"{ix.p_err:.4f}"
            self.ix_table.setItem(row, 6, QTableWidgetItem(up_err_str))
            self.ix_table.setItem(row, 7, QTableWidgetItem(p_err_str))
            # CR 误差列
            cr_err_str = "—"
            if getattr(ix, 'compression_err', None) is not None and np.isfinite(ix.compression_err):
                cr_err_str = f"{ix.compression_err:.4f}"
            self.ix_table.setItem(row, 8, QTableWidgetItem(cr_err_str))
            # Rho 误差列
            rho_err_str = "—"
            if getattr(ix, 'rho_err', None) is not None and np.isfinite(ix.rho_err):
                rho_err_str = f"{ix.rho_err:.4f}"
            self.ix_table.setItem(row, 9, QTableWidgetItem(rho_err_str))

        # Update curve selection combos
        self._update_curve_combos()

        # Update reflect combos
        self.reflect_curve_combo.clear()
        for mid, mat in materials.items():
            self.reflect_curve_combo.addItem(mat.name, mid)
        if self.reflect_curve_combo.count() > 0:
            self.reflect_curve_combo.setCurrentIndex(0)

        self.reflect_center_combo.clear()
        for ix in intersections:
            label = f"{ix.curve1_id}-{ix.curve2_id} @ ({ix.up:.3f}, {ix.p:.3f})"
            self.reflect_center_combo.addItem(label, ix.id)
        if self.reflect_center_combo.count() > 0:
            self.reflect_center_combo.setCurrentIndex(0)

        # Update reverse match combos
        self.reverse_ix_combo.clear()
        for ix in intersections:
            label = f"{ix.curve1_id}-{ix.curve2_id} @ ({ix.up:.3f}, {ix.p:.3f})"
            self.reverse_ix_combo.addItem(label, ix.id)
        # Connect to auto-fill up/p when selection changes
        self.reverse_ix_combo.currentIndexChanged.connect(self._on_reverse_ix_selected)

        self.reverse_hugoniot_combo.clear()
        for mid, mat in materials.items():
            self.reverse_hugoniot_combo.addItem(mat.name, mid)

    def clear(self):
        """清空交点表（用于 material refresh 全局重置）。"""
        self.set_intersections([], {})

    def is_auto_update_enabled(self) -> bool:
        """自适应刷新是否开启（默认 True）。"""
        return self.auto_update_check.isChecked()

    def update_rayleigh_lines(self, rayleigh_lines: dict):
        """Update available Rayleigh lines."""
        self._rayleigh_lines = rayleigh_lines
        self._update_curve_combos()

    def update_reflected_curves(self, reflected_curves: list):
        """Update available reflected curves."""
        self._reflected_curves = reflected_curves
        self._update_curve_combos()

    def _update_curve_combos(self):
        """Update curve selection combo boxes."""
        # Save current selections
        curve1_id = self.curve1_combo.currentData()
        curve2_id = self.curve2_combo.currentData()

        self.curve1_combo.clear()
        self.curve2_combo.clear()

        # Build list of all entries: [(label, data)]
        hugoniot_entries = []
        for mid, mat in self._materials.items():
            hugoniot_entries.append((mat.name, mid))

        rayleigh_entries = []
        for rl_id, rl in self._rayleigh_lines.items():
            label = f"Rayleigh ({rl.material_id}, D={rl.D:.2f})"
            rayleigh_entries.append((label, rl_id))

        reflected_entries = []
        for rc in self._reflected_curves:
            source_name = rc.get("source_id", "Unknown")
            if rc.get("kind") == "release":
                label = f"Release {source_name} @ Up={rc.get('anchor_up', rc.get('center_up', 0)):.3f}"
            else:
                label = f"Reflected {source_name}"
            reflected_entries.append((label, rc["id"]))

        all_entries = hugoniot_entries + rayleigh_entries + reflected_entries

        for label, data in all_entries:
            self.curve1_combo.addItem(label, data)
            self.curve2_combo.addItem(label, data)

        # Restore curve1 if still valid
        if curve1_id:
            idx = self.curve1_combo.findData(curve1_id)
            if idx >= 0:
                self.curve1_combo.setCurrentIndex(idx)

        # Smart default for curve2: prefer different curve matching curve1
        n_hug = len(hugoniot_entries)
        n_rl = len(rayleigh_entries)
        n_total = len(all_entries)

        c1_data = self.curve1_combo.currentData()
        c2_set = False

        if n_hug >= 1 and n_rl >= 1:
            # Find first Rayleigh whose material_id matches curve1's Hugoniot
            for i, (rl_label, rl_data) in enumerate(rayleigh_entries):
                rl = self._rayleigh_lines.get(rl_data)
                if rl and rl.material_id == c1_data:
                    self.curve2_combo.setCurrentIndex(n_hug + i)
                    c2_set = True
                    break
            # If no match, try Rayleigh whose material matches any loaded Hugoniot
            if not c2_set:
                for i, (rl_label, rl_data) in enumerate(rayleigh_entries):
                    rl = self._rayleigh_lines.get(rl_data)
                    if rl and rl.material_id in self._materials:
                        self.curve2_combo.setCurrentIndex(n_hug + i)
                        c2_set = True
                        break
        elif n_hug >= 2:
            # Two different Hugoniot curves
            c1_idx = self.curve1_combo.currentIndex()
            c2_idx = 0 if c1_idx != 0 else 1
            self.curve2_combo.setCurrentIndex(c2_idx)
            c2_set = True

        # If curve2 was previously set and still valid, prefer keeping it
        # unless we already set a smart default
        if not c2_set and curve2_id:
            idx = self.curve2_combo.findData(curve2_id)
            if idx >= 0:
                self.curve2_combo.setCurrentIndex(idx)

    def _on_selection(self):
        rows = self.ix_table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            if row < len(self._intersections):
                ix = self._intersections[row]
                # Also select in center combo
                idx = self.reflect_center_combo.findData(ix.id)
                if idx >= 0:
                    self.reflect_center_combo.setCurrentIndex(idx)

    def _on_find_intersection(self):
        """Find intersection between selected curves."""
        curve1_id = self.curve1_combo.currentData()
        curve2_id = self.curve2_combo.currentData()

        if not curve1_id or not curve2_id:
            return

        ignore_first = self.ignore_first_check.isChecked()
        include_reflected = self.include_reflected_check.isChecked()

        self.find_intersection.emit(curve1_id, curve2_id, include_reflected)

    def _on_reflect(self):
        source_id = self.reflect_curve_combo.currentData()
        ix_id = self.reflect_center_combo.currentData()
        if not source_id or not ix_id:
            return

        # Find center_up from intersection
        ix = next((x for x in self._intersections if x.id == ix_id), None)
        if ix is None:
            return

        # Check if this reflection already exists
        reflection_key = f"{source_id}_{ix.up:.4f}"
        if reflection_key in self._reflected_entries:
            return  # Already reflected, do nothing

        self.reflect_requested.emit(source_id, ix.up)
        self._reflected_entries[reflection_key] = True

    def _on_release_clicked(self):
        """固定 Up 锚的 release 线：对所选 Hugoniot 在指定 Up 点做镜像。"""
        source_id = self.reflect_curve_combo.currentData()
        if not source_id:
            return
        up_value = self.release_up_spin.value()
        # 去重键与交点反射（f"{source_id}_{up:.4f}"）区分开
        release_key = f"release_{source_id}_{up_value:.4f}"
        if release_key in self._reflected_entries:
            return
        self.release_requested.emit(source_id, up_value)
        self._reflected_entries[release_key] = True

    def _on_remove_reflection(self):
        current = self.refl_list.currentItem()
        if current:
            refl_id = current.data(Qt.UserRole)
            self.refl_list.takeItem(self.refl_list.row(current))
            if refl_id:
                self.remove_reflected.emit(refl_id)
            # Clean up duplicate tracking
            keys_to_remove = [k for k, v in self._reflected_entries.items() if v == refl_id]
            for k in keys_to_remove:
                del self._reflected_entries[k]

    def _on_show_errorbars_toggled(self, checked: bool):
        self.show_errorbars_changed.emit(checked)

    def _on_delete_intersection(self):
        """Delete selected intersection."""
        rows = self.ix_table.selectionModel().selectedRows()
        if not rows:
            return

        row = rows[0].row()
        if row < len(self._intersections):
            ix = self._intersections[row]
            self.remove_intersection.emit(ix.id)

    def add_reflected_entry(self, refl_id: str, source_name: str, center_up: float,
                            kind: str = "reflected", source_id: str | None = None):
        if kind == "release":
            text = f"Release {source_name} @ Up={center_up:.3f}"
        else:
            text = f"Reflected {source_name} @ center_up={center_up:.3f}"
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, refl_id)
        self.refl_list.addItem(item)
        # 登记去重键并绑定到 refl_id，让 _on_remove_reflection 能按 id 清理
        # （否则删除后同参数 Add 会被静默吞掉）。直接调用 _on_add_release 等
        # 程序化创建路径不经过 _on_release_clicked，键只能在这里统一登记。
        if source_id:
            prefix = "release_" if kind == "release" else ""
            key = f"{prefix}{source_id}_{center_up:.4f}"
            self._reflected_entries[key] = refl_id

    def _on_refl_item_double_clicked(self, item: QListWidgetItem):
        """双击 Release 条目弹编辑对话框，OK 后 emit release_edited。

        MainWindow 侧重算镜像曲线并按需自动重算依赖交点（阻抗匹配结果）。
        Reflected 条目锚定交点、跟随交点移动，不在此编辑。
        """
        refl_id = item.data(Qt.UserRole)
        rc = next((r for r in self._reflected_curves if r.get("id") == refl_id), None)
        if rc is None or rc.get("kind") != "release":
            return
        old_up = rc.get("anchor_up", 0.0)
        mat = self._materials.get(rc.get("source_id"))
        source_name = mat.name if mat is not None else rc.get("source_id", "?")
        dlg = ReleaseEditDialog(source_name, old_up, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_up = dlg.up_value()
        if abs(new_up - old_up) < 1e-9:
            return  # 没变化，避免无谓的 refresh
        self.release_edited.emit(refl_id, new_up)

    def _on_reverse_ix_selected(self, index):
        """Auto-fill up and p from selected intersection."""
        ix_id = self.reverse_ix_combo.currentData()
        if not ix_id:
            return
        ix = next((x for x in self._intersections if x.id == ix_id), None)
        if ix:
            self.reverse_up_spin.setValue(ix.up)
            self.reverse_p_spin.setValue(ix.p)

    def _on_reverse_match(self):
        """Trigger reverse impedance matching."""
        target_up = self.reverse_up_spin.value()
        target_p = self.reverse_p_spin.value()
        hugoniot_id = self.reverse_hugoniot_combo.currentData()

        if not hugoniot_id:
            return

        self.reverse_match_requested.emit(target_up, target_p, hugoniot_id)

    def get_selected_intersection(self) -> Intersection | None:
        rows = self.ix_table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            if row < len(self._intersections):
                return self._intersections[row]
        return None
