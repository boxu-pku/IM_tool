#!/usr/bin/env python3
"""Offscreen smoke test: cursor coordinate readout (status-bar coord label).

验证项：
1. 三个画布类都有 cursor_moved 信号，_dz_emit_hover 输出正确格式。
2. 变量名/单位跟画布类型走：P-Up(Up,P)、P-CR(compression,P)、Generic(x_var,y_var)。
3. P 单位跟 p_unit（Mbar/GPa），compression 无量纲无单位后缀。
4. 光标移出 axes（xdata/ydata=None）→ 空串清位。
5. _dz_on_motion 入口也触发读数（hover 挂在既有 motion 连接上）。
6. MainWindow：coord_label 存在、9 个画布的 cursor_moved 都连到它、切 tab 清空。
"""

import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace

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

from PyQt5.QtWidgets import QApplication, QLabel  # noqa: E402

app = QApplication([])

from im_app.core.plotter import (  # noqa: E402
    InteractiveHugoniotPlot, EOSPlot, GenericHugoniotPlot,
)


def hover(plot, xdata, ydata):
    """收集一次 _dz_emit_hover 的信号输出。"""
    got = []
    plot.cursor_moved.connect(got.append)
    plot._dz_emit_hover(SimpleNamespace(xdata=xdata, ydata=ydata))
    assert len(got) == 1, f"expected 1 emit, got {got}"
    return got[0]


# --- 1. InteractiveHugoniotPlot：P-Up 主图，默认 Mbar -----------------------
p = InteractiveHugoniotPlot()
s = hover(p, 2.5, 1.2)
print("P-Up default:", s)
assert s == "Up = 2.5000 km/s    P = 1.2000 Mbar", s

# p_unit 切 GPa 后单位跟随（axes 数据坐标即显示单位）
p.p_unit = "GPa"
s = hover(p, 2.5, 1.2)
print("P-Up GPa:   ", s)
assert "P = 1.2000 GPa" in s, s

# 光标移出 axes → 空串
assert hover(p, None, 1.0) == ""
assert hover(p, 2.5, None) == ""

# --- 2. EOSPlot：P-CR，x=compression（无量纲） --------------------------------
e = EOSPlot()
s = hover(e, 1.5, 2.0)
print("P-CR:       ", s)
assert s == "compression = 1.5000    P = 2.0000 Mbar", s

# --- 3. GenericHugoniotPlot：x_var/y_var 跟构造参数走 -------------------------
g = GenericHugoniotPlot("Us", "Up")
s = hover(g, 8.0, 3.0)
print("Us-Up:      ", s)
assert s == "Us = 8.0000 km/s    Up = 3.0000 km/s", s

g2 = GenericHugoniotPlot("compression", "P", tab_key="test")
s = hover(g2, 2.0, 5.0)
print("CR-P:       ", s)
assert s == "compression = 2.0000    P = 5.0000 Mbar", s

g2.p_unit = "GPa"
s = hover(g2, 2.0, 5.0)
assert "P = 5.0000 GPa" in s, s

# P 在 x 轴位置时单位同样跟随 p_unit
g3 = GenericHugoniotPlot("P", "T", tab_key="test")
g3.p_unit = "GPa"
s = hover(g3, 0.5, 4.0)
print("P-T (GPa):  ", s)
assert s == "P = 0.5000 GPa    T = 4.0000 eV", s

# --- 4. _dz_on_motion 入口也触发读数 ------------------------------------------
got = []
p2 = InteractiveHugoniotPlot()
p2.cursor_moved.connect(got.append)
p2._dz_on_motion(SimpleNamespace(x=100, y=100, xdata=3.0, ydata=0.7))
assert got == ["Up = 3.0000 km/s    P = 0.7000 Mbar"], got
# 拖拽中（_zoom_start 非 None）同样更新
p2._zoom_start = (90, 90)
p2._dz_on_motion(SimpleNamespace(x=100, y=100, xdata=3.1, ydata=0.8))
assert got[-1] == "Up = 3.1000 km/s    P = 0.8000 Mbar", got[-1]
print("motion entry OK")

# --- 5. MainWindow：coord_label + 9 画布接线 + 切 tab 清空 --------------------
os.chdir(PROJECT_ROOT)   # MainWindow 用相对路径 ("im_app/standard_library", "workflows")
from im_app.gui.main_window import MainWindow  # noqa: E402

w = MainWindow("im_app/standard_library", "workflows")
assert isinstance(w.coord_label, QLabel)

plots = [w.hugoniot_plot, w.eos_plot, w.p_rho_plot, w.us_up_plot,
         w.p_t_plot, w.rho_up_plot, w.t_up_plot, w.e_up_plot, w.p_us_plot]
assert len(plots) == 9
for plot in plots:
    plot.cursor_moved.emit("probe")
    assert w.coord_label.text() == "probe", f"{type(plot).__name__} not wired"

w.coord_label.setText("stale")
w._on_tab_changed(1)
assert w.coord_label.text() == "", w.coord_label.text()
print("MainWindow wiring OK (9 plots, tab-change clears)")

print("SMOKE OK")
