"""
Main window for the impedance matching tool.

Layout: left panel (materials, rayleigh, plot settings, intersections) | right panel (square plot).
Window starts maximized.
"""

from __future__ import annotations

import json
import os

import numpy as np
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QTabWidget, QToolBar, QAction, QFileDialog,
    QMessageBox, QStatusBar, QLabel, QGroupBox,
    QFormLayout, QDoubleSpinBox, QCheckBox, QComboBox,
    QHBoxLayout, QPushButton, QScrollArea, QDialog,
    QListWidget, QListWidgetItem,
)
from PyQt5.QtCore import Qt, QSize

from im_app.core.data_loader import list_available_materials, load_material_by_id
from im_app.core.reference_curve import VARIABLE_MAPPING
from im_app.core.physics import (
    MaterialData, RayleighLine,
    rayleigh_line, find_intersections, compression_ratio,
)
from im_app.core.plotter import InteractiveHugoniotPlot, EOSPlot, GenericHugoniotPlot
from im_app.gui.material_panel import MaterialPanel
from im_app.gui.rayleigh_panel import RayleighPanel
from im_app.gui.intersection_panel import IntersectionPanel
from im_app.gui.reference_curve_panel import ReferenceCurvePanel

# 硬编码默认范围，'a' 键重置时使用。已和 _init_plot_controls 的初值对齐。
PLOT_DEFAULTS = {
    "P-Up":   ((0, 30), (0, 30)),
    "P-CR":   ((1, 5),  (0, 10)),
    "Us-Up":  ((0, 30), (0, 30)),
    "P-T":    ((0, 30), (0, 10)),
    "rho-Up": ((2, 20), (0, 30)),
    "T-Up":   ((0, 10), (0, 30)),
    "E-Up":   ((0, 20), (0, 30)),
    "P-Us":   ((0, 30), (0, 30)),
}

# Tab key to (x_var, y_var) mapping for scatter points
TAB_XY_MAP = {
    "P-Up":   ("Up", "P"),
    "P-CR":   ("compression", "P"),
    "Us-Up":  ("Us", "Up"),
    "P-T":    ("P", "T"),
    "rho-Up": ("rho", "Up"),
    "T-Up":   ("T", "Up"),
    "E-Up":   ("E", "Up"),
    "P-Us":   ("P", "Us"),
}


class MainWindow(QMainWindow):
    """Impedance matching tool main window."""

    def __init__(self, lib_dir: str, workflows_dir: str):
        super().__init__()
        self.lib_dir = lib_dir
        self.workflows_dir = workflows_dir
        os.makedirs(workflows_dir, exist_ok=True)

        self._init_ui()
        self._init_toolbar()
        self._init_menu()
        self._connect_signals()

        # All UI is now created — safe to trigger first material library refresh
        # (this emits reset_all_requested, which calls _on_material_reset_all
        # accessing hugoniot_plot, rayleigh_panel, intersection_panel, etc.)
        self.material_panel.refresh_library()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _init_plot_controls(self, parent_layout):
        """Initialize plot parameter controls with per-plot settings."""
        grp = QGroupBox("Plot Settings")
        main_layout = QVBoxLayout(grp)

        # Plot selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Target Plot:"))
        self.target_plot_combo = QComboBox()
        self.target_plot_combo.addItems([
            "P-Up Diagram",
            "P-CR Diagram",
            "Us-Up Diagram",
            "P-T Diagram",
            "rho-Up Diagram",
            "T-Up Diagram",
            "E-Up Diagram",
            "P-Us Diagram",
        ])
        self.target_plot_combo.currentIndexChanged.connect(self._on_target_plot_changed)
        selector_layout.addWidget(self.target_plot_combo)
        main_layout.addLayout(selector_layout)

        # Axis info label
        self.axis_info_label = QLabel("Axes: Up (km/s) vs P (Mbar)")
        self.axis_info_label.setStyleSheet("color: #666; font-style: italic; font-size: 24px;")
        main_layout.addWidget(self.axis_info_label)

        form = QFormLayout()

        # X-axis limits
        xlim_layout = QHBoxLayout()
        self.xmin_spin = QDoubleSpinBox()
        self.xmin_spin.setRange(0, 100)
        self.xmin_spin.setValue(0)
        self.xmin_spin.setSingleStep(1)
        self.xmin_spin.setSuffix(" km/s")
        self.xmax_spin = QDoubleSpinBox()
        self.xmax_spin.setRange(0, 100)
        self.xmax_spin.setValue(30)
        self.xmax_spin.setSingleStep(1)
        self.xmax_spin.setSuffix(" km/s")
        xlim_layout.addWidget(self.xmin_spin)
        xlim_layout.addWidget(QLabel("-"))
        xlim_layout.addWidget(self.xmax_spin)
        form.addRow("X limits:", xlim_layout)

        # Y-axis limits
        ylim_layout = QHBoxLayout()
        self.ymin_spin = QDoubleSpinBox()
        self.ymin_spin.setRange(0, 100)
        self.ymin_spin.setValue(0)
        self.ymin_spin.setSingleStep(1)
        self.ymin_spin.setSuffix(" Mbar")
        self.ymax_spin = QDoubleSpinBox()
        self.ymax_spin.setRange(0, 100)
        self.ymax_spin.setValue(30)
        self.ymax_spin.setSingleStep(1)
        self.ymax_spin.setSuffix(" Mbar")
        ylim_layout.addWidget(self.ymin_spin)
        ylim_layout.addWidget(QLabel("-"))
        ylim_layout.addWidget(self.ymax_spin)
        form.addRow("Y limits:", ylim_layout)

        # Legend checkbox
        self.legend_check = QCheckBox("Show Legend")
        self.legend_check.setChecked(True)
        form.addRow(self.legend_check)

        # Line style (only for P-Up)
        self.linestyle_combo = QComboBox()
        self.linestyle_combo.addItems(["Solid (-)", "Dashed (---)", "Dotted (...)", "Dash-dot (-.-)"])
        self.linestyle_combo.setCurrentIndex(0)
        form.addRow("Line style:", self.linestyle_combo)

        # Line width (only for P-Up)
        self.linewidth_spin = QDoubleSpinBox()
        self.linewidth_spin.setRange(0.5, 5.0)
        self.linewidth_spin.setValue(1.2)
        self.linewidth_spin.setSingleStep(0.1)
        form.addRow("Line width:", self.linewidth_spin)

        # Action buttons row
        action_btn_layout = QHBoxLayout()

        self.auto_range_btn = QPushButton("Auto Range")
        self.auto_range_btn.setToolTip("Set axis limits to data range (1.1x margin)")
        self.auto_range_btn.clicked.connect(self._on_auto_range)
        action_btn_layout.addWidget(self.auto_range_btn)

        self.inverse_axes_btn = QPushButton("Inverse Axes")
        self.inverse_axes_btn.setToolTip("Swap X and Y axes")
        self.inverse_axes_btn.clicked.connect(self._on_inverse_axes)
        action_btn_layout.addWidget(self.inverse_axes_btn)

        # Apply button
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_plot_settings)
        action_btn_layout.addWidget(apply_btn)

        form.addRow(action_btn_layout)

        main_layout.addLayout(form)
        parent_layout.addWidget(grp)

        # Store independent settings for each plot
        self._plot_settings = {
            "P-Up": {
                "xlim": (0, 30),
                "ylim": (0, 30),
                "show_legend": True,
                "linestyle": "-",
                "linewidth": 1.2,
                "inverse": False,
            },
            "P-CR": {
                "xlim": (1, 5),
                "ylim": (0, 10),
                "show_legend": True,
                "inverse": False,
            },
            "Us-Up": {
                "xlim": (0, 30),
                "ylim": (0, 30),
                "show_legend": True,
                "inverse": False,
            },
            "P-T": {
                "xlim": (0, 30),  # X = P
                "ylim": (0, 10),  # Y = T
                "show_legend": True,
                "inverse": False,
            },
            "rho-Up": {
                "xlim": (2, 20),  # X = rho
                "ylim": (0, 30),  # Y = Up
                "show_legend": True,
                "inverse": False,
            },
            "T-Up": {
                "xlim": (0, 10),  # X = T
                "ylim": (0, 30),  # Y = Up
                "show_legend": True,
                "inverse": False,
            },
            "E-Up": {
                "xlim": (0, 20),  # X = E
                "ylim": (0, 30),  # Y = Up
                "show_legend": True,
                "inverse": False,
            },
            "P-Us": {
                "xlim": (0, 30),  # X = P
                "ylim": (0, 30),  # Y = Us
                "show_legend": True,
                "inverse": False,
            },
        }

        # Store original plot configurations for inverse functionality
        self._original_plot_configs = {
            "Us-Up Diagram": ("Us", "Up"),
            "P-T Diagram": ("P", "T"),
            "rho-Up Diagram": ("rho", "Up"),
            "T-Up Diagram": ("T", "Up"),
            "E-Up Diagram": ("E", "Up"),
            "P-Us Diagram": ("P", "Us"),
        }

        # Track current inverse state for each generic plot
        self._plot_inverse_state = {
            "Us-Up": False,
            "P-T": False,
            "rho-Up": False,
            "T-Up": False,
            "E-Up": False,
            "P-Us": False,
        }

    def _init_scatter_controls(self, parent_layout):
        """Initialize scatter point controls (intersection + manual)."""
        grp = QGroupBox("Scatter Points")
        layout = QVBoxLayout(grp)

        # ─── From Intersection ───
        ix_row = QHBoxLayout()
        ix_row.addWidget(QLabel("Intersection:"))
        self.scatter_ix_combo = QComboBox()
        self.scatter_ix_combo.setMinimumWidth(200)
        ix_row.addWidget(self.scatter_ix_combo, 1)
        self.scatter_ix_add_btn = QPushButton("Add")
        self.scatter_ix_add_btn.setEnabled(False)
        self.scatter_ix_add_btn.clicked.connect(self._add_intersection_scatter_point)
        ix_row.addWidget(self.scatter_ix_add_btn)
        layout.addLayout(ix_row)

        # ─── Manual ───
        manual_box = QGroupBox()
        manual_box.setTitle("Manual")
        manual_layout = QHBoxLayout(manual_box)
        self.scatter_manual_tab_lbl = QLabel("current tab: P-Up")
        manual_layout.addWidget(self.scatter_manual_tab_lbl)
        manual_layout.addStretch()
        self.scatter_x_label = QLabel("Up:")
        manual_layout.addWidget(self.scatter_x_label)
        self.scatter_x_spin = QDoubleSpinBox()
        self.scatter_x_spin.setRange(0, 30)
        self.scatter_x_spin.setDecimals(3)
        self.scatter_x_spin.setValue(5.0)
        manual_layout.addWidget(self.scatter_x_spin)
        self.scatter_y_label = QLabel("P:")
        manual_layout.addWidget(self.scatter_y_label)
        self.scatter_y_spin = QDoubleSpinBox()
        self.scatter_y_spin.setRange(0, 100)
        self.scatter_y_spin.setDecimals(3)
        self.scatter_y_spin.setValue(1.0)
        manual_layout.addWidget(self.scatter_y_spin)
        self.scatter_manual_add_btn = QPushButton("Add")
        self.scatter_manual_add_btn.clicked.connect(self._add_manual_scatter_point)
        manual_layout.addWidget(self.scatter_manual_add_btn)
        layout.addWidget(manual_box)

        # ─── Points list ───
        self.scatter_list = QListWidget()
        self.scatter_list.setMaximumHeight(120)
        layout.addWidget(self.scatter_list)
        list_btn_row = QHBoxLayout()
        self.scatter_delete_btn = QPushButton("Delete Selected")
        self.scatter_delete_btn.clicked.connect(self._on_scatter_delete_selected)
        list_btn_row.addWidget(self.scatter_delete_btn)
        self.scatter_clear_btn = QPushButton("Clear All")
        self.scatter_clear_btn.clicked.connect(self._clear_all_scatter_points)
        list_btn_row.addWidget(self.scatter_clear_btn)
        layout.addLayout(list_btn_row)

        parent_layout.addWidget(grp)

        # Scatter 状态
        self._scatter_points = []
        self._scatter_counter = 0
        self._scatter_color_counter = 0

    def _init_ui(self):
        self.setWindowTitle("Impedance Matching Tool")
        self.setMinimumSize(1000, 700)

        # Global group box title style: bold + larger font
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 28px;
                background-color: #eaf2fb;
                border: 2px solid #b0c4de;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #1a3a6b;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        # Horizontal splitter: left panel | right plot
        splitter = QSplitter(Qt.Horizontal)

        # Left panel container with scroll area
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Material panel
        self.material_panel = MaterialPanel(self.lib_dir)
        # Connect reset signal BEFORE triggering first refresh (Task 11 removed auto-refresh)
        self.material_panel.reset_all_requested.connect(self._on_material_reset_all)
        # NOTE: refresh_library() deferred until after _init_scatter_controls runs
        left_layout.addWidget(self.material_panel)

        # Rayleigh panel
        self.rayleigh_panel = RayleighPanel()
        left_layout.addWidget(self.rayleigh_panel)

        # Intersection panel
        self.intersection_panel = IntersectionPanel()
        left_layout.addWidget(self.intersection_panel)

        # Scatter point controls
        self._init_scatter_controls(left_layout)
        # NOTE: refresh_library() is called at end of __init__ (after all UI is created),
        # because it triggers _on_material_reset_all which accesses hugoniot_plot etc.

        # Reference curve panel
        curve_dir = os.path.join(self.lib_dir, "reference_curves")
        self.reference_curve_panel = ReferenceCurvePanel(curve_dir)
        left_layout.addWidget(self.reference_curve_panel)

        left_layout.addStretch()

        # Plot controls at the bottom (outside analysis flow)
        self._init_plot_controls(left_layout)

        # Wrap in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(left_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 左面板最小宽 600px（既保证控件可读，又不会挤掉右侧画图区）。
        # 不设 maximumWidth，让用户可以随意拖宽。
        scroll_area.setMinimumWidth(600)

        # Right panel: square canvas plot
        self.plot_tabs = QTabWidget()
        self.hugoniot_plot = InteractiveHugoniotPlot()
        self.eos_plot = EOSPlot()

        # Create generic plots
        self.us_up_plot = GenericHugoniotPlot("Us", "Up")
        self.p_t_plot = GenericHugoniotPlot("P", "T")
        self.rho_up_plot = GenericHugoniotPlot("rho", "Up")
        self.t_up_plot = GenericHugoniotPlot("T", "Up")
        self.e_up_plot = GenericHugoniotPlot("E", "Up")
        self.p_us_plot = GenericHugoniotPlot("P", "Us")

        # Add tabs
        self.plot_tabs.addTab(self.hugoniot_plot, "P-Up Diagram")
        self.plot_tabs.addTab(self.eos_plot, "P-CR Diagram")
        self.plot_tabs.addTab(self.us_up_plot, "Us-Up Diagram")
        self.plot_tabs.addTab(self.p_t_plot, "P-T Diagram")
        self.plot_tabs.addTab(self.rho_up_plot, "rho-Up Diagram")
        self.plot_tabs.addTab(self.t_up_plot, "T-Up Diagram")
        self.plot_tabs.addTab(self.e_up_plot, "E-Up Diagram")
        self.plot_tabs.addTab(self.p_us_plot, "P-Us Diagram")
        self.plot_tabs.currentChanged.connect(self._on_tab_changed)

        # Add to splitter
        splitter.addWidget(scroll_area)
        splitter.addWidget(self.plot_tabs)
        # 初始 38:62 比例，左右都设 stretchFactor=1 让窗口缩放时同步分摊；
        # 禁止 collapsible 防止误拖到 0 宽。
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([380, 620])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        # 保存 splitter 引用，便于记住用户调整后的比例（未来扩展）
        self.main_splitter = splitter

        layout.addWidget(splitter)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready - select materials and add Rayleigh lines")

        # Author info (permanent widget on right)
        self.author_label = QLabel("Author: BoXu Email: boxu25@stu.pku.edu.cn")
        self.status.addPermanentWidget(self.author_label)

    def _init_toolbar(self):
        tb = QToolBar("Main Tools")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        self.act_find_ix = QAction("Find Intersections", self)
        self.act_find_ix.setToolTip("Compute all Hugoniot-Rayleigh intersections")
        tb.addAction(self.act_find_ix)

        tb.addSeparator()

        self.act_save_plot = QAction("Save Plot", self)
        tb.addAction(self.act_save_plot)

        self.act_save_workflow = QAction("Save Workflow", self)
        tb.addAction(self.act_save_workflow)

        self.act_load_workflow = QAction("Load Workflow", self)
        tb.addAction(self.act_load_workflow)

    def _init_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        file_menu.addAction("Load Workflow...", self._load_workflow)
        file_menu.addAction("Save Workflow...", self._save_workflow)
        file_menu.addSeparator()
        file_menu.addAction("Export Plot...", self._export_plot)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        # Reference Curves menu
        ref_menu = mb.addMenu("Reference Curves")
        ref_menu.addAction("Manage Curves...", self._manage_reference_curves)
        ref_menu.addAction("Create New Curve...", self._create_reference_curve)

    def _manage_reference_curves(self):
        """打开参考曲线管理对话框"""
        from im_app.gui.reference_curve_manager import ReferenceCurveManager

        curve_dir = os.path.join(self.lib_dir, "reference_curves")
        dialog = ReferenceCurveManager(curve_dir, self)
        dialog.exec()

    def _create_reference_curve(self):
        """创建新的参考曲线"""
        from im_app.gui.reference_curve_dialog import ReferenceCurveDialog

        curve_dir = os.path.join(self.lib_dir, "reference_curves")
        dialog = ReferenceCurveDialog(curve_dir, self)
        if dialog.exec() == QDialog.Accepted:
            # 刷新参考曲线面板
            self.reference_curve_panel.refresh_library()

    def _on_reference_curves_changed(self):
        """当参考曲线选择改变时调用"""
        curves = self.reference_curve_panel.get_selected_curves()

        # 定义每个图表需要的变量对
        plot_requirements = {
            # 图表对象: (需要的X变量字段名, 需要的Y变量字段名)
            self.hugoniot_plot: ("up", "p"),
            self.p_t_plot: ("p", "temperature"),
            self.us_up_plot: ("us", "up"),
            self.rho_up_plot: ("rho", "up"),
            self.t_up_plot: ("temperature", "up"),
            self.e_up_plot: ("energy", "up"),
            self.p_us_plot: ("p", "us"),
        }

        # 同步到各个图表
        for plot, (x_var, y_var) in plot_requirements.items():
            # 获取当前已加载的参考曲线ID
            ref_curve_ids = {mid for mid in plot.materials.keys() if mid.startswith("ref_")}
            new_curve_ids = set(curves.keys())

            # 移除未选中的
            for mid in ref_curve_ids - new_curve_ids:
                plot.remove_material(mid)

            # 添加新选中的 - 只有当曲线有该图表需要的变量时才添加
            for mid, mat in curves.items():
                if mid not in plot.materials:
                    # 检查曲线是否有该图表需要的 X 和 Y 变量
                    x_data = getattr(mat, x_var, None)
                    y_data = getattr(mat, y_var, None)

                    # 检查数据是否存在且不为空
                    x_exists = x_data is not None and len(x_data) > 0
                    y_exists = y_data is not None and len(y_data) > 0

                    if x_exists and y_exists:
                        plot.add_material(mat)

        # P-CR 图 (EOSPlot) 使用 self.hugoniot_plot.materials，不需要单独处理

        self._update_status()

    def _on_reference_curve_selected(self, filepath: str):
        """这个方法不再使用，保留用于兼容"""
        pass

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self.material_panel.materials_changed.connect(self._on_materials_changed)
        self.material_panel.material_added.connect(self._on_material_added)
        self.rayleigh_panel.rayleigh_changed.connect(self._on_rayleigh_changed)
        self.reference_curve_panel.curves_changed.connect(self._on_reference_curves_changed)
        self.hugoniot_plot.intersection_selected.connect(self._on_intersection_selected)
        self.hugoniot_plot.element_selected.connect(self._on_element_selected)
        self.hugoniot_plot.element_deleted.connect(self._on_element_deleted)
        self.hugoniot_plot.style_changed.connect(self._on_element_style_changed)

        # 其他 7 个 plot 也连接元素交互信号（EOS / Generic）
        for plot in [self.eos_plot, self.us_up_plot, self.p_t_plot,
                     self.rho_up_plot, self.t_up_plot, self.e_up_plot,
                     self.p_us_plot]:
            plot.element_selected.connect(self._on_element_selected)
            plot.element_deleted.connect(self._on_element_deleted)
            plot.style_changed.connect(self._on_element_style_changed)

        self.intersection_panel.reflect_requested.connect(self._on_reflect)
        self.intersection_panel.find_intersection.connect(self._find_specific_intersection)
        self.intersection_panel.reverse_match_requested.connect(self._on_reverse_match)
        self.intersection_panel.remove_reflected.connect(self._on_remove_reflected)
        self.intersection_panel.remove_intersection.connect(self._on_remove_intersection)

        self.act_find_ix.triggered.connect(self._find_intersections)
        self.act_save_plot.triggered.connect(self._export_plot)
        self.act_save_workflow.triggered.connect(self._save_workflow)
        self.act_load_workflow.triggered.connect(self._load_workflow)

        # 拖拽缩放 + 'a' 重置信号连接
        plot_key_pairs = [
            (self.hugoniot_plot, "P-Up"),
            (self.eos_plot,      "P-CR"),
            (self.us_up_plot,    "Us-Up"),
            (self.p_t_plot,      "P-T"),
            (self.rho_up_plot,   "rho-Up"),
            (self.t_up_plot,     "T-Up"),
            (self.e_up_plot,     "E-Up"),
            (self.p_us_plot,     "P-Us"),
        ]
        for plot, key in plot_key_pairs:
            plot.zoom_applied.connect(
                lambda x0, x1, y0, y1, k=key:
                    self._on_plot_zoom_applied(k, x0, x1, y0, y1)
            )
            plot.reset_view.connect(
                lambda k=key: self._on_plot_reset_view(k)
            )

        # Initialize plot settings display
        self._on_target_plot_changed(0)

    def _on_material_added(self, filename: str):
        """Handle when a new material is added"""
        # Refresh material panel to show new material
        self.material_panel.refresh_library()
        self.status.showMessage(f"New material added: {filename}")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_materials_changed(self):
        materials = self.material_panel.get_selected_materials()
        self.rayleigh_panel.update_materials(materials)

        # Sync materials to all plots through add/remove to keep _mat_visible in sync

        # Sync to hugoniot plot (排除参考曲线，参考曲线以 ref_ 开头)
        current_ids = set(self.hugoniot_plot.materials.keys())
        new_ids = set(materials.keys())
        # 只移除非参考曲线的材料
        for mid in current_ids - new_ids:
            if not mid.startswith("ref_"):
                self.hugoniot_plot.remove_material(mid)
        for mid, mat in materials.items():
            if mid not in self.hugoniot_plot.materials:
                self.hugoniot_plot.add_material(mat)
            else:
                self.hugoniot_plot.materials[mid] = mat

        self.hugoniot_plot.refresh()

        # Sync to all generic plots (同样排除参考曲线)
        generic_plots = [
            self.us_up_plot, self.p_t_plot, self.rho_up_plot,
            self.t_up_plot, self.e_up_plot, self.p_us_plot
        ]
        for plot in generic_plots:
            plot_current_ids = set(plot.materials.keys())
            for mid in plot_current_ids - new_ids:
                if not mid.startswith("ref_"):
                    plot.remove_material(mid)
            for mid, mat in materials.items():
                if mid not in plot.materials:
                    plot.add_material(mat)
                else:
                    plot.materials[mid] = mat

        # Update reverse match Hugoniot combo
        self.intersection_panel._materials = materials
        self.intersection_panel.reverse_hugoniot_combo.clear()
        for mid, mat in materials.items():
            self.intersection_panel.reverse_hugoniot_combo.addItem(mat.name, mid)

        # Refresh curve selection combos
        self.intersection_panel._update_curve_combos()

        # If currently on P-CR tab (index 1), update reference curves
        current_index = self.plot_tabs.currentIndex()
        if current_index == 1:
            materials_for_eos = self.hugoniot_plot.materials  # Always show materials
            eos_settings = self._plot_settings["P-CR"]
            self.eos_plot.update_plot(
                materials=materials_for_eos,
                scatter_points=self._scatter_points,
                xlim=eos_settings["xlim"],
                ylim=eos_settings["ylim"],
            )

        self._update_status()

    def _on_material_reset_all(self):
        """Material library refresh 触发的全部状态重置。"""
        # 防御：__init__ 期间可能尚未创建所有属性（启动时序）
        if not hasattr(self, "hugoniot_plot") or not hasattr(self, "_scatter_points"):
            return

        # 1. 取消所有材料勾选（不 emit materials_changed）
        for i in range(self.material_panel.material_list.count()):
            item = self.material_panel.material_list.item(i)
            item.setCheckState(Qt.Unchecked)

        # 2. 清空 hugoniot_plot 内部状态
        self.hugoniot_plot.materials.clear()
        self.hugoniot_plot.rayleigh_lines.clear()
        self.hugoniot_plot.intersections.clear()
        self.hugoniot_plot.reflected_curves.clear()
        self.hugoniot_plot._artist_map.clear()
        self.hugoniot_plot._element_meta.clear()
        # Note: _element_zorder doesn't exist in the current implementation
        self.hugoniot_plot._selected_element_id = None
        self.hugoniot_plot.set_scatter_points([])

        # 3. 清空 panel UIs
        self.rayleigh_panel.clear()
        self.intersection_panel.clear()

        # 4. 清空 scatter
        self._scatter_points.clear()
        self._scatter_counter = 0
        self._scatter_color_counter = 0
        if hasattr(self, '_update_scatter_list_widget'):
            self._update_scatter_list_widget()
        if hasattr(self, '_refresh_scatter_ix_combo'):
            self._refresh_scatter_ix_combo()

        # 5. 重置 plot settings 到默认
        for key, settings in self._plot_settings.items():
            defaults = PLOT_DEFAULTS[key]
            settings["xlim"] = defaults[0]
            settings["ylim"] = defaults[1]
            settings["show_legend"] = False
        if hasattr(self, '_sync_plot_settings_to_ui'):
            self._sync_plot_settings_to_ui()

        # 6. refresh 所有 plot
        if hasattr(self, '_refresh_all_plots_with_scatter'):
            self._refresh_all_plots_with_scatter()
        else:
            self.hugoniot_plot.refresh()

        self._update_status()
        self.status.showMessage("All state reset")

    def _on_rayleigh_changed(self):
        self.hugoniot_plot.rayleigh_lines = self.rayleigh_panel.get_visible_rayleigh_lines()
        self.hugoniot_plot.refresh()
        self.intersection_panel.update_rayleigh_lines(self.hugoniot_plot.rayleigh_lines)
        self._update_status()
        # 自适应刷新：依赖 Rayleigh 的交点 / 反射线跟随移动
        if self.intersection_panel.is_auto_update_enabled():
            self._auto_refresh_intersections()

    def _resolve_curve_data(self, curve_id):
        """根据数据 ID 找 (up, p) 数组。

        顺序：可见 material → 已加载但隐藏的 material → 全部 Rayleigh（含未显示）→ 反射曲线。
        找不到返回 (None, None)。
        """
        if curve_id is None:
            return None, None
        if curve_id in self.hugoniot_plot.materials:
            mat = self.hugoniot_plot.materials[curve_id]
            return mat.up, mat.p
        loaded = getattr(self.material_panel, "_loaded", {})
        if curve_id in loaded:
            mat = loaded[curve_id]
            return mat.up, mat.p
        all_rl = self.rayleigh_panel.get_all_rayleigh_lines()
        if curve_id in all_rl:
            rl = all_rl[curve_id]
            return rl.up, rl.p
        for rc in self.hugoniot_plot.reflected_curves:
            if rc["id"] == curve_id:
                return rc["up"], rc["p"]
        return None, None

    def _compute_compression_for_ix(self, ix, up_val):
        """根据 ix 的 source_curve IDs 与当前曲线数据，计算 up_val 处的 compression_ratio。

        优先级：Hugoniot 表中 compression 列（更准）> Rayleigh 的 D/(D-up) 解析值。
        """
        compression = None
        rl_D = None
        materials_with_cr = []
        for src_id in (ix.source_curve1_id, ix.source_curve2_id):
            if src_id is None:
                continue
            all_rl = self.rayleigh_panel.get_all_rayleigh_lines()
            if src_id in all_rl:
                rl_D = all_rl[src_id].D
                continue
            mat = self.hugoniot_plot.materials.get(src_id)
            if mat is None:
                mat = getattr(self.material_panel, "_loaded", {}).get(src_id)
            if mat is not None and mat.compression is not None and len(mat.compression) > 0:
                materials_with_cr.append(mat)

        # 1) Rayleigh D/(D-up) 初值
        if rl_D is not None and (rl_D - up_val) > 0:
            try:
                compression = float(rl_D / (rl_D - up_val))
            except Exception:
                pass
        # 2) Hugoniot compression 列覆盖（更准）
        for m in materials_with_cr:
            try:
                from scipy.interpolate import interp1d as _interp1d
                cr_interp = _interp1d(m.up, m.compression, bounds_error=False, fill_value=np.nan)
                cr_val = float(cr_interp(up_val))
                if np.isfinite(cr_val):
                    compression = cr_val
                    break
            except Exception:
                pass
        return compression

    def _auto_refresh_intersections(self):
        """当 Rayleigh / 反射线 / material 变化时，自动重算依赖它们的交点。

        依赖顺序（同一帧内分 4 pass，全部原位修改保住 id / 样式）：
          1) 重算 Hugoniot × Rayleigh 类交点（不依赖反射线）
          2) 锚定到这些交点的反射曲线跟随移动
          3) 反射线依赖的交点重算（如 reverse-match / 用户 Reflect 出的二级 ix）
          4) 清理孤儿（连带级联）

        递归安全：本方法不 emit rayleigh_changed / materials_changed，只原位改 + refresh。
        """
        from im_app.core.physics import find_intersections, reflect_hugoniot, reverse_impedance_match
        from scipy.interpolate import interp1d

        ix_orphans: set[str] = set()
        refl_orphans: set[str] = set()

        def depends_on_reflected(ix) -> bool:
            for src in (ix.source_curve1_id, ix.source_curve2_id):
                if src and src.startswith("refl_"):
                    return True
            return False

        def recompute_ix(ix) -> bool:
            up1, p1 = self._resolve_curve_data(ix.source_curve1_id)
            up2, p2 = self._resolve_curve_data(ix.source_curve2_id)
            if up1 is None or up2 is None:
                ix_orphans.add(ix.id)
                return False
            try:
                up_ints = find_intersections(
                    up1, p1, up2, p2,
                    ignore_first=ix.ignore_first_at_creation,
                )
            except Exception:
                up_ints = np.array([])
            if len(up_ints) == 0:
                ix_orphans.add(ix.id)
                return False
            up_val = float(up_ints[0])
            # 用 curve1 的 (up, p) 插值取 p（与 _find_specific_intersection 一致）
            try:
                sort_idx = np.argsort(up1)
                interp = interp1d(
                    np.asarray(up1)[sort_idx], np.asarray(p1)[sort_idx],
                    bounds_error=False, fill_value="extrapolate",
                )
                p_val = float(interp(up_val))
            except Exception:
                p_val = float(np.interp(up_val, up1, p1))
            ix.up = up_val
            ix.p = p_val
            ix.compression_ratio = self._compute_compression_for_ix(ix, up_val)
            return True

        # Pass 1: Hugoniot × Rayleigh 类交点
        for ix in self.hugoniot_plot.intersections:
            if depends_on_reflected(ix):
                continue
            if ix.source_curve1_id is None and ix.source_curve2_id is None:
                continue  # 老 workflow 加载的，没有 source 信息，跳过
            recompute_ix(ix)

        # Pass 2: 锚定反射曲线跟随（两类：Reflect 出来的 anchor ix；Reverse Match 的 source ix）
        for rc in self.hugoniot_plot.reflected_curves:
            anchor_id = rc.get("anchor_intersection_id")
            source_ix_id = rc.get("source_ix_id")

            if anchor_id is not None:
                # 普通反射：以锚 ix 为中心镜像
                anchor_ix = next((x for x in self.hugoniot_plot.intersections if x.id == anchor_id), None)
                if anchor_ix is None or anchor_ix.id in ix_orphans:
                    refl_orphans.add(rc["id"])
                    continue
                new_center = anchor_ix.up
                if abs(new_center - rc["center_up"]) <= 1e-9:
                    continue
                source_mat = (self.hugoniot_plot.materials.get(rc["source_id"])
                              or getattr(self.material_panel, "_loaded", {}).get(rc["source_id"]))
                if source_mat is None:
                    refl_orphans.add(rc["id"])
                    continue
                up_r, p_r = reflect_hugoniot(source_mat.up, source_mat.p, new_center)
                rc["up"] = up_r
                rc["p"] = p_r
                rc["center_up"] = new_center
                # 同步 refl_list 文本
                for i in range(self.intersection_panel.refl_list.count()):
                    item = self.intersection_panel.refl_list.item(i)
                    if item.data(Qt.UserRole) == rc["id"]:
                        item.setText(f"Reflected {source_mat.name} @ center_up={new_center:.3f}")
                        break
            elif source_ix_id is not None:
                # Reverse-match：source ix 移动后，用新 (up, p) 重新求解
                src_ix = next((x for x in self.hugoniot_plot.intersections if x.id == source_ix_id), None)
                if src_ix is None or src_ix.id in ix_orphans:
                    refl_orphans.add(rc["id"])
                    continue
                source_mat = (self.hugoniot_plot.materials.get(rc["source_id"])
                              or getattr(self.material_panel, "_loaded", {}).get(rc["source_id"]))
                if source_mat is None:
                    refl_orphans.add(rc["id"])
                    continue
                # 用当前 ix 的 (up, p) 作为新 target 重解；若曲线已无解，孤儿化
                try:
                    new_results = reverse_impedance_match(
                        src_ix.up, src_ix.p,
                        source_mat.up, source_mat.p,
                    )
                except Exception:
                    new_results = []
                if not new_results:
                    refl_orphans.add(rc["id"])
                    continue
                r0 = new_results[0]
                rc["up"] = r0["reflected_up"]
                rc["p"] = r0["reflected_p"]
                rc["center_up"] = r0["center_up"]
                # 同步 refl_list 文本
                for i in range(self.intersection_panel.refl_list.count()):
                    item = self.intersection_panel.refl_list.item(i)
                    if item.data(Qt.UserRole) == rc["id"]:
                        item.setText(f"Reflected {source_mat.name} @ center_up={r0['center_up']:.3f}")
                        break

        # Pass 3: 反射线依赖的 ix（包含 reverse-match 类）
        for ix in self.hugoniot_plot.intersections:
            if not depends_on_reflected(ix):
                continue
            if ix.id in ix_orphans:
                continue
            # 若 source 中的反射线即将被删，标记本 ix 为孤儿
            src_refls = [s for s in (ix.source_curve1_id, ix.source_curve2_id)
                         if s and s.startswith("refl_")]
            if any(s in refl_orphans for s in src_refls):
                ix_orphans.add(ix.id)
                continue
            recompute_ix(ix)

        # Pass 4: 清理孤儿（含级联）
        if ix_orphans:
            # 锚 / source 到孤儿 ix 的反射线也孤儿
            for rc in self.hugoniot_plot.reflected_curves:
                anchor_id = rc.get("anchor_intersection_id")
                source_ix_id = rc.get("source_ix_id")
                if (anchor_id and anchor_id in ix_orphans) or (source_ix_id and source_ix_id in ix_orphans):
                    refl_orphans.add(rc["id"])
            self.hugoniot_plot.intersections = [
                ix for ix in self.hugoniot_plot.intersections if ix.id not in ix_orphans
            ]
            if self.hugoniot_plot.selected_intersection_id in ix_orphans:
                self.hugoniot_plot.selected_intersection_id = None

        if refl_orphans:
            # 反射线被删 → 依赖它的 ix 也孤儿（保险；通常 Pass 3 已处理）
            refl_lookup = {rc["id"]: rc for rc in self.hugoniot_plot.reflected_curves}
            for ix in self.hugoniot_plot.intersections:
                for src in (ix.source_curve1_id, ix.source_curve2_id):
                    if src and src.startswith("refl_") and src in refl_orphans:
                        ix_orphans.add(ix.id)
                        break
            if ix_orphans:
                self.hugoniot_plot.intersections = [
                    ix for ix in self.hugoniot_plot.intersections if ix.id not in ix_orphans
                ]
                if self.hugoniot_plot.selected_intersection_id in ix_orphans:
                    self.hugoniot_plot.selected_intersection_id = None
            self.hugoniot_plot.reflected_curves = [
                rc for rc in self.hugoniot_plot.reflected_curves if rc["id"] not in refl_orphans
            ]
            for i in range(self.intersection_panel.refl_list.count() - 1, -1, -1):
                item = self.intersection_panel.refl_list.item(i)
                if item.data(Qt.UserRole) in refl_orphans:
                    self.intersection_panel.refl_list.takeItem(i)

        # 收尾：refresh + 重建表格 / 反射线 combo
        self.hugoniot_plot.refresh()
        self.intersection_panel.set_intersections(
            self.hugoniot_plot.intersections,
            self.hugoniot_plot.materials,
        )
        self.intersection_panel.update_reflected_curves(self.hugoniot_plot.reflected_curves)
        if hasattr(self, '_refresh_scatter_ix_combo'):
            self._refresh_scatter_ix_combo()
        self._update_status()

    def _on_intersection_selected(self, ix_id: str):
        for i, ix in enumerate(self.hugoniot_plot.intersections):
            if ix.id == ix_id:
                self.intersection_panel.ix_table.selectRow(i)

                # TODO Task 15: Replace with scatter_ix_combo mechanism
                # cr = f"{ix.compression_ratio:.3f}" if hasattr(ix, 'compression_ratio') and ix.compression_ratio else "-"
                # self._update_eos_inputs_from_intersection(ix.curve1_id, ix.up, ix.p, cr)

                cr_info = f", selected: Up={ix.up:.4f}, P={ix.p:.4f}"
                self.status.showMessage(f"Intersection {ix_id}{cr_info}")
                break
        else:
            self.status.showMessage(f"Intersection {ix_id}")

    def _find_intersections(self):
        """Find intersection between the two curves selected in the panel."""
        curve1_id = self.intersection_panel.curve1_combo.currentData()
        curve2_id = self.intersection_panel.curve2_combo.currentData()
        if curve1_id and curve2_id:
            self._find_specific_intersection(curve1_id, curve2_id, False)
        else:
            self.status.showMessage("Select two curves in the intersection panel first")

    def _find_specific_intersection(self, curve1_id: str, curve2_id: str, include_reflected: bool):
        """Find intersection between two specific curves."""
        from im_app.core.physics import find_intersections, get_thermodynamics_at_intersection

        # Get curve data
        up1, p1, name1 = None, None, None
        up2, p2, name2 = None, None, None
        is_rayleigh1 = False
        is_rayleigh2 = False
        mat1 = None  # MaterialData if curve1 is a Hugoniot
        mat2 = None  # MaterialData if curve2 is a Hugoniot

        # Find first curve
        if curve1_id in self.hugoniot_plot.materials:
            mat = self.hugoniot_plot.materials[curve1_id]
            up1, p1, name1 = mat.up, mat.p, mat.name
            mat1 = mat
        elif curve1_id in self.hugoniot_plot.rayleigh_lines:
            rl = self.hugoniot_plot.rayleigh_lines[curve1_id]
            up1, p1, name1 = rl.up, rl.p, f"Rayleigh {rl.material_id}"
            is_rayleigh1 = True
        else:
            for rc in self.hugoniot_plot.reflected_curves:
                if rc["id"] == curve1_id:
                    up1, p1, name1 = rc["up"], rc["p"], f"Reflected {rc['source_id']}"
                    break

        # Find second curve
        if curve2_id in self.hugoniot_plot.materials:
            mat = self.hugoniot_plot.materials[curve2_id]
            up2, p2, name2 = mat.up, mat.p, mat.name
            mat2 = mat
        elif curve2_id in self.hugoniot_plot.rayleigh_lines:
            rl = self.hugoniot_plot.rayleigh_lines[curve2_id]
            up2, p2, name2 = rl.up, rl.p, f"Rayleigh {rl.material_id}"
            is_rayleigh2 = True
        else:
            for rc in self.hugoniot_plot.reflected_curves:
                if rc["id"] == curve2_id:
                    up2, p2, name2 = rc["up"], rc["p"], f"Reflected {rc['source_id']}"
                    break

        if up1 is None or up2 is None:
            self.status.showMessage("Cannot find specified curves")
            return

        # Find intersection
        up_ints = find_intersections(up1, p1, up2, p2, ignore_first=True)

        if len(up_ints) == 0:
            self.status.showMessage(f"No intersection found between {name1} and {name2}")
            return

        # Use first meaningful intersection
        up_val = float(up_ints[0])

        # Get pressure at intersection
        from scipy.interpolate import interp1d
        interp1 = interp1d(up1, p1, bounds_error=False, fill_value="extrapolate")
        p_val = float(interp1(up_val))

        # Calculate compression ratio
        compression = "-"
        if is_rayleigh1 and curve1_id in self.hugoniot_plot.rayleigh_lines:
            D = self.hugoniot_plot.rayleigh_lines[curve1_id].D
            compression = f"{D / (D - up_val):.3f}"
        elif is_rayleigh2 and curve2_id in self.hugoniot_plot.rayleigh_lines:
            D = self.hugoniot_plot.rayleigh_lines[curve2_id].D
            compression = f"{D / (D - up_val):.3f}"

        # If a Hugoniot is involved and has compression data, look up CR from table
        for m in [mat1, mat2]:
            if m is not None and m.compression is not None and len(m.compression) > 0:
                from scipy.interpolate import interp1d as _interp1d
                cr_interp = _interp1d(m.up, m.compression, bounds_error=False, fill_value=np.nan)
                cr_val = float(cr_interp(up_val))
                if np.isfinite(cr_val):
                    compression = f"{cr_val:.3f}"
                    break

        # Create intersection
        from im_app.core.physics import Intersection

        # Check for duplicate
        for existing in self.hugoniot_plot.intersections:
            if (abs(existing.up - up_val) < 0.01 and abs(existing.p - p_val) < 0.001):
                self.status.showMessage(
                    f"Intersection already exists: {name1} x {name2} @ ({up_val:.3f}, {p_val:.3f})"
                )
                return

        # 确定 material_id：优先 mat1，其次 mat2（一个是 Hugoniot，另一个是 Rayleigh 或 reflected）
        primary_mat_id = None
        if mat1 is not None:
            primary_mat_id = curve1_id
        elif mat2 is not None:
            primary_mat_id = curve2_id

        ix = Intersection(
            id=f"ix_specific_{len(self.hugoniot_plot.intersections)}",
            curve1_id=name1,
            curve2_id=name2,
            up=up_val,
            p=p_val,
            type="custom",
            material_id=primary_mat_id,
            compression_ratio=float(compression) if compression != "-" else None,
            source_curve1_id=curve1_id,
            source_curve2_id=curve2_id,
            ignore_first_at_creation=True,
        )

        # Add to plot
        self.hugoniot_plot.intersections.append(ix)
        self.hugoniot_plot.refresh()

        # Update panel
        self.intersection_panel.set_intersections(
            self.hugoniot_plot.intersections,
            self.hugoniot_plot.materials,
        )

        self.status.showMessage(f"Found intersection: {name1} x {name2} @ ({up_val:.3f}, {p_val:.3f}) CR={compression}")
        self._update_status()

        # Refresh scatter intersection dropdown
        if hasattr(self, '_refresh_scatter_ix_combo'):
            self._refresh_scatter_ix_combo()

        # TODO Task 15: Replace with scatter_ix_combo mechanism
        # self._update_eos_inputs_from_intersection(name1, up_val, p_val, compression)

    def _on_reflect(self, source_mat_id: str, center_up: float):
        refl_id = self.hugoniot_plot.add_reflected(source_mat_id, center_up)
        if refl_id:
            # 记录锚 ix.id，让自适应刷新能跟随锚交点移动这条反射线
            anchor_ix_id = self.intersection_panel.reflect_center_combo.currentData()
            if anchor_ix_id:
                for rc in self.hugoniot_plot.reflected_curves:
                    if rc["id"] == refl_id:
                        rc["anchor_intersection_id"] = anchor_ix_id
                        break
            mat = self.hugoniot_plot.materials.get(source_mat_id)
            name = mat.name if mat else source_mat_id
            self.intersection_panel.add_reflected_entry(refl_id, name, center_up)
            self.intersection_panel.update_reflected_curves(self.hugoniot_plot.reflected_curves)
            self.status.showMessage(f"Added reflected {name} @ center_up={center_up:.3f}")
            self._update_status()

    def _on_remove_reflected(self, refl_id: str):
        """Remove a reflected curve from the plot."""
        self.hugoniot_plot.remove_reflected(refl_id)
        self.intersection_panel.update_reflected_curves(self.hugoniot_plot.reflected_curves)
        self._update_status()

    def _on_remove_intersection(self, ix_id: str):
        """Remove an intersection from the plot."""
        # Remove from hugoniot_plot.intersections list
        self.hugoniot_plot.intersections = [ix for ix in self.hugoniot_plot.intersections if ix.id != ix_id]

        # Clear selected if it was the removed one
        if self.hugoniot_plot.selected_intersection_id == ix_id:
            self.hugoniot_plot.selected_intersection_id = None

        # Update plot and panel
        self.hugoniot_plot.refresh()
        self.intersection_panel.set_intersections(
            self.hugoniot_plot.intersections,
            self.hugoniot_plot.materials,
        )
        # Refresh scatter intersection dropdown
        if hasattr(self, '_refresh_scatter_ix_combo'):
            self._refresh_scatter_ix_combo()
        self.status.showMessage(f"Removed intersection: {ix_id}")
        self._update_status()

    def _on_element_selected(self, element_id: str, element_type: str):
        """Handle element selection from plot."""
        # Extract data_id from element_id
        # Format: mat_{id}, rl_{id}, refl_{id}, ix_{id}
        parts = element_id.split("_", 1)
        if len(parts) < 2:
            return
        data_id = parts[1]

        self.status.showMessage(f"Selected {element_type}: {element_id}")
        self._update_status()

    def _on_element_deleted(self, element_id: str, element_type: str):
        """Handle element deletion from plot context menu."""
        from im_app.core.element_style import TYPE_MATERIAL, TYPE_RAYLEIGH, TYPE_REFLECTED, TYPE_INTERSECTION, TYPE_SCATTER

        # Extract data_id from element_id
        parts = element_id.split("_", 1)
        if len(parts) < 2:
            return
        data_id = parts[1]

        if element_type == TYPE_MATERIAL:
            # Remove material
            self.hugoniot_plot.materials.pop(data_id, None)
            self.hugoniot_plot._mat_visible.pop(data_id, None)
            self.hugoniot_plot._element_meta.pop(element_id, None)
            # Also update material panel
            self.material_panel.set_material_checked(data_id, False)
            self.status.showMessage(f"Deleted material: {data_id}")

        elif element_type == TYPE_RAYLEIGH:
            # Remove rayleigh line
            self.hugoniot_plot.rayleigh_lines.pop(data_id, None)
            self.hugoniot_plot._rl_visible.pop(data_id, None)
            self.hugoniot_plot._element_meta.pop(element_id, None)
            # Also update rayleigh panel
            self.rayleigh_panel.remove_rayleigh(data_id)
            self.status.showMessage(f"Deleted Rayleigh line: {data_id}")

        elif element_type == TYPE_REFLECTED:
            # Remove reflected curve
            self.hugoniot_plot.remove_reflected(data_id)
            self.hugoniot_plot._element_meta.pop(element_id, None)
            # Update intersection panel
            self.intersection_panel.update_reflected_curves(self.hugoniot_plot.reflected_curves)
            self.status.showMessage(f"Deleted reflected curve: {data_id}")

        elif element_type == TYPE_INTERSECTION:
            # Remove intersection
            self.hugoniot_plot.intersections = [ix for ix in self.hugoniot_plot.intersections if ix.id != data_id]
            if self.hugoniot_plot.selected_intersection_id == data_id:
                self.hugoniot_plot.selected_intersection_id = None
            # Update intersection panel
            self.intersection_panel.set_intersections(
                self.hugoniot_plot.intersections,
                self.hugoniot_plot.materials,
            )
            # Refresh scatter intersection dropdown
            if hasattr(self, '_refresh_scatter_ix_combo'):
                self._refresh_scatter_ix_combo()
            self.status.showMessage(f"Deleted intersection: {data_id}")

        elif element_type == TYPE_SCATTER:
            # Remove scatter point
            self._remove_scatter_point(data_id)
            return  # _remove_scatter_point handles refresh and status

        self.hugoniot_plot.refresh()
        self._update_status()

    def _on_element_style_changed(self, element_id: str, new_style: dict):
        """Handle element style change.

        Scatter 的 style dict 在所有 plot 间共享（render_scatter_points 注册的是引用），
        改一个 tab 上的 scatter style 后，需要 refresh 所有 plot 才能在其他 tab 看到。
        """
        self.status.showMessage(f"Style updated for: {element_id}")
        if element_id.startswith("scat_") and hasattr(self, '_refresh_all_plots_with_scatter'):
            self._refresh_all_plots_with_scatter()

    def _on_reverse_match(self, target_up: float, target_p: float, hugoniot_id: str):
        """Reverse impedance match: find reflected Hugoniot through a known point."""
        from im_app.core.physics import reverse_impedance_match, Intersection

        mat = self.hugoniot_plot.materials.get(hugoniot_id)
        if mat is None:
            self.status.showMessage(f"Material {hugoniot_id} not found")
            return

        results = reverse_impedance_match(
            target_up, target_p,
            mat.up, mat.p,
        )

        if not results:
            self.status.showMessage(
                f"No reverse match found for ({target_up:.3f}, {target_p:.3f}) on {mat.name}"
            )
            return

        # Add first result as a reflected curve and intersection
        r = results[0]
        center_up = r["center_up"]
        up_r = r["reflected_up"]
        p_r = r["reflected_p"]

        # Add reflected curve to plot
        self.hugoniot_plot._counter += 1
        rid = f"refl_{self.hugoniot_plot._counter}"
        # 若 target 来自 reverse_ix_combo 选中的 ix，记下 source_ix_id；
        # 自适应刷新时若该 ix 移动，会自动重算 reverse-match（re-solve）。
        # 注意：spinbox 有 decimals=4 截断，无法与 ix 原值严格相等，所以只要 combo
        # 有选中就追踪；用户若想手动 target，应把 combo 清空（默认无选中）。
        source_ix_id = self.intersection_panel.reverse_ix_combo.currentData()
        self.hugoniot_plot.reflected_curves.append({
            "id": rid,
            "up": up_r,
            "p": p_r,
            "source_id": hugoniot_id,
            "center_up": center_up,
            "visible": True,
            "source_ix_id": source_ix_id,
        })

        # Add intersection point (where reflected meets original Hugoniot)
        ix = Intersection(
            id=f"ix_rev_{len(self.hugoniot_plot.intersections)}",
            curve1_id=mat.name,
            curve2_id=f"Reflected {mat.name}",
            up=r["intersection_up"],
            p=r["intersection_p"],
            type="reverse-match",
            material_id=hugoniot_id,
            compression_ratio=None,  # Will be set below if available
            source_curve1_id=hugoniot_id,
            source_curve2_id=rid,
            ignore_first_at_creation=True,
        )

        # Calculate compression ratio from Hugoniot table
        if mat.compression is not None and len(mat.compression) > 0:
            from scipy.interpolate import interp1d as _interp1d
            cr_interp = _interp1d(mat.up, mat.compression, bounds_error=False, fill_value=np.nan)
            cr_val = float(cr_interp(r["intersection_up"]))
            if np.isfinite(cr_val):
                ix.compression_ratio = cr_val

        self.hugoniot_plot.intersections.append(ix)

        # Add to lists
        self.intersection_panel.add_reflected_entry(rid, mat.name, center_up)
        self.intersection_panel.set_intersections(
            self.hugoniot_plot.intersections,
            self.hugoniot_plot.materials,
        )
        self.intersection_panel.update_rayleigh_lines(self.hugoniot_plot.rayleigh_lines)
        self.intersection_panel.update_reflected_curves(self.hugoniot_plot.reflected_curves)

        self.hugoniot_plot.refresh()

        # Refresh scatter intersection dropdown
        if hasattr(self, '_refresh_scatter_ix_combo'):
            self._refresh_scatter_ix_combo()

        self.status.showMessage(
            f"Reverse match: {mat.name} reflected @ center_up={center_up:.3f}, "
            f"intersection @ ({r['intersection_up']:.3f}, {r['intersection_p']:.3f})"
        )
        self._update_status()

    def _apply_plot_settings(self):
        """Apply plot settings from control panel to the selected plot."""
        target = self.target_plot_combo.currentText()

        # Get limits
        xmin = self.xmin_spin.value()
        xmax = self.xmax_spin.value()
        ymin = self.ymin_spin.value()
        ymax = self.ymax_spin.value()

        # Get legend state
        show_legend = self.legend_check.isChecked()

        # Map target name to settings key
        settings_key = target.replace(" Diagram", "").replace(" Curve", "")
        settings_key = settings_key.replace("-", "-")  # Keep P-CR as is

        # Save to settings
        self._plot_settings[settings_key]["xlim"] = (xmin, xmax)
        self._plot_settings[settings_key]["ylim"] = (ymin, ymax)
        self._plot_settings[settings_key]["show_legend"] = show_legend

        # Apply to specific plot
        if target == "P-Up Diagram":
            # Get line style
            linestyle_map = {0: "-", 1: "--", 2: ":", 3: "-."}
            linestyle = linestyle_map[self.linestyle_combo.currentIndex()]
            self._plot_settings[settings_key]["linestyle"] = linestyle

            # Get line width
            linewidth = self.linewidth_spin.value()
            self._plot_settings[settings_key]["linewidth"] = linewidth

            # Apply to hugoniot plot
            self.hugoniot_plot.set_xlim(xmin, xmax)
            self.hugoniot_plot.set_ylim(ymin, ymax)
            self.hugoniot_plot.set_legend_visible(show_legend)
            self.hugoniot_plot.set_linestyle(linestyle)
            self.hugoniot_plot.set_linewidth(linewidth)

        elif target == "P-CR Diagram":
            # Apply to EOS plot
            materials = self.hugoniot_plot.materials  # Always show materials
            self.eos_plot.update_plot(
                materials=materials,
                scatter_points=self._scatter_points,
                xlim=(xmin, xmax),
                ylim=(ymin, ymax),
            )

        elif target == "Us-Up Diagram":
            self.us_up_plot.set_xlim(xmin, xmax)
            self.us_up_plot.set_ylim(ymin, ymax)
            self.us_up_plot.set_legend_visible(show_legend)

        elif target == "P-T Diagram":
            self.p_t_plot.set_xlim(xmin, xmax)
            self.p_t_plot.set_ylim(ymin, ymax)
            self.p_t_plot.set_legend_visible(show_legend)

        elif target == "rho-Up Diagram":
            self.rho_up_plot.set_xlim(xmin, xmax)
            self.rho_up_plot.set_ylim(ymin, ymax)
            self.rho_up_plot.set_legend_visible(show_legend)

        elif target == "T-Up Diagram":
            self.t_up_plot.set_xlim(xmin, xmax)
            self.t_up_plot.set_ylim(ymin, ymax)
            self.t_up_plot.set_legend_visible(show_legend)

        elif target == "E-Up Diagram":
            self.e_up_plot.set_xlim(xmin, xmax)
            self.e_up_plot.set_ylim(ymin, ymax)
            self.e_up_plot.set_legend_visible(show_legend)

        elif target == "P-Us Diagram":
            self.p_us_plot.set_xlim(xmin, xmax)
            self.p_us_plot.set_ylim(ymin, ymax)
            self.p_us_plot.set_legend_visible(show_legend)

        self.status.showMessage(f"{target} settings: xlim=({xmin},{xmax}), ylim=({ymin},{ymax})")

    def _on_target_plot_changed(self, index):
        """Update displayed settings when target plot selection changes."""
        target = self.target_plot_combo.currentText()

        # Map target to settings key
        if target == "P-Up Diagram":
            settings_key = "P-Up"
            self.xmin_spin.setRange(0, 100)
            self.xmax_spin.setRange(0, 100)
            self.xmin_spin.setSuffix(" km/s")
            self.xmax_spin.setSuffix(" km/s")
            self.ymin_spin.setSuffix(" Mbar")
            self.ymax_spin.setSuffix(" Mbar")
            self.axis_info_label.setText("Axes: Up (km/s) vs P (Mbar)")
        elif target == "P-CR Diagram":
            settings_key = "P-CR"
            self.xmin_spin.setRange(0.5, 20)
            self.xmax_spin.setRange(0.5, 20)
            self.xmin_spin.setSuffix("")  # Compression is unitless
            self.xmax_spin.setSuffix("")
            self.ymin_spin.setSuffix(" Mbar")
            self.ymax_spin.setSuffix(" Mbar")
            self.axis_info_label.setText("Axes: Compression Ratio vs P (Mbar)")
        elif target == "Us-Up Diagram":
            settings_key = "Us-Up"
            self.xmin_spin.setRange(0, 100)
            self.xmax_spin.setRange(0, 100)
            self.xmin_spin.setSuffix(" km/s")  # X = Us
            self.xmax_spin.setSuffix(" km/s")
            self.ymin_spin.setSuffix(" km/s")  # Y = Up
            self.ymax_spin.setSuffix(" km/s")
            self.axis_info_label.setText("Axes: Us (km/s) vs Up (km/s)")
        elif target == "P-T Diagram":
            settings_key = "P-T"
            self.xmin_spin.setRange(0, 100)
            self.xmax_spin.setRange(0, 100)
            self.xmin_spin.setSuffix(" Mbar")  # X = P
            self.xmax_spin.setSuffix(" Mbar")
            self.ymin_spin.setSuffix(" eV")  # Y = T
            self.ymax_spin.setSuffix(" eV")
            self.axis_info_label.setText("Axes: P (Mbar) vs T (eV)")
        elif target == "rho-Up Diagram":
            settings_key = "rho-Up"
            self.xmin_spin.setRange(0, 100)
            self.xmax_spin.setRange(0, 100)
            self.xmin_spin.setSuffix(" g/cm^3")  # X = rho
            self.xmax_spin.setSuffix(" g/cm^3")
            self.ymin_spin.setSuffix(" km/s")  # Y = Up
            self.ymax_spin.setSuffix(" km/s")
            self.axis_info_label.setText("Axes: rho (g/cm^3) vs Up (km/s)")
        elif target == "T-Up Diagram":
            settings_key = "T-Up"
            self.xmin_spin.setRange(0, 100)
            self.xmax_spin.setRange(0, 100)
            self.xmin_spin.setSuffix(" eV")  # X = T
            self.xmax_spin.setSuffix(" eV")
            self.ymin_spin.setSuffix(" km/s")  # Y = Up
            self.ymax_spin.setSuffix(" km/s")
            self.axis_info_label.setText("Axes: T (eV) vs Up (km/s)")
        elif target == "E-Up Diagram":
            settings_key = "E-Up"
            self.xmin_spin.setRange(0, 100)
            self.xmax_spin.setRange(0, 100)
            self.xmin_spin.setSuffix(" MJ/g")  # X = E
            self.xmax_spin.setSuffix(" MJ/g")
            self.ymin_spin.setSuffix(" km/s")  # Y = Up
            self.ymax_spin.setSuffix(" km/s")
            self.axis_info_label.setText("Axes: E (MJ/g) vs Up (km/s)")
        elif target == "P-Us Diagram":
            settings_key = "P-Us"
            self.xmin_spin.setRange(0, 100)
            self.xmax_spin.setRange(0, 100)
            self.xmin_spin.setSuffix(" Mbar")  # X = P
            self.xmax_spin.setSuffix(" Mbar")
            self.ymin_spin.setSuffix(" km/s")  # Y = Us
            self.ymax_spin.setSuffix(" km/s")
            self.axis_info_label.setText("Axes: P (Mbar) vs Us (km/s)")
        else:
            settings_key = "P-Up"  # Default fallback

        settings = self._plot_settings.get(settings_key, {})

        # Update values
        if settings:
            xmin, xmax = settings.get("xlim", (0, 30))
            ymin, ymax = settings.get("ylim", (0, 30))
            self.xmin_spin.setValue(xmin)
            self.xmax_spin.setValue(xmax)
            self.ymin_spin.setValue(ymin)
            self.ymax_spin.setValue(ymax)
            self.legend_check.setChecked(settings.get("show_legend", True))

        # Update P-Up specific controls
        if target == "P-Up Diagram":
            linestyle_map = {"-": 0, "--": 1, ":": 2, "-.": 3}
            self.linestyle_combo.setCurrentIndex(linestyle_map.get(settings.get("linestyle", "-"), 0))
            self.linewidth_spin.setValue(settings.get("linewidth", 1.2))
            self.linestyle_combo.setEnabled(True)
            self.linewidth_spin.setEnabled(True)
        else:
            self.linestyle_combo.setEnabled(False)
            self.linewidth_spin.setEnabled(False)

    def _sync_plot_settings_to_ui(self):
        """当前 tab 的 plot settings 同步到 spinbox。"""
        tab_idx = self.plot_tabs.currentIndex()
        tab_keys = ["P-Up", "P-CR", "Us-Up", "P-T", "rho-Up", "T-Up", "E-Up", "P-Us"]
        if not (0 <= tab_idx < len(tab_keys)):
            return
        key = tab_keys[tab_idx]
        settings = self._plot_settings.get(key, {})

        if not settings:
            return

        # Get axis limits
        xmin, xmax = settings.get("xlim", (0, 30))
        ymin, ymax = settings.get("ylim", (0, 30))

        # Block signals to prevent feedback loops
        self.xmin_spin.blockSignals(True)
        self.xmax_spin.blockSignals(True)
        self.ymin_spin.blockSignals(True)
        self.ymax_spin.blockSignals(True)

        # Update values
        self.xmin_spin.setValue(xmin)
        self.xmax_spin.setValue(xmax)
        self.ymin_spin.setValue(ymin)
        self.ymax_spin.setValue(ymax)

        # Unblock signals
        self.xmin_spin.blockSignals(False)
        self.xmax_spin.blockSignals(False)
        self.ymin_spin.blockSignals(False)
        self.ymax_spin.blockSignals(False)

        # Update legend checkbox
        self.legend_check.setChecked(settings.get("show_legend", True))

        # Update P-Up specific controls if on P-Up tab
        if key == "P-Up":
            linestyle_map = {"-": 0, "--": 1, ":": 2, "-.": 3}
            self.linestyle_combo.setCurrentIndex(linestyle_map.get(settings.get("linestyle", "-"), 0))
            self.linewidth_spin.setValue(settings.get("linewidth", 1.2))
            self.linestyle_combo.setEnabled(True)
            self.linewidth_spin.setEnabled(True)
        else:
            self.linestyle_combo.setEnabled(False)
            self.linewidth_spin.setEnabled(False)

    def _on_tab_changed(self, index):
        """Sync plot selector when tab changes and refresh plot with saved settings."""
        # Map tab index to plot name and settings key
        tab_names = [
            "P-Up Diagram",
            "P-CR Diagram",
            "Us-Up Diagram",
            "P-T Diagram",
            "rho-Up Diagram",
            "T-Up Diagram",
            "E-Up Diagram",
            "P-Us Diagram",
        ]
        settings_keys = ["P-Up", "P-CR", "Us-Up", "P-T", "rho-Up", "T-Up", "E-Up", "P-Us"]

        if index >= len(tab_names):
            return

        target = tab_names[index]
        settings_key = settings_keys[index]
        self.target_plot_combo.setCurrentIndex(index)

        settings = self._plot_settings.get(settings_key, {})

        # Apply settings to the specific plot
        if index == 0:  # P-Up Diagram
            self.hugoniot_plot.set_xlim(settings["xlim"][0], settings["xlim"][1])
            self.hugoniot_plot.set_ylim(settings["ylim"][0], settings["ylim"][1])
            self.hugoniot_plot.set_legend_visible(settings["show_legend"])
            self.hugoniot_plot.set_linestyle(settings.get("linestyle", "-"))
            self.hugoniot_plot.set_linewidth(settings.get("linewidth", 1.2))
            self.hugoniot_plot.refresh()
        elif index == 1:  # P-CR Diagram
            materials = self.hugoniot_plot.materials  # Always show materials
            self.eos_plot.update_plot(
                materials=materials,
                scatter_points=self._scatter_points,
                xlim=settings["xlim"],
                ylim=settings["ylim"],
            )
        elif index == 2:  # Us-Up Diagram
            self.us_up_plot.set_xlim(settings["xlim"][0], settings["xlim"][1])
            self.us_up_plot.set_ylim(settings["ylim"][0], settings["ylim"][1])
            self.us_up_plot.set_legend_visible(settings["show_legend"])
        elif index == 3:  # P-T Diagram
            self.p_t_plot.set_xlim(settings["xlim"][0], settings["xlim"][1])
            self.p_t_plot.set_ylim(settings["ylim"][0], settings["ylim"][1])
            self.p_t_plot.set_legend_visible(settings["show_legend"])
        elif index == 4:  # rho-Up Diagram
            self.rho_up_plot.set_xlim(settings["xlim"][0], settings["xlim"][1])
            self.rho_up_plot.set_ylim(settings["ylim"][0], settings["ylim"][1])
            self.rho_up_plot.set_legend_visible(settings["show_legend"])
        elif index == 5:  # T-Up Diagram
            self.t_up_plot.set_xlim(settings["xlim"][0], settings["xlim"][1])
            self.t_up_plot.set_ylim(settings["ylim"][0], settings["ylim"][1])
            self.t_up_plot.set_legend_visible(settings["show_legend"])
        elif index == 6:  # E-Up Diagram
            self.e_up_plot.set_xlim(settings["xlim"][0], settings["xlim"][1])
            self.e_up_plot.set_ylim(settings["ylim"][0], settings["ylim"][1])
            self.e_up_plot.set_legend_visible(settings["show_legend"])
        elif index == 7:  # P-Us Diagram
            self.p_us_plot.set_xlim(settings["xlim"][0], settings["xlim"][1])
            self.p_us_plot.set_ylim(settings["ylim"][0], settings["ylim"][1])
            self.p_us_plot.set_legend_visible(settings["show_legend"])

        # 同步手动输入区
        tab_keys = ["P-Up", "P-CR", "Us-Up", "P-T", "rho-Up", "T-Up", "E-Up", "P-Us"]
        if 0 <= index < len(tab_keys):
            self._refresh_manual_input_for_tab(tab_keys[index])

        # 让当前 plot canvas 获得键盘焦点，否则按 'a' 重置范围不会触发
        # （matplotlib canvas 默认 Qt.NoFocus，DragZoomMixin 改成 StrongFocus，
        # 但切 tab 后焦点会丢失，需要主动恢复）
        current_plot = self._get_plot_by_key(settings_key)
        if current_plot is not None:
            current_plot.setFocus()

    def _on_auto_range(self):
        """Auto-scale axis limits to data range with 1.1x margin."""
        target = self.target_plot_combo.currentText()
        settings_key = target.replace(" Diagram", "").replace(" Curve", "")

        # Get data ranges from materials
        import numpy as np

        x_data_all = []
        y_data_all = []

        # Collect data from all materials
        for mat in self.hugoniot_plot.materials.values():
            if target == "P-Up Diagram":
                x_data_all.extend(mat.up)
                y_data_all.extend(mat.p)
            elif target == "P-CR Diagram":
                if mat.compression is not None:
                    x_data_all.extend(mat.compression)
                y_data_all.extend(mat.p)
            elif target == "Us-Up Diagram":
                if mat.us is not None:
                    x_data_all.extend(mat.us)
                y_data_all.extend(mat.up)
            elif target == "P-T Diagram":
                x_data_all.extend(mat.p)
                if mat.temperature is not None:
                    y_data_all.extend(mat.temperature)
            elif target == "rho-Up Diagram":
                if mat.rho is not None:
                    x_data_all.extend(mat.rho)
                y_data_all.extend(mat.up)
            elif target == "T-Up Diagram":
                if mat.temperature is not None:
                    x_data_all.extend(mat.temperature)
                y_data_all.extend(mat.up)
            elif target == "E-Up Diagram":
                if mat.energy is not None:
                    x_data_all.extend(mat.energy)
                y_data_all.extend(mat.up)
            elif target == "P-Us Diagram":
                x_data_all.extend(mat.p)
                if mat.us is not None:
                    y_data_all.extend(mat.us)

        # Filter out NaN/inf values
        x_data_all = np.array([x for x in x_data_all if np.isfinite(x)])
        y_data_all = np.array([y for y in y_data_all if np.isfinite(y)])

        if len(x_data_all) == 0 or len(y_data_all) == 0:
            self.status.showMessage("No data available for auto-range")
            return

        # Calculate ranges with 1.1x margin
        x_min, x_max = x_data_all.min(), x_data_all.max()
        y_min, y_max = y_data_all.min(), y_data_all.max()

        x_margin = (x_max - x_min) * 0.05  # 5% margin each side = 10% total
        y_margin = (y_max - y_min) * 0.05

        # Handle zero range cases
        if x_max == x_min:
            x_margin = max(abs(x_min) * 0.1, 0.1) if x_min != 0 else 1.0
        if y_max == y_min:
            y_margin = max(abs(y_min) * 0.1, 0.1) if y_min != 0 else 1.0

        xmin = max(0, x_min - x_margin) if x_min >= 0 else x_min - x_margin
        xmax = x_max + x_margin
        ymin = max(0, y_min - y_margin) if y_min >= 0 else y_min - y_margin
        ymax = y_max + y_margin

        # Update spinboxes
        self.xmin_spin.setValue(xmin)
        self.xmax_spin.setValue(xmax)
        self.ymin_spin.setValue(ymin)
        self.ymax_spin.setValue(ymax)

        # Apply settings
        self._apply_plot_settings()

        self.status.showMessage(f"Auto-range: X=[{xmin:.3g}, {xmax:.3g}], Y=[{ymin:.3g}, {ymax:.3g}]")

    def _on_inverse_axes(self):
        """Swap X and Y axes for generic plots."""
        target = self.target_plot_combo.currentText()

        # Inverse only works for generic plots (not P-Up or P-CR)
        if target in ["P-Up Diagram", "P-CR Diagram"]:
            self.status.showMessage("Inverse not available for P-Up or P-CR plots")
            return

        # Map target to settings key and plot instance
        plot_map = {
            "Us-Up Diagram": ("Us-Up", self.us_up_plot),
            "P-T Diagram": ("P-T", self.p_t_plot),
            "rho-Up Diagram": ("rho-Up", self.rho_up_plot),
            "T-Up Diagram": ("T-Up", self.t_up_plot),
            "E-Up Diagram": ("E-Up", self.e_up_plot),
            "P-Us Diagram": ("P-Us", self.p_us_plot),
        }

        if target not in plot_map:
            return

        settings_key, plot_instance = plot_map[target]

        # Toggle inverse state
        current_inverse = self._plot_inverse_state.get(settings_key, False)
        new_inverse = not current_inverse
        self._plot_inverse_state[settings_key] = new_inverse

        # Get original configuration
        orig_x_var, orig_y_var = self._original_plot_configs.get(target, (None, None))

        if new_inverse:
            # Swap axes
            new_x_var, new_y_var = orig_y_var, orig_x_var
        else:
            new_x_var, new_y_var = orig_x_var, orig_y_var

        # Recreate the plot with swapped axes
        from im_app.core.plotter import GenericHugoniotPlot

        # Create new plot instance
        new_plot = GenericHugoniotPlot(new_x_var, new_y_var)

        # Copy materials
        for mat_id, mat in plot_instance.materials.items():
            new_plot.materials[mat_id] = mat
            new_plot._mat_visible[mat_id] = plot_instance._mat_visible.get(mat_id, True)

        # Update settings
        old_xlim = self._plot_settings[settings_key]["xlim"]
        old_ylim = self._plot_settings[settings_key]["ylim"]

        # Swap limits
        self._plot_settings[settings_key]["xlim"] = old_ylim
        self._plot_settings[settings_key]["ylim"] = old_xlim

        # Replace plot instance in the tab
        tab_index = self.plot_tabs.currentIndex()
        self.plot_tabs.removeTab(tab_index)
        self.plot_tabs.insertTab(tab_index, new_plot, target)

        # Update reference
        if settings_key == "Us-Up":
            self.us_up_plot = new_plot
        elif settings_key == "P-T":
            self.p_t_plot = new_plot
        elif settings_key == "rho-Up":
            self.rho_up_plot = new_plot
        elif settings_key == "T-Up":
            self.t_up_plot = new_plot
        elif settings_key == "E-Up":
            self.e_up_plot = new_plot
        elif settings_key == "P-Us":
            self.p_us_plot = new_plot

        # Apply swapped limits
        new_plot.set_xlim(old_ylim[0], old_ylim[1])
        new_plot.set_ylim(old_xlim[0], old_xlim[1])
        new_plot.set_legend_visible(self._plot_settings[settings_key]["show_legend"])

        # Update UI display
        self.plot_tabs.setCurrentIndex(tab_index)
        self._on_target_plot_changed(tab_index)

        state_text = "inverted" if new_inverse else "restored"
        self.status.showMessage(f"Axes {state_text}: now {new_x_var} vs {new_y_var}")

    def _update_status(self):
        n_mat = len(self.hugoniot_plot.materials)
        n_rl = len(self.hugoniot_plot.rayleigh_lines)
        n_ix = len(self.hugoniot_plot.intersections)
        n_refl = len(self.hugoniot_plot.reflected_curves)

        # 计算参考曲线数量（以ref_开头的材料）
        n_ref = len([mid for mid in self.hugoniot_plot.materials.keys() if mid.startswith("ref_")])

        self.status.showMessage(
            f"Materials: {n_mat - n_ref} | Ref Curves: {n_ref} | Rayleigh: {n_rl} | Intersections: {n_ix} | Reflected: {n_refl}"
        )

    def _next_scatter_id(self) -> str:
        """Generate next unique scatter point ID."""
        self._scatter_counter += 1
        return f"sc_{self._scatter_counter:04d}"

    def _next_scatter_color(self) -> str:
        """Get next color in cycle for scatter points."""
        from im_app.core.plot_style import PRL_COLORS
        colors = list(PRL_COLORS.values())
        c = colors[self._scatter_color_counter % len(colors)]
        self._scatter_color_counter += 1
        return c

    def _get_xy_vars_for_tab(self, tab_key: str):
        """Get (x_var, y_var) tuple for a given tab key."""
        return TAB_XY_MAP.get(tab_key, ("Up", "P"))

    def _lookup_material(self, material_id: str):
        """查找材料：画布 → 库加载 → 内存材料。"""
        if not material_id:
            return None
        if material_id in self.hugoniot_plot.materials:
            return self.hugoniot_plot.materials[material_id]
        if material_id in self.material_panel._loaded:
            return self.material_panel._loaded[material_id]
        if hasattr(self.material_panel, '_in_memory_materials'):
            if material_id in self.material_panel._in_memory_materials:
                return self.material_panel._in_memory_materials[material_id]
        return None

    def _intersection_to_scatter_point(self, ix_id: str):
        """Convert an intersection to a global scatter point.

        力学量（Up, P, Us, rho, compression, E）一律从 Rankine-Hugoniot 守恒关系
        推导（强冲击波近似 P₀≈0, E₀≈0），保证 8 个 tab 上的 scatter 严格自洽。
        T 不在守恒律范围内 → 仅当材料有 T 数据时用 cubic spline 插值，且 label 标注。
        """
        from im_app.core.physics import compute_hugoniot_state, lookup_material_state_at_up
        from im_app.core.element_style import DEFAULT_SCATTER_STYLE

        ix = next((x for x in self.hugoniot_plot.intersections if x.id == ix_id), None)
        if ix is None:
            return None

        # 材料查找：优先 ix.material_id；找不到时用 curve1_id 反查材料名
        material = self._lookup_material(ix.material_id) if ix.material_id else None
        if material is None and ix.curve1_id:
            # curve1_id 是显示名（如 "Aluminum"），遍历材料找匹配
            for mid, mat in self.hugoniot_plot.materials.items():
                if mat.name == ix.curve1_id:
                    material = mat
                    break
            if material is None:
                # 也在 material_panel._loaded 里找
                for mid, mat in getattr(self.material_panel, "_loaded", {}).items():
                    if mat.name == ix.curve1_id:
                        material = mat
                        break

        rho0 = getattr(material, "rho0", None) if material else None

        # 如果材料找不到 ρ₀，尝试从交点的 compression_ratio 反推：
        # η = Us/(Us-Up), P = ρ₀·Us·Up/100
        # ⟹ ρ₀ = 100·P·(η-1)/(η·Up²)
        if not rho0 and ix.up and ix.p:
            cr = getattr(ix, "compression_ratio", None)
            if cr and cr > 1.0:
                try:
                    rho0 = 100.0 * ix.p * (cr - 1.0) / (cr * ix.up * ix.up)
                except Exception:
                    pass

        # 力学状态从 Hugoniot 公式推导
        state = compute_hugoniot_state(ix.up, ix.p, rho0 if rho0 else 0.0)

        # 如果 compression 仍是 None 但 ix.compression_ratio 有值，直接用
        if state.get("compression") is None:
            cr = getattr(ix, "compression_ratio", None)
            if cr is not None:
                state["compression"] = float(cr)
                # ρ = ρ₀ · η
                if rho0:
                    state["rho"] = rho0 * cr

        state["T"] = None
        t_interpolated = False

        # T 仅在材料有 T 列时用 spline 插值
        if material is not None:
            mat_T = getattr(material, "temperature", None)
            if mat_T is not None and len(mat_T) > 0:
                looked = lookup_material_state_at_up(material, ix.up)
                t_val = looked.get("T")
                if t_val is not None:
                    state["T"] = t_val
                    t_interpolated = True

        mat_name = material.name if material else (ix.material_id or ix.curve1_id)
        label = f"{ix_id} ({mat_name})"
        if t_interpolated:
            label += " [T interp]"

        return {
            "id":         self._next_scatter_id(),
            "label":      label,
            "source":     "intersection",
            "scope":      "global",
            "target_tab": None,
            "style":      {**DEFAULT_SCATTER_STYLE, "color": self._next_scatter_color()},
            **state,
        }

    def _add_intersection_scatter_point(self):
        """从交点下拉添加 scatter（Task 15 完整实现）。"""
        ix_id = self.scatter_ix_combo.currentData()
        if not ix_id:
            self.status.showMessage("No intersection selected")
            return

        # 去重：按 source=intersection + label
        for existing in self._scatter_points:
            if existing.get("source") == "intersection" and existing.get("label", "").startswith(ix_id):
                self.status.showMessage(f"Scatter point for {ix_id} already exists")
                return

        point = self._intersection_to_scatter_point(ix_id)
        if point is None:
            self.status.showMessage(f"Intersection {ix_id} not found")
            return

        self._scatter_points.append(point)
        if hasattr(self, '_update_scatter_list_widget'):
            self._update_scatter_list_widget()
        self._refresh_all_plots_with_scatter()
        self.status.showMessage(f"Added scatter from {ix_id}")

    def _add_manual_scatter_point(self):
        """手动添加 scatter（Task 15 完整实现）。"""
        from im_app.core.element_style import DEFAULT_SCATTER_STYLE

        tab_idx = self.plot_tabs.currentIndex()
        tab_keys = ["P-Up", "P-CR", "Us-Up", "P-T", "rho-Up", "T-Up", "E-Up", "P-Us"]
        tab_key = tab_keys[tab_idx] if 0 <= tab_idx < len(tab_keys) else "P-Up"

        x_var, y_var = self._get_xy_vars_for_tab(tab_key)
        x_val = float(self.scatter_x_spin.value())
        y_val = float(self.scatter_y_spin.value())

        # 去重
        for existing in self._scatter_points:
            if (existing.get("scope") == "local"
                and existing.get("target_tab") == tab_key
                and abs((existing.get(x_var) or -999) - x_val) < 1e-3
                and abs((existing.get(y_var) or -999) - y_val) < 1e-3):
                self.status.showMessage(f"Point already exists on {tab_key}")
                return

        n = sum(1 for p in self._scatter_points
                if p.get("scope") == "local" and p.get("target_tab") == tab_key) + 1

        point = {
            "id":         self._next_scatter_id(),
            "label":      f"Manual {tab_key} #{n}",
            "source":     "manual",
            "scope":      "local",
            "target_tab": tab_key,
            "style":      {**DEFAULT_SCATTER_STYLE, "color": self._next_scatter_color()},
            x_var:        x_val,
            y_var:        y_val,
        }
        self._scatter_points.append(point)
        if hasattr(self, '_update_scatter_list_widget'):
            self._update_scatter_list_widget()
        self._refresh_all_plots_with_scatter()
        self.status.showMessage(f"Added manual point on {tab_key}: {x_var}={x_val:.3f}, {y_var}={y_val:.3f}")

    def _update_scatter_list_widget(self):
        """刷新面板的 scatter 列表。"""
        self.scatter_list.clear()
        for p in self._scatter_points:
            scope_tag = p.get("target_tab") or "global"
            text = f"{p['label']}  —  {scope_tag}"
            from PyQt5.QtWidgets import QListWidgetItem
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, p["id"])
            self.scatter_list.addItem(item)

    def _on_scatter_delete_selected(self):
        """面板列表选中后删除。"""
        items = self.scatter_list.selectedItems()
        if not items:
            self.status.showMessage("No scatter point selected")
            return
        for item in items:
            scatter_id = item.data(Qt.UserRole)
            self._remove_scatter_point(scatter_id)

    def _remove_scatter_point(self, scatter_id: str):
        """删除指定 scatter 点（面板和右键共用入口）。"""
        before = len(self._scatter_points)
        self._scatter_points = [p for p in self._scatter_points if p["id"] != scatter_id]
        if len(self._scatter_points) == before:
            return  # 没找到，无变化

        # 若正在选中该 scatter，清空选中
        if (getattr(self.hugoniot_plot, "_selected_element_id", None)
            == f"scat_{scatter_id}"):
            self.hugoniot_plot._selected_element_id = None

        self._update_scatter_list_widget()
        self._refresh_all_plots_with_scatter()
        self.status.showMessage(f"Removed scatter {scatter_id}")

    def _clear_all_scatter_points(self):
        """清空所有 scatter（Task 16 完整实现）。"""
        self._scatter_points.clear()
        if hasattr(self, '_refresh_all_plots_with_scatter'):
            self._refresh_all_plots_with_scatter()

    def _refresh_all_plots_with_scatter(self):
        """Refresh 全部 8 个 plot（Task 15 完整实现）。"""
        sp = self._scatter_points
        mats = self.hugoniot_plot.materials or None

        # P-Up (InteractiveHugoniotPlot)
        self.hugoniot_plot.set_scatter_points(sp)
        self.hugoniot_plot.refresh()

        # 其他 7 个 plot
        PLOT_KWARGS = [
            (self.eos_plot,      "P-CR"),
            (self.us_up_plot,    "Us-Up"),
            (self.p_t_plot,      "P-T"),
            (self.rho_up_plot,   "rho-Up"),
            (self.t_up_plot,     "T-Up"),
            (self.e_up_plot,     "E-Up"),
            (self.p_us_plot,     "P-Us"),
        ]
        for plot, key in PLOT_KWARGS:
            settings = self._plot_settings[key]
            plot.update_plot(
                materials=mats,
                scatter_points=sp,
                xlim=settings["xlim"], ylim=settings["ylim"],
            )

    def _refresh_manual_input_for_tab(self, tab_key: str):
        """切换 tab 时同步手动输入区。"""
        from im_app.core.plotter import GenericHugoniotPlot
        x_var, y_var = self._get_xy_vars_for_tab(tab_key)
        self.scatter_x_label.setText(f"{x_var}:")
        self.scatter_y_label.setText(f"{y_var}:")
        self.scatter_manual_tab_lbl.setText(f"current tab: {tab_key}")
        xmin, xmax = GenericHugoniotPlot.DEFAULT_LIMITS.get(x_var, (0, 30))
        ymin, ymax = GenericHugoniotPlot.DEFAULT_LIMITS.get(y_var, (0, 30))
        self.scatter_x_spin.setRange(xmin, xmax)
        self.scatter_y_spin.setRange(ymin, ymax)
        self.scatter_x_spin.setValue((xmin + xmax) / 2)
        self.scatter_y_spin.setValue((ymin + ymax) / 2)

    def _refresh_scatter_ix_combo(self):
        """填充交点下拉。"""
        self.scatter_ix_combo.blockSignals(True)
        self.scatter_ix_combo.clear()
        for ix in self.hugoniot_plot.intersections:
            mat = self._lookup_material(ix.material_id) if ix.material_id else None
            mat_name = mat.name if mat else (ix.material_id or ix.curve1_id)
            text = f"{ix.id}: {mat_name} @ Up={ix.up:.3f}, P={ix.p:.3f}"
            self.scatter_ix_combo.addItem(text, userData=ix.id)
        self.scatter_ix_combo.blockSignals(False)
        self.scatter_ix_add_btn.setEnabled(self.scatter_ix_combo.count() > 0)

    def _get_plot_by_key(self, key: str):
        """Map settings key (e.g. "P-Up") to plot instance."""
        return {
            "P-Up":   self.hugoniot_plot,
            "P-CR":   self.eos_plot,
            "Us-Up":  self.us_up_plot,
            "P-T":    self.p_t_plot,
            "rho-Up": self.rho_up_plot,
            "T-Up":   self.t_up_plot,
            "E-Up":   self.e_up_plot,
            "P-Us":   self.p_us_plot,
        }.get(key)

    def _on_plot_zoom_applied(self, key: str, xmin: float, xmax: float,
                              ymin: float, ymax: float):
        """拖拽缩放：更新 _plot_settings + 应用到 plot + 同步 spinbox。"""
        self._plot_settings[key]["xlim"] = (xmin, xmax)
        self._plot_settings[key]["ylim"] = (ymin, ymax)

        plot = self._get_plot_by_key(key)
        if plot is not None:
            if key == "P-CR":
                # EOSPlot 使用 update_plot 方法而不是 set_xlim/set_ylim
                materials = self.hugoniot_plot.materials  # Always show materials
                plot.update_plot(
                    materials=materials,
                    scatter_points=self._scatter_points,
                    xlim=(xmin, xmax),
                    ylim=(ymin, ymax),
                )
            else:
                plot.set_xlim(xmin, xmax)
                plot.set_ylim(ymin, ymax)

        # 若当前 tab 是该 plot，同步 4 个 spinbox
        current_target = self.target_plot_combo.currentText()
        target_name = key + " Diagram"   # "P-Up" -> "P-Up Diagram"
        if current_target == target_name:
            self.xmin_spin.setValue(xmin)
            self.xmax_spin.setValue(xmax)
            self.ymin_spin.setValue(ymin)
            self.ymax_spin.setValue(ymax)

        self.status.showMessage(
            f"{target_name} zoomed: X=[{xmin:.3g}, {xmax:.3g}], "
            f"Y=[{ymin:.3g}, {ymax:.3g}]"
        )

    def _on_plot_reset_view(self, key: str):
        """'a' 键重置：恢复硬编码默认范围。"""
        defaults = PLOT_DEFAULTS.get(key)
        if defaults is None:
            return
        (xlim, ylim) = defaults
        xmin, xmax = xlim
        ymin, ymax = ylim
        self._on_plot_zoom_applied(key, xmin, xmax, ymin, ymax)
        self.status.showMessage(f"{key} Diagram reset to default view")

    # ------------------------------------------------------------------
    # Save / Load / Export
    # ------------------------------------------------------------------

    def _export_plot(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Export directory")
        if not dir_path:
            return
        from im_app.core.plot_style import save_prl_figure
        save_prl_figure(self.hugoniot_plot.fig, os.path.join(dir_path, "p_up_diagram.png"))
        save_prl_figure(self.eos_plot.fig, os.path.join(dir_path, "p_cr_diagram.png"))
        save_prl_figure(self.us_up_plot.fig, os.path.join(dir_path, "us_up_diagram.png"))
        save_prl_figure(self.p_t_plot.fig, os.path.join(dir_path, "p_t_diagram.png"))
        save_prl_figure(self.rho_up_plot.fig, os.path.join(dir_path, "rho_up_diagram.png"))
        save_prl_figure(self.t_up_plot.fig, os.path.join(dir_path, "t_up_diagram.png"))
        save_prl_figure(self.e_up_plot.fig, os.path.join(dir_path, "e_up_diagram.png"))
        save_prl_figure(self.p_us_plot.fig, os.path.join(dir_path, "p_us_diagram.png"))
        self.status.showMessage(f"All plots exported to {dir_path}")

    def _save_workflow(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Workflow", self.workflows_dir, "JSON (*.json)"
        )
        if not path:
            return

        workflow = {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "materials": [
                {"id": mid, "visible": True}
                for mid in self.hugoniot_plot.materials
            ],
            "rayleigh_lines": [
                {
                    "id": rl.id,
                    "material_id": rl.material_id,
                    "D": rl.D,
                    "rho0": rl.rho0,
                }
                for rl in self.rayleigh_panel.get_all_rayleigh_lines().values()
            ],
            "intersections": [
                {
                    "id": ix.id,
                    "curve1_id": ix.curve1_id,
                    "curve2_id": ix.curve2_id,
                    "up": ix.up,
                    "p": ix.p,
                    "type": ix.type,
                    "material_id": getattr(ix, "material_id", None),
                    "compression_ratio": getattr(ix, "compression_ratio", None),
                    "source_curve1_id": getattr(ix, "source_curve1_id", None),
                    "source_curve2_id": getattr(ix, "source_curve2_id", None),
                    "ignore_first_at_creation": getattr(ix, "ignore_first_at_creation", True),
                }
                for ix in self.hugoniot_plot.intersections
            ],
            "reflected_curves": [
                {
                    "id": rc["id"],
                    "source_id": rc["source_id"],
                    "center_up": rc["center_up"],
                    "anchor_intersection_id": rc.get("anchor_intersection_id"),
                    "source_ix_id": rc.get("source_ix_id"),
                }
                for rc in self.hugoniot_plot.reflected_curves
            ],
            "plot_settings": {
                "p_up": {
                    "xlim": list(self.hugoniot_plot.xlim),
                    "ylim": list(self.hugoniot_plot.ylim),
                    "show_legend": self.hugoniot_plot.show_legend,
                    "linewidth": self.hugoniot_plot.linewidth,
                    "linestyle": self.hugoniot_plot.linestyle,
                },
                "p_cr": self._plot_settings["P-CR"],
                "us_up": self._plot_settings["Us-Up"],
                "p_t": self._plot_settings["P-T"],
                "rho_up": self._plot_settings["rho-Up"],
                "t_up": self._plot_settings["T-Up"],
                "e_up": self._plot_settings["E-Up"],
                "p_us": self._plot_settings["P-Us"],
            },
            "scatter_points": self._scatter_points,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=4, ensure_ascii=False)
        self.status.showMessage(f"Workflow saved to {path}")

    def _load_workflow(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Workflow", self.workflows_dir, "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                wf = json.load(f)

            # Deselect all materials first
            self.material_panel._deselect_all()

            # Select materials
            for m in wf.get("materials", []):
                mid = m["id"]
                for i in range(self.material_panel.material_list.count()):
                    item = self.material_panel.material_list.item(i)
                    if item.data(Qt.UserRole) == mid:
                        item.setCheckState(Qt.Checked)
                        break

            # Add Rayleigh lines
            for rl_data in wf.get("rayleigh_lines", []):
                self.rayleigh_panel.D_spin.setValue(rl_data["D"])
                self.rayleigh_panel.rho0_spin.setValue(rl_data["rho0"])
                # Set material combo: preset 命中就选中对应项；否则把保存的
                # material_id（自定义名）还原成 edit text，让 _add_line 把它
                # 当成 standalone Rayleigh line 处理，而不是错误地继承先前选中
                # 项的 data。
                combo = self.rayleigh_panel.custom_name_edit
                idx = combo.findData(rl_data["material_id"])
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setEditText(rl_data["material_id"])
                # 保留原 rl_id，让 ix.source_curve*_id 仍能解析
                self.rayleigh_panel._add_line(explicit_id=rl_data.get("id"))

            # Restore reflected curves
            for refl_data in wf.get("reflected_curves", []):
                source_id = refl_data["source_id"]
                center_up = refl_data["center_up"]
                # 保留原 refl_id（如 "refl_3"），避免 ix.source_curve*_id 失效
                refl_id = self.hugoniot_plot.add_reflected(
                    source_id, center_up, explicit_id=refl_data.get("id")
                )
                if refl_id:
                    # 恢复 anchor_intersection_id（若保存在 workflow 中）
                    anchor_id = refl_data.get("anchor_intersection_id")
                    source_ix_id = refl_data.get("source_ix_id")
                    if anchor_id is not None or source_ix_id is not None:
                        for rc in self.hugoniot_plot.reflected_curves:
                            if rc["id"] == refl_id:
                                if anchor_id is not None:
                                    rc["anchor_intersection_id"] = anchor_id
                                if source_ix_id is not None:
                                    rc["source_ix_id"] = source_ix_id
                                break
                    mat = self.hugoniot_plot.materials.get(source_id)
                    name = mat.name if mat else source_id
                    self.intersection_panel.add_reflected_entry(refl_id, name, center_up)

            # Restore intersections
            from im_app.core.physics import Intersection
            self.hugoniot_plot.intersections.clear()
            for ix_data in wf.get("intersections", []):
                ix = Intersection(
                    id=ix_data["id"],
                    curve1_id=ix_data["curve1_id"],
                    curve2_id=ix_data["curve2_id"],
                    up=ix_data["up"],
                    p=ix_data["p"],
                    type=ix_data.get("type", "custom"),
                    material_id=ix_data.get("material_id"),
                    compression_ratio=ix_data.get("compression_ratio"),
                    source_curve1_id=ix_data.get("source_curve1_id"),
                    source_curve2_id=ix_data.get("source_curve2_id"),
                    ignore_first_at_creation=ix_data.get("ignore_first_at_creation", True),
                )
                self.hugoniot_plot.intersections.append(ix)

            # Update intersection panel
            self.intersection_panel.set_intersections(
                self.hugoniot_plot.intersections,
                self.hugoniot_plot.materials,
            )
            self.intersection_panel.update_rayleigh_lines(self.hugoniot_plot.rayleigh_lines)
            self.intersection_panel.update_reflected_curves(self.hugoniot_plot.reflected_curves)

            # Restore plot settings
            ps = wf.get("plot_settings", {})
            if ps:
                # P-Up plot settings
                p_up_ps = ps.get("p_up", {})
                if p_up_ps:
                    xlim = p_up_ps.get("xlim", [0, 30])
                    ylim = p_up_ps.get("ylim", [0, 30])
                    self.hugoniot_plot.set_xlim(xlim[0], xlim[1])
                    self.hugoniot_plot.set_ylim(ylim[0], ylim[1])
                    if "show_legend" in p_up_ps:
                        self.hugoniot_plot.set_legend_visible(p_up_ps["show_legend"])
                    if "linewidth" in p_up_ps:
                        self.hugoniot_plot.set_linewidth(p_up_ps["linewidth"])
                    if "linestyle" in p_up_ps:
                        self.hugoniot_plot.set_linestyle(p_up_ps["linestyle"])
                    # Update internal settings
                    self._plot_settings["P-Up"]["xlim"] = tuple(xlim)
                    self._plot_settings["P-Up"]["ylim"] = tuple(ylim)
                    self._plot_settings["P-Up"]["show_legend"] = p_up_ps.get("show_legend", True)
                    self._plot_settings["P-Up"]["linewidth"] = p_up_ps.get("linewidth", 1.2)
                    self._plot_settings["P-Up"]["linestyle"] = p_up_ps.get("linestyle", "-")

                # All other plot settings (with migration for old "eos" key)
                if "p_cr" in ps:
                    self._plot_settings["P-CR"] = ps["p_cr"]
                elif "eos" in ps:
                    # 旧格式迁移：eos -> p_cr
                    self._plot_settings["P-CR"] = ps["eos"]
                if "us_up" in ps:
                    self._plot_settings["Us-Up"] = ps["us_up"]
                if "p_t" in ps:
                    self._plot_settings["P-T"] = ps["p_t"]
                if "rho_up" in ps:
                    self._plot_settings["rho-Up"] = ps["rho_up"]
                if "t_up" in ps:
                    self._plot_settings["T-Up"] = ps["t_up"]
                if "e_up" in ps:
                    self._plot_settings["E-Up"] = ps["e_up"]
                if "p_us" in ps:
                    self._plot_settings["P-Us"] = ps["p_us"]

            # Restore EOS scatter points with migration from old format
            # 迁移：兼容旧字段 eos_scatter_points
            old_pts = wf.get("eos_scatter_points", [])
            new_pts = wf.get("scatter_points", [])
            if old_pts and not new_pts:
                # 旧格式迁移：补全 schema
                from im_app.core.element_style import DEFAULT_SCATTER_STYLE
                from im_app.core.plot_style import PRL_COLORS
                colors = list(PRL_COLORS.values())
                migrated = []
                for i, op in enumerate(old_pts, 1):
                    migrated.append({
                        "id":         f"sc_{i:04d}",
                        "label":      op.get("label", f"Point {i}"),
                        "source":     "manual",
                        "scope":      "global",
                        "target_tab": None,
                        "style":      {**DEFAULT_SCATTER_STYLE, "color": colors[(i-1) % len(colors)]},
                        "Up":          None,
                        "P":           op.get("pressure"),
                        "compression": op.get("compression"),
                        "T":           None,
                        "E":           None,
                        "rho":         None,
                        "Us":          None,
                    })
                self._scatter_points = migrated
            else:
                self._scatter_points = new_pts

            # 重置 counter 避免与已加载点冲突
            existing_ids = []
            for p in self._scatter_points:
                pid = p.get("id", "")
                if "_" in pid:
                    try:
                        num = int(pid.split("_")[1])
                        existing_ids.append(num)
                    except (ValueError, IndexError):
                        pass
            self._scatter_counter = max(existing_ids, default=0)
            # 也重置 color counter (近似)
            self._scatter_color_counter = len(self._scatter_points)

            # Refresh UI to show loaded scatter points
            if hasattr(self, '_update_scatter_list_widget'):
                self._update_scatter_list_widget()
            materials = self.hugoniot_plot.materials  # Always show materials
            eos_settings = self._plot_settings["P-CR"]
            self.eos_plot.update_plot(
                materials=materials,
                scatter_points=self._scatter_points,
                xlim=eos_settings["xlim"],
                ylim=eos_settings["ylim"],
            )

            # Update plot settings display
            self._on_target_plot_changed(self.target_plot_combo.currentIndex())

            # TODO Task 15: Replace with scatter_ix_combo mechanism
            # # Update EOS inputs with the last intersection if available
            # if self.hugoniot_plot.intersections:
            #     last_ix = self.hugoniot_plot.intersections[-1]
            #     cr = f"{last_ix.compression_ratio:.3f}" if hasattr(last_ix, 'compression_ratio') and last_ix.compression_ratio else "-"
            #     self._update_eos_inputs_from_intersection(last_ix.curve1_id, last_ix.up, last_ix.p, cr)

            self.hugoniot_plot.refresh()
            # Refresh scatter UI after workflow load
            if hasattr(self, '_refresh_scatter_ix_combo'):
                self._refresh_scatter_ix_combo()
            if hasattr(self, '_update_scatter_list_widget'):
                self._update_scatter_list_widget()
            if hasattr(self, '_refresh_all_plots_with_scatter'):
                self._refresh_all_plots_with_scatter()
            self.status.showMessage(f"Workflow loaded from {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()
