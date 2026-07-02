"""
Error propagation for impedance matching analysis.

Computes uncertainties in intersection points, reflected Hugoniots, and
reverse impedance matching results from material Hugoniot error bands.

Supported error models:
  - ``linear``: Us = a0 + a1*(up - beta)
  - ``piecewise_quadratic``: Us = a + b*Up + c*Up² (piecewise)

Usage:
    from im_app.core.error_propagation import (
        intersection_error_propagation,
        reflect_error_propagation,
        reverse_match_error_propagation,
    )
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from scipy.interpolate import interp1d

from im_app.core.physics import MaterialData, RayleighLine


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _interp_err_at_up(
    up_val: float,
    up_arr: np.ndarray,
    err_arr: np.ndarray | None,
) -> float:
    """在指定 up 处线性插值误差值。无误差时返回 0。"""
    if err_arr is None or len(err_arr) == 0:
        return 0.0
    up_arr = np.asarray(up_arr, dtype=float)
    err_arr = np.asarray(err_arr, dtype=float)
    # 过滤无效值
    mask = np.isfinite(up_arr) & np.isfinite(err_arr)
    if mask.sum() < 2:
        return 0.0
    up_masked = up_arr[mask]
    err_masked = err_arr[mask]
    # np.interp 要求 x 严格递增（反射曲线可能递减，需先排序）
    sort_idx = np.argsort(up_masked)
    try:
        return float(np.interp(
            float(up_val),
            up_masked[sort_idx],
            err_masked[sort_idx],
        ))
    except Exception:
        return 0.0


def _estimate_slope(
    up_arr: np.ndarray,
    p_arr: np.ndarray,
    up_val: float,
    window: float = 0.01,
) -> float:
    """在 up_val 附近用局部线性拟合估算曲线斜率 dP/dup。"""
    up_arr = np.asarray(up_arr, dtype=float)
    p_arr = np.asarray(p_arr, dtype=float)
    mask = np.isfinite(up_arr) & np.isfinite(p_arr)
    up_arr = up_arr[mask]
    p_arr = p_arr[mask]
    if len(up_arr) < 4:
        return 0.0
    # 无论递增/递减，窗口用全跨度绝对值
    half = window * abs(up_arr[-1] - up_arr[0])
    left = float(up_val) - half
    right = float(up_val) + half
    idx = (up_arr >= left) & (up_arr <= right)
    if idx.sum() < 2:
        return 0.0
    xs = up_arr[idx]
    ys = p_arr[idx]
    if len(xs) < 2:
        return 0.0
    # 线性回归斜率（对递增/递减均正确）
    dx = xs - xs.mean()
    dy = ys - ys.mean()
    denom = np.sum(dx ** 2)
    if denom == 0:
        return 0.0
    return float(np.sum(dx * dy) / denom)


# ---------------------------------------------------------------------------
# 交点误差传播
# ---------------------------------------------------------------------------

def intersection_error_propagation(
    up_int: float,
    p_int: float,
    curve1_up: np.ndarray,
    curve1_p: np.ndarray,
    curve1_err: np.ndarray | None,
    curve2_up: np.ndarray,
    curve2_p: np.ndarray,
    curve2_err: np.ndarray | None,
) -> dict:
    """
    计算两个曲线交点的不确定度。

    使用局部线性近似传播 Hugoniot 误差带到交点坐标。

    Parameters
    ----------
    up_int : float
        交点处的粒子速度 (km/s)。
    p_int : float
        交点处的压力 (Mbar)。
    curve1_up, curve1_p : ndarray
        第一条曲线的 up, p 数组。
    curve1_err : ndarray or None
        第一条曲线的 p_err 数组（与 curve1_up 同长）。
    curve2_up, curve2_p : ndarray
        第二条曲线的 up, p 数组。
    curve2_err : ndarray or None
        第二条曲线的 p_err 数组（与 curve2_up 同长）。

    Returns
    -------
    dict
        {"up_err": float, "p_err": float, "method": str}
    """
    # 插值得到交点处两曲线的压力误差
    e1 = _interp_err_at_up(up_int, curve1_up, curve1_err)
    e2 = _interp_err_at_up(up_int, curve2_up, curve2_err)

    # 估算局部斜率
    s1 = _estimate_slope(curve1_up, curve1_p, up_int)
    s2 = _estimate_slope(curve2_up, curve2_p, up_int)

    ds = s1 - s2

    if abs(ds) < 1e-12:
        # 平行或相切 — 误差极大（不可靠）
        up_err = float("inf")
        p_err = float("inf")
        method = "singular"
    else:
        # σ_up² = (e1² + e2²) / (s1 - s2)²
        p_band = np.sqrt(e1 ** 2 + e2 ** 2)
        up_err = p_band / abs(ds)
        # σ_p 通过曲线 1 的斜率与 σ_up 传播
        p_err = np.sqrt(e1 ** 2 + (s1 * up_err) ** 2)
        method = "linear_approx"

    return {
        "up_err": up_err,
        "p_err": p_err,
        "method": method,
    }


# ---------------------------------------------------------------------------
# 反射 Hugoniot 误差传播
# ---------------------------------------------------------------------------

def reflect_error_propagation(
    source_p_err: np.ndarray | None,
    center_up_err: float,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """
    计算反射 Hugoniot 的误差带。

    反射操作: up_r = 2*center - up, P_r = P
    因此:
      σ_up_r = 2 * σ_center (reflected up 的不确定度来自中心点误差)
      σ_P_r  = σ_P         (P 值不变，误差与源材料相同)

    Parameters
    ----------
    source_p_err : ndarray or None
        源材料的 p_err 数组。
    center_up_err : float
        反射中心 up 的不确定度（来自交点的 up_err）。

    Returns
    -------
    tuple[ndarray or None, ndarray or None]
        (up_r_err, p_r_err) — 反射后的误差数组。
    """
    if source_p_err is None:
        return None, None

    up_r_err = np.full_like(source_p_err, 2.0 * center_up_err)
    p_r_err = source_p_err.copy()
    return up_r_err, p_r_err


# ---------------------------------------------------------------------------
# 反向阻抗匹配误差传播
# ---------------------------------------------------------------------------

def reverse_match_error_propagation(
    target_up: float,
    target_p: float,
    sigma_target_up: float,
    sigma_target_p: float,
    hugoniot_up: np.ndarray,
    hugoniot_p: np.ndarray,
    hugoniot_p_err: np.ndarray | None,
    center_up_result: float,
    epsilon: float = 1e-4,
) -> dict:
    """
    计算反向阻抗匹配结果的不确定度。

    使用有限差分估计 center_up 对 target_up 和 target_p 的敏感度，
    然后传播误差。

    Parameters
    ----------
    target_up : float
        已知粒子速度 (km/s)。
    target_p : float
        已知压力 (Mbar)。
    sigma_target_up : float
        target_up 的 ±σ。
    sigma_target_p : float
        target_p 的 ±σ。
    hugoniot_up : ndarray
        参考 Hugoniot 的 up 数组。
    hugoniot_p : ndarray
        参考 Hugoniot 的 p 数组。
    hugoniot_p_err : ndarray or None
        参考 Hugoniot 的 p_err 数组。
    center_up_result : float
        reverse_impedance_match 找到的反射中心 up。
    epsilon : float
        有限差分步长（相对值，默认 1e-4）。

    Returns
    -------
    dict
        {"center_up_err": float, "method": str}
    """
    from im_app.core.physics import reverse_impedance_match

    # 若 Hugoniot 无误差，只传播 target 输入的误差
    if hugoniot_p_err is None:
        # 构建插值函数估算敏感度
        sort_idx = np.argsort(hugoniot_up)
        us = hugoniot_up[sort_idx]
        ps = hugoniot_p[sort_idx]
        unique_mask = np.diff(us, prepend=-np.inf) > 1e-10
        us = us[unique_mask]
        ps = ps[unique_mask]
        p_interp = interp1d(us, ps, kind="linear", bounds_error=False, fill_value=np.nan)

        up_min, up_max = us[0], us[-1]
        center_min = (up_min + target_up) / 2.0
        center_max = (up_max + target_up) / 2.0
        if center_max <= center_min:
            return {"center_up_err": float("inf"), "method": "singular"}

        def f(center):
            up_orig = 2.0 * center - target_up
            if up_orig < up_min or up_orig > up_max:
                return np.nan
            return float(p_interp(up_orig)) - target_p

        def dcenter_dtarget_up(c_val, delta):
            """有限差分 ∂center/∂target_up"""
            target_up_p = target_up + delta
            target_up_m = target_up - delta
            # 重新扫描，近似敏感度
            centers_p = np.linspace(center_min, center_max, 1000)
            f_vals_p = np.array([
                float(p_interp(2.0 * c - target_up_p)) - target_p
                if (2.0 * c - target_up_p) >= up_min and (2.0 * c - target_up_p) <= up_max
                else np.nan
                for c in centers_p
            ])
            sign_p = np.where(np.diff(np.sign(np.nan_to_num(f_vals_p, nan=0.0))))[0]
            c_p = float(np.mean(centers_p[sign_p])) if len(sign_p) > 0 else c_val

            f_vals_m = np.array([
                float(p_interp(2.0 * c - target_up_m)) - target_p
                if (2.0 * c - target_up_m) >= up_min and (2.0 * c - target_up_m) <= up_max
                else np.nan
                for c in centers_p
            ])
            sign_m = np.where(np.diff(np.sign(np.nan_to_num(f_vals_m, nan=0.0))))[0]
            c_m = float(np.mean(centers_p[sign_m])) if len(sign_m) > 0 else c_val

            if delta == 0:
                return 0.0
            return (c_p - c_m) / (2.0 * delta)

        def dcenter_dtarget_p(c_val, delta):
            """有限差分 ∂center/∂target_p"""
            target_p_p = target_p + delta
            target_p_m = target_p - delta
            centers_p = np.linspace(center_min, center_max, 1000)

            def find_center(tp):
                fv = np.array([
                    float(p_interp(2.0 * c - target_up)) - tp
                    if (2.0 * c - target_up) >= up_min and (2.0 * c - target_up) <= up_max
                    else np.nan
                    for c in centers_p
                ])
                si = np.where(np.diff(np.sign(np.nan_to_num(fv, nan=0.0))))[0]
                return float(np.mean(centers_p[si])) if len(si) > 0 else c_val

            c_p = find_center(target_p_p)
            c_m = find_center(target_p_m)
            if delta == 0:
                return 0.0
            return (c_p - c_m) / (2.0 * delta)

        delta_up = max(epsilon * abs(target_up), 1e-6)
        delta_p = max(epsilon * abs(target_p), 1e-6)

        dc_du = dcenter_dtarget_up(center_up_result, delta_up)
        dc_dp = dcenter_dtarget_p(center_up_result, delta_p)

        sigma_c = np.sqrt(
            (dc_du * sigma_target_up) ** 2 +
            (dc_dp * sigma_target_p) ** 2
        )
        return {"center_up_err": float(sigma_c) if np.isfinite(sigma_c) else float("inf"),
                "method": "finite_difference"}

    # 有 Hugoniot 误差：叠加 Hugoniot 误差贡献
    # 用交点误差的简化估算：Hugoniot 误差在 up_orig 处影响 center 求解
    # 其中 up_orig = 2*center - target_up
    up_orig = 2.0 * center_up_result - target_up
    e_hug = _interp_err_at_up(up_orig, hugoniot_up, hugoniot_p_err)

    # 来自 Hugoniot 误差的 center 不确定度 ≈ e_hug / (2 * |slope(up_orig)|)
    s_hug = _estimate_slope(hugoniot_up, hugoniot_p, up_orig)
    if abs(s_hug) > 1e-12:
        sigma_center_from_hug = e_hug / (2.0 * abs(s_hug))
    else:
        sigma_center_from_hug = float("inf")

    # 总的不确定度 = 输入误差 + Hugoniot 误差（平方和）
    sigma_total = np.sqrt(
        sigma_target_up ** 2 + sigma_target_p ** 2 + sigma_center_from_hug ** 2
    )

    return {
        "center_up_err": float(sigma_total) if np.isfinite(sigma_total) else float("inf"),
        "method": "linear_approx",
    }
