#!/usr/bin/env python3
"""Offscreen verification for the two UI changes:

1. LASL SHD materials (id *_lasl) are drawn as scatter (marker-only
   Line2D) in P-Up and P-CR plots, while SESAME materials stay lines.
2. Default axis view is auto (data-fit, not the old hardcoded (0,30)),
   and reset ('a' -> _on_plot_reset_view) returns to auto after zooming.
"""

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

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from im_app.gui.main_window import MainWindow  # noqa: E402

w = MainWindow("im_app/standard_library", "workflows")
print("MainWindow constructed", flush=True)
import numpy as np  # noqa: E402


def check_item(substr):
    lst = w.material_panel.material_list
    for i in range(lst.count()):
        it = lst.item(i)
        if substr.upper() in it.text().upper():
            return it
    return None


def material_artists(plot):
    from matplotlib.lines import Line2D
    return [a for a in plot.ax.get_lines()
            if isinstance(a, Line2D) and a.get_label() != "_nolegend_"
            and str(a.get_label()).startswith(("GOLD", "Aluminum"))]


def toggle(item, on=True):
    item.setCheckState(Qt.Checked if on else Qt.Unchecked)


# --- 1. LASL material drawn as scatter, auto view fits data -------------
gold = check_item("GOLD")
assert gold is not None, "GOLD LASL item not found"
toggle(gold, True)
app.processEvents()

arts = material_artists(w.hugoniot_plot)
assert arts, "no artist for GOLD"
a = arts[0]
assert a.get_linestyle() == "None", f"GOLD linestyle={a.get_linestyle()!r}"
assert a.get_marker() == "o", f"GOLD marker={a.get_marker()!r}"
print("P-Up GOLD artist: linestyle=None marker=o  OK", flush=True)

x0, x1 = w.hugoniot_plot.ax.get_xlim()
assert (x0, x1) != (0, 30) and x1 < 5, f"P-Up xlim not auto-fit: {(x0, x1)}"
y0, y1 = w.hugoniot_plot.ax.get_ylim()
assert y1 < 5, f"P-Up ylim not auto-fit: {(y0, y1)}"
print(f"P-Up auto view: X=[{x0:.3g}, {x1:.3g}], Y=[{y0:.3g}, {y1:.3g}]  OK",
      flush=True)

# --- 2. SESAME material stays a line ------------------------------------
al = check_item("3717")
assert al is not None, "Al_3717_sesame item not found"
toggle(al, True)
app.processEvents()
arts = material_artists(w.hugoniot_plot)
by_label = {a.get_label(): a for a in arts}
al_arts = [a for lbl, a in by_label.items() if "Aluminum" in lbl]
assert al_arts, f"no Aluminum artist: {list(by_label)}"
assert al_arts[0].get_linestyle() != "None", "SESAME drawn as scatter!"
print("P-Up SESAME artist stays a line  OK", flush=True)

# --- 3. zoom then 'a' reset returns to auto -----------------------------
w._on_plot_zoom_applied("P-Up", 0.0, 1.0, 0.0, 0.5)
assert w.hugoniot_plot.ax.get_xlim() == (0.0, 1.0)
w._on_plot_reset_view("P-Up")
x0, x1 = w.hugoniot_plot.ax.get_xlim()
assert x1 > 1.5, f"reset did not return to auto: {(x0, x1)}"
assert w._plot_settings["P-Up"]["xlim"] is None
print(f"zoom then 'a' -> auto again: X=[{x0:.3g}, {x1:.3g}]  OK", flush=True)

# --- 4. tab switching survives with None limits -------------------------
for idx in range(9):
    w.plot_tabs.setCurrentIndex(idx)
    app.processEvents()
print("all 9 tabs switched without error  OK", flush=True)

# --- 5. P-CR plot: GOLD scatter + auto view ------------------------------
w.plot_tabs.setCurrentIndex(1)
app.processEvents()
eos_lines = [a for a in w.eos_plot.ax.get_lines()
             if str(a.get_label()).startswith("GOLD")]
assert eos_lines, "no GOLD artist on P-CR"
assert eos_lines[0].get_linestyle() == "None"
assert eos_lines[0].get_marker() == "o"
# auto 状态下上限应贴近数据最大 compression（图上还有 Al SESAME，comp≈4.5），
# 而不是旧的硬编码 5
comp_max = max((float(np.max(m.compression)) for m in (w.eos_plot._last_materials or {}).values()
                if m.compression is not None and len(m.compression)), default=1.0)
cx1 = w.eos_plot.ax.get_xlim()[1]
assert abs(cx1 - comp_max * 1.05) / comp_max < 0.2, (
    f"P-CR xlim {cx1} not data-fit (comp_max={comp_max:.3g})")
assert w.eos_plot._last_xlim is None
print(f"P-CR GOLD scatter + auto view (xlim {cx1:.3g} ~ comp_max {comp_max:.3g})  OK",
      flush=True)

# --- 6. generic tab (P-rho): GOLD scatter --------------------------------
w.plot_tabs.setCurrentIndex(2)
app.processEvents()
pr_lines = [a for a in w.p_rho_plot.ax.get_lines()
            if str(a.get_label()).startswith("GOLD")]
assert pr_lines and pr_lines[0].get_linestyle() == "None"
print("P-rho GOLD scatter  OK", flush=True)

# --- 7. reset-all keeps everything consistent ----------------------------
w._on_material_reset_all()
app.processEvents()
assert w._plot_settings["P-Up"]["xlim"] is None
print("reset-all OK", flush=True)

print("SMOKE OK", flush=True)
