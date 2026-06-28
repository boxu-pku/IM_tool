"""
参考曲线数据加载器

支持简单的CSV格式参考曲线数据：
- 第一行：列名称（必须匹配标准变量名）
- 第二行：单位
- 第三行开始：数据

标准变量名：Up, Us, P, rho, compression, T, E
"""

import os
from typing import Optional
import numpy as np
import pandas as pd


# 标准变量名映射
VARIABLE_MAPPING = {
    "Up": "up",
    "Us": "us",
    "P": "p",
    "rho": "rho",
    "compression": "compression",
    "T": "temperature",
    "E": "energy",
}


def load_reference_curve(filepath: str) -> dict:
    """
    加载参考曲线CSV文件。

    Parameters
    ----------
    filepath : str
        CSV文件路径

    Returns
    -------
    dict
        包含以下键的字典：
        - "name": 曲线名称（从文件名提取）
        - "variables": 变量名列表
        - "units": 单位列表
        - "data": DataFrame, 数据
        - "columns": 列名到标准字段名的映射

    Raises
    ------
    FileNotFoundError
        文件不存在
    ValueError
        文件格式不正确
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if len(lines) < 3:
        raise ValueError(f"文件格式错误：至少需要3行（列名、单位、数据）")

    # 第一行：列名称
    column_names = [name.strip() for name in lines[0].strip().split(',')]
    if not column_names:
        raise ValueError("第一行必须包含列名称")

    # 第二行：单位
    units = [unit.strip() for unit in lines[1].strip().split(',')]
    if len(units) != len(column_names):
        raise ValueError(f"单位数量({len(units)})与列数量({len(column_names)})不匹配")

    # 第三行开始：数据
    data_lines = [line.strip() for line in lines[2:] if line.strip()]
    if not data_lines:
        raise ValueError("文件中没有数据")

    # 解析数据
    data_list = []
    for line in data_lines:
        values = [v.strip() for v in line.split(',')]
        if len(values) != len(column_names):
            continue  # 跳过格式不正确的行
        try:
            data_list.append([float(v) if v else np.nan for v in values])
        except ValueError:
            continue

    if not data_list:
        raise ValueError("没有有效的数据行")

    # 创建DataFrame
    df = pd.DataFrame(data_list, columns=column_names)

    # 验证列名是否匹配标准变量名
    valid_columns = {}
    for col in column_names:
        if col in VARIABLE_MAPPING:
            valid_columns[col] = VARIABLE_MAPPING[col]
        else:
            raise ValueError(f"不支持的列名称: {col}。支持的名称: {list(VARIABLE_MAPPING.keys())}")

    # 从文件名提取曲线名称
    curve_name = os.path.splitext(os.path.basename(filepath))[0]

    return {
        "name": curve_name,
        "variables": column_names,
        "units": units,
        "data": df,
        "columns": valid_columns,
        "filepath": filepath,
    }


def save_reference_curve(
    filepath: str,
    curve_name: str,
    variables: list,
    units: list,
    data: np.ndarray,
) -> None:
    """
    保存参考曲线到CSV文件。

    Parameters
    ----------
    filepath : str
        保存路径
    curve_name : str
        曲线名称（用于文件名）
    variables : list
        变量名列表
    units : list
        单位列表
    data : np.ndarray
        数据数组 (n_samples, n_variables)
    """
    # 验证
    if len(variables) != len(units):
        raise ValueError("变量数量与单位数量不匹配")

    if data.shape[1] != len(variables):
        raise ValueError(f"数据列数({data.shape[1]})与变量数量({len(variables)})不匹配")

    # 验证变量名
    for var in variables:
        if var not in VARIABLE_MAPPING:
            raise ValueError(f"不支持的变量名: {var}")

    # 确保目录存在
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # 写入文件
    with open(filepath, 'w', encoding='utf-8') as f:
        # 第一行：列名称
        f.write(','.join(variables) + '\n')
        # 第二行：单位
        f.write(','.join(units) + '\n')
        # 数据行
        for row in data:
            f.write(','.join([f'{v:.6g}' if np.isfinite(v) else '' for v in row]) + '\n')


def list_reference_curves(curve_dir: str) -> list:
    """
    列出参考曲线目录中的所有曲线。

    Parameters
    ----------
    curve_dir : str
        参考曲线目录

    Returns
    -------
    list
        曲线信息列表，每个元素包含：
        - "name": 曲线名称
        - "filepath": 文件路径
        - "variables": 变量列表
    """
    curves = []
    if not os.path.isdir(curve_dir):
        return curves

    for filename in os.listdir(curve_dir):
        if not filename.lower().endswith('.csv'):
            continue

        filepath = os.path.join(curve_dir, filename)
        try:
            info = load_reference_curve(filepath)
            curves.append({
                "name": info["name"],
                "filepath": filepath,
                "variables": info["variables"],
            })
        except Exception:
            # 跳过无法加载的文件
            continue

    return curves
