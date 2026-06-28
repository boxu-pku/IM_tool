"""
Core physics calculations for impedance matching analysis.

Generic, material-agnostic implementation.  All materials are represented
by :class:`MaterialData` instances; Rayleigh lines and intersections are
tracked via dedicated dataclasses.

Usage:
    from core.physics import (
        MaterialData, RayleighLine, Intersection,
        rayleigh_line, find_intersections, find_all_intersections,
        reflect_hugoniot, compression_ratio,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.interpolate import interp1d


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MaterialData:
    """
    Hugoniot curve data for a single material.

    Attributes
    ----------
    id : str
        Unique identifier (e.g. ``"Al_3717_sesame"``).
    name : str
        Human-readable name (e.g. ``"Aluminum"``).
    rho0 : float
        Initial density (g/cm^3).
    up : ndarray
        Particle velocity array (km/s).
    p : ndarray
        Pressure array (Mbar).
    us : ndarray or None
        Shock velocity array (km/s), if available.
    compression : ndarray or None
        Compression ratio rho/rho0 array, if available.
    rho : ndarray or None
        Density array (g/cm^3), if available.
    temperature : ndarray or None
        Temperature array (eV), if available.
    energy : ndarray or None
        Internal energy array (MJ/g), if available.
    """
    id: str
    name: str
    rho0: float
    up: np.ndarray
    p: np.ndarray
    us: Optional[np.ndarray] = None
    compression: Optional[np.ndarray] = None
    rho: Optional[np.ndarray] = None
    temperature: Optional[np.ndarray] = None
    energy: Optional[np.ndarray] = None


@dataclass
class RayleighLine:
    """
    A Rayleigh line: P = rho0 * up * D * 0.01.

    Attributes
    ----------
    id : str
        Unique identifier for this Rayleigh line.
    material_id : str
        ID of the material whose rho0 is used.
    D : float
        Measured shock velocity (km/s).
    rho0 : float
        Initial density of the material (g/cm^3).
    up : ndarray
        Particle velocity x-values (km/s).
    p : ndarray
        Pressure y-values (Mbar), computed as rho0 * up * D * 0.01.
    """
    id: str
    material_id: str
    D: float
    rho0: float
    up: np.ndarray
    p: np.ndarray


@dataclass
class Intersection:
    """
    An intersection point between two curves.

    Attributes
    ----------
    id : str
        Unique identifier for this intersection.
    curve1_id : str
        Display name of the first curve (material name, "Rayleigh X", or "Reflected X").
    curve2_id : str
        Display name of the second curve.
    up : float
        Particle velocity at the intersection (km/s).
    p : float
        Pressure at the intersection (Mbar).
    type : str
        ``"hugoniot-rayleigh"``, ``"hugoniot-hugoniot"``, or ``"custom"``.
    material_id : str or None
        ID of the primary material for this intersection (used by scatter lookup).
        For hugoniot-rayleigh: the material side; for hugoniot-hugoniot: curve1's material.
    compression_ratio : float or None
        Compression ratio at the intersection (rho/rho0).
    """
    id: str
    curve1_id: str
    curve2_id: str
    up: float
    p: float
    type: str
    material_id: Optional[str] = None
    compression_ratio: Optional[float] = None


# ---------------------------------------------------------------------------
# Physics functions
# ---------------------------------------------------------------------------

def rayleigh_line(up: np.ndarray, rho0: float, D: float) -> np.ndarray:
    """
    Compute Rayleigh line pressure.

    P = rho0 * up * D * 0.01  (Mbar)

    Parameters
    ----------
    up : array_like
        Particle velocity (km/s).
    rho0 : float
        Initial density (g/cm^3).
    D : float
        Shock velocity (km/s).

    Returns
    -------
    ndarray
        Pressure array (Mbar).
    """
    return rho0 * np.asarray(up) * D * 0.01


def _ensure_sorted(
    up: np.ndarray, p: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Sort (up, p) arrays so up is monotonically increasing."""
    order = np.argsort(up)
    return up[order], p[order]


def find_intersections(
    up1: np.ndarray,
    p1: np.ndarray,
    up2: np.ndarray,
    p2: np.ndarray,
    grid_points: int = 15000,
    ignore_first: bool = False,
    first_threshold: float = 1.0,
) -> np.ndarray:
    """
    Find all intersections between two (up, P) curves via sign-change
    detection on interpolated values.

    Both curves are interpolated onto a common fine grid; the positions
    where the difference changes sign are refined with linear
    interpolation for sub-grid accuracy.

    Parameters
    ----------
    up1, p1 : ndarray
        First curve (e.g. Hugoniot).
    up2, p2 : ndarray
        Second curve (e.g. Rayleigh line or reflected Hugoniot).
    grid_points : int
        Number of grid points for the interpolation mesh.
    ignore_first : bool
        If True, ignore the first intersection near zero.
    first_threshold : float
        Threshold for ignoring first intersection (km/s).

    Returns
    -------
    ndarray
        1-D array of particle velocities at intersection points.
        Empty if no intersections are found.
    """
    # 确保 up 单调递增（反射 Hugoniot 等曲线可能递减）
    up1, p1 = _ensure_sorted(np.asarray(up1), np.asarray(p1))
    up2, p2 = _ensure_sorted(np.asarray(up2), np.asarray(p2))

    interp1 = interp1d(
        up1, p1, kind="linear",
        bounds_error=False, fill_value=np.nan,
    )
    interp2 = interp1d(
        up2, p2, kind="linear",
        bounds_error=False, fill_value=np.nan,
    )

    # 两个曲线的公共定义域
    min_up = max(up1[0], up2[0])
    max_up = min(up1[-1], up2[-1])
    if min_up >= max_up:
        return np.array([])

    up_common = np.linspace(min_up, max_up, grid_points)
    diff = interp1(up_common) - interp2(up_common)

    # NaN 区域不做判断
    valid = np.isfinite(diff)
    up_common_v = up_common[valid]
    diff_v = diff[valid]

    sign_changes = np.where(np.diff(np.sign(diff_v)))[0]
    intersections: list[float] = []
    for i in sign_changes:
        # 线性插值精确定位
        u1, u2 = up_common_v[i], up_common_v[i + 1]
        d1, d2 = diff_v[i], diff_v[i + 1]
        if d2 != d1:
            up_int = u1 - d1 * (u2 - u1) / (d2 - d1)
            # Ignore first intersection near zero if requested
            if ignore_first and up_int < first_threshold:
                continue
            intersections.append(float(up_int))

    return np.array(intersections)


def find_all_intersections(
    materials: dict[str, MaterialData],
    rayleigh_lines: dict[str, RayleighLine],
    ignore_first: bool = True,
) -> list[Intersection]:
    """
    Find intersections between every loaded material Hugoniot and every
    Rayleigh line.

    Parameters
    ----------
    materials : dict[str, MaterialData]
        Mapping of material ID -> MaterialData.
    rayleigh_lines : dict[str, RayleighLine]
        Mapping of Rayleigh line ID -> RayleighLine.
    ignore_first : bool
        If True, ignore the first intersection near zero (default: True).

    Returns
    -------
    list[Intersection]
        All detected intersection points.
    """
    results: list[Intersection] = []
    counter = 0

    for mat_id, mat in materials.items():
        for rl_id, rl in rayleigh_lines.items():
            up_ints = find_intersections(
                mat.up, mat.p,
                rl.up, rl.p,
                ignore_first=ignore_first,
            )
            for up_val in up_ints:
                p_val = float(rayleigh_line(np.array([up_val]), rl.rho0, rl.D)[0])
                results.append(Intersection(
                    id=f"ix_{counter}",
                    curve1_id=mat_id,
                    curve2_id=rl_id,
                    up=float(up_val),
                    p=p_val,
                    type="hugoniot-rayleigh",
                ))
                counter += 1

    return results


def reflect_hugoniot(
    up: np.ndarray,
    p: np.ndarray,
    center_up: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Reflect a Hugoniot curve about *center_up*.

    up_reflected = 2 * center_up - up

    Parameters
    ----------
    up : ndarray
        Original particle velocity array (km/s).
    p : ndarray
        Original pressure array (Mbar).
    center_up : float
        Reflection center — the interface particle velocity (km/s).

    Returns
    -------
    tuple[ndarray, ndarray]
        Reflected (up, p).  Pressure is unchanged; up is mirrored.
    """
    up_r = 2.0 * center_up - np.asarray(up)
    return up_r, np.asarray(p).copy()


def compression_ratio(D: float, up: float) -> float:
    """
    Compute the compression ratio rho / rho0 = D / (D - up).

    Parameters
    ----------
    D : float
        Shock velocity (km/s).
    up : float
        Particle velocity (km/s).

    Returns
    -------
    float
        Compression ratio.  Returns ``float("inf")`` if D <= up
        (physically invalid — shock cannot be overtaken).
    """
    denom = D - up
    if denom <= 0:
        return float("inf")
    return D / denom


def generate_ideal_plasma_hugoniot(
    name: str,
    rho0: float,
    gamma: float = 5.0 / 3.0,
    up_max: float = 200.0,
    n_points: int = 500,
) -> MaterialData:
    """
    Generate an ideal gas/plasma Hugoniot curve analytically.

    Uses the strong-shock Rankine-Hugoniot relations for a γ-law gas:
        Us = (γ+1)/2 · Up
        P  = ρ₀ · (γ+1)/2 · Up² · 0.01   (Mbar)
        ρ/ρ₀ = (γ+1)/(γ-1)                (constant)

    Parameters
    ----------
    name : str
        Material name (used for display).
    rho0 : float
        Initial density (g/cm³).
    gamma : float
        Adiabatic index (default 5/3 for monatomic ideal gas).
    up_max : float
        Maximum particle velocity (km/s).
    n_points : int
        Number of data points to generate.

    Returns
    -------
    MaterialData
        Complete Hugoniot data (id is set to ``"{name}_ideal_plasma"``).

    Raises
    ------
    ValueError
        If gamma <= 1, rho0 <= 0, or up_max <= 0.
    """
    if gamma <= 1.0:
        raise ValueError(f"gamma must be > 1.0, got {gamma}")
    if rho0 <= 0:
        raise ValueError(f"rho0 must be > 0, got {rho0}")
    if up_max <= 0:
        raise ValueError(f"up_max must be > 0, got {up_max}")

    up = np.linspace(1e-6, up_max, n_points)
    us = (gamma + 1) / 2.0 * up
    p = rho0 * us * up * 0.01  # Mbar

    cr = (gamma + 1) / (gamma - 1)
    rho = np.full_like(up, rho0 * cr)
    compression = np.full_like(up, cr)

    # 比内能 E = P / ((γ-1)·ρ)，单位换算 Mbar·cm³/g → MJ/g (×100)
    energy = p / ((gamma - 1) * rho) * 100.0

    mat_id = f"{name.replace(' ', '_')}_ideal_plasma"

    return MaterialData(
        id=mat_id,
        name=name,
        rho0=rho0,
        up=up,
        p=p,
        us=us,
        compression=compression,
        rho=rho,
        temperature=None,
        energy=energy,
    )


def find_rayleigh_reflected_intersections(
    rayleigh_line: RayleighLine,
    reflected_up: np.ndarray,
    reflected_p: np.ndarray,
) -> np.ndarray:
    """
    Find intersections between a Rayleigh line and a reflected Hugoniot.

    Parameters
    ----------
    rayleigh_line : RayleighLine
        The Rayleigh line to intersect with.
    reflected_up : ndarray
        Reflected Hugoniot particle velocities (km/s).
    reflected_p : ndarray
        Reflected Hugoniot pressures (Mbar).

    Returns
    -------
    ndarray
        Particle velocities at intersection points (km/s).
    """
    return find_intersections(
        rayleigh_line.up, rayleigh_line.p,
        reflected_up, reflected_p,
        ignore_first=True,
    )


def get_thermodynamics_at_intersection(
    up: float,
    p: float,
    D: float,
    material: MaterialData | None = None,
) -> dict:
    """
    Get thermodynamic state at an intersection point.

    Parameters
    ----------
    up : float
        Particle velocity (km/s).
    p : float
        Pressure (Mbar).
    D : float
        Shock velocity (km/s).
    material : MaterialData, optional
        Material data for compression ratio calculation.

    Returns
    -------
    dict
        Thermodynamic state including compression ratio.
    """
    state = {
        "up": up,
        "p": p,
        "D": D,
        "compression": compression_ratio(D, up),
    }
    return state


def reverse_impedance_match(
    target_up: float,
    target_p: float,
    hugoniot_up: np.ndarray,
    hugoniot_p: np.ndarray,
) -> list[dict]:
    """
    Given a known point (target_up, target_p) on a reflected Hugoniot,
    find the reflection center(s) such that the reflected Hugoniot passes
    through that point.

    The reflected Hugoniot satisfies: up_r = 2*center - up_orig, P_r = P_orig.
    For the target point to lie on the reflected curve:
        up_orig = 2*center - target_up
        P(up_orig) = target_p

    We scan over center_up values and find where P(2*center - target_up) = target_p.

    Parameters
    ----------
    target_up : float
        Known particle velocity at the intersection (km/s).
    target_p : float
        Known pressure at the intersection (Mbar).
    hugoniot_up : ndarray
        Original Hugoniot particle velocity array (km/s).
    hugoniot_p : ndarray
        Original Hugoniot pressure array (Mbar).

    Returns
    -------
    list[dict]
        Each dict contains:
        - center_up: the reflection center velocity
        - reflected_up: reflected Hugoniot up array
        - reflected_p: reflected Hugoniot p array
        - intersection_up: velocity at intersection of reflected with original Hugoniot
        - intersection_p: pressure at intersection of reflected with original Hugoniot
    """
    from scipy.optimize import brentq

    # Build Hugoniot interpolator P(up)
    sort_idx = np.argsort(hugoniot_up)
    up_s = hugoniot_up[sort_idx]
    p_s = hugoniot_p[sort_idx]

    # Remove duplicates for interpolation
    unique_mask = np.diff(up_s, prepend=-np.inf) > 1e-10
    up_s = up_s[unique_mask]
    p_s = p_s[unique_mask]

    p_interp = interp1d(up_s, p_s, kind="linear", bounds_error=False, fill_value=np.nan)

    # Scan: for a given center_up, the original point maps to
    # up_orig = 2*center_up - target_up
    # We need P(up_orig) = target_p
    # Define f(center) = P(2*center - target_up) - target_p = 0

    up_min, up_max = up_s[0], up_s[-1]

    def f(center):
        up_orig = 2.0 * center - target_up
        if up_orig < up_min or up_orig > up_max:
            return np.nan
        return float(p_interp(up_orig)) - target_p

    # Scan center range: up_orig must be in [up_min, up_max]
    # so 2*center - target_up in [up_min, up_max]
    # center in [(up_min + target_up)/2, (up_max + target_up)/2]
    center_min = (up_min + target_up) / 2.0
    center_max = (up_max + target_up) / 2.0

    if center_min >= center_max:
        return []

    # Fine scan for sign changes
    n_scan = 5000
    centers = np.linspace(center_min, center_max, n_scan)
    f_vals = np.array([f(c) for c in centers])
    valid = np.isfinite(f_vals)

    results = []
    sign_changes = np.where(np.diff(np.sign(f_vals[valid])))[0]
    valid_centers = centers[valid]
    valid_f = f_vals[valid]

    for si in sign_changes:
        try:
            c1, c2 = valid_centers[si], valid_centers[si + 1]
            center_up = brentq(f, c1, c2, xtol=1e-8)
        except (ValueError, RuntimeError):
            continue

        # Compute reflected curve
        up_r, p_r = reflect_hugoniot(hugoniot_up, hugoniot_p, center_up)

        # Find intersection of reflected Hugoniot with original Hugoniot
        up_ints = find_intersections(hugoniot_up, hugoniot_p, up_r, p_r, ignore_first=True)

        for u_int in up_ints:
            p_int = float(p_interp(u_int))
            results.append({
                "center_up": center_up,
                "reflected_up": up_r,
                "reflected_p": p_r,
                "intersection_up": u_int,
                "intersection_p": p_int,
            })

    return results


# ---------------------------------------------------------------------------
# Scatter point interpolation helpers
# ---------------------------------------------------------------------------

def lookup_material_state_at_up(
    material: MaterialData,
    up: float,
) -> dict:
    """
    在指定 up 处对材料 Hugoniot 各列做 cubic spline 插值。

    若某列数据点不足（<4）或非严格单调 → 退化为线性插值。
    若材料不含该列 → None。

    Returns
    -------
    dict
        Keys: Up, P, compression, T, E, rho, Us (任一可能为 None)
    """
    result = {"Up": float(up)}
    up_col = np.asarray(material.up, dtype=float)

    columns = [
        ("p",           "P"),
        ("compression", "compression"),
        ("temperature", "T"),
        ("energy",      "E"),
        ("rho",         "rho"),
        ("us",          "Us"),
    ]

    for attr, out_key in columns:
        col = getattr(material, attr, None)
        result[out_key] = _interp_column_cubic(up, up_col, col)

    return result


def _interp_column_cubic(up: float, up_col: np.ndarray, col) -> float | None:
    """Cubic spline 插值，含退化分支。"""
    if col is None or len(col) == 0:
        return None

    col_arr = np.asarray(col, dtype=float)
    mask = ~np.isnan(col_arr) & ~np.isnan(up_col)
    if mask.sum() < 2:
        return None

    xs = up_col[mask]
    ys = col_arr[mask]
    sort_idx = np.argsort(xs)
    xs, ys = xs[sort_idx], ys[sort_idx]

    # 去重（CubicSpline 要求严格单调）
    unique_mask = np.concatenate([[True], np.diff(xs) > 1e-10])
    xs_u, ys_u = xs[unique_mask], ys[unique_mask]

    # 优先 cubic spline（需要 >= 4 个点）
    if len(xs_u) >= 4:
        try:
            from scipy.interpolate import CubicSpline
            cs = CubicSpline(xs_u, ys_u, extrapolate=True)
            return float(cs(up))
        except Exception:
            pass  # 落到线性插值

    # 退化：线性插值
    try:
        return float(np.interp(up, xs_u, ys_u))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Hugoniot 守恒关系（强冲击波近似，P₀ ≈ 0, E₀ ≈ 0）
# ---------------------------------------------------------------------------

def compute_hugoniot_state(up: float, p: float, rho0: float) -> dict:
    """
    用 Rankine-Hugoniot 关系从 (Up, P, ρ₀) 推导完整力学状态。

    强冲击波近似（P₀ ≈ 0, E₀ ≈ 0）下的 4 个守恒方程：
        1. 动量:  P [Mbar] = ρ₀ [g/cm³] · Us [km/s] · Up [km/s] / 100
        2. 质量:  ρ [g/cm³] = ρ₀ · Us / (Us - Up)
        3. 压缩比: η = ρ/ρ₀ = Us / (Us - Up)
        4. 能量:  E [MJ/g] = Up² / 2000

    单位约定：Up, Us [km/s]；P [Mbar]；ρ₀, ρ [g/cm³]；E [MJ/g]。
    T 不在守恒律范围内（需要 EOS），本函数不计算 T。

    Parameters
    ----------
    up : float
        Particle velocity [km/s]. 必须非零（否则动量方程奇异）。
    p : float
        Pressure [Mbar].
    rho0 : float
        Initial density [g/cm³]. 必须为正。

    Returns
    -------
    dict
        Keys: Up, P, Us, rho, compression, E. 任一无法计算时为 None。
    """
    state = {"Up": float(up) if up is not None else None,
             "P":  float(p)  if p  is not None else None,
             "Us": None, "rho": None, "compression": None, "E": None}

    # 能量守恒: E = Up² / 2000  （仅依赖 Up，永远能算，包括 Up=0 → E=0）
    if up is not None:
        try:
            state["E"] = float(up * up / 2000.0)
        except Exception:
            pass

    if not rho0 or rho0 <= 0 or not up or up == 0:
        return state

    # 动量守恒: Us = 100 · P / (ρ₀ · Up)
    try:
        us = 100.0 * p / (rho0 * up)
        state["Us"] = float(us)
    except Exception:
        us = None

    # 质量 + 压缩比: 需要 Us - Up ≠ 0
    if us is not None and (us - up) != 0:
        try:
            state["compression"] = float(us / (us - up))
            state["rho"] = float(rho0 * us / (us - up))
        except Exception:
            pass

    return state
