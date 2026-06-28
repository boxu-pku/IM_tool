"""
Reference curve control panel.

加载和管理参考曲线，类似于 MaterialPanel 的功能。
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QLabel, QMessageBox, QDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont

import os
from im_app.core.reference_curve import (
    list_reference_curves,
    load_reference_curve,
    VARIABLE_MAPPING,
)
from im_app.core.physics import MaterialData
import numpy as np


class ReferenceCurvePanel(QWidget):
    """Reference curve selection panel with checkboxes."""

    curves_changed = pyqtSignal()   # emitted when selection changes

    def __init__(self, curve_dir: str, parent=None):
        super().__init__(parent)
        self.curve_dir = curve_dir
        self._loaded: dict[str, MaterialData] = {}  # id -> MaterialData
        self._curve_info: dict[str, dict] = {}  # id -> curve info
        self._init_ui()
        self.refresh_library()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Reference curve management group
        grp = QGroupBox("Reference Curves")
        vbox = QVBoxLayout(grp)

        # Action buttons
        action_row = QHBoxLayout()
        self.create_btn = QPushButton("Create New")
        self.create_btn.setToolTip("Create a new reference curve")
        self.create_btn.clicked.connect(self._on_create)
        action_row.addWidget(self.create_btn)

        self.manage_btn = QPushButton("Manage")
        self.manage_btn.setToolTip("Manage existing curves")
        self.manage_btn.clicked.connect(self._on_manage)
        action_row.addWidget(self.manage_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Refresh curve list")
        self.refresh_btn.clicked.connect(self.refresh_library)
        action_row.addWidget(self.refresh_btn)

        vbox.addLayout(action_row)

        # Curve list
        self.curve_list = QListWidget()
        self.curve_list.itemChanged.connect(self._on_item_changed)
        self.curve_list.setMinimumHeight(200)
        vbox.addWidget(self.curve_list)

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

    def _populate(self):
        self.curve_list.clear()

        # 确保目录存在
        os.makedirs(self.curve_dir, exist_ok=True)

        try:
            curves = list_reference_curves(self.curve_dir)
        except FileNotFoundError:
            self.info_label.setText("Curve directory not found")
            return

        # Sort entries alphabetically by name
        curves = sorted(curves, key=lambda x: x['name'].lower())

        for curve in curves:
            # 创建显示名称：名称 + 变量
            display_name = f"{curve['name']} ({', '.join(curve['variables'])})"
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, curve['filepath'])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.curve_list.addItem(item)

        self.info_label.setText(f"{len(curves)} curves available")

    def _on_item_changed(self, item: QListWidgetItem):
        filepath = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self._load_curve(filepath)
        else:
            # 从已加载中移除
            curve_id = self._get_curve_id_from_filepath(filepath)
            if curve_id:
                self._loaded.pop(curve_id, None)
                self._curve_info.pop(curve_id, None)
        self.curves_changed.emit()

    def _load_curve(self, filepath: str):
        """加载参考曲线并转换为 MaterialData"""
        curve_id = self._get_curve_id_from_filepath(filepath)
        if curve_id and curve_id in self._loaded:
            return  # 已加载

        try:
            info = load_reference_curve(filepath)
            df = info["data"]

            # 确定变量
            variables = info["variables"]
            if len(variables) < 2:
                return

            # 提取所有可用的数据
            up_data = None
            p_data = None
            us_data = None
            compression_data = None
            rho_data = None
            temperature_data = None
            energy_data = None

            for i, var in enumerate(variables):
                standard_name = VARIABLE_MAPPING.get(var)
                if standard_name and i < len(df.columns):
                    data = df.iloc[:, i].values
                    if standard_name == "up":
                        up_data = data
                    elif standard_name == "p":
                        p_data = data
                    elif standard_name == "us":
                        us_data = data
                    elif standard_name == "compression":
                        compression_data = data
                    elif standard_name == "rho":
                        rho_data = data
                    elif standard_name == "temperature":
                        temperature_data = data
                    elif standard_name == "energy":
                        energy_data = data

            # 参考曲线可能只有部分变量
            # MaterialData 要求 up 和 p 必须存在，所以创建空数组作为占位符

            # 创建MaterialData - 对于必需字段使用空数组，可选字段使用None
            mat = MaterialData(
                id=f"ref_{info['name']}",
                name=f"Ref: {info['name']}",
                rho0=2.7,  # 默认值
                up=up_data if up_data is not None else np.array([]),
                p=p_data if p_data is not None else np.array([]),
                us=us_data,
                compression=compression_data,
                rho=rho_data,
                temperature=temperature_data,
                energy=energy_data,
            )

            self._loaded[mat.id] = mat
            self._curve_info[mat.id] = info

            print(f"Loaded curve {mat.id}: up={up_data is not None}, p={p_data is not None}, T={temperature_data is not None}")

        except Exception as e:
            print(f"Error loading curve: {e}")
            import traceback
            traceback.print_exc()

    def _get_curve_id_from_filepath(self, filepath: str) -> str:
        """从文件路径获取曲线ID"""
        name = os.path.splitext(os.path.basename(filepath))[0]
        return f"ref_{name}"

    def _select_all(self):
        for i in range(self.curve_list.count()):
            self.curve_list.item(i).setCheckState(Qt.Checked)

    def _deselect_all(self):
        for i in range(self.curve_list.count()):
            self.curve_list.item(i).setCheckState(Qt.Unchecked)

    def get_selected_curves(self) -> dict[str, MaterialData]:
        """返回选中的参考曲线"""
        return dict(self._loaded)

    def refresh_library(self):
        """刷新曲线列表"""
        # 保存当前选中状态
        selected_paths = set()
        for i in range(self.curve_list.count()):
            item = self.curve_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_paths.add(item.data(Qt.UserRole))

        self._loaded.clear()
        self._curve_info.clear()
        self._populate()

        # 恢复选中状态
        for i in range(self.curve_list.count()):
            item = self.curve_list.item(i)
            if item.data(Qt.UserRole) in selected_paths:
                item.setCheckState(Qt.Checked)

    def _on_create(self):
        """创建新曲线"""
        from im_app.gui.reference_curve_dialog import ReferenceCurveDialog

        dialog = ReferenceCurveDialog(self.curve_dir, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh_library()

    def _on_manage(self):
        """管理曲线"""
        from im_app.gui.reference_curve_manager import ReferenceCurveManager

        dialog = ReferenceCurveManager(self.curve_dir, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh_library()
