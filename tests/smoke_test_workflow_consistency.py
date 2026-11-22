#!/usr/bin/env python3
"""AI(headless) 重算 vs 历史手工分析的一致性回归。

对照集：im_app/workflows/*.json 里存的交点数值（用户在 GUI 手工分析时
保存的结果）。对每个 workflow 开一个全新 HeadlessSession（等价于 GUI
重新打开会话）load + refresh，逐交点按 id 比对 up / p；compression_ratio
只报告差异（历史值可能被手工微调过，如 AC 系列的 2.700000）。

另取代表性 workflow 走 CLI 子进程端到端（真 'AI 调用' 路径）再比对一次。
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

from im_app.api.headless import HeadlessSession  # noqa: E402

WF_DIR = PROJECT_ROOT / "im_app" / "workflows"
# 分档容差：
# - GUI 手工保存的 workflow（IM_tool 自己算的，15 位精度）：直接交点复现
#   ~1e-9，reverse-match 链上（ix_rev_* / 依赖 refl 的二级 ix）在 GUI 求解
#   与 refresh 重算两条数值路径间有 ~1e-6 的插值差异 → 收口 1e-5。
# - *_AI.json：外部 AI 工具独立计算的对照草稿（存储值仅 6 位小数），
#   与 IM_tool 引擎的交叉实现差异 ~2.5e-5 → 收口 1e-4（远低于实验精度）。
REL_TOL_GUI = 1e-5
REL_TOL_AI = 1e-4


def reldiff(a, b) -> float:
    return abs(a - b) / max(1e-12, abs(b))


# --- 1. 引擎级：全部 workflow --------------------------------------------
rows, n_bad = [], 0
for p in sorted(WF_DIR.glob("*.json")):
    wf = json.loads(p.read_text(encoding="utf-8"))
    stored = [ix for ix in wf.get("intersections", [])
              if ix.get("source_curve1_id") or ix.get("source_curve2_id")]
    if not stored:
        continue
    s = HeadlessSession()
    try:
        info = s.load_workflow(str(p))
        s.refresh()
        res = s.results()
        recomp = {ix["id"]: ix for ix in res["intersections"]}
        missing = info.get("missing_materials", [])
        tol = REL_TOL_AI if p.stem.endswith("_AI") else REL_TOL_GUI
        for ix in stored:
            r = recomp.get(ix["id"])
            if r is None:
                status = "ORPHANED" if not missing else "SKIP(missing mat)"
                if not missing:
                    n_bad += 1
                rows.append((p.name, ix["id"], status, None, None))
                continue
            d_up = reldiff(r["up_km_s"], ix["up"])
            d_p = reldiff(r["p_mbar"], ix["p"])
            ok = d_up <= tol and d_p <= tol
            if not ok:
                n_bad += 1
            cr_note = ""
            sc, rc = ix.get("compression_ratio"), r["compression_ratio"]
            if sc is not None and rc is not None and reldiff(rc, sc) > 1e-3:
                cr_note = f"  [cr {sc:.4f}->{rc:.4f}]"  # 报告即可（历史值可能手工调过）
            rows.append((p.name, ix["id"], "OK" if ok else "DIFF",
                         d_up, d_p, cr_note))
    finally:
        s.close()

n_ix = len(rows)
for name, ixid, status, d_up, d_p, *rest in rows:
    note = rest[0] if rest else ""
    if status == "OK":
        print(f"  {name:26s} {ixid:14s} OK    "
              f"(rel_up={d_up:.2e}, rel_p={d_p:.2e}){note}")
    else:
        print(f"  {name:26s} {ixid:14s} {status} {d_up} {d_p}{note}")
assert n_ix >= 30, f"unexpectedly few comparisons: {n_ix}"
print(f"engine recompute vs stored: {n_ix} ix, {n_bad} mismatches", flush=True)
assert n_bad == 0, f"{n_bad} intersections did not reproduce stored values"

# --- 2. CLI 端到端（真 AI 调用路径）---------------------------------------
env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
           PYTHONIOENCODING="utf-8", PYTHONPATH=str(PROJECT_ROOT))
tmp = Path(tempfile.mkdtemp(prefix="imt_consist_"))

for name in ("AC_shot390-R.json", "AC_shot384-L.json", "HMXshot128_AI.json"):
    p = WF_DIR / name
    out = tmp / name.replace(".json", "")
    proc = subprocess.run(
        [sys.executable, "-m", "im_app.cli", "run", str(p), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=600)
    assert proc.returncode == 0, f"{name} rc={proc.returncode}\n{proc.stderr[-2000:]}"
    summary = json.loads(proc.stdout)
    results = json.loads(Path(summary["results_json"]).read_text(encoding="utf-8"))
    got = {ix["id"]: ix for ix in results["intersections"]}
    stored = {ix["id"]: ix for ix in json.loads(p.read_text(encoding="utf-8"))["intersections"]}
    assert got.keys() >= stored.keys(), f"{name}: missing ids {stored.keys() - got.keys()}"
    for ixid, st in stored.items():
        tol = REL_TOL_AI if p.stem.endswith("_AI") else REL_TOL_GUI
        assert reldiff(got[ixid]["up_km_s"], st["up"]) <= tol, (name, ixid, "up")
        assert reldiff(got[ixid]["p_mbar"], st["p"]) <= tol, (name, ixid, "p")
    print(f"cli end-to-end {name}: {len(stored)} ix reproduced "
          f"(figures={len(summary['figures'])})", flush=True)

print("SMOKE OK", flush=True)
