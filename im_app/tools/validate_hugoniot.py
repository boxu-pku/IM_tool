"""
Hugoniot 数据文件格式验证工具

用法:
    python -m im_app.tools.validate_hugoniot <文件路径>

示例:
    python -m im_app.tools.validate_hugoniot im_app/standard_library/materials/Al_Celliers2005.txt
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# 标准列名定义
REQUIRED_COLUMNS = ["Up(km/s)", "Us(km/s)", "P(Mbar)", "rho(g/cm3)", "compression"]
OPTIONAL_COLUMNS = ["T(eV)", "E(MJ/g)", "source"]
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class ValidationResult:
    """验证结果类"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.valid = True
        self.errors = []
        self.warnings = []
        self.info = {}

    def add_error(self, msg: str):
        """添加错误信息"""
        self.valid = False
        self.errors.append(msg)

    def add_warning(self, msg: str):
        """添加警告信息"""
        self.warnings.append(msg)

    def add_info(self, key: str, value):
        """添加信息"""
        self.info[key] = value

    def print_report(self):
        """打印验证报告"""
        print(f"{'='*60}")
        print(f"File: {self.filepath}")
        print(f"{'='*60}")

        if self.valid:
            print("[OK] Format validation passed")
        else:
            print("[FAIL] Format validation failed")

        print()

        # 打印信息
        if self.info:
            print("File Info:")
            for key, value in self.info.items():
                print(f"  {key}: {value}")
            print()

        # 打印警告
        if self.warnings:
            print("Warnings:")
            for warning in self.warnings:
                print(f"  [WARN] {warning}")
            print()

        # 打印错误
        if self.errors:
            print("Errors:")
            for error in self.errors:
                print(f"  [ERROR] {error}")
            print()

        print(f"{'='*60}")


def validate_file_exists(result: ValidationResult) -> bool:
    """验证文件存在"""
    if not os.path.isfile(result.filepath):
        result.add_error("文件不存在")
        return False
    return True


def validate_file_encoding(result: ValidationResult) -> bool:
    """验证文件编码（UTF-8）"""
    try:
        with open(result.filepath, 'r', encoding='utf-8') as f:
            f.read(100)  # 尝试读取前100个字符
        return True
    except UnicodeDecodeError:
        result.add_error("文件编码不是 UTF-8，请使用 UTF-8 编码保存")
        return False


def validate_header(result: ValidationResult):
    """验证文件头部"""
    with open(result.filepath, 'r', encoding='utf-8') as f:
        lines = []
        for i, line in enumerate(f):
            if i >= 50:  # 只检查前50行
                break
            lines.append(line.rstrip('\n'))

    # 检查是否有足够的头部信息
    if len(lines) < 10:
        result.add_error("文件行数过少，可能缺少头部信息")
        return

    # 检查是否有文件标识
    has_file_marker = any("# Hugoniot Data File" in line for line in lines)
    if not has_file_marker:
        result.add_warning("缺少文件标识 '# Hugoniot Data File'")

    # 检查必需的元数据字段
    metadata_fields = {
        "# Material:": "material name",
        "# Reference:": "reference",
        "# Initial Density": "initial density",
    }

    for field, field_name in metadata_fields.items():
        has_field = any(line.startswith(field) for line in lines)
        if not has_field:
            result.add_error(f"缺少必需的元数据字段: {field} ({field_name})")

    # 提取并存储元数据信息
    for line in lines:
        if line.startswith("# Material:"):
            result.add_info("Material", line.split(":", 1)[1].strip())
        elif line.startswith("# Reference:"):
            result.add_info("Reference", line.split(":", 1)[1].strip())
        elif line.startswith("# Initial Density"):
            try:
                rho0 = line.split(":")[1].strip().split()[0]
                result.add_info("Initial Density (g/cm^3)", rho0)
            except:
                pass


def validate_data_columns(result: ValidationResult):
    """Validate data columns"""
    try:
        df = pd.read_csv(
            result.filepath,
            sep="\t",
            comment="#",
            skipinitialspace=True,
            encoding="utf-8",
        )
    except Exception as e:
        result.add_error(f"数据解析失败: {e}")
        return

    # 检查是否为空
    if df.empty:
        result.add_error("数据为空")
        return

    # 存储数据信息
    result.add_info("Number of points", len(df))
    result.add_info("Number of columns", len(df.columns))

    # 检查必需列
    missing_cols = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_cols:
        result.add_error(f"缺少必需列: {', '.join(missing_cols)}")

    # 检查列名正确性
    for col in df.columns:
        if col.strip() != col:
            result.add_warning(f"列名 '{col}' 包含前后空格")

    # 数值验证
    if "Up(km/s)" in df.columns:
        up = df["Up(km/s)"]
        if (up < 0).any():
            result.add_error("存在负粒子速度 (Up < 0)")
        if up.is_monotonic_increasing:
            pass
        else:
            result.add_warning("Up 列非单调递增")

        if len(up) > 0:
            result.add_info("Up range (km/s)", f"[{up.min():.5g}, {up.max():.5g}]")

    if "P(Mbar)" in df.columns:
        p = df["P(Mbar)"]
        if (p < 0).any():
            result.add_error("存在负压力 (P < 0)")

        if len(p) > 0:
            result.add_info("P range (Mbar)", f"[{p.min():.5g}, {p.max():.5g}]")

    if "compression" in df.columns:
        comp = df["compression"]
        if (comp <= 0).any():
            result.add_warning("存在非正压缩比 (compression <= 0)")
        elif (comp < 1.0).any():
            result.add_warning("存在小于1的压缩比 (compression < 1，非压缩状态)")

        if len(comp) > 0:
            result.add_info("Compression ratio range", f"[{comp.min():.5g}, {comp.max():.5g}]")

    # 检查缺失值
    for col in REQUIRED_COLUMNS:
        if col in df.columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                result.add_error(f"必需列 '{col}' 有 {null_count} 个缺失值")

    # 检查重复行
    if df.duplicated().sum() > 0:
        result.add_warning(f"存在 {df.duplicated().sum()} 个重复数据行")

    return df


def validate_line_endings(result: ValidationResult):
    """Validate line endings (should be LF, not CRLF)"""
    with open(result.filepath, 'rb') as f:
        content = f.read()

    cr_count = content.count(b'\r')
    lf_count = content.count(b'\n')

    if cr_count > 0 and lf_count > 0:
        # 可能有 CRLF
        crlf_count = content.count(b'\r\n')
        if crlf_count > 0:
            result.add_warning(f"检测到 CRLF 行尾符 ({crlf_count} 处)，建议使用 LF")

    # 检查是否有双回车
    crcrlf_count = content.count(b'\r\r\n')
    if crcrlf_count > 0:
        result.add_error(f"检测到双回车行尾符 ({crcrlf_count} 处 \\r\\r\\n)，这会导致数据列错位")


def validate_file(filepath: str) -> ValidationResult:
    """完整验证文件"""
    result = ValidationResult(filepath)

    # 基础检查
    if not validate_file_exists(result):
        return result

    if not validate_file_encoding(result):
        return result

    # 行尾符检查
    validate_line_endings(result)

    # 头部验证
    validate_header(result)

    # 数据列验证
    validate_data_columns(result)

    return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="验证 Hugoniot 数据文件格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s materials/Al_3717_sesame.txt
  %(prog)s /path/to/hugoniot.txt
        """
    )

    parser.add_argument(
        "filepath",
        help="Hugoniot 数据文件路径 (.txt)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细信息"
    )

    args = parser.parse_args()

    # 验证文件
    result = validate_file(args.filepath)

    # 打印报告
    result.print_report()

    # 返回码
    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
