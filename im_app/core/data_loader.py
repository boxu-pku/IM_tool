"""
Hugoniot data loader for the standard CSV format.

Loads data files produced by ``data_converter.py`` and stored in
``standard_library/materials/``.  Each file has 7 header lines starting
with ``#``, followed by tab-separated columns::

    Up(km/s), Us(km/s), P(Mbar), rho(g/cm3), compression, [T(eV)], [E(MJ/g)], [source]

Required columns: Up, Us, P, rho, compression.
Optional columns: T, E, source.

Usage:
    from core.data_loader import load_material_by_id, list_available_materials

    materials = list_available_materials("standard_library")
    df = load_material_by_id("standard_library", "Al_3717_sesame")
    up = df["Up(km/s)"].values
    p  = df["P(Mbar)"].values
"""

from __future__ import annotations

import json
import os
from typing import Any

import numpy as np
import pandas as pd

# 标准格式的注释行数
_COMMENT_LINES = 7

# 必需列
REQUIRED_COLUMNS = {"Up(km/s)", "Us(km/s)", "P(Mbar)", "rho(g/cm3)", "compression"}


# ---------------------------------------------------------------------------
# 公共接口
# ---------------------------------------------------------------------------

def load_standard_hugoniot(filepath: str) -> pd.DataFrame:
    """
    Load a standard-format CSV file, skipping the 7 comment header lines.

    Parameters
    ----------
    filepath : str
        Path to the CSV file (tab-separated, 7 ``#``-comment lines at top).

    Returns
    -------
    pd.DataFrame
        DataFrame with columns such as ``"Up(km/s)"``, ``"P(Mbar)"``, etc.

    Raises
    ------
    FileNotFoundError
        If *filepath* does not exist.
    ValueError
        If required columns are missing.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")

    df = pd.read_csv(
        filepath,
        sep="\t",
        comment="#",
        skipinitialspace=True,
        encoding="utf-8",
    )

    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

    # Validate required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns in {filepath}: {missing}"
        )

    # Drop fully-empty rows (trailing tabs can create them)
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


def load_metadata(lib_dir: str) -> dict[str, Any]:
    """
    Load ``metadata.json`` from the standard library directory.

    Parameters
    ----------
    lib_dir : str
        Path to the standard library root (containing ``metadata.json``).

    Returns
    -------
    dict
        Parsed JSON content.

    Raises
    ------
    FileNotFoundError
        If ``metadata.json`` does not exist in *lib_dir*.
    """
    meta_path = os.path.join(lib_dir, "metadata.json")
    if not os.path.isfile(meta_path):
        raise FileNotFoundError(f"metadata.json not found in {lib_dir}")
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_available_materials(lib_dir: str) -> list[dict[str, Any]]:
    """
    Return a list of material metadata dicts from the standard library.

    Each entry is a dict with keys ``id``, ``name``, ``source``, ``rho0``,
    ``file``, etc., as defined in ``metadata.json``.

    Parameters
    ----------
    lib_dir : str
        Path to the standard library root.

    Returns
    -------
    list[dict]
        List of material metadata entries.
    """
    meta = load_metadata(lib_dir)
    return meta.get("materials", [])


def load_material_by_id(lib_dir: str, material_id: str) -> tuple[pd.DataFrame, dict | None]:
    """
    Load a specific material's Hugoniot data by its ID.

    Looks up *material_id* in ``metadata.json``, resolves the relative
    file path, and calls :func:`load_standard_hugoniot_auto`.

    Parameters
    ----------
    lib_dir : str
        Path to the standard library root.
    material_id : str
        Material identifier, e.g. ``"Al_3717_sesame"``.

    Returns
    -------
    tuple[pd.DataFrame, dict | None]
        (DataFrame, fit_params) — fit_params 为误差元数据解析结果。

    Raises
    ------
    FileNotFoundError
        If *material_id* is not found in metadata.
    """
    materials = list_available_materials(lib_dir)
    for entry in materials:
        if entry["id"] == material_id:
            rel_path = entry["file"]
            abs_path = os.path.join(lib_dir, rel_path)
            return load_standard_hugoniot_auto(abs_path)

    raise FileNotFoundError(
        f"Material ID '{material_id}' not found in metadata. "
        f"Available: {[m['id'] for m in materials]}"
    )


def load_standard_hugoniot_auto(
    filepath: str,
) -> tuple[pd.DataFrame, dict | None]:
    """
    自动检测格式（CSV 或 TXT）并加载标准 Hugoniot 数据文件。

    根据文件扩展名选择加载方法：
    - .csv → load_standard_hugoniot()
    - .txt → read_standard_txt()

    Parameters
    ----------
    filepath : str
        Path to the data file (.csv or .txt).

    Returns
    -------
    tuple[pd.DataFrame, dict | None]
        (DataFrame, fit_params) — fit_params 为误差元数据解析结果，无误差时返回 None。
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")

    # 解析误差元数据（在所有格式加载前，先读取头部行）
    header_lines = _read_header_lines(filepath)
    fit_params = _parse_error_metadata(header_lines)

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext == ".csv":
        return load_standard_hugoniot(filepath), fit_params
    elif ext == ".txt":
        from im_app.core.data_converter import read_standard_txt
        return read_standard_txt(filepath), fit_params
    elif ext == ".hug":
        return load_feos_hug(filepath), fit_params
    else:
        raise ValueError(
            f"Unsupported file extension: {ext}. "
            f"Supported formats: .csv, .txt, .hug"
        )


def _read_header_lines(filepath: str, n_lines: int = 15) -> list[str]:
    """
    读取文件头部若干行（用于提取误差元数据）。
    在 pd.read_csv(comment="#") 跳过的行中提取 # Error 行。
    """
    lines = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for _ in range(n_lines):
                line = f.readline()
                if not line:
                    break
                lines.append(line.rstrip("\n\r"))
    except Exception:
        pass
    return lines


def _parse_error_metadata(header_lines: list[str]) -> dict | None:
    """
    从文件头部行中解析误差元数据。

    Returns
    -------
    dict or None
        {"model": str, "params": {...}} or None if no error metadata found.
    """
    fit_params = {}
    model = None
    for line in header_lines:
        stripped = line.lstrip("#").strip()
        if stripped.startswith("Error Model:"):
            model = stripped[len("Error Model:"):].strip()
        elif stripped.startswith("Error Formula:"):
            fit_params["formula"] = stripped[len("Error Formula:"):].strip()
        elif stripped.startswith("Error Params:"):
            raw = stripped[len("Error Params:"):].strip()
            # 解析 key=value 对
            tokens = raw.replace(",", " ").split()
            for token in tokens:
                if "=" in token:
                    k, v = token.split("=", 1)
                    try:
                        fit_params[k] = float(v)
                    except ValueError:
                        fit_params[k] = v

    if model is None:
        return None

    fit_params["model"] = model
    return fit_params


def compute_material_error_bands(mat: MaterialData) -> MaterialData:
    """
    根据 MaterialData.fit_params 计算 p_err 和 us_err 误差带。

    支持的模型:
    - "linear"    : Us = a0 + a1*(up - beta)
    - "piecewise_quadratic" : Us = a + b*Up + c*Up^2 (Up<break_up)
                              Us = (a - c*break_up^2) + b*Up + 2c*break_up*Up (Up>=break_up)

    Parameters
    ----------
    mat : MaterialData
        需包含 fit_params 属性。

    Returns
    -------
    MaterialData
        填充了 p_err 和 us_err 的同一对象（原位修改并返回）。
    """
    if mat.fit_params is None:
        return mat

    fp = mat.fit_params
    model = fp.get("model", "")

    if model == "linear":
        # Us = a0 + a1*(up - beta)
        a0 = fp.get("a0", 0)
        a1 = fp.get("a1", 0)
        beta = fp.get("beta", 0)
        sigma_a0 = fp.get("sigma_a0", 0)
        sigma_a1 = fp.get("sigma_a1", 0)

        # Us 的不确定度: σ_Us² = σ_a₀² + (up - β)² · σ_a₁²
        us_err = np.sqrt(sigma_a0**2 + (mat.up - beta)**2 * sigma_a1**2)

        # P 的不确定度: σ_P² = (ρ₀ · up · 0.01)² · σ_Us²
        p_err = (mat.rho0 * mat.up * 0.01) * us_err

        mat.us_err = us_err
        mat.p_err = p_err

    elif model == "piecewise_quadratic":
        # Us = a + b*Up + c*Up^2 (Up < break_up)
        # Us = (a - c*break_up^2) + b*Up + 2c*break_up*Up (Up >= break_up)
        a = fp.get("a", 0)
        b = fp.get("b", 0)
        c = fp.get("c", 0)
        sigma_a = fp.get("sigma_a", 0)
        sigma_b = fp.get("sigma_b", 0)
        sigma_c = fp.get("sigma_c", 0)
        break_up = fp.get("break_up", float("inf"))

        # 计算偏导数 ∂Us/∂a, ∂Us/∂b, ∂Us/∂c
        dUs_da = np.ones_like(mat.up)
        dUs_db = mat.up.copy()
        dUs_dc = np.where(mat.up < break_up,
                          mat.up**2,
                          2 * break_up * mat.up - break_up**2)

        # σ_Us² = (∂Us/∂a)²·σ_a² + (∂Us/∂b)²·σ_b² + (∂Us/∂c)²·σ_c²
        us_err = np.sqrt(
            dUs_da**2 * sigma_a**2 +
            dUs_db**2 * sigma_b**2 +
            dUs_dc**2 * sigma_c**2
        )

        # σ_P² = (ρ₀ · up · 0.01)² · σ_Us²
        p_err = (mat.rho0 * mat.up * 0.01) * us_err

        mat.us_err = us_err
        mat.p_err = p_err

    return mat


def load_feos_hug(filepath: str) -> pd.DataFrame:
    """
    加载 FEOS .hug 格式文件。

    FEOS .hug 格式:
    - 第一行: 注释行，包含列名和单位
    - 第二行开始: 科学计数法数据，空格分隔

    列顺序: rho, T, P, E, Us, Up
    单位说明:
    - rho: g/cm^3 (直接读取)
    - T: eV (直接读取)
    - P: Mbar (注释显示 P[1e12 dyne/cm^2]，数值*1e12/1e12=数值Mbar，直接读取)
    - E: erg/g -> MJ/g (除以 1e10)
    - Us, Up: km/s (注释显示 Us[1e5 cm/s]，数值*1e5/1e5=数值km/s，直接读取)

    Parameters
    ----------
    filepath : str
        Path to the .hug file.

    Returns
    -------
    pd.DataFrame
        DataFrame with standard column names and units.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"FEOS .hug file not found: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if len(lines) < 2:
        raise ValueError(f"Invalid .hug file: {filepath} (at least 2 lines required)")

    # 读取数据行
    data_list = []
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            # 科学计数法，空格分隔
            values = [float(v) for v in line.split()]
            if len(values) >= 6:  # rho, T, P, E, Us, Up
                data_list.append(values)
        except ValueError:
            continue

    if not data_list:
        raise ValueError(f"No valid data found in {filepath}")

    # 转换为 numpy 数组
    import numpy as np
    data = np.array(data_list)

    # 提取各列
    # FEOS 注释格式：Us [1.000000e+05 cm/s] 表示数值单位为 km/s（已经预转换）
    # 所以直接读取数值即可
    rho = data[:, 0]          # g/cm^3
    T = data[:, 1]             # eV
    P = data[:, 2]             # Mbar (数值 * 1e12 dyne/cm^2 / 1e12 = 数值 Mbar)
    E = data[:, 3] / 1e10    # erg/g -> MJ/g (1 MJ/g = 10^10 erg/g)
    Us = data[:, 4]            # km/s (数值 * 1e5 cm/s / 1e5 = 数值 km/s)
    Up = data[:, 5]            # km/s (数值 * 1e5 cm/s / 1e5 = 数值 km/s)

    # 计算压缩比
    rho0 = rho[0]  # 使用第一个点作为初始密度
    compression = rho / rho0

    # 创建 DataFrame
    df = pd.DataFrame({
        "Up(km/s)": Up,
        "Us(km/s)": Us,
        "P(Mbar)": P,
        "rho(g/cm3)": rho,
        "compression": compression,
        "T(eV)": T,
        "E(MJ/g)": E,
    })

    return df
