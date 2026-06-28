"""
Hugoniot 数据格式转换器

将各种原始数据格式转换为标准 CSV 格式。
标准格式规范:
  - 前 7 行为 # 开头的元数据
  - Tab 分隔
  - 列名: Up(km/s), Us(km/s), P(Mbar), rho(g/cm3), compression, T(eV), E(MJ/g), source
  - 必需列: Up(km/s), Us(km/s), P(Mbar), rho(g/cm3), compression
  - 可选列: T(eV), E(MJ/g), source
"""

import os
import re
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd


# 标准列名
REQUIRED_COLUMNS = ["Up(km/s)", "Us(km/s)", "P(Mbar)", "rho(g/cm3)", "compression"]
OPTIONAL_COLUMNS = ["T(eV)", "E(MJ/g)", "source"]
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

# 元数据头部模板
HEADER_TEMPLATE = [
    "# Material: {material}",
    "# Reference: {reference}",
    "# Initial Density (g/cm³): {rho0}",
    "# Data Source: {data_source}",
    "# Date Created: {date}",
    "# Notes: {notes}",
    "# Columns: Up(km/s), Us(km/s), P(Mbar), rho(g/cm3), compression, T(eV), E(MJ/g), source",
]


def _write_standard_csv(
    output_path: str,
    df: pd.DataFrame,
    material_info: dict,
):
    """将 DataFrame 写入标准格式 CSV"""
    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 确保所有必需列存在
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            raise ValueError(f"缺少必需列: {col}")

    # 补充可选列
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            if col == "source":
                df[col] = material_info.get("source", "")
            else:
                df[col] = np.nan

    # 按标准列顺序排列
    cols_to_write = [c for c in ALL_COLUMNS if c in df.columns]
    df_out = df[cols_to_write]

    # 写入文件
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        # 写入元数据头部
        info = {
            "material": material_info.get("material", "Unknown"),
            "reference": material_info.get("reference", ""),
            "rho0": material_info.get("rho0", ""),
            "data_source": material_info.get("data_source", ""),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "notes": material_info.get("notes", ""),
        }
        for line in HEADER_TEMPLATE:
            f.write(line.format(**info) + "\n")

        # 写入数据
        df_out.to_csv(f, sep="\t", index=False, na_rep="")


def convert_sesame_to_standard(input_path: str, output_path: str, info: dict):
    """转换 SESAME .hug.txt 到标准格式（支持 7 行头和无头两种格式）"""
    with open(input_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    # 检测格式：是否有 # 开头的行为注释
    has_seven_line_header = any(line.startswith("#") for line in all_lines[:7])

    if has_seven_line_header:
        # 标准 SESAME 格式（7行头）
        data_list = []
        columns = []
        line_count = 0
        for line in all_lines:
            line_count += 1
            clean_line = line.rstrip("\n\r")
            if not clean_line:
                continue
            if line_count == 7:
                raw_cols = clean_line.split()
                columns = [c.lstrip("#").strip() for c in raw_cols]
                continue
            if line_count < 8:
                continue
            parts = [p for p in clean_line.split() if p]
            if len(parts) < len(columns):
                continue
            try:
                row_data = [float(p) for p in parts[: len(columns)]]
                data_list.append(row_data)
            except ValueError:
                continue
        df = pd.DataFrame(data_list, columns=columns)
    else:
        # 无头的欧洲格式（如 7360alphaquartz.hug.txt）
        convert_european_to_standard(input_path, output_path, info)
        return

    rho0 = float(info.get("rho0", 2.70))

    # 标准化列名
    rename_map = {}
    col_lower = {c.lower().replace(" ", "").replace("#", ""): c for c in df.columns}

    mapping = {
        "up(km/s)": "Up(km/s)",
        "us(km/s)": "Us(km/s)",
        "us(km/s)7386": "Us(km/s)",
    }
    for key, target in mapping.items():
        if key in col_lower:
            rename_map[col_lower[key]] = target

    for c in df.columns:
        cl = c.lower().replace(" ", "").replace("#", "")
        if "p" in cl and ("mbar" in cl or "p0" in cl):
            rename_map[c] = "P(Mbar)"
        if cl in ("r(g/cm3)", "rho(g/cm3)"):
            rename_map[c] = "rho(g/cm3)"
        if cl == "t(ev)":
            rename_map[c] = "T(eV)"
        if "kj/g" in cl:
            rename_map[c] = "E(MJ/g)"

    df = df.rename(columns=rename_map)

    if "compression" not in df.columns:
        if "rho(g/cm3)" in df.columns:
            df["compression"] = df["rho(g/cm3)"] / rho0
        elif "Us(km/s)" in df.columns and "Up(km/s)" in df.columns:
            denom = df["Us(km/s)"] - df["Up(km/s)"]
            df["compression"] = np.where(
                denom > 0, df["Us(km/s)"] / denom, np.inf
            )

    _write_standard_csv(output_path, df, info)


def convert_european_to_standard(input_path: str, output_path: str, info: dict):
    """转换欧洲逗号格式到标准格式"""
    data_list = []
    columns = []

    with open(input_path, "r", encoding="utf-8") as f:
        header_line = f.readline().strip()
        if not header_line:
            raise ValueError("文件第一行为空")
        # Try tab-split first, fall back to space-split
        if "\t" in header_line:
            columns = header_line.split("\t")
        else:
            columns = header_line.split()
        columns = [c.strip() for c in columns if c.strip()]
        if not columns:
            raise ValueError("未识别到列名")

        for line in f:
            clean_line = line.strip()
            if not clean_line:
                continue
            if "\t" in clean_line:
                parts = clean_line.split("\t")
            else:
                parts = clean_line.split()
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) < len(columns):
                continue
            try:
                row_data = [float(p.replace(",", ".")) for p in parts[: len(columns)]]
                data_list.append(row_data)
            except ValueError:
                continue

    df = pd.DataFrame(data_list, columns=columns)
    rho0 = float(info.get("rho0", 2.04))

    # 标准化列名
    rename_map = {}
    for c in df.columns:
        cl = c.lower().replace(" ", "").replace("_", "")
        if cl in ("up(km/s)", "up(kms)"):
            rename_map[c] = "Up(km/s)"
        # Match "us(km/s)", "us(km/s)7386" etc.
        if cl in ("us(km/s)", "us(kms)") or cl.startswith("us(km/s)") or cl.startswith("us(kms)"):
            rename_map[c] = "Us(km/s)"
        if "p" in cl and ("mbar" in cl or "bar" in cl):
            rename_map[c] = "P(Mbar)"
        if cl.startswith("p") and cl[1:].isdigit():
            rename_map[c] = "P(Mbar)"
        if cl in ("p_sh(mbar)", "psh(mbar)"):
            rename_map[c] = "P(Mbar)"
        if cl in ("r(g/cm3)", "#r(g/cm3)"):
            rename_map[c] = "rho(g/cm3)"
        elif "rho" in cl and "rho0" not in cl and "compression" not in cl:
            rename_map[c] = "rho(g/cm3)"
        if "rho/rho" in c.lower():
            rename_map[c] = "compression"
        if cl == "t(ev)":
            rename_map[c] = "T(eV)"
        if "kj/g" in cl or "j/g" in cl:
            rename_map[c] = "E(MJ/g)"

    df = df.rename(columns=rename_map)

    if "compression" not in df.columns:
        if "rho(g/cm3)" in df.columns:
            df["compression"] = df["rho(g/cm3)"] / rho0

    _write_standard_csv(output_path, df, info)


def convert_excel_to_standard(input_path: str, output_path: str, info: dict):
    """转换 Excel 到标准格式"""
    ext = os.path.splitext(input_path)[1].lower()
    engine = "xlrd" if ext == ".xls" else "openpyxl"
    df = pd.read_excel(input_path, engine=engine)
    df.columns = df.columns.str.strip()
    rho0 = float(info.get("rho0", 2.65))

    rename_map = {}
    for c in df.columns:
        cl = c.lower().replace(" ", "").replace("_", "")
        if cl in ("up(km/s)", "up(kms)"):
            rename_map[c] = "Up(km/s)"
        if cl in ("us(km/s)", "d_sh(kms)", "us(kms)", "d_sh(km/s)", "dsh(km/s)", "dsh(kms)"):
            rename_map[c] = "Us(km/s)"
        if "p" in cl and ("mbar" in cl or "sh(mbar)" in cl):
            rename_map[c] = "P(Mbar)"
        if cl in ("ro_sh(g/cm^3)", "rosh(g/cm^3)", "ro_sh(g/cm3)"):
            rename_map[c] = "rho(g/cm3)"
        if cl in ("t_sh(ev)", "t(ev)", "tsh(ev)"):
            rename_map[c] = "T(eV)"

    df = df.rename(columns=rename_map)

    if "compression" not in df.columns:
        if "rho(g/cm3)" in df.columns:
            df["compression"] = df["rho(g/cm3)"] / rho0
        elif "Us(km/s)" in df.columns and "Up(km/s)" in df.columns:
            denom = df["Us(km/s)"] - df["Up(km/s)"]
            df["compression"] = np.where(denom > 0, df["Us(km/s)"] / denom, np.inf)

    _write_standard_csv(output_path, df, info)


def convert_csv_to_standard(input_path: str, output_path: str, info: dict):
    """转换现有 CSV 到标准格式（列名标准化）"""
    df = pd.read_csv(input_path)
    df.columns = df.columns.str.strip()
    rho0 = float(info.get("rho0", 2.70))

    rename_map = {}
    for c in df.columns:
        cl = c.lower().replace(" ", "")
        if cl in ("up(km/s)", "up(kms)"):
            rename_map[c] = "Up(km/s)"
        if cl in ("us(km/s)", "us(kms)"):
            rename_map[c] = "Us(km/s)"
        if cl == "p(mbar)":
            rename_map[c] = "P(Mbar)"
        if cl == "compression_ratio":
            rename_map[c] = "compression"

    df = df.rename(columns=rename_map)

    if "rho(g/cm3)" not in df.columns:
        if "compression" in df.columns:
            df["rho(g/cm3)"] = rho0 * df["compression"]
        elif "Us(km/s)" in df.columns and "Up(km/s)" in df.columns:
            denom = df["Us(km/s)"] - df["Up(km/s)"]
            df["compression"] = np.where(denom > 0, df["Us(km/s)"] / denom, np.inf)
            df["rho(g/cm3)"] = rho0 * df["compression"]

    if "compression" not in df.columns and "rho(g/cm3)" in df.columns:
        df["compression"] = df["rho(g/cm3)"] / rho0

    _write_standard_csv(output_path, df, info)


def validate_standard_format(file_path: str) -> dict:
    """
    验证标准格式文件完整性。

    Returns
    -------
    dict: {"valid": bool, "errors": [str], "warnings": [str], "stats": dict}
    """
    result = {"valid": True, "errors": [], "warnings": [], "stats": {}}

    if not os.path.exists(file_path):
        result["valid"] = False
        result["errors"].append(f"文件不存在: {file_path}")
        return result

    # 读取头部
    header_lines = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                header_lines.append(line.strip())
            else:
                break

    if len(header_lines) < 7:
        result["valid"] = False
        result["errors"].append(f"元数据头部不足 7 行（当前 {len(header_lines)} 行）")
        return result

    # 解析元数据
    metadata = {}
    for line in header_lines:
        match = re.match(r"#\s*(\w[\w\s]*?):\s*(.*)", line)
        if match:
            metadata[match.group(1).strip()] = match.group(2).strip()

    # 验证必需元数据
    for key in ["Material", "Initial Density (g/cm³)"]:
        if key not in metadata:
            result["warnings"].append(f"缺少元数据: {key}")

    # 读取数据
    try:
        df = pd.read_csv(file_path, sep="\t", comment="#")
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"数据解析失败: {e}")
        return result

    if df.empty:
        result["valid"] = False
        result["errors"].append("数据为空")
        return result

    # 验证必需列
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            result["valid"] = False
            result["errors"].append(f"缺少必需列: {col}")

    if not result["valid"]:
        return result

    # 数值验证
    result["stats"] = {
        "rows": len(df),
        "up_range": (float(df["Up(km/s)"].min()), float(df["Up(km/s)"].max())),
        "p_range": (float(df["P(Mbar)"].min()), float(df["P(Mbar)"].max())),
        "compression_range": (
            float(df["compression"].min()),
            float(df["compression"].max()),
        ),
    }

    # 物理验证
    if (df["compression"] <= 0).any():
        result["warnings"].append("存在非正压缩比")
    if (df["Up(km/s)"] < 0).any():
        result["warnings"].append("存在负粒子速度")
    if (df["P(Mbar)"] < 0).any():
        result["warnings"].append("存在负压力")

    # 单调性检查
    if df["Up(km/s)"].is_monotonic_increasing:
        pass
    else:
        result["warnings"].append("Up 列非单调递增")

    return result


# =============================================================================
# TXT 格式支持
# =============================================================================

TXT_HEADER_TEMPLATE = """# =============================================================================
# Hugoniot Data File
# Format Version: 1.0
# =============================================================================
# Material:          {material}
# Reference:         {reference}
# Initial Density:   {rho0} g/cm^3
# Data Source:       {data_source}
# Date Created:      {date}
# Notes:             {notes}
# =============================================================================
# Column Units:
#   Up      km/s       - Particle velocity
#   Us      km/s       - Shock velocity
#   P       Mbar       - Pressure (1 Mbar = 100 GPa)
#   rho     g/cm^3     - Density
#   eta     -          - Compression ratio (rho/rho0)
#   T       eV         - Temperature (optional)
#   E       MJ/g       - Internal energy (optional)
# =============================================================================
"""


def write_standard_txt(
    output_path: str,
    df: pd.DataFrame,
    material_info: dict,
):
    """将 DataFrame 写入标准格式 TXT（人类可读，避免编码问题）"""
    output_dir = os.path.dirname(output_path)
    if output_dir:  # 只有当目录部分非空时才创建
        os.makedirs(output_dir, exist_ok=True)

    # 确保所有必需列存在
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            if col == "source":
                df[col] = material_info.get("source", "")
            else:
                df[col] = np.nan

    # 确保所有可选列也存在（如果不存在则添加空列）
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            if col == "source":
                df[col] = ""
            else:
                df[col] = np.nan

    # 按标准列顺序排列 - 写入所有列
    cols_to_write = ALL_COLUMNS
    df_out = df[cols_to_write]

    # 准备元数据
    info = {
        "material": material_info.get("material", "Unknown"),
        "reference": material_info.get("reference", ""),
        "rho0": material_info.get("rho0", ""),
        "data_source": material_info.get("data_source", ""),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "notes": material_info.get("notes", ""),
    }

    # 写入文件
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        # 写入格式化头部
        f.write(TXT_HEADER_TEMPLATE.format(**info))

        # 写入列名行（不带#前缀，pandas需要读取列名）
        f.write("\t".join(cols_to_write) + "\n")

        # 写入数据（使用科学计数法，保持精度）
        for _, row in df_out.iterrows():
            values = []
            for col in cols_to_write:
                val = row[col]
                if pd.isna(val):
                    values.append("")
                elif col in ["Up(km/s)", "Us(km/s)", "P(Mbar)", "rho(g/cm3)", "compression"]:
                    # 数值列使用科学计数法
                    values.append(f"{float(val):.8E}")
                elif col == "source":
                    values.append(str(val))
                else:
                    values.append(f"{float(val):.8E}")
            f.write("\t".join(values) + "\n")

        # 写入尾部统计信息
        f.write("# =============================================================================\n")
        f.write("# End of Data\n")
        f.write(f"# Total Points: {len(df_out)}\n")

        # 计算并写入范围，处理NaN值
        up_col = df_out['Up(km/s)'].dropna()
        if len(up_col) > 0:
            f.write(f"# Up Range: [{float(up_col.min()):.5g}, {float(up_col.max()):.5g}] km/s\n")

        p_col = df_out['P(Mbar)'].dropna()
        if len(p_col) > 0:
            f.write(f"# P Range: [{float(p_col.min()):.5g}, {float(p_col.max()):.5g}] Mbar\n")

        if "compression" in df_out.columns:
            comp_col = df_out['compression'].dropna()
            if len(comp_col) > 0:
                f.write(f"# Compression Range: [{float(comp_col.min()):.5g}, {float(comp_col.max()):.5g}]\n")

        f.write("# =============================================================================\n")


def read_standard_txt(filepath: str) -> pd.DataFrame:
    """读取标准格式 TXT 文件"""
    # TXT 格式与 CSV 格式使用相同的分隔符和注释符
    # 可以直接使用 pandas 的 read_csv
    df = pd.read_csv(
        filepath,
        sep="\t",
        comment="#",
        skipinitialspace=True,
        encoding="utf-8",
    )

    # 清理列名
    df.columns = df.columns.str.strip()

    # 删除全空行
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df
