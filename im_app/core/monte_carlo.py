"""
Monte Carlo error propagation for impedance matching analysis.

Replaces the analytic linear-approximation error propagation with a
sampling-based approach that correctly handles multi-level chains:

    1. Sample fit parameters of uncertain materials (Celliers Al, Hamel Quartz)
    2. For each sample, run the full deterministic impedance matching chain
    3. Aggregate statistics (mean, std) from the ensemble

Usage:
    from im_app.core.monte_carlo import MonteCarloEngine, MonteCarloResult

    engine = MonteCarloEngine()
    result = engine.run(
        materials=..., intersections=...,
        reflected_curves=..., rayleigh_lines=...,
        n_samples=500,
    )
    # result.intersection_stats[ix_id].up_std  → σ_up
    # result.reflected_stats[rc_id].p_err      → array of σ_P per point
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from im_app.core.physics import (
    MaterialData,
    RayleighLine,
    Intersection,
    find_intersections,
    reflect_hugoniot,
    reverse_impedance_match,
    rayleigh_line,
)
from scipy.interpolate import interp1d


# ---------------------------------------------------------------------------
# 辅助：从 fit_params 生成随机 Hugoniot 曲线
# ---------------------------------------------------------------------------

def generate_random_hugoniot(
    mat: MaterialData,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """
    根据 MaterialData.fit_params 生成一条随机 Hugoniot 曲线。

    只扰动 P（压强）值，up 网格保持原材料不变。

    Parameters
    ----------
    mat : MaterialData
        必须包含 fit_params。
    rng : np.random.Generator
        NumPy 随机数生成器。

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (up, p) — 扰动后的曲线。
    """
    fp = mat.fit_params
    if fp is None:
        # 无 fit_params → 返回原始数据
        return mat.up.copy(), mat.p.copy()

    model = fp.get("model", "")
    up = mat.up
    rho0 = mat.rho0

    if model == "linear":
        # Us = a0 + a1*(up - beta)
        a0_mean = fp["a0"]
        a1_mean = fp["a1"]
        beta = fp["beta"]
        sigma_a0 = fp.get("sigma_a0", 0.0)
        sigma_a1 = fp.get("sigma_a1", 0.0)

        a0_s = rng.normal(a0_mean, max(sigma_a0, 1e-10))
        a1_s = rng.normal(a1_mean, max(sigma_a1, 1e-10))

        Us = a0_s + a1_s * (up - beta)
        p = rho0 * up * Us * 0.01

    elif model == "piecewise_quadratic":
        # Us = a + b*Up + c*Up^2 (Up < break_up)
        # Us = (a - c*break_up^2) + b*Up + 2c*break_up*Up (Up >= break_up)
        a_mean = fp["a"]
        b_mean = fp["b"]
        c_mean = fp["c"]
        break_up = fp.get("break_up", float("inf"))
        sigma_a = fp.get("sigma_a", 0.0)
        sigma_b = fp.get("sigma_b", 0.0)
        sigma_c = fp.get("sigma_c", 0.0)

        a_s = rng.normal(a_mean, max(sigma_a, 1e-10))
        b_s = rng.normal(b_mean, max(sigma_b, 1e-10))
        c_s = rng.normal(c_mean, max(sigma_c, 1e-10))

        mask_lo = up < break_up
        Us = np.empty_like(up)
        Us[mask_lo] = a_s + b_s * up[mask_lo] + c_s * up[mask_lo] ** 2
        mask_hi = ~mask_lo
        Us[mask_hi] = (a_s - c_s * break_up ** 2) + b_s * up[mask_hi] + 2.0 * c_s * break_up * up[mask_hi]

        p = rho0 * up * Us * 0.01

    else:
        # 未知模型 → 返回原始数据
        return mat.up.copy(), mat.p.copy()

    return up.copy(), p


# ---------------------------------------------------------------------------
# 场景曲线解析（镜像 main_window._resolve_curve_data 的逻辑）
# ---------------------------------------------------------------------------

def _resolve_curve_in_scene(
    curve_id: str,
    perturbed_materials: dict[str, tuple[np.ndarray, np.ndarray]],
    original_materials: dict[str, MaterialData],
    rayleigh_lines: dict[str, RayleighLine],
    reflected_curves: list[dict],
    per_sample_reflected: dict[str, tuple[np.ndarray, np.ndarray]],
    perturbed_rayleigh: dict[str, tuple[np.ndarray, np.ndarray]] | None = None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """
    在"场景"中解析一条曲线 ID → (up, p)。

    查找顺序（与 main_window._resolve_curve_data 一致）：
      1. perturbed_materials（本轮已扰动的材料）
      2. original_materials（未被扰动的材料）
      3. perturbed_rayleigh（本轮扰动的 Rayleigh 线）
      4. rayleigh_lines（Rayleigh 线原始曲线）
      5. per_sample_reflected（本轮已计算的反射曲线）
      6. reflected_curves 配置中的原始曲线（作为回退）
    """
    if curve_id is None:
        return None, None

    # 1) 本轮扰动后的材料
    if curve_id in perturbed_materials:
        return perturbed_materials[curve_id]

    # 2) 原始材料（未被扰动）
    if curve_id in original_materials:
        mat = original_materials[curve_id]
        return mat.up, mat.p

    # 3) 本轮扰动的 Rayleigh 线
    if perturbed_rayleigh and curve_id in perturbed_rayleigh:
        return perturbed_rayleigh[curve_id]

    # 4) 原始 Rayleigh 线
    if curve_id in rayleigh_lines:
        rl = rayleigh_lines[curve_id]
        return rl.up, rl.p

    # 5) 本轮已计算的反射曲线
    if curve_id in per_sample_reflected:
        return per_sample_reflected[curve_id]

    # 6) 反射曲线原始存储（回退）
    for rc in reflected_curves:
        if rc["id"] == curve_id:
            return rc["up"], rc["p"]

    return None, None


# ---------------------------------------------------------------------------
# 数据容器
# ---------------------------------------------------------------------------

@dataclass
class IntersectionStats:
    """单个交点的 MC 统计结果。"""
    up_mean: float = 0.0
    up_std: float = 0.0
    p_mean: float = 0.0
    p_std: float = 0.0
    n_valid: int = 0


@dataclass
class ReflectedStats:
    """单条反射曲线的 MC 统计结果。"""
    up_err: np.ndarray | None = None   # 常数数组：2 * σ_center
    p_err: np.ndarray | None = None    # 逐点的 P 标准差


@dataclass
class MonteCarloResult:
    """MC 运行的完整结果。"""
    intersection_stats: dict[str, IntersectionStats] = field(default_factory=dict)
    reflected_stats: dict[str, ReflectedStats] = field(default_factory=dict)
    n_total: int = 0


# ---------------------------------------------------------------------------
# 判断类型辅助
# ---------------------------------------------------------------------------

def _depends_on_reflected(curve_id: str) -> bool:
    """检查曲线 ID 是否以 'refl_' 开头。"""
    return bool(curve_id) and curve_id.startswith("refl_")


def _scene_has_error_sources(
    materials: dict[str, MaterialData],
    rayleigh_lines: dict[str, RayleighLine] | None = None,
) -> bool:
    """检查场景中是否有误差源（材料 fit_params 或 Rayleigh sigma）。"""
    for mat in materials.values():
        if mat.fit_params is not None:
            return True
    if rayleigh_lines:
        for rl in rayleigh_lines.values():
            if (getattr(rl, 'sigma_D', 0.0) or 0.0) > 0 or (getattr(rl, 'sigma_rho0', 0.0) or 0.0) > 0:
                return True
    return False


# ---------------------------------------------------------------------------
# 蒙特卡洛引擎
# ---------------------------------------------------------------------------

class MonteCarloEngine:
    """
    蒙特卡洛误差传播引擎。

    用法：
        engine = MonteCarloEngine()
        result = engine.run(
            materials=..., intersections=...,
            reflected_curves=..., rayleigh_lines=...,
        )
    """

    def __init__(self):
        self._rng = np.random.default_rng()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def run(
        self,
        materials: dict[str, MaterialData],
        intersections: list[Intersection],
        reflected_curves: list[dict],
        rayleigh_lines: dict[str, RayleighLine],
        n_samples: int = 500,
        progress_callback: Callable[[int], bool] | None = None,
    ) -> MonteCarloResult:
        """
        运行蒙特卡洛模拟。

        Parameters
        ----------
        materials : dict[str, MaterialData]
            场景中所有材料（含误差源）。
        intersections : list[Intersection]
            需要在 MC 中追踪的所有交点。
        reflected_curves : list[dict]
            场景中所有反射曲线配置。
        rayleigh_lines : dict[str, RayleighLine]
            场景中所有 Rayleigh 线。
        n_samples : int
            抽样次数（默认 500）。
        progress_callback : callable or None
            进度回调，签名为 callback(current_step) -> bool。
            返回 False 表示取消。

        Returns
        -------
        MonteCarloResult
            MC 统计结果。
        """
        if not _scene_has_error_sources(materials, rayleigh_lines):
            # 无误差源 → 返回空结果
            print("[MC DEBUG] engine: _scene_has_error_sources returned False")
            return MonteCarloResult(n_total=0)

        print(f"[MC DEBUG] engine: starting {n_samples} samples, "
              f"{len(materials)} materials, {len(rayleigh_lines)} rayleigh lines, "
              f"{len(intersections)} intersections, {len(reflected_curves)} reflected curves")

        # 打印 Rayleigh 线的不确定度状态
        for rl_id, rl in rayleigh_lines.items():
            sd = getattr(rl, 'sigma_D', 0.0) or 0.0
            sr = getattr(rl, 'sigma_rho0', 0.0) or 0.0
            if sd > 0 or sr > 0:
                print(f"[MC DEBUG]   Rayleigh {rl_id}: sigma_D={sd}, sigma_rho0={sr}")

        # 预分类：找出哪些交点/反射曲线依赖反射线
        # 不依赖反射线的交点（Pass 1）
        pass1_ix = [ix for ix in intersections if not _depends_on_reflected(ix.source_curve1_id)
                     and not _depends_on_reflected(ix.source_curve2_id)]
        # 反射曲线（Pass 2）
        # 依赖反射线的交点（Pass 3）
        pass3_ix = [ix for ix in intersections if _depends_on_reflected(ix.source_curve1_id)
                     or _depends_on_reflected(ix.source_curve2_id)]

        print(f"[MC DEBUG] Classification: {len(pass1_ix)} pass1, {len(pass3_ix)} pass3")
        for ix in pass1_ix:
            print(f"[MC DEBUG]   Pass1 {ix.id}: src1={ix.source_curve1_id}, src2={ix.source_curve2_id}")
        for ix in pass3_ix:
            print(f"[MC DEBUG]   Pass3 {ix.id}: src1={ix.source_curve1_id}, src2={ix.source_curve2_id}")

        # 找出有 fit_params 的误差源材料 ID
        error_source_ids = {
            mid for mid, mat in materials.items()
            if mat.fit_params is not None
        }

        # 准备存储每轮结果
        # ix_samples[ix_id] = list of (up, p)
        ix_samples: dict[str, list[tuple[float, float]]] = {
            ix.id: [] for ix in intersections
        }
        # rc_p_samples[rc_id] = list of p_arrays
        rc_p_samples: dict[str, list[np.ndarray]] = {
            rc["id"]: [] for rc in reflected_curves
        }
        # rc_center_samples[rc_id] = list of center_up values
        rc_center_samples: dict[str, list[float]] = {
            rc["id"]: [] for rc in reflected_curves
        }

        for i in range(n_samples):
            if progress_callback is not None:
                try:
                    cancel = progress_callback(i)
                    if cancel:
                        break
                except Exception:
                    pass

            # ---- 第 1 步：生成扰动后的材料曲线 ----
            perturbed_materials: dict[str, tuple[np.ndarray, np.ndarray]] = {}
            for mid in error_source_ids:
                mat = materials[mid]
                try:
                    up_p, p_p = generate_random_hugoniot(mat, self._rng)
                    perturbed_materials[mid] = (up_p, p_p)
                except Exception:
                    # 生成失败 → 使用原始曲线
                    perturbed_materials[mid] = (mat.up.copy(), mat.p.copy())

            # ---- 第 1b 步：生成扰动后的 Rayleigh 线（若有 sigma） ----
            perturbed_rayleigh: dict[str, tuple[np.ndarray, np.ndarray]] = {}
            for rl_id, rl in rayleigh_lines.items():
                sigma_D = getattr(rl, "sigma_D", 0.0) or 0.0
                sigma_rho0 = getattr(rl, "sigma_rho0", 0.0) or 0.0
                if sigma_D <= 0 and sigma_rho0 <= 0:
                    continue
                if i == 0:
                    print(f"[MC DEBUG] Rayleigh {rl_id}: sigma_D={sigma_D}, sigma_rho0={sigma_rho0}")
                D_s = self._rng.normal(rl.D, max(sigma_D, 1e-10))
                rho0_s = self._rng.normal(rl.rho0, max(sigma_rho0, 1e-10))
                if D_s <= 0 or rho0_s <= 0:
                    D_s = rl.D
                    rho0_s = rl.rho0
                p_s = rayleigh_line(rl.up, rho0_s, D_s)
                perturbed_rayleigh[rl_id] = (rl.up.copy(), p_s)

            # ---- 第 2 步（Pass 1）：不依赖反射线的交点 ----
            sample_ix_results: dict[str, tuple[float, float] | None] = {}
            for ix in pass1_ix:
                try:
                    up1, p1 = _resolve_curve_in_scene(
                        ix.source_curve1_id, perturbed_materials, materials,
                        rayleigh_lines, reflected_curves, {},
                        perturbed_rayleigh=perturbed_rayleigh,
                    )
                    up2, p2 = _resolve_curve_in_scene(
                        ix.source_curve2_id, perturbed_materials, materials,
                        rayleigh_lines, reflected_curves, {},
                        perturbed_rayleigh=perturbed_rayleigh,
                    )
                    if up1 is None or up2 is None:
                        if i == 0:
                            print(f"[MC DEBUG]   sample 0, {ix.id}: up1={up1 is not None}, up2={up2 is not None}")
                        sample_ix_results[ix.id] = None
                        continue

                    ints = find_intersections(
                        up1, p1, up2, p2,
                        ignore_first=ix.ignore_first_at_creation,
                    )
                    if len(ints) == 0:
                        if i == 0:
                            print(f"[MC DEBUG]   sample 0, {ix.id}: find_intersections returned empty (up1 range=[{up1[0]:.2f},{up1[-1]:.2f}], up2 range=[{up2[0]:.2f},{up2[-1]:.2f}])")
                        sample_ix_results[ix.id] = None
                        continue

                    up_val = float(ints[0])
                    # 使用 curve1 插值取 p
                    sort_idx = np.argsort(up1)
                    interp = interp1d(
                        up1[sort_idx], p1[sort_idx],
                        bounds_error=False, fill_value="extrapolate",
                    )
                    p_val = float(interp(up_val))
                    sample_ix_results[ix.id] = (up_val, p_val)
                except Exception as e:
                    if i == 0:
                        import traceback
                        print("[MC DEBUG] Pass 1 error for %s (sample 0): %s" % (ix.id, e))
                        traceback.print_exc()
                    sample_ix_results[ix.id] = None

            # ---- 第 3 步（Pass 2）：反射曲线 ----
            sample_reflected: dict[str, tuple[np.ndarray, np.ndarray]] = {}
            for rc in reflected_curves:
                try:
                    source_id = rc["source_id"]
                    # 获取源材料曲线（已扰动或原始）
                    if source_id in perturbed_materials:
                        up_s, p_s = perturbed_materials[source_id]
                    elif source_id in materials:
                        mat_s = materials[source_id]
                        up_s, p_s = mat_s.up, mat_s.p
                    else:
                        continue

                    anchor_id = rc.get("anchor_intersection_id")
                    source_ix_id = rc.get("source_ix_id")
                    center_up = None

                    if anchor_id is not None:
                        # 普通反射：从锚交点取 center
                        if anchor_id in sample_ix_results and sample_ix_results[anchor_id] is not None:
                            center_up = sample_ix_results[anchor_id][0]
                    elif source_ix_id is not None:
                        # Reverse match：从 source_ix 重解
                        if source_ix_id in sample_ix_results and sample_ix_results[source_ix_id] is not None:
                            s_up, s_p = sample_ix_results[source_ix_id]
                            rev_results = reverse_impedance_match(s_up, s_p, up_s, p_s)
                            if rev_results:
                                center_up = rev_results[0]["center_up"]

                    # 计算反射曲线并保存结果
                    if center_up is not None:
                        if anchor_id is not None:
                            up_r, p_r = reflect_hugoniot(up_s, p_s, center_up)
                        elif source_ix_id is not None:
                            # reverse match 已给出反射曲线，直接用
                            up_r = rev_results[0]["reflected_up"]
                            p_r = rev_results[0]["reflected_p"]
                        else:
                            continue

                        sample_reflected[rc["id"]] = (up_r, p_r)
                        rc_center_samples[rc["id"]].append(center_up)
                except Exception as e:
                    if i == 0:
                        import traceback
                        print("[MC DEBUG] Pass 2 error for rc %s (sample 0): %s" % (rc.get('id','?'), e))
                        traceback.print_exc()

            # ---- 第 4 步（Pass 3）：依赖反射线的交点 ----
            for ix in pass3_ix:
                try:
                    up1, p1 = _resolve_curve_in_scene(
                        ix.source_curve1_id, perturbed_materials, materials,
                        rayleigh_lines, reflected_curves, sample_reflected,
                        perturbed_rayleigh=perturbed_rayleigh,
                    )
                    up2, p2 = _resolve_curve_in_scene(
                        ix.source_curve2_id, perturbed_materials, materials,
                        rayleigh_lines, reflected_curves, sample_reflected,
                        perturbed_rayleigh=perturbed_rayleigh,
                    )
                    if up1 is None or up2 is None:
                        sample_ix_results[ix.id] = None
                        continue

                    ints = find_intersections(
                        up1, p1, up2, p2,
                        ignore_first=ix.ignore_first_at_creation,
                    )
                    if len(ints) == 0:
                        sample_ix_results[ix.id] = None
                        continue

                    up_val = float(ints[0])
                    sort_idx = np.argsort(up1)
                    interp = interp1d(
                        up1[sort_idx], p1[sort_idx],
                        bounds_error=False, fill_value="extrapolate",
                    )
                    p_val = float(interp(up_val))
                    sample_ix_results[ix.id] = (up_val, p_val)
                except Exception as e:
                    if i == 0:
                        import traceback
                        print("[MC DEBUG] Pass 3 error for %s (sample 0): %s" % (ix.id, e))
                        traceback.print_exc()
                    sample_ix_results[ix.id] = None

            # ---- 第 4.5 步：本轮调试 ----
            if i == 0:
                n_found = sum(1 for v in sample_ix_results.values() if v is not None)
                print("[MC DEBUG] Sample 0: %d/%d intersections found, %d reflected" %
                      (n_found, len(sample_ix_results), len(sample_reflected)))

            # ---- 第 5 步：收集本轮结果 ----
            for ix_id, result in sample_ix_results.items():
                if result is not None:
                    ix_samples[ix_id].append(result)

            for rc_id, (up_r, p_r) in sample_reflected.items():
                rc_p_samples[rc_id].append(p_r)

        # ---- 聚合统计 ----
        result = MonteCarloResult(n_total=n_samples)

        for ix in intersections:
            samples = ix_samples.get(ix.id, [])
            if len(samples) < 10:
                continue
            up_vals = np.array([s[0] for s in samples])
            p_vals = np.array([s[1] for s in samples])
            result.intersection_stats[ix.id] = IntersectionStats(
                up_mean=float(np.mean(up_vals)),
                up_std=float(np.std(up_vals, ddof=1)),
                p_mean=float(np.mean(p_vals)),
                p_std=float(np.std(p_vals, ddof=1)),
                n_valid=len(samples),
            )

        print(f"[MC DEBUG] engine done: {len(result.intersection_stats)} intersection stats, "
              f"{len(result.reflected_stats)} reflected stats")

        for rc in reflected_curves:
            rc_id = rc["id"]
            p_arrays = rc_p_samples.get(rc_id, [])
            centers = rc_center_samples.get(rc_id, [])

            if not p_arrays or not centers:
                continue

            # p_err: 逐点标准差
            try:
                min_len = min(arr.size for arr in p_arrays)
                if min_len < 2:
                    continue
                p_stacked = np.stack([arr[:min_len] for arr in p_arrays], axis=0)
                p_std_arr = np.nanstd(p_stacked, axis=0, ddof=1)
            except Exception:
                continue

            # up_err: 从中心交点变动计算
            centers_arr = np.array(centers)
            center_std = float(np.std(centers_arr, ddof=1))
            up_err_arr = np.full(min_len, 2.0 * center_std)

            result.reflected_stats[rc_id] = ReflectedStats(
                up_err=up_err_arr,
                p_err=p_std_arr,
            )

        return result
