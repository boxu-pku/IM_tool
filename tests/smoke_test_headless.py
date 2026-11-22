#!/usr/bin/env python3
"""Offscreen verification for the headless engine + CLI (AI 接入层):

1. HeadlessSession: load workflow → refresh（交点重算）→ results() 可 JSON
   序列化 → export 落盘 results.json / intersections.csv / PNG。
2. save_workflow → 新会话重载 round-trip。
3. find_intersection / add_release 经引擎可用。
4. 蒙特卡洛 offscreen 可跑（sigma_D>0 → up_err/p_err 写回）。
5. CLI 子进程：materials search / template / run（含非仓库 cwd）。
"""

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                              errors="replace", write_through=True)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REPO = str(PROJECT_ROOT)
WF = str(PROJECT_ROOT / "im_app" / "workflows" / "AC_shot384-L.json")

# --- 1. 引擎：load → refresh → results → export --------------------------
from im_app.api.headless import HeadlessSession  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="imt_headless_"))

s = HeadlessSession()
info = s.load_workflow(WF)
assert info["missing_materials"] == [], f"materials missing: {info}"
s.refresh()

res = s.results(workflow_path=WF)
json.dumps(res)  # 必须可序列化
assert res["materials"], "no materials loaded"
assert len(res["intersections"]) >= 2, f"intersections: {len(res['intersections'])}"
for ix in res["intersections"]:
    assert ix["up_km_s"] and ix["p_mbar"], f"ix not recomputed: {ix}"
print(f"engine load+refresh: {len(res['materials'])} mats, "
      f"{len(res['intersections'])} ix "
      f"(up={[round(i['up_km_s'], 3) for i in res['intersections']]})  OK", flush=True)

exports = s.export(str(tmp / "run1"), results=res)
rj = Path(exports["results_json"])
assert rj.exists() and rj.stat().st_size > 100
assert Path(exports["intersections_csv"]).exists()
assert exports["figures"], f"no figures exported: {exports}"
for f in exports["figures"]:
    assert (tmp / "run1" / f).stat().st_size > 5000, f"{f} suspiciously small"
print(f"engine export: {len(exports['figures'])} figures "
      f"({', '.join(exports['figures'])}), skipped={exports['skipped_empty']}  OK",
      flush=True)

# --- 2. save → 新会话重载 round-trip --------------------------------------
saved = str(tmp / "roundtrip.json")
s.save_workflow(saved)
s.close()

s2 = HeadlessSession()
s2.load_workflow(saved)
s2.refresh()
res2 = s2.results()
assert len(res2["intersections"]) == len(res["intersections"])
for a, b in zip(res["intersections"], res2["intersections"]):
    assert abs(a["up_km_s"] - b["up_km_s"]) < 1e-6, "round-trip ix drifted"
print("save → reload round-trip: intersections identical  OK", flush=True)

# --- 3. find_intersection / add_release ------------------------------------
rl_ids = [rl["id"] for rl in res2["rayleigh_lines"]]
mat_id = res2["materials"][0]["id"]
n_before = len(s2.w.hugoniot_plot.intersections)
s2.find_intersection(mat_id, rl_ids[1])  # 材料与第二条瑞利线的新曲线对
assert len(s2.w.hugoniot_plot.intersections) == n_before + 1, "find failed"
rid = s2.add_release(mat_id, 1.0)
assert rid, "add_release returned nothing"
kinds = [rc.get("kind") for rc in s2.w.hugoniot_plot.reflected_curves]
assert "release" in kinds, f"release not added: {kinds}"
print(f"engine find_intersection + add_release ({rid})  OK", flush=True)

# --- 4. 蒙特卡洛 offscreen -------------------------------------------------
s2.w.rayleigh_panel.get_all_rayleigh_lines()[rl_ids[0]].sigma_D = 0.3
s2.refresh()
res3 = s2.results()
with_err = [ix for ix in res3["intersections"]
            if ix["up_err_km_s"] is not None and ix["p_err_mbar"] is not None]
assert with_err, "MC did not write back errors (or QProgressDialog blocked)"
print(f"monte carlo offscreen: {len(with_err)} ix with errors  OK", flush=True)
s2.close()

# --- 5. CLI 子进程（含非仓库 cwd）-----------------------------------------
# 从非仓库 cwd 用绝对路径跑 run（PYTHONPATH 提供模块入口，验证 --lib
# 默认路径与 workflow 输出路径不依赖 cwd）
env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
           PYTHONIOENCODING="utf-8", PYTHONPATH=REPO)


def cli(*args, cwd=REPO, timeout=300):
    p = subprocess.run(
        [sys.executable, "-m", "im_app.cli", *args],
        capture_output=True, text=True, encoding="utf-8", cwd=cwd, env=env,
        timeout=timeout)
    return p.returncode, p.stdout, p.stderr


# --- 5b. stdout 守卫：MC 触发时 stdout 仍是纯 JSON ------------------------
wf = json.loads(Path(WF).read_text(encoding="utf-8"))
wf["rayleigh_lines"][0]["sigma_D"] = 0.3  # 触发 MC
sig_wf = tmp / "sigma.json"
sig_wf.write_text(json.dumps(wf), encoding="utf-8")
rc, out, err = cli("run", str(sig_wf), "--out", str(tmp / "run_mc"))
assert rc == 0, err
j = json.loads(out)  # MC 运行时 stdout 也必须能直接解析
assert j["ok"]
assert "MC DEBUG" not in out  # 调试打印已全部移除；stdout 永远纯 JSON
full = json.loads(Path(j["results_json"]).read_text(encoding="utf-8"))
assert any(ix["up_err_km_s"] is not None for ix in full["intersections"])
print("cli run with MC: stdout pure JSON, ix errors written  OK", flush=True)


rc, out, err = cli("materials", "search", "quartz")
assert rc == 0, f"search rc={rc}\n{err}"
j = json.loads(out)
assert any(m["id"] == "Quartz_Hamel2012" for m in j["materials"]), out[:400]
print(f"cli materials search quartz: {j['count']} hits  OK", flush=True)

rc, out, err = cli("materials", "show", "gold_p81_lasl", "--data")
assert rc == 0, f"show rc={rc}\n{err}"
j = json.loads(out)
assert j["n_rows"] >= 5 and j.get("rows"), out[:200]
print(f"cli materials show --data: {j['n_rows']} rows  OK", flush=True)

rc, out, err = cli("template", "impedance")
assert rc == 0, err
j = json.loads(out)
for key in ("version", "materials", "rayleigh_lines", "intersections",
            "reflected_curves", "plot_settings", "scatter_points"):
    assert key in j, f"template missing {key}"
print("cli template impedance: schema complete  OK", flush=True)

# 从非仓库 cwd 用绝对路径跑 run（验证 lib 默认路径解析）
rc, out, err = cli("run", WF, "--out", str(tmp / "run2"), cwd=str(tmp))
assert rc == 0, f"run rc={rc}\n{out}\n{err}"
j = json.loads(out)
assert j["ok"] and j["n_intersections"] >= 2 and j["figures"], out[:400]
assert Path(j["results_json"]).exists()
print(f"cli run (cwd={tmp}): {j['n_intersections']} ix, "
      f"{len(j['figures'])} figures  OK", flush=True)

print("SMOKE OK", flush=True)
