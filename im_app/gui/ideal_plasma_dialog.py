"""
理想等离子体 Hugoniot 曲线创建对话框。

基于强冲击波极限 Rankine-Hugoniot 关系 + γ律气体状态方程，
解析生成 Hugoniot 数据，直接创建 MaterialData 对象。
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QSpinBox,
    QPushButton, QCheckBox, QGroupBox, QMessageBox,
)
from PyQt5.QtCore import Qt

from im_app.core.physics import generate_ideal_plasma_hugoniot, MaterialData

INPUT_FONT_SIZE = 11


class IdealPlasmaDialog(QDialog):
    """理想等离子体 Hugoniot 参数输入对话框。"""

    def __init__(self, lib_dir: str = "", parent=None):
        super().__init__(parent)
        self.lib_dir = lib_dir
        self._material: MaterialData | None = None
        self._save_to_library = False
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("创建理想等离子体 Hugoniot")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        font = self.font()
        font.setPointSize(INPUT_FONT_SIZE)

        # ── 参数输入 ──
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例: CH Foam")
        self.name_edit.setFont(font)
        form.addRow("材料名称:", self.name_edit)

        self.rho0_spin = QDoubleSpinBox()
        self.rho0_spin.setRange(0.001, 100.0)
        self.rho0_spin.setDecimals(3)
        self.rho0_spin.setValue(0.089)
        self.rho0_spin.setSuffix("  g/cm³")
        self.rho0_spin.setFont(font)
        form.addRow("初始密度 ρ₀:", self.rho0_spin)

        self.gamma_spin = QDoubleSpinBox()
        self.gamma_spin.setRange(1.01, 10.0)
        self.gamma_spin.setDecimals(3)
        self.gamma_spin.setValue(5.0 / 3.0)
        self.gamma_spin.setSuffix("  γ")
        self.gamma_spin.setFont(font)
        form.addRow("绝热指数:", self.gamma_spin)

        self.upmax_spin = QDoubleSpinBox()
        self.upmax_spin.setRange(1.0, 1000.0)
        self.upmax_spin.setDecimals(1)
        self.upmax_spin.setValue(200.0)
        self.upmax_spin.setSuffix("  km/s")
        self.upmax_spin.setFont(font)
        form.addRow("最大 Up:", self.upmax_spin)

        self.npoints_spin = QSpinBox()
        self.npoints_spin.setRange(50, 10000)
        self.npoints_spin.setValue(500)
        self.npoints_spin.setFont(font)
        form.addRow("数据点数:", self.npoints_spin)

        layout.addLayout(form)

        # ── 预览区 ──
        preview_grp = QGroupBox("预览")
        preview_layout = QVBoxLayout(preview_grp)
        self.preview_label = QLabel()
        self.preview_label.setFont(font)
        self.preview_label.setStyleSheet("color: #333;")
        preview_layout.addWidget(self.preview_label)
        layout.addWidget(preview_grp)

        # ── 保存选项 ──
        self.save_cb = QCheckBox("保存到标准材料库")
        self.save_cb.setFont(font)
        self.save_cb.setToolTip("将生成的数据写入 standard_library/materials/ 并注册到 metadata.json")
        layout.addWidget(self.save_cb)

        # ── 按钮 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        create_btn = QPushButton("创建")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(create_btn)
        layout.addLayout(btn_row)

        # ── 信号 ──
        self.gamma_spin.valueChanged.connect(self._update_preview)
        self.rho0_spin.valueChanged.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self):
        gamma = self.gamma_spin.value()
        rho0 = self.rho0_spin.value()
        cr = (gamma + 1) / (gamma - 1)
        us_slope = (gamma + 1) / 2.0
        rho_shocked = rho0 * cr

        self.preview_label.setText(
            f"压缩比 ρ/ρ₀ = {cr:.3f}\n"
            f"Us = {us_slope:.3f} × Up\n"
            f"冲击后密度 ρ = {rho_shocked:.3f} g/cm³（常数）"
        )

    def _on_create(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "参数错误", "请输入材料名称。")
            return

        rho0 = self.rho0_spin.value()
        gamma = self.gamma_spin.value()
        up_max = self.upmax_spin.value()
        n_points = self.npoints_spin.value()

        self._material = generate_ideal_plasma_hugoniot(
            name=name,
            rho0=rho0,
            gamma=gamma,
            up_max=up_max,
            n_points=n_points,
        )

        # 如果勾选了保存到库
        if self.save_cb.isChecked() and self.lib_dir:
            self._save_to_library = True
            try:
                self._save_material_to_library()
            except OSError as e:
                QMessageBox.warning(self, "保存失败", f"无法写入文件:\n{e}")
                return
        else:
            self._save_to_library = False

        self.accept()

    def _save_material_to_library(self):
        """将生成的材料写入标准库。"""
        mat = self._material
        materials_dir = os.path.join(self.lib_dir, "materials")
        os.makedirs(materials_dir, exist_ok=True)

        filename = f"{mat.id}.txt"
        filepath = os.path.join(materials_dir, filename)

        # 构建 DataFrame
        df = pd.DataFrame({
            "Up(km/s)": mat.up,
            "Us(km/s)": mat.us,
            "P(Mbar)": mat.p,
            "rho(g/cm3)": mat.rho,
            "compression": mat.compression,
            "E(MJ/g)": mat.energy,
        })

        # 写入标准格式文件
        from im_app.core.data_converter import write_standard_txt
        material_info = {
            "material": mat.name,
            "reference": f"Ideal Plasma (γ={self.gamma_spin.value():.3f})",
            "rho0": str(mat.rho0),
            "data_source": "Analytical (strong shock Rankine-Hugoniot)",
            "notes": f"γ={self.gamma_spin.value():.3f}, ρ/ρ₀={float(mat.compression.mean()):.3f}" if mat.compression is not None else "",
        }
        write_standard_txt(filepath, df, material_info)

        # 更新 metadata.json
        meta_path = os.path.join(self.lib_dir, "metadata.json")
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            metadata = {"version": "1.0", "materials": []}

        # 检查是否已存在
        existing_ids = {m["id"] for m in metadata.get("materials", [])}
        if mat.id not in existing_ids:
            metadata["materials"].append({
                "id": mat.id,
                "name": mat.name,
                "source": f"Ideal Plasma (γ={self.gamma_spin.value():.3f})",
                "rho0": mat.rho0,
                "file": f"materials/{filename}",
                "tags": ["ideal_plasma"],
                "points": len(mat.up),
                "up_range": [float(mat.up[0]), float(mat.up[-1])],
                "p_range": [float(mat.p[0]), float(mat.p[-1])],
                "compression_range": [
                    float(mat.compression.min()),
                    float(mat.compression.max()),
                ] if mat.compression is not None else [1.0, 1.0],
            })
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)

    def get_material(self) -> MaterialData:
        return self._material

    def save_to_library(self) -> bool:
        return self._save_to_library
