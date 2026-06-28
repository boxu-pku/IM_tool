#!/usr/bin/env python3
"""
批量转换现有 Hugoniot 数据到标准格式

用法: python scripts/convert_to_standard.py
"""

import os
import sys
import json

# 确保项目根目录在路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from im_app.core.data_converter import (
    convert_sesame_to_standard,
    convert_european_to_standard,
    convert_excel_to_standard,
    convert_csv_to_standard,
    validate_standard_format,
)

REFERENCE_DIR = os.path.join(project_root, "reference", "Hugoniot_curve")
LIB_DIR = os.path.join(project_root, "im_app", "standard_library", "materials")

CONVERSION_CONFIG = [
    {
        "input": "3717.hug.txt",
        "output": "Al_3717_sesame.csv",
        "format": "sesame",
        "material": "Aluminum",
        "reference": "SESAME 3717",
        "rho0": 2.70,
        "data_source": "Los Alamos National Laboratory",
        "notes": "Principal Hugoniot from SESAME EOS table 3717",
    },
    {
        "input": "3720.hug.txt",
        "output": "Al_3720_sesame.csv",
        "format": "sesame",
        "material": "Aluminum",
        "reference": "SESAME 3720",
        "rho0": 2.70,
        "data_source": "Los Alamos National Laboratory",
        "notes": "Alternative Aluminum Hugoniot from SESAME EOS table 3720",
    },
    {
        "input": "7360alphaquartz.hug.txt",
        "output": "Quartz_7360_sesame.csv",
        "format": "european",
        "material": "Alpha Quartz",
        "reference": "SESAME 7360",
        "rho0": 2.65,
        "data_source": "Los Alamos National Laboratory",
        "notes": "Alpha Quartz Hugoniot from SESAME EOS table 7360",
    },
    {
        "input": "Hugoniot A-quartz 7385 tab.xls",
        "output": "Quartz_7385_sesame.csv",
        "format": "excel",
        "material": "Alpha Quartz",
        "reference": "SESAME 7385",
        "rho0": 2.65,
        "data_source": "Los Alamos National Laboratory",
        "notes": "Alpha Quartz Hugoniot from SESAME EOS table 7385 (Excel source)",
    },
    {
        "input": "BN hugoniot.txt",
        "output": "BN_LEA.csv",
        "format": "european",
        "material": "Boron Nitride",
        "reference": "LEA SESAME",
        "rho0": 2.04,
        "data_source": "Lawrence Livermore National Laboratory",
        "notes": "Hexagonal BN Hugoniot from LEA/SESAME",
    },
    {
        "input": os.path.join("复现zhanghuan使用的Hugoniot", "Al_Hugoniot.csv"),
        "output": "Al_Celliers2005.csv",
        "format": "csv",
        "material": "Aluminum",
        "reference": "Celliers et al. 2005, PRL",
        "rho0": 2.70,
        "data_source": "Analytical fit: Us = 17.992 + 1.167*(up - 9.838)",
        "notes": "Aluminum Hugoniot from Celliers et al. 2005 linear Us-Up fit",
    },
    {
        "input": os.path.join("复现zhanghuan使用的Hugoniot", "Quartz_Hugoniot_uniform.csv"),
        "output": "Quartz_Hamel2012.csv",
        "format": "csv",
        "material": "Alpha Quartz",
        "reference": "Hamel et al. 2012",
        "rho0": 2.65,
        "data_source": "Analytical fit: Us = 2.4 + 1.68*up - 0.0155*up^2",
        "notes": "Quartz Hugoniot from Hamel et al. 2012 quadratic Us-Up fit (regenerated with uniform spacing)",
    },
    {
        "input": os.path.join("复现zhanghuan使用的Hugoniot", "LASL_BN_extract.csv"),
        "output": "BN_LASL_extract.csv",
        "format": "csv_gbk",
        "material": "Boron Nitride",
        "reference": "LASL Shock Hugoniot Data",
        "rho0": 2.04,
        "data_source": "LASL Shock Compendium (extracted)",
        "notes": "BN experimental data extracted from LASL shock Hugoniot compendium",
    },
]

CONVERTERS = {
    "sesame": convert_sesame_to_standard,
    "european": convert_european_to_standard,
    "excel": convert_excel_to_standard,
    "csv": convert_csv_to_standard,
    "csv_gbk": None,  # handled specially below
}


def convert_csv_gbk_to_standard(input_path, output_path, info):
    """转换 GBK 编码的 CSV"""
    import pandas as _pd
    # LASL file has metadata in first row, header in second row
    df = _pd.read_csv(input_path, encoding="gbk", on_bad_lines="skip", header=1)
    df.columns = df.columns.str.strip()
    rho0 = float(info.get("rho0", 2.04))

    rename_map = {}
    for c in df.columns:
        cl = c.lower().replace(" ", "")
        if cl in ("up(km/s)", "up(kms)"):
            rename_map[c] = "Up(km/s)"
        if cl in ("us(km/s)", "us(kms)"):
            rename_map[c] = "Us(km/s)"
        if cl == "p(mbar)":
            rename_map[c] = "P(Mbar)"
        if cl == "p(gpa)":
            df[c] = _pd.to_numeric(df[c], errors="coerce") / 100.0
            rename_map[c] = "P(Mbar)"
        if cl == "compression_ratio":
            rename_map[c] = "compression"
        if cl == "v/v0":
            rename_map[c] = "compression"
        if cl == "rho" and "rho0" not in c:
            rename_map[c] = "rho(g/cm3)"

    df = df.rename(columns=rename_map)

    # 只保留数值行
    if "Up(km/s)" in df.columns:
        df = df[_pd.to_numeric(df["Up(km/s)"], errors="coerce").notna()].copy()
        for col in df.columns:
            df[col] = _pd.to_numeric(df[col], errors="coerce")

    if "rho(g/cm3)" not in df.columns and "compression" in df.columns:
        df["rho(g/cm3)"] = rho0 * df["compression"]
    if "compression" not in df.columns and "rho(g/cm3)" in df.columns:
        df["compression"] = df["rho(g/cm3)"] / rho0

    from im_app.core.data_converter import _write_standard_csv
    _write_standard_csv(output_path, df, info)


def generate_metadata_index(converted_files: list):
    """生成 metadata.json 索引"""
    metadata = {"version": "1.0", "materials": []}

    for item in converted_files:
        output_path = os.path.join(LIB_DIR, item["output"])
        validation = validate_standard_format(output_path)

        entry = {
            "id": os.path.splitext(item["output"])[0],
            "name": item["material"],
            "source": item["reference"],
            "rho0": item["rho0"],
            "file": f"materials/{item['output']}",
            "tags": item.get("tags", []),
        }

        if validation["valid"] and "stats" in validation:
            stats = validation["stats"]
            entry["points"] = stats["rows"]
            entry["up_range"] = list(stats["up_range"])
            entry["p_range"] = list(stats["p_range"])
            entry["compression_range"] = list(stats["compression_range"])

        metadata["materials"].append(entry)

    # 写入 metadata.json
    meta_path = os.path.join(os.path.dirname(LIB_DIR), "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    print(f"\n元数据索引已生成: {meta_path}")


def main():
    import io, sys
    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    os.makedirs(LIB_DIR, exist_ok=True)

    converted = []
    errors = []

    for config in CONVERSION_CONFIG:
        input_path = os.path.join(REFERENCE_DIR, config["input"])
        output_path = os.path.join(LIB_DIR, config["output"])

        if not os.path.exists(input_path):
            print(f"SKIP {config['input']}: file not found")
            errors.append(f"File not found: {config['input']}")
            continue

        print(f"Converting: {config['input']}")

        try:
            if config["format"] == "csv_gbk":
                convert_csv_gbk_to_standard(input_path, output_path, config)
            else:
                converter = CONVERTERS[config["format"]]
                converter(input_path, output_path, config)

            # 验证
            validation = validate_standard_format(output_path)
            if validation["valid"]:
                stats = validation["stats"]
                print(
                    f"  -> {config['output']}: {stats['rows']} rows, "
                    f"Up=[{stats['up_range'][0]:.2f}, {stats['up_range'][1]:.2f}], "
                    f"P=[{stats['p_range'][0]:.4f}, {stats['p_range'][1]:.4f}]"
                )
                for w in validation["warnings"]:
                    print(f"  WARNING: {w}")
                converted.append(config)
            else:
                print(f"  ERROR: validation failed")
                for e in validation["errors"]:
                    print(f"    {e}")
                errors.append(f"Validation failed: {config['output']}")

        except Exception as e:
            print(f"  ERROR: {e}")
            errors.append(f"Conversion failed: {config['input']}: {e}")

    # 生成索引
    generate_metadata_index(converted)

    # 总结
    print(f"\n=== Conversion Complete ===")
    print(f"Success: {len(converted)}")
    print(f"Failed: {len(errors)}")
    if errors:
        print("Errors:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
