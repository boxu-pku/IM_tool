"""
参考曲线管理对话框

用于加载、查看和管理参考曲线。
"""

from __future__ import annotations

import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

import numpy as np
from im_app.core.reference_curve import (
    load_reference_curve,
    list_reference_curves,
    VARIABLE_MAPPING,
)


class ReferenceCurveManager(QDialog):
    """参考曲线管理对话框"""

    curve_selected = pyqtSignal(str)  # 发射曲线文件路径

    def __init__(self, curve_dir: str, parent=None):
        super().__init__(parent)

        self.curve_dir = curve_dir
        self.setWindowTitle("Reference Curves")
        self.setMinimumSize(1400, 900)

        # 设置字体
        font = self.font()
        font.setPointSize(11)
        self.setFont(font)

        # 确保目录存在
        os.makedirs(curve_dir, exist_ok=True)

        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_list)
        toolbar_layout.addWidget(refresh_btn)

        create_btn = QPushButton("Create New")
        create_btn.clicked.connect(self._create_new)
        toolbar_layout.addWidget(create_btn)

        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self._edit_selected)
        toolbar_layout.addWidget(edit_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_selected)
        toolbar_layout.addWidget(delete_btn)

        toolbar_layout.addStretch()

        layout.addLayout(toolbar_layout)

        # 分割器：列表 | 详情
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：曲线列表
        left_widget = QGroupBox("Available Curves")
        left_layout = QVBoxLayout(left_widget)

        self.curve_list = QListWidget()
        self.curve_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.curve_list.itemDoubleClicked.connect(self._load_curve)
        left_layout.addWidget(self.curve_list)

        splitter.addWidget(left_widget)

        # 右侧：曲线详情
        right_widget = QGroupBox("Curve Details")
        right_layout = QVBoxLayout(right_widget)

        # 信息标签
        self.info_label = QLabel("Select a curve to view details")
        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label)

        # 数据表格
        self.data_table = QTableWidget()
        self.data_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.data_table)

        splitter.addWidget(right_widget)

        layout.addWidget(splitter)

        # 底部按钮
        btn_layout = QHBoxLayout()

        load_btn = QPushButton("Load Selected Curve")
        load_btn.clicked.connect(self._load_curve)
        btn_layout.addWidget(load_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # 设置分割比例
        splitter.setSizes([400, 1000])

    def _refresh_list(self):
        """刷新曲线列表"""
        self.curve_list.clear()
        curves = list_reference_curves(self.curve_dir)

        for curve in curves:
            item = QListWidgetItem(
                f"{curve['name']} ({', '.join(curve['variables'])})"
            )
            item.setData(Qt.UserRole, curve)
            self.curve_list.addItem(item)

        self.info_label.setText(f"Found {len(curves)} reference curve(s)")

    def _on_selection_changed(self):
        """选择改变时显示详情"""
        selected_items = self.curve_list.selectedItems()
        if not selected_items:
            return

        curve = selected_items[0].data(Qt.UserRole)

        try:
            info = load_reference_curve(curve["filepath"])
            df = info["data"]

            # 更新信息标签
            info_text = f"<b>Name:</b> {info['name']}<br>"
            info_text += f"<b>Variables:</b> {', '.join(info['variables'])}<br>"
            info_text += f"<b>Units:</b> {', '.join(info['units'])}<br>"
            info_text += f"<b>Points:</b> {len(df)}"
            self.info_label.setText(info_text)

            # 更新数据表格
            self.data_table.setColumnCount(len(df.columns))
            self.data_table.setRowCount(len(df))
            self.data_table.setHorizontalHeaderLabels(df.columns)

            for row_idx in range(len(df)):
                for col_idx in range(len(df.columns)):
                    val = df.iloc[row_idx, col_idx]
                    if np.isfinite(val):
                        self.data_table.setItem(
                            row_idx, col_idx,
                            QTableWidgetItem(f"{val:.6g}")
                        )
                    else:
                        self.data_table.setItem(
                            row_idx, col_idx,
                            QTableWidgetItem("")
                        )

        except Exception as e:
            self.info_label.setText(f"Error loading curve: {str(e)}")

    def _create_new(self):
        """创建新曲线"""
        from im_app.gui.reference_curve_dialog import ReferenceCurveDialog

        dialog = ReferenceCurveDialog(self.curve_dir, self)
        if dialog.exec() == QDialog.Accepted:
            self._refresh_list()

    def _edit_selected(self):
        """编辑选中的曲线"""
        selected_items = self.curve_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "请先选择一个曲线")
            return

        curve = selected_items[0].data(Qt.UserRole)

        from im_app.gui.reference_curve_dialog import ReferenceCurveDialog

        dialog = ReferenceCurveDialog(self.curve_dir, self)
        dialog.setWindowTitle("Edit Reference Curve")

        # 加载现有数据
        try:
            info = load_reference_curve(curve["filepath"])
            dialog.name_edit.setText(info["name"])

            variables = info["variables"]
            if len(variables) >= 2:
                dialog.x_var_combo.setCurrentText(variables[0])
                dialog.y_var_combo.setCurrentText(variables[1])

            units = info["units"]
            if len(units) >= 2:
                dialog.x_unit_edit.setText(units[0])
                dialog.y_unit_edit.setText(units[1])

            # 加载数据
            df = info["data"]
            dialog.data_table.setRowCount(len(df))
            for row_idx in range(len(df)):
                for col_idx in range(min(2, len(df.columns))):
                    val = df.iloc[row_idx, col_idx]
                    if np.isfinite(val):
                        dialog.data_table.setItem(
                            row_idx, col_idx,
                            QTableWidgetItem(f"{val:.6g}")
                        )

            if dialog.exec() == QDialog.Accepted:
                self._refresh_list()

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"无法加载曲线:\n{str(e)}")

    def _delete_selected(self):
        """删除选中的曲线"""
        selected_items = self.curve_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "请先选择一个曲线")
            return

        curve = selected_items[0].data(Qt.UserRole)

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"确定要删除曲线 '{curve['name']}' 吗？\n\n文件: {curve['filepath']}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                os.remove(curve["filepath"])
                self._refresh_list()
                QMessageBox.information(self, "Deleted", f"曲线 '{curve['name']}' 已删除")
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"删除失败:\n{str(e)}")

    def _load_curve(self):
        """加载选中的曲线"""
        selected_items = self.curve_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "请先选择一个曲线")
            return

        curve = selected_items[0].data(Qt.UserRole)
        self.curve_selected.emit(curve["filepath"])
        QMessageBox.information(
            self, "Curve Loaded",
            f"曲线 '{curve['name']}' 已加载到可视化系统"
        )
