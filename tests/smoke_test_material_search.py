#!/usr/bin/env python3
"""Offscreen verification for the material-list search filter:

1. 全量条目 ≥ 200；检索框置空时全部可见。
2. "quartz" → 只显示命中项（id/名称/来源），Quartz_Hamel2012 可见。
3. 多关键词 AND："gold lasl" 收窄到 GOLD（LASL SHD）。
4. tag 检索："lasl-shd" 命中 LASL 系列。
5. 过滤是纯视图操作：被隐藏材料的勾选/加载状态保留。
6. Select All 尊重过滤：只勾选可见行。
7. refresh_library 后过滤自动重应用；清空关键词恢复全量。
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from im_app.gui.material_panel import MaterialPanel  # noqa: E402

panel = MaterialPanel(str(PROJECT_ROOT / "im_app" / "standard_library"))
panel.refresh_library()
lst = panel.material_list
SearchRole = MaterialPanel._SearchRole

total = lst.count()
assert total >= 200, f"library unexpectedly small: {total}"
assert not any(lst.isRowHidden(i) for i in range(total))
print(f"library loaded: {total} materials, all visible  OK", flush=True)


def visible_ids():
    return [lst.item(i).data(Qt.UserRole) for i in range(total)
            if not lst.isRowHidden(i)]


def visible_hays():
    return [lst.item(i).data(SearchRole) for i in range(total)
            if not lst.isRowHidden(i)]


# --- 1. quartz ---
panel.search_edit.setText("quartz")
vis = visible_ids()
assert 0 < len(vis) < total, f"quartz filter broken: {len(vis)}"
assert "Quartz_Hamel2012" in vis, f"Quartz_Hamel2012 missing: {vis}"
assert all("quartz" in h for h in visible_hays())
print(f"'quartz': {len(vis)} / {total} shown, includes Quartz_Hamel2012  OK", flush=True)

# --- 2. 多关键词 AND ---
panel.search_edit.setText("gold lasl")
vis = visible_ids()
assert "gold_p81_lasl" in vis, vis
assert all("gold" in h and "lasl" in h for h in visible_hays())
print(f"'gold lasl' (AND): {len(vis)} shown, includes gold_p81_lasl  OK", flush=True)

# --- 3. tag 检索 ---
panel.search_edit.setText("lasl-shd")
vis_hays = visible_hays()
assert len(vis_hays) >= 100, f"lasl-shd tag should hit the whole SHD import: {len(vis_hays)}"
assert all("lasl-shd" in h for h in vis_hays)
print(f"'lasl-shd' tag: {len(vis_hays)} shown  OK", flush=True)

# --- 4. 过滤不破坏勾选状态：勾 GOLD 后换过滤词使其隐藏，仍处于已加载 ---
panel.search_edit.setText("gold")
assert "gold_p81_lasl" in visible_ids()
panel.set_material_checked("gold_p81_lasl", True)
panel.search_edit.setText("quartz")  # GOLD 行被隐藏
assert "gold_p81_lasl" not in visible_ids()
assert "gold_p81_lasl" in panel.get_selected_materials()
panel.set_material_checked("gold_p81_lasl", False)  # 还原
print("hidden material keeps its loaded state while filtered  OK", flush=True)

# --- 5. Select All 尊重过滤 ---
panel.search_edit.setText("gold lasl")
n_gold = len(visible_ids())
panel._select_all()
checked_gold = [lst.item(i).data(Qt.UserRole) for i in range(total)
                if lst.item(i).checkState() == Qt.Checked]
assert len(checked_gold) == n_gold, f"select-all leaked past filter: {checked_gold}"
panel._deselect_all()
assert not [i for i in range(total) if lst.item(i).checkState() == Qt.Checked]
print(f"select-all respects filter ({n_gold} checked only)  OK", flush=True)

# --- 6. refresh_library 后过滤重应用；清空恢复全量 ---
panel.refresh_library()
app.processEvents()
assert 0 < len(visible_ids()) == n_gold, "filter not reapplied after refresh"
panel.search_edit.setText("")
app.processEvents()
assert len(visible_ids()) == total
assert not any(lst.isRowHidden(i) for i in range(total))
assert "materials available" in panel.info_label.text()
print("filter survives refresh_library; empty query restores full list  OK", flush=True)

print("SMOKE OK", flush=True)
