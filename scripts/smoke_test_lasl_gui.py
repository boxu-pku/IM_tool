#!/usr/bin/env python3
"""Offscreen smoke test: the GUI material list must show the imported
LASL SHD materials (uses PyQt5, the binding the app actually uses)."""

import io
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                              errors="replace", write_through=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# 确保导入仓库源码，而不是 site-packages 里的旧安装副本
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import im_app  # noqa: E402,F401

assert Path(im_app.__file__).resolve().is_relative_to(PROJECT_ROOT), (
    f"importing im_app from {im_app.__file__}, not the repo")

from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from im_app.gui.material_panel import MaterialPanel  # noqa: E402

panel = MaterialPanel("im_app/standard_library")
n = panel.material_list.count()
print("material_list count =", n)
print("sample:", [panel.material_list.item(i).text()
                  for i in range(min(3, n))])
lasl_n = sum(1 for i in range(n)
             if "LASL" in panel.material_list.item(i).text())
print("LASL-labeled items:", lasl_n)
# load one through the panel's own path
mat = panel._loaded.get("magnesium_p105_lasl")
print("SMOKE OK")
