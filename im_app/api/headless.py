"""Headless 引擎：offscreen 实例化 MainWindow，复用 GUI 同一条编排逻辑。

设计原则（docs/AI_GUIDE.md 有完整说明）：
- 阻抗匹配的编排逻辑（曲线依赖解析 / 自动重算交点 / release-reflect 语义 /
  蒙特卡洛触发 / workflow 序列化）大部分在 MainWindow 里，headless 直接驱动
  真实窗口对象，保证行为与 GUI 100% 同一条代码路径，永不漂移。
- 会话即 workflow JSON 文件：AI 生成/修改的会话 GUI 能打开，GUI 存的会话
  AI 能跑。
- 本模块导入前自动设置 QT_QPA_PLATFORM=offscreen；PyQt5 独占进程的约束
  照旧（CLI 每次调用独立进程，天然规避）。
"""

from __future__ import annotations

import os

# 必须在导入 PyQt5 之前设置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from datetime import datetime
from pathlib import Path

# 仓库根：im_app/api/headless.py → 上三级
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 9 个绘图标签页的内部键 → 导出文件名
_TAB_KEYS = ["P-Up", "P-CR", "P-rho", "Us-Up", "P-T",
             "rho-Up", "T-Up", "E-Up", "P-Us"]


def _f(x, nd=None):
    """numpy 标量 → 内置 float（JSON 可序列化）；None 原样返回。"""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if nd is not None else v


class HeadlessSession:
    """无头会话。用法：

        s = HeadlessSession()
        s.load_workflow("wf.json")     # 或 build 场景后手动操作
        s.refresh()                    # 自动重算交点 + MC（可选）
        results = s.results()          # dict，可直接 json.dump
        files = s.export("out_dir")    # results.json + 9 张图 + 交点 CSV
    """

    def __init__(self, lib_dir: str | None = None, workflows_dir: str | None = None):
        self.lib_dir = str(Path(lib_dir) if lib_dir else _REPO_ROOT / "im_app" / "standard_library")
        self.workflows_dir = str(Path(workflows_dir) if workflows_dir else _REPO_ROOT / "im_app" / "workflows")

        from PyQt5.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])

        from im_app.gui.main_window import MainWindow
        self.w = MainWindow(self.lib_dir, self.workflows_dir)

    # ------------------------------------------------------------------
    # 会话载入 / 持久化
    # ------------------------------------------------------------------
    def load_workflow(self, path: str, run_mc: bool = False) -> dict:
        """加载 workflow JSON。返回 {"missing_materials": [...]} 形式的告警信息。

        默认 run_mc=False：批处理流程由 refresh() 统一触发一次蒙特卡洛，
        避免 500 样本 MC 跑两遍。
        """
        wf = json.loads(Path(path).read_text(encoding="utf-8"))
        self.w._apply_workflow_dict(wf, run_mc=run_mc)
        missing = [m.get("id") for m in wf.get("materials", [])
                   if m.get("id") not in self.w.hugoniot_plot.materials]
        missing = [m for m in missing if m]
        self._warnings = [f"material not found in library: {m}" for m in missing]
        self._process_events()
        return {"missing_materials": missing}

    def save_workflow(self, path: str) -> str:
        """把当前会话存回 workflow JSON（与 GUI 保存格式完全一致）。"""
        self.w.save_workflow_to(str(path))
        return str(path)

    # ------------------------------------------------------------------
    # 分析操作（与 GUI 操作一一对应）
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """自动重算全部交点 + 反射线跟随 + 孤儿清理 + MC（与 GUI 自适应刷新同一路径）。"""
        self.w._auto_refresh_intersections()
        self._process_events()

    def find_intersection(self, curve1_id: str, curve2_id: str,
                          include_reflected: bool = False) -> None:
        """在两条曲线间找交点并加入会话（等价于 GUI 的 Find Intersection 按钮）。"""
        self.w._find_specific_intersection(curve1_id, curve2_id, include_reflected)
        self._process_events()

    def add_release(self, source_mat_id: str, up_value: float) -> str | None:
        """在指定 Hugoniot 的 Up 点添加 release 线，返回曲线 id。"""
        before = {rc["id"] for rc in self.w.hugoniot_plot.reflected_curves}
        self.w._on_add_release(source_mat_id, up_value)
        self._process_events()
        new = [rc for rc in self.w.hugoniot_plot.reflected_curves
               if rc["id"] not in before]
        return new[0]["id"] if new else None

    def curve_data(self, curve_id: str) -> dict:
        """按 id 取任意曲线数据（Hugoniot / Rayleigh / 反射或 release 线）。"""
        up, p, p_err = self.w._resolve_curve_data(curve_id)
        if up is None:
            raise KeyError(f"curve not found or not visible: {curve_id}")
        return {
            "id": curve_id,
            "n_points": int(len(up)),
            "up_km_s": [_f(v, 6) for v in up],
            "p_mbar": [_f(v, 6) for v in p],
            "p_err_mbar": ([_f(v, 6) for v in p_err]
                           if p_err is not None else None),
        }

    # ------------------------------------------------------------------
    # 结果收集 / 导出
    # ------------------------------------------------------------------
    def results(self, workflow_path: str | None = None) -> dict:
        """收集当前会话全部数值结果（JSON 可序列化）。"""
        w = self.w
        visible_rl = set(w.rayleigh_panel.get_visible_rayleigh_lines())

        materials = []
        for mid, mat in w.hugoniot_plot.materials.items():
            materials.append({
                "id": mid,
                "name": mat.name,
                "rho0_g_cm3": _f(getattr(mat, "rho0", None), 4),
                "n_points": int(len(mat.up)) if mat.up is not None else 0,
                "up_range_km_s": ([_f(mat.up.min(), 4), _f(mat.up.max(), 4)]
                                  if mat.up is not None and len(mat.up) else None),
                "p_range_mbar": ([_f(mat.p.min(), 4), _f(mat.p.max(), 4)]
                                 if mat.p is not None and len(mat.p) else None),
            })

        rayleigh_lines = []
        for rl_id, rl in w.rayleigh_panel.get_all_rayleigh_lines().items():
            rayleigh_lines.append({
                "id": rl_id,
                "material_id": rl.material_id,
                "D_km_s": _f(rl.D, 4),
                "rho0_g_cm3": _f(rl.rho0, 4),
                "sigma_D_km_s": _f(rl.sigma_D, 4),
                "sigma_rho0_g_cm3": _f(rl.sigma_rho0, 4),
                "visible": rl_id in visible_rl,
            })

        reflected_curves = []
        for rc in w.hugoniot_plot.reflected_curves:
            reflected_curves.append({
                "id": rc["id"],
                "source_id": rc.get("source_id"),
                "kind": rc.get("kind") or "reflected",
                "anchor_up_km_s": _f(rc.get("anchor_up"), 4),
                "center_up_km_s": _f(rc.get("center_up"), 4),
                "anchor_intersection_id": rc.get("anchor_intersection_id"),
                "source_ix_id": rc.get("source_ix_id"),
                "up_err_km_s": _f(rc.get("up_err"), 6),
                "p_err_mbar": _f(rc.get("p_err"), 6),
            })

        intersections = []
        for ix in w.hugoniot_plot.intersections:
            intersections.append({
                "id": ix.id,
                "curve1_id": ix.curve1_id,
                "curve2_id": ix.curve2_id,
                "source_curve1_id": getattr(ix, "source_curve1_id", None),
                "source_curve2_id": getattr(ix, "source_curve2_id", None),
                "up_km_s": _f(ix.up, 6),
                "p_mbar": _f(ix.p, 6),
                "compression_ratio": _f(getattr(ix, "compression_ratio", None), 4),
                "up_err_km_s": _f(getattr(ix, "up_err", None), 6),
                "p_err_mbar": _f(getattr(ix, "p_err", None), 6),
                "compression_err": _f(getattr(ix, "compression_err", None), 6),
                "rho_err_g_cm3": _f(getattr(ix, "rho_err", None), 6),
            })

        out = {
            "generated_at": datetime.now().isoformat(),
            "workflow": str(workflow_path) if workflow_path else None,
            "units": {
                "up": "km/s",
                "p": "Mbar",
                "rho0": "g/cm^3",
                "note": "内部压力单位一律 Mbar；换算 GPa 需 ×100",
            },
            "materials": materials,
            "rayleigh_lines": rayleigh_lines,
            "reflected_curves": reflected_curves,
            "intersections": intersections,
        }
        if getattr(self, "_warnings", None):
            out["warnings"] = self._warnings
        return out

    def export(self, out_dir: str, results: dict | None = None,
               dpi: int = 200) -> dict:
        """导出 results.json + 全部图 PNG + 交点表 CSV 到 out_dir。

        返回 {"results_json": path, "figures": [...], "skipped_empty": [...],
               "intersections_csv": path}
        """
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        if results is None:
            results = self.results()
        rj = out / "results.json"
        rj.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                      encoding="utf-8")

        # 交点表 CSV（AI 友好的平铺格式）
        import csv
        import io as _io
        csv_path = out / "intersections.csv"
        buf = _io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["id", "curve1", "curve2", "up_km_s", "p_mbar",
                         "compression_ratio", "up_err_km_s", "p_err_mbar",
                         "compression_err", "rho_err_g_cm3"])
        for ix in results["intersections"]:
            writer.writerow([
                "nan" if ix.get(k) is None else ix[k]
                for k in ("id", "curve1_id", "curve2_id")
            ] + [
                "nan" if ix.get(k) is None else f"{float(ix[k]):.6g}"
                for k in ("up_km_s", "p_mbar", "compression_ratio",
                          "up_err_km_s", "p_err_mbar", "compression_err",
                          "rho_err_g_cm3")
            ])
        csv_path.write_text(buf.getvalue(), encoding="utf-8")

        # 逐标签页导图：切过去（触发该页 refresh）再 savefig
        exported, skipped = [], []
        for idx in range(self.w.plot_tabs.count()):
            label = self.w.plot_tabs.tabText(idx)          # 如 "P-Up Diagram"
            key = label.replace(" Diagram", "")
            canvas = self.w.plot_tabs.widget(idx)
            if canvas is None:
                continue
            self.w.plot_tabs.setCurrentIndex(idx)
            self._process_events()
            fig = getattr(canvas, "figure", None)
            if fig is None:
                continue
            has_content = any(
                str(artist.get_label()) != "_nolegend_"
                for ax in fig.axes
                for artist in (ax.get_lines() + ax.collections)
            )
            if not has_content:
                skipped.append(key)
                continue
            fname = f"{key.lower().replace('-', '_')}.png"
            fig.savefig(out / fname, dpi=dpi, bbox_inches="tight")
            exported.append(fname)

        return {
            "results_json": str(rj),
            "intersections_csv": str(csv_path),
            "figures": exported,
            "skipped_empty": skipped,
        }

    # ------------------------------------------------------------------
    def _process_events(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

    def close(self):
        self.w.close()
