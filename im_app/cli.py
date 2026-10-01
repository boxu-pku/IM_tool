"""IM Tool CLI —— AI / 脚本无头接入入口。

用法（仓库根目录）：
    python -m im_app.cli materials search quartz
    python -m im_app.cli materials show gold_p81_lasl --data
    python -m im_app.cli template impedance
    python -m im_app.cli run im_app/workflows/AC_shot384-L.json --out runs/AC_shot384-L/

约定：所有输出均为 stdout 纯 JSON（UTF-8）；图片 / results.json / CSV 落到
--out 目录。完整说明见 docs/AI_GUIDE.md。
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


@contextlib.contextmanager
def _stdout_guard():
    """引擎执行期间把 stdout 重定向到 stderr。

    CLI 的契约是 stdout 只有纯 JSON；库代码若有任何 stray print，
    统一引到 stderr，避免污染 JSON 输出。
    """
    sys.stdout.flush()
    old, sys.stdout = sys.stdout, sys.stderr
    try:
        yield
    finally:
        sys.stdout.flush()
        sys.stdout = old


def _setup_stdout():
    """Windows 控制台默认 GBK，强制 stdout/stderr 为 UTF-8。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        try:
            if not isinstance(stream, io.TextIOWrapper) or stream.encoding.lower().replace("-", "") != "utf8":
                setattr(sys, name, io.TextIOWrapper(
                    stream.buffer, encoding="utf-8", errors="replace", line_buffering=True))
        except Exception:
            pass


def _print_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _default_lib() -> str:
    return str(_REPO_ROOT / "im_app" / "standard_library")


# ----------------------------------------------------------------------
# 查询命令（纯数据层，不启动 Qt）
# ----------------------------------------------------------------------
def _load_material_index(lib_dir: str) -> list[dict]:
    from im_app.core.data_loader import list_available_materials
    return list_available_materials(lib_dir)


def cmd_materials(args) -> int:
    lib = args.lib
    mats = _load_material_index(lib)

    if args.materials_cmd == "list":
        out = {
            "library": lib,
            "count": len(mats),
            "materials": mats[:args.limit],
            "truncated": len(mats) > args.limit,
        }
    elif args.materials_cmd == "search":
        kw = args.keyword.lower()
        hits = [m for m in mats
                if kw in str(m.get("id", "")).lower()
                or kw in str(m.get("name", "")).lower()
                or any(kw in str(t).lower() for t in (m.get("tags") or []))]
        out = {"keyword": args.keyword, "count": len(hits), "materials": hits}
    else:  # show
        from im_app.core.data_loader import load_material_by_id
        idx = next((m for m in mats if m.get("id") == args.material_id), None)
        if idx is None:
            _print_json({"error": f"material id not found: {args.material_id}",
                         "hint": "use 'imt materials search <keyword>' to find ids"})
            return 2
        df, meta = load_material_by_id(lib, args.material_id)
        out = {"material": idx}
        if df is not None:
            out["columns"] = [str(c) for c in df.columns]
            out["n_rows"] = int(len(df))
            if args.data:
                out["rows"] = [
                    [None if (v is None or v != v) else float(v) if hasattr(v, "__float__") else str(v)
                     for v in row]
                    for row in df.itertuples(index=False, name=None)
                ]
    _print_json(out)
    return 0


def cmd_curves(args) -> int:
    from im_app.api.headless import HeadlessSession
    s = HeadlessSession(lib_dir=args.lib)
    try:
        with _stdout_guard():
            info = s.load_workflow(args.workflow)
            err = None
            try:
                data = s.curve_data(args.curve_id)
            except KeyError as e:
                err = str(e)
        if err is not None:
            _print_json({"error": err, "load_warnings": info})
            return 2
        if args.max_points and data["n_points"] > args.max_points:
            step = data["n_points"] // args.max_points + 1
            for k in ("up_km_s", "p_mbar"):
                data[k] = data[k][::step]
            if data.get("p_err_mbar") is not None:
                data["p_err_mbar"] = data["p_err_mbar"][::step]
            data["n_points"] = len(data["up_km_s"])
            data["downsampled"] = True
        _print_json(data)
        return 0
    finally:
        s.close()


# ----------------------------------------------------------------------
# 模板
# ----------------------------------------------------------------------
def impedance_template() -> dict:
    """两层阻抗匹配（标准件 + 样品）workflow 模板。

    占位符：MATERIAL_STANDARD / MATERIAL_SAMPLE 换成 `imt materials search`
    查到的库内 id；D / rho0 / sigma 换成实测值。intersections 里的 up/p 是
    占位（0），`imt run` 会按 source_curve*_id 全部重算，不要删 source 字段。
    """
    return {
        "version": "1.0",
        "created": "<run 时自动生成>",
        "materials": [
            {"id": "MATERIAL_STANDARD", "visible": True},
            {"id": "MATERIAL_SAMPLE", "visible": True},
        ],
        "rayleigh_lines": [
            {"id": "rl_1", "material_id": "MATERIAL_STANDARD",
             "D": 8.0, "rho0": 2.7, "sigma_D": 0.05, "sigma_rho0": 0.0},
            {"id": "rl_2", "material_id": "MATERIAL_SAMPLE",
             "D": 9.0, "rho0": 3.5, "sigma_D": 0.05, "sigma_rho0": 0.0},
        ],
        "intersections": [
            {"id": "ix_specific_0",
             "curve1_id": "MATERIAL_STANDARD", "curve2_id": "Rayleigh MATERIAL_STANDARD",
             "up": 0, "p": 0, "type": "custom", "material_id": "MATERIAL_STANDARD",
             "compression_ratio": None,
             "source_curve1_id": "MATERIAL_STANDARD", "source_curve2_id": "rl_1",
             "ignore_first_at_creation": True},
            {"id": "ix_specific_1",
             "curve1_id": "Rayleigh MATERIAL_SAMPLE", "curve2_id": "Reflected MATERIAL_STANDARD",
             "up": 0, "p": 0, "type": "custom", "material_id": None,
             "compression_ratio": None,
             "source_curve1_id": "rl_2", "source_curve2_id": "refl_1",
             "ignore_first_at_creation": True},
        ],
        "reflected_curves": [
            {"id": "refl_1", "source_id": "MATERIAL_STANDARD", "center_up": 0,
             "anchor_intersection_id": "ix_specific_0", "source_ix_id": None,
             "kind": None, "anchor_up": None},
        ],
        "plot_settings": {},
        "scatter_points": [],
    }


def cmd_template(args) -> int:
    from datetime import datetime
    templates = {"impedance": impedance_template}
    tpl = templates[args.name]()
    if args.out:
        tpl = dict(tpl)
        tpl["created"] = datetime.now().isoformat()
        Path(args.out).write_text(
            json.dumps(tpl, ensure_ascii=False, indent=4), encoding="utf-8")
        _print_json({"ok": True, "written": str(Path(args.out).resolve())})
    else:
        _print_json(tpl)
    return 0


# ----------------------------------------------------------------------
# 批处理 run
# ----------------------------------------------------------------------
def cmd_run(args) -> int:
    from im_app.api.headless import HeadlessSession
    s = HeadlessSession(lib_dir=args.lib)
    try:
        with _stdout_guard():
            load_info = s.load_workflow(args.workflow)
            if not args.no_refresh:
                s.refresh()
            if args.find:
                for pair in args.find:
                    c1, c2 = pair.split(",", 1)
                    s.find_intersection(c1.strip(), c2.strip())
            results = s.results(workflow_path=args.workflow)
            results["load_warnings"] = load_info
            exports = s.export(args.out, results=results, dpi=args.dpi)
        _print_json({
            "ok": True,
            "workflow": str(Path(args.workflow).resolve()),
            "out_dir": str(Path(args.out).resolve()),
            "n_intersections": len(results["intersections"]),
            "n_materials": len(results["materials"]),
            "warnings": results.get("warnings", []) + [
                f"material not found: {m}" for m in load_info.get("missing_materials", [])],
            **exports,
        })
        return 0
    finally:
        s.close()


# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="imt",
        description="IM Tool 无头接入 CLI（AI / 脚本用），输出均为 JSON。")
    p.add_argument("--lib", default=_default_lib(),
                   help="标准材料库路径（默认仓库内 im_app/standard_library）")
    sub = p.add_subparsers(dest="cmd", required=True)

    mp = sub.add_parser("materials", help="查询标准材料库")
    mp.add_argument("--limit", type=int, default=500)
    msub = mp.add_subparsers(dest="materials_cmd", required=True)
    msub.add_parser("list")
    sp = msub.add_parser("search")
    sp.add_argument("keyword")
    shp = msub.add_parser("show")
    shp.add_argument("material_id")
    shp.add_argument("--data", action="store_true", help="附带全部数据行")

    cp = sub.add_parser("curves", help="查看会话中的曲线数据")
    cp.add_argument("curve_id")
    cp.add_argument("--workflow", "-w", required=True, help="会话 workflow JSON")
    cp.add_argument("--max-points", type=int, default=0, help="降采样输出")

    tp = sub.add_parser("template", help="生成 workflow 模板")
    tp.add_argument("name", choices=["impedance"])
    tp.add_argument("--out", help="写入文件而不是打印")

    rp = sub.add_parser("run", help="执行 workflow：重算 + MC + 导出")
    rp.add_argument("workflow", help="workflow JSON 路径")
    rp.add_argument("--out", "-o", required=True, help="输出目录")
    rp.add_argument("--no-refresh", action="store_true",
                    help="跳过自动重算（按 workflow 里存的数值输出）")
    rp.add_argument("--find", action="append", default=[],
                    metavar="CURVE1,CURVE2",
                    help="运行中额外找一对交点（可重复）")
    rp.add_argument("--dpi", type=int, default=200)

    return p


def main(argv=None) -> int:
    _setup_stdout()
    args = build_parser().parse_args(argv)
    handlers = {"materials": cmd_materials, "curves": cmd_curves,
                "template": cmd_template, "run": cmd_run}
    try:
        return handlers[args.cmd](args)
    except FileNotFoundError as e:
        _print_json({"error": f"file not found: {e}"})
        return 2
    except json.JSONDecodeError as e:
        _print_json({"error": f"invalid workflow JSON: {e}"})
        return 2
    except Exception as e:  # noqa: BLE001 —— CLI 顶层兜底，错误走 JSON 输出
        _print_json({"error": f"{type(e).__name__}: {e}"})
        return 1


if __name__ == "__main__":
    sys.exit(main())
