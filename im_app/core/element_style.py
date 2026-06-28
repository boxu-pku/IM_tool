"""
Element style management and editing dialogs.

Provides style data structures and Qt dialogs for editing plot element styles.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QDoubleSpinBox, QPushButton, QLabel,
    QGroupBox, QCheckBox, QColorDialog, QTabWidget,
    QWidget, QSpinBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from im_app.core.plot_style import PRL_COLORS


# Element types
TYPE_MATERIAL = "material"
TYPE_RAYLEIGH = "rayleigh"
TYPE_REFLECTED = "reflected"
TYPE_INTERSECTION = "intersection"
TYPE_SCATTER = "scatter"

# Available styles
LINE_STYLES = {
    "-": "Solid",
    "--": "Dashed",
    "-.": "Dash-dot",
    ":": "Dotted",
}

MARKERS = ["o", "s", "D", "^", "v", "P", "*", "X", "p", "h", "H", "+", "x"]

COLOR_MAP = {
    "blue": PRL_COLORS["blue"],
    "red": PRL_COLORS["red"],
    "green": PRL_COLORS["green"],
    "orange": PRL_COLORS["orange"],
    "purple": PRL_COLORS["purple"],
    "black": PRL_COLORS["black"],
}

DEFAULT_SCATTER_STYLE = {
    "color":            None,    # 创建时由调用方分配
    "marker":           "o",
    "markersize":       10.0,
    "markeredgecolor":  "black",
    "markeredgewidth":  1.5,
    "alpha":            1.0,
}


class ElementStyle:
    """Style data for a plot element."""

    def __init__(
        self,
        element_type: str,
        color: str | None = None,
        linewidth: float | None = None,
        linestyle: str | None = None,
        marker: str | None = None,
        markersize: float | None = None,
        alpha: float | None = None,
        markeredgecolor: str | None = None,
        markeredgewidth: float | None = None,
    ):
        self.element_type = element_type
        self.color = color
        self.linewidth = linewidth
        self.linestyle = linestyle
        self.marker = marker
        self.markersize = markersize
        self.alpha = alpha
        self.markeredgecolor = markeredgecolor
        self.markeredgewidth = markeredgewidth

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "color": self.color,
            "linewidth": self.linewidth,
            "linestyle": self.linestyle,
            "marker": self.marker,
            "markersize": self.markersize,
            "alpha": self.alpha,
            "markeredgecolor": self.markeredgecolor,
            "markeredgewidth": self.markeredgewidth,
        }

    @classmethod
    def from_dict(cls, element_type: str, data: dict) -> ElementStyle:
        """Create from dictionary."""
        return cls(
            element_type=element_type,
            color=data.get("color"),
            linewidth=data.get("linewidth"),
            linestyle=data.get("linestyle"),
            marker=data.get("marker"),
            markersize=data.get("markersize"),
            alpha=data.get("alpha"),
            markeredgecolor=data.get("markeredgecolor"),
            markeredgewidth=data.get("markeredgewidth"),
        )


class StyleEditorDialog(QDialog):
    """Dialog for editing plot element style."""

    def __init__(self, element_id: str, element_type: str, current_style: dict, parent=None):
        super().__init__(parent)
        self.element_id = element_id
        self.element_type = element_type
        self.current_style = current_style.copy()
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"Edit Style: {self.element_id}")
        layout = QVBoxLayout(self)

        # Element info
        info_label = QLabel(f"<b>Element Type:</b> {self.element_type}")
        layout.addWidget(info_label)

        # Build form based on element type
        form = QFormLayout()

        # Color selector
        self.color_combo = QComboBox()
        self.color_combo.addItems(list(COLOR_MAP.keys()))
        current_color = self.current_style.get("color")
        if current_color:
            # Match by name first, then by hex value
            if current_color in COLOR_MAP:
                self.color_combo.setCurrentText(current_color)
            else:
                for name, hex_val in COLOR_MAP.items():
                    if hex_val == current_color:
                        self.color_combo.setCurrentText(name)
                        break
        form.addRow("Color:", self.color_combo)

        # Alpha (transparency)
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.1, 1.0)
        self.alpha_spin.setSingleStep(0.1)
        self.alpha_spin.setValue(self.current_style.get("alpha") or 1.0)
        form.addRow("Transparency:", self.alpha_spin)

        # Line styles (for curves)
        if self.element_type in [TYPE_MATERIAL, TYPE_RAYLEIGH, TYPE_REFLECTED]:
            # Linewidth
            self.linewidth_spin = QDoubleSpinBox()
            self.linewidth_spin.setRange(0.5, 5.0)
            self.linewidth_spin.setSingleStep(0.1)
            self.linewidth_spin.setValue(self.current_style.get("linewidth") or 1.2)
            form.addRow("Line Width:", self.linewidth_spin)

            # Linestyle
            self.linestyle_combo = QComboBox()
            self.linestyle_combo.addItems(list(LINE_STYLES.values()))
            current_ls = self.current_style.get("linestyle") or "-"
            for code, name in LINE_STYLES.items():
                if code == current_ls:
                    self.linestyle_combo.setCurrentText(name)
                    break
            form.addRow("Line Style:", self.linestyle_combo)

        # Marker styles (for intersections)
        if self.element_type == TYPE_INTERSECTION:
            # Marker
            self.marker_combo = QComboBox()
            self.marker_combo.addItems(MARKERS)
            current_marker = self.current_style.get("marker") or "o"
            if current_marker in MARKERS:
                self.marker_combo.setCurrentText(current_marker)
            form.addRow("Marker:", self.marker_combo)

            # Marker size
            self.markersize_spin = QDoubleSpinBox()
            self.markersize_spin.setRange(4, 20)
            self.markersize_spin.setSingleStep(1)
            self.markersize_spin.setValue(self.current_style.get("markersize") or 8)
            form.addRow("Marker Size:", self.markersize_spin)

        # Marker styles (for scatter points)
        if self.element_type == TYPE_SCATTER:
            # Marker
            self.scatter_marker_combo = QComboBox()
            self.scatter_marker_combo.addItems(MARKERS)
            current_marker = self.current_style.get("marker") or "o"
            if current_marker in MARKERS:
                self.scatter_marker_combo.setCurrentText(current_marker)
            form.addRow("Marker:", self.scatter_marker_combo)

            # Marker size
            self.scatter_markersize_spin = QDoubleSpinBox()
            self.scatter_markersize_spin.setRange(4, 20)
            self.scatter_markersize_spin.setSingleStep(1)
            self.scatter_markersize_spin.setValue(self.current_style.get("markersize") or 10)
            form.addRow("Marker Size:", self.scatter_markersize_spin)

            # Edge color
            self.edge_color_combo = QComboBox()
            self.edge_color_combo.addItems(list(COLOR_MAP.keys()))
            current_edge = self.current_style.get("markeredgecolor") or "black"
            if current_edge:
                # Match by name first, then by hex value
                if current_edge in COLOR_MAP:
                    self.edge_color_combo.setCurrentText(current_edge)
                else:
                    for name, hex_val in COLOR_MAP.items():
                        if hex_val == current_edge:
                            self.edge_color_combo.setCurrentText(name)
                            break
            form.addRow("Edge Color:", self.edge_color_combo)

            # Edge width
            self.edgewidth_spin = QDoubleSpinBox()
            self.edgewidth_spin.setRange(0.0, 5.0)
            self.edgewidth_spin.setSingleStep(0.5)
            self.edgewidth_spin.setValue(self.current_style.get("markeredgewidth") or 1.5)
            form.addRow("Edge Width:", self.edgewidth_spin)

        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def get_updated_style(self) -> dict:
        """Return the updated style dictionary."""
        result = self.current_style.copy()

        # Update color
        color_name = self.color_combo.currentText()
        result["color"] = COLOR_MAP.get(color_name, result.get("color"))

        # Update alpha
        result["alpha"] = self.alpha_spin.value()

        # Update line styles
        if self.element_type in [TYPE_MATERIAL, TYPE_RAYLEIGH, TYPE_REFLECTED]:
            result["linewidth"] = self.linewidth_spin.value()
            # Convert name back to code
            ls_name = self.linestyle_combo.currentText()
            for code, name in LINE_STYLES.items():
                if name == ls_name:
                    result["linestyle"] = code
                    break

        # Update marker styles
        if self.element_type == TYPE_INTERSECTION:
            result["marker"] = self.marker_combo.currentText()
            result["markersize"] = self.markersize_spin.value()

        # Update scatter styles
        if self.element_type == TYPE_SCATTER:
            result["marker"] = self.scatter_marker_combo.currentText()
            result["markersize"] = self.scatter_markersize_spin.value()
            edge_name = self.edge_color_combo.currentText()
            result["markeredgecolor"] = COLOR_MAP.get(edge_name, result.get("markeredgecolor"))
            result["markeredgewidth"] = self.edgewidth_spin.value()

        return result


class QuickColorDialog(QDialog):
    """Quick dialog for changing element color."""

    def __init__(self, current_color: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Color")
        self.selected_color = current_color
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Color buttons
        color_layout = QVBoxLayout()
        for name, hex_val in COLOR_MAP.items():
            btn = QPushButton()
            btn.setText(f"  {name.capitalize()}  ")
            btn.setStyleSheet(f"background-color: {hex_val}; color: white; font-weight: bold;")
            btn.clicked.connect(lambda checked, c=hex_val: self._select_color(c))
            color_layout.addWidget(btn)

        layout.addLayout(color_layout)

        # Custom color button
        custom_btn = QPushButton("Custom Color...")
        custom_btn.clicked.connect(self._custom_color)
        layout.addWidget(custom_btn)

        # Cancel
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _select_color(self, color: str):
        self.selected_color = color
        self.accept()

    def _custom_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.selected_color = color.name()
            self.accept()
