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
)
from PyQt5.QtCore import pyqtSignal, Qt

from im_app.core.physics import Intersection, RayleighLine
from im_app.core.data_loader import list_available_materials, load_material_by_id
from im_app.core.physics import MaterialData


class IntersectionPanel(QWidget):
    """Panel for intersection selection and reflection with precise control."""

    reflect_requested = pyqtSignal(str, float)  # (source_material_id, center_up)
    find_intersection = pyqtSignal(str, str, bool)  # (curve1_id, curve2_id, include_reflected)
    reverse_match_requested = pyqtSignal(float, float, str)  # (target_up, target_p, hugoniot_id)
    remove_reflected = pyqtSignal(str)  # (reflected_curve_id)
    remove_intersection = pyqtSignal(str)  # (intersection_id)

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

        self.ix_table = QTableWidget(0, 6)
        self.ix_table.setHorizontalHeaderLabels(["ID", "Curve 1", "Curve 2", "Up (km/s)", "P (Mbar)", "CR"])
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

        # Reflection controls
        refl_grp = QGroupBox("Reflect Hugoniot")
        refl_layout = QHBoxLayout(refl_grp)

        refl_layout.addWidget(QLabel("Curve:"))
        self.reflect_curve_combo = QComboBox()
        refl_layout.addWidget(self.reflect_curve_combo)

        refl_layout.addWidget(QLabel("About intersection:"))
        self.reflect_center_combo = QComboBox()
        refl_layout.addWidget(self.reflect_center_combo)

        self.reflect_btn = QPushButton("Reflect")
        self.reflect_btn.clicked.connect(self._on_reflect)
        refl_layout.addWidget(self.reflect_btn)

        self.remove_refl_btn = QPushButton("Remove Reflection")
        self.remove_refl_btn.clicked.connect(self._on_remove_reflection)
        refl_layout.addWidget(self.remove_refl_btn)

        layout.addWidget(refl_grp)

        # Reflected curves list
        self.refl_list = QListWidget()
        self.refl_list.setMinimumHeight(200)
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

    def _on_delete_intersection(self):
        """Delete selected intersection."""
        rows = self.ix_table.selectionModel().selectedRows()
        if not rows:
            return

        row = rows[0].row()
        if row < len(self._intersections):
            ix = self._intersections[row]
            self.remove_intersection.emit(ix.id)

    def add_reflected_entry(self, refl_id: str, source_name: str, center_up: float):
        item = QListWidgetItem(f"Reflected {source_name} @ center_up={center_up:.3f}")
        item.setData(Qt.UserRole, refl_id)
        self.refl_list.addItem(item)

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
