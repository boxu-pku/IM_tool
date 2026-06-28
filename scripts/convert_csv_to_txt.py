"""
批量将标准库中的CSV文件转换为TXT格式

用法:
    python scripts/convert_csv_to_txt.py
"""

import json
import os
from pathlib import Path

import pandas as pd

# 添加项目根目录到路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from im_app.core.data_converter import write_standard_txt


def extract_metadata_from_csv(csv_path: str) -> dict:
    """从CSV文件中提取元数据"""
    metadata = {
        "material": "Unknown",
        "reference": "",
        "rho0": "",
        "data_source": "",
        "notes": "",
    }

    with open(csv_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('# Material:'):
                metadata['material'] = line.split(':', 1)[1].strip()
            elif line.startswith('# Reference:'):
                metadata['reference'] = line.split(':', 1)[1].strip()
            elif line.startswith('# Initial Density'):
                # 提取数值部分
                parts = line.split(':')
                if len(parts) > 1:
                    value_part = parts[1].strip()
                    # 提取数字（去掉单位）
                    try:
                        metadata['rho0'] = float(value_part.split()[0])
                    except:
                        pass
            elif line.startswith('# Data Source:'):
                metadata['data_source'] = line.split(':', 1)[1].strip()
            elif line.startswith('# Notes:'):
                metadata['notes'] = line.split(':', 1)[1].strip()
            elif not line.startswith('#'):
                break

    return metadata


def convert_library_csv_to_txt():
    """将标准库中的所有CSV文件转换为TXT格式"""

    # 路径设置
    base_dir = Path(__file__).parent.parent
    lib_dir = base_dir / 'im_app' / 'standard_library'
    materials_dir = lib_dir / 'materials'
    metadata_path = lib_dir / 'metadata.json'

    print(f"标准库目录: {lib_dir}")
    print(f"材料目录: {materials_dir}")
    print(f"元数据文件: {metadata_path}")
    print()

    # 读取现有元数据
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata_json = json.load(f)

    # 转换每个材料
    converted_count = 0
    for material in metadata_json['materials']:
        # 确定源文件：优先使用.csv，如果不存在则使用当前file
        current_file = material['file']
        if current_file.endswith('.txt'):
            # 如果当前是txt，尝试找对应的csv
            csv_file = current_file.replace('.txt', '.csv')
            csv_path = lib_dir / csv_file
            if not csv_path.exists():
                # CSV不存在，使用当前的TXT作为源
                csv_file = current_file
                csv_path = lib_dir / csv_file
        else:
            csv_file = current_file
            csv_path = lib_dir / csv_file

        if not csv_path.exists():
            print(f"[WARN] File not found: {csv_path}")
            continue

        # 读取源数据（CSV或TXT都可以，因为格式兼容）
        try:
            df = pd.read_csv(csv_path, sep='\t', comment='#', encoding='utf-8')
        except Exception as e:
            print(f"[ERROR] Failed to read source {csv_file}: {e}")
            continue

        # 提取元数据
        source_metadata = extract_metadata_from_csv(str(csv_path))

        # 生成TXT文件名（确保是.txt）
        if csv_file.endswith('.csv'):
            txt_filename = csv_file.replace('.csv', '.txt')
        else:
            txt_filename = csv_file  # 已经是.txt
        txt_path = lib_dir / txt_filename

        # 写入TXT文件
        material_info = {
            'material': source_metadata['material'],
            'reference': source_metadata['reference'],
            'rho0': source_metadata.get('rho0', material.get('rho0', '')),
            'data_source': source_metadata['data_source'],
            'notes': source_metadata['notes'],
        }

        try:
            write_standard_txt(str(txt_path), df, material_info)
            print(f"[OK] Converted: {csv_file} -> {txt_filename}")
            converted_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to write TXT {txt_filename}: {e}")
            continue

        # 更新元数据中的文件路径
        material['file'] = txt_filename

    # 保存更新后的元数据
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata_json, f, indent=4, ensure_ascii=False)

    print()
    print(f"[DONE] Conversion complete! Total files converted: {converted_count}")
    print(f"[INFO] Metadata updated, all materials now use .txt format")


if __name__ == '__main__':
    convert_library_csv_to_txt()
