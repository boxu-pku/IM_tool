"""
参考曲线编辑对话框

用于创建和编辑简单的参考曲线数据。
"""

from __future__ import annotations

import os
from datetime import datetime

import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QTableWidget,
    QTableWidgetItem, QMessageBox, QFileDialog,
    QGroupBox, QFormLayout, QSpinBox, QHeaderView,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from im_app.core.reference_curve import (
    save_reference_curve,
    VARIABLE_MAPPING,
)


class ReferenceCurveDialog(QDialog):
    """参考曲线创建/编辑对话框"""

    def __init__(self, curve_dir: str, parent=None):
        super().__init__(parent)
        self.curve_dir = curve_dir
        self.setWindowTitle("Create Reference Curve")
        self.setMinimumSize(1200, 800)

        # 设置字体
        font = self.font()
        font.setPointSize(11)
        self.setFont(font)

        # 数据存储
        self._data_rows = 10  # 初始行数
        self._current_variables = []

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 基本信息
        info_group = QGroupBox("Curve Information")
        info_layout = QFormLayout(info_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter curve name...")
        info_layout.addRow("Curve Name:", self.name_edit)

        layout.addWidget(info_group)

        # 变量选择
        var_group = QGroupBox("Variables")
        var_layout = QVBoxLayout(var_group)

        # 第一列变量
        col1_layout = QHBoxLayout()
        col1_layout.addWidget(QLabel("X Variable:"))
        self.x_var_combo = QComboBox()
        self.x_var_combo.addItems(list(VARIABLE_MAPPING.keys()))
        self.x_var_combo.setCurrentIndex(2)  # 默认选择 P
        self.x_var_combo.currentTextChanged.connect(self._update_unit_suggestions)
        col1_layout.addWidget(self.x_var_combo)
        var_layout.addLayout(col1_layout)

        # X变量单位
        x_unit_layout = QHBoxLayout()
        x_unit_layout.addWidget(QLabel("X Unit:"))
        self.x_unit_edit = QLineEdit()
        self.x_unit_edit.setPlaceholderText("e.g., Mbar")
        x_unit_layout.addWidget(self.x_unit_edit)
        var_layout.addLayout(x_unit_layout)

        # 第二列变量
        col2_layout = QHBoxLayout()
        col2_layout.addWidget(QLabel("Y Variable:"))
        self.y_var_combo = QComboBox()
        self.y_var_combo.addItems(list(VARIABLE_MAPPING.keys()))
        self.y_var_combo.setCurrentIndex(5)  # 默认选择 T
        self.y_var_combo.currentTextChanged.connect(self._update_unit_suggestions)
        col2_layout.addWidget(self.y_var_combo)
        var_layout.addLayout(col2_layout)

        # Y变量单位
        y_unit_layout = QHBoxLayout()
        y_unit_layout.addWidget(QLabel("Y Unit:"))
        self.y_unit_edit = QLineEdit()
        self.y_unit_edit.setPlaceholderText("e.g., eV")
        y_unit_layout.addWidget(self.y_unit_edit)
        var_layout.addLayout(y_unit_layout)

        layout.addWidget(var_group)

        # 单位建议映射
        self._unit_suggestions = {
            "Up": "km/s",
            "Us": "km/s",
            "P": "Mbar",
            "rho": "g/cm^3",
            "compression": "-",
            "T": "eV",
            "E": "MJ/g",
        }

        # 数据表格
        table_group = QGroupBox("Data Points")
        table_layout = QVBoxLayout(table_group)

        # 表头
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("X:"))
        self.x_header_label = QLabel("P")
        self.x_header_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.x_header_label)
        header_layout.addWidget(QLabel("Y:"))
        self.y_header_label = QLabel("T")
        self.y_header_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.y_header_label)
        header_layout.addStretch()
        table_layout.addLayout(header_layout)

        # 表格
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(2)
        self.data_table.setRowCount(self._data_rows)
        self.data_table.setHorizontalHeaderLabels(["X Value", "Y Value"])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.data_table)

        # 行操作按钮
        row_btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("Add Row")
        add_row_btn.clicked.connect(self._add_row)
        row_btn_layout.addWidget(add_row_btn)

        remove_row_btn = QPushButton("Remove Last Row")
        remove_row_btn.clicked.connect(self._remove_row)
        row_btn_layout.addWidget(remove_row_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_data)
        row_btn_layout.addWidget(clear_btn)

        row_btn_layout.addStretch()
        table_layout.addLayout(row_btn_layout)

        layout.addWidget(table_group)

        # 现在可以更新单位建议和表头了
        self._update_unit_suggestions()

        # 底部按钮
        btn_layout = QHBoxLayout()

        from_file_btn = QPushButton("Load from File")
        from_file_btn.clicked.connect(self._load_from_file)
        btn_layout.addWidget(from_file_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Curve")
        save_btn.clicked.connect(self._save_curve)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

        # 初始化一些默认数据
        self._init_sample_data()

    def _update_unit_suggestions(self):
        """更新单位建议"""
        x_var = self.x_var_combo.currentText()
        y_var = self.y_var_combo.currentText()

        if not self.x_unit_edit.text():
            self.x_unit_edit.setText(self._unit_suggestions.get(x_var, ""))
        if not self.y_unit_edit.text():
            self.y_unit_edit.setText(self._unit_suggestions.get(y_var, ""))

        # 更新表头（如果标签已经创建）
        if hasattr(self, 'x_header_label') and hasattr(self, 'y_header_label'):
            self.x_header_label.setText(x_var)
            self.y_header_label.setText(y_var)

    def _add_row(self):
        """添加一行"""
        current_row = self.data_table.rowCount()
        self.data_table.insertRow(current_row)
        self._data_rows += 1

    def _remove_row(self):
        """删除最后一行"""
        if self.data_table.rowCount() > 1:
            self.data_table.removeRow(self.data_table.rowCount() - 1)
            self._data_rows -= 1

    def _clear_data(self):
        """清空数据"""
        for row in range(self.data_table.rowCount()):
            for col in range(self.data_table.columnCount()):
                item = self.data_table.item(row, col)
                if item:
                    item.setText("")

    def _init_sample_data(self):
        """初始化示例数据（P-T关系）"""
        sample_data = [
            (0.1, 0.5),
            (0.5, 1.0),
            (1.0, 2.0),
            (2.0, 3.5),
            (5.0, 6.0),
            (10.0, 8.5),
        ]

        for row, (x, y) in enumerate(sample_data):
            if row < self.data_table.rowCount():
                self.data_table.setItem(row, 0, QTableWidgetItem(str(x)))
                self.data_table.setItem(row, 1, QTableWidgetItem(str(y)))

    def _load_from_file(self):
        """从现有CSV文件加载"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Reference Curve",
            self.curve_dir,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not filepath:
            return

        try:
            from im_app.core.reference_curve import load_reference_curve
            info = load_reference_curve(filepath)

            # 设置名称
            self.name_edit.setText(info["name"])

            # 设置变量
            variables = info["variables"]
            if len(variables) >= 2:
                self.x_var_combo.setCurrentText(variables[0])
                self.y_var_combo.setCurrentText(variables[1])

            # 设置单位
            units = info["units"]
            if len(units) >= 2:
                self.x_unit_edit.setText(units[0])
                self.y_unit_edit.setText(units[1])

            # 加载数据
            df = info["data"]
            self.data_table.setRowCount(len(df))
            for row_idx in range(len(df)):
                for col_idx in range(min(2, len(df.columns))):
                    val = df.iloc[row_idx, col_idx]
                    if np.isfinite(val):
                        self.data_table.setItem(
                            row_idx, col_idx,
                            QTableWidgetItem(f"{val:.6g}")
                        )

            QMessageBox.information(
                self, "Load Successful",
                f"Loaded curve '{info['name']}' with {len(df)} data points."
            )

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load file:\n{str(e)}")

    def _get_data_from_table(self) -> tuple:
        """从表格获取数据"""
        x_var = self.x_var_combo.currentText()
        y_var = self.y_var_combo.currentText()

        variables = [x_var, y_var]
        units = [self.x_unit_edit.text(), self.y_unit_edit.text()]

        data_list = []
        for row in range(self.data_table.rowCount()):
            x_item = self.data_table.item(row, 0)
            y_item = self.data_table.item(row, 1)

            x_val = x_item.text() if x_item else ""
            y_val = y_item.text() if y_item else ""

            # 跳过空行
            if not x_val.strip() and not y_val.strip():
                continue

            try:
                x_float = float(x_val) if x_val.strip() else np.nan
                y_float = float(y_val) if y_val.strip() else np.nan
                data_list.append([x_float, y_float])
            except ValueError:
                continue

        if not data_list:
            raise ValueError("没有有效的数据")

        data = np.array(data_list)
        return variables, units, data

    def _save_curve(self):
        """保存曲线"""
        # 获取曲线名称
        curve_name = self.name_edit.text().strip()
        if not curve_name:
            QMessageBox.warning(self, "Missing Name", "请输入曲线名称")
            return

        # 获取数据
        try:
            variables, units, data = self._get_data_from_table()
        except Exception as e:
            QMessageBox.warning(self, "Data Error", str(e))
            return

        # 生成文件名
        filename = f"{curve_name}.csv"
        filepath = os.path.join(self.curve_dir, filename)

        # 检查文件是否存在
        if os.path.exists(filepath):
            reply = QMessageBox.question(
                self, "File Exists",
                f"文件 '{filename}' 已存在，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        try:
            save_reference_curve(filepath, curve_name, variables, units, data)
            QMessageBox.information(
                self, "Save Successful",
                f"曲线 '{curve_name}' 已保存:\n{filepath}\n\n包含 {len(data)} 个数据点"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"保存失败:\n{str(e)}")
