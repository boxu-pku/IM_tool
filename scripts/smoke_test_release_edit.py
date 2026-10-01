#!/usr/bin/env python3
"""Offscreen verification for Release-edit + GUI legend size:

1. Double-click a "Release @ Up" entry (via panel handler with the dialog
   mocked) emits release_edited and MainWindow recomputes the mirror curve,
   syncs the list text / dedup keys, and auto-recomputes dependent
   intersections (impedance matching results).
2. Removing a release entry frees its dedup key, so re-adding the same
   (source, Up) is not silently swallowed (regression for the True-valued
   dedup-key bug).
3. GUI plots draw their legend at GUI_LEGEND_FONTSIZE (=18), while the
   paper-export constant LEGEND_FONTSIZE stays 14.
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

import im_app.gui.intersection_panel as ipmod  # noqa: E402
from im_app.core.plot_style import LEGEND_FONTSIZE, GUI_LEGEND_FONTSIZE  # noqa: E402
from im_app.gui.main_window import MainWindow  # noqa: E402

w = MainWindow("im_app/standard_library", "workflows")
print("MainWindow constructed", flush=True)

# --- setup: GOLD visible + one Rayleigh line -----------------------------
lst = w.material_panel.material_list
gold = next((lst.item(i) for i in range(lst.count())
             if "GOLD" in lst.item(i).text().upper()), None)
assert gold is not None, "GOLD item not found"
gold.setCheckState(Qt.Checked)
app.processEvents()

mat_id = next(iter(w.hugoniot_plot.materials))
print(f"source material: {mat_id}", flush=True)

w.rayleigh_panel.custom_name_edit.setEditText("Al standard")
w.rayleigh_panel.D_spin.setValue(6.0)
w.rayleigh_panel.rho0_spin.setValue(2.7)
w.rayleigh_panel._add_line()
rl_id = next(iter(w.rayleigh_panel.get_all_rayleigh_lines()))
app.processEvents()

# --- 1. add release @ Up=2.0 ---------------------------------------------
w._on_add_release(mat_id, 2.0)
app.processEvents()
rcs = [r for r in w.hugoniot_plot.reflected_curves if r.get("kind") == "release"]
assert len(rcs) == 1, f"expected 1 release curve, got {len(rcs)}"
rc = rcs[0]
refl_id = rc["id"]
assert rc["anchor_up"] == 2.0
assert w.intersection_panel.refl_list.count() == 1
key2 = f"release_{mat_id}_2.0000"
assert w.intersection_panel._reflected_entries.get(key2) == refl_id, (
    "dedup key not bound to refl_id after add")
print("Add Release @2.0 + dedup key bound  OK", flush=True)

# dependent intersection: release x rayleigh
w._find_specific_intersection(refl_id, rl_id, False)
app.processEvents()
ix_list = [x for x in w.hugoniot_plot.intersections
           if refl_id in (x.source_curve1_id, x.source_curve2_id)]
assert ix_list, "no intersection depends on the release curve"
ix = ix_list[0]
old_up_ix, old_p_ix = ix.up, ix.p
old_rc_mid_up = float(rc["up"][len(rc["up"]) // 2])
print(f"dependent ix {ix.id}: Up={old_up_ix:.4f} P={old_p_ix:.4f}", flush=True)

# --- 2. edit anchor 2.0 -> 3.0 via MainWindow handler ---------------------
w._on_edit_release(refl_id, 3.0)
app.processEvents()
assert rc["anchor_up"] == 3.0
assert abs(float(rc["up"][len(rc["up"]) // 2]) - old_rc_mid_up) > 1e-6, (
    "mirror curve unchanged")
assert w.intersection_panel._reflected_entries.get(f"release_{mat_id}_3.0000") == refl_id
assert key2 not in w.intersection_panel._reflected_entries, "old dedup key leaked"
assert abs(ix.up - old_up_ix) > 1e-6 or abs(ix.p - old_p_ix) > 1e-6, (
    "dependent intersection did not follow the new anchor")
texts = [w.intersection_panel.refl_list.item(i).text()
         for i in range(w.intersection_panel.refl_list.count())]
assert any("@ Up=3.000" in t for t in texts), f"refl_list text not synced: {texts}"
row_up = None
for row in range(w.intersection_panel.ix_table.rowCount()):
    if w.intersection_panel.ix_table.item(row, 0).text() == ix.id:
        row_up = w.intersection_panel.ix_table.item(row, 3).text()
assert row_up is not None and abs(float(row_up) - ix.up) < 5e-4, (
    f"ix table not refreshed: {row_up} vs {ix.up}")
print(f"edit 2.0->3.0: mirror moved, ix -> ({ix.up:.4f}, {ix.p:.4f}), "
      f"table/list synced  OK", flush=True)

# --- 3. double-click handler (dialog mocked) emits and updates ------------
orig_dlg = ipmod.ReleaseEditDialog


class FakeDlg:
    def __init__(self, source_name, up_value, parent=None):
        self._up = up_value + 1.0  # 3.0 -> 4.0

    def exec_(self):
        return ipmod.QDialog.Accepted

    def up_value(self):
        return self._up


ipmod.ReleaseEditDialog = FakeDlg
try:
    w.intersection_panel._on_refl_item_double_clicked(
        w.intersection_panel.refl_list.item(0))
finally:
    ipmod.ReleaseEditDialog = orig_dlg
app.processEvents()
assert rc["anchor_up"] == 4.0, f"double-click edit failed: {rc['anchor_up']}"
print("double-click edit 3.0->4.0 via panel handler  OK", flush=True)

# unknown / non-release ids are ignored silently
bogus = ipmod.QListWidgetItem("Reflected nothing @ center_up=1.000")
bogus.setData(Qt.UserRole, "refl_nope")
w.intersection_panel.refl_list.addItem(bogus)
w.intersection_panel._on_refl_item_double_clicked(bogus)
w.intersection_panel.refl_list.takeItem(w.intersection_panel.refl_list.row(bogus))
print("non-release double-click ignored  OK", flush=True)

# --- 4. remove frees dedup key; re-add same Up not swallowed --------------
w.intersection_panel.refl_list.setCurrentItem(
    w.intersection_panel.refl_list.item(0))
w.intersection_panel._on_remove_reflection()
app.processEvents()
assert not [r for r in w.hugoniot_plot.reflected_curves if r.get("id") == refl_id]
assert f"release_{mat_id}_4.0000" not in w.intersection_panel._reflected_entries, (
    "dedup key not freed on remove")
idx = w.intersection_panel.reflect_curve_combo.findData(mat_id)
assert idx >= 0, "reflect_curve_combo has no material entries"
w.intersection_panel.reflect_curve_combo.setCurrentIndex(idx)
w.intersection_panel.release_up_spin.setValue(4.0)
w.intersection_panel._on_release_clicked()
app.processEvents()
rcs = [r for r in w.hugoniot_plot.reflected_curves if r.get("kind") == "release"]
assert len(rcs) == 1, f"re-add after remove was swallowed: {len(rcs)} release curves"
assert w.intersection_panel.refl_list.count() == 1
print("remove frees dedup key, re-add @4.0 works  OK", flush=True)

# --- 5. GUI legend at 18pt, paper constant stays 14 ------------------------
assert GUI_LEGEND_FONTSIZE == 18 and LEGEND_FONTSIZE == 14
lg = w.hugoniot_plot.ax.get_legend()
assert lg is not None, "no legend drawn"
sizes = {t.get_fontsize() for t in lg.get_texts()}
assert sizes and abs(next(iter(sizes)) - GUI_LEGEND_FONTSIZE) < 1e-6, (
    f"legend fontsize {sizes} != {GUI_LEGEND_FONTSIZE}")
print(f"GUI legend fontsize = {next(iter(sizes)):.0f} (paper export keeps "
      f"{LEGEND_FONTSIZE})  OK", flush=True)

print("SMOKE OK", flush=True)
