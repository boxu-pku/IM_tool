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


def load_material_by_id(lib_dir: str, material_id: str) -> pd.DataFrame:
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
    pd.DataFrame
        Loaded Hugoniot data.

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


def load_standard_hugoniot_auto(filepath: str) -> pd.DataFrame:
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
    pd.DataFrame
        Loaded Hugoniot data.

    Raises
    ------
    ValueError
        If file extension is not supported or required columns are missing.
    FileNotFoundError
        If file does not exist.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Data file not found: {filepath}")

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext == ".csv":
        return load_standard_hugoniot(filepath)
    elif ext == ".txt":
        from im_app.core.data_converter import read_standard_txt
        return read_standard_txt(filepath)
    elif ext == ".hug":
        return load_feos_hug(filepath)
    else:
        raise ValueError(
            f"Unsupported file extension: {ext}. "
            f"Supported formats: .csv, .txt, .hug"
        )


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
