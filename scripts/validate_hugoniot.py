"""
Hugoniot 数据文件格式验证工具

独立脚本版本，可直接运行: python scripts/validate_hugoniot.py <文件路径>

用法:
    python scripts/validate_hugoniot.py <文件路径>

示例:
    python scripts/validate_hugoniot.py materials/Al_3717_sesame.txt
    python scripts/validate_hugoniot.py ../my_data.txt
"""

import sys
import os

# 添加项目根目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

# 导入验证模块
from im_app.tools.validate_hugoniot import main

if __name__ == "__main__":
    main()
