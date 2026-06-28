#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IM Tool 发布包打包脚本。

将项目打包为一个面向最终用户的 zip 压缩包，包含：
- im_app/（应用代码 + 标准材料库）
- scripts/、docs/、README.md、requirements.txt、run_app.py、run_app.bat、pyproject.toml
- 自动生成的 快速开始.md

排除：__pycache__、.claude、dist、egg-info、tests、reference（legacy notebooks）、
      CLAUDE.md、new_demand.md、verify_fixes.py、test_simple.py 等。

用法：
    python scripts/package_release.py [--version 1.1.0]
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 需要复制的顶层文件
TOP_FILES = [
    "README.md",
    "requirements.txt",
    "run_app.py",
    "run_app.bat",
    "pyproject.toml",
]

# 需要复制的目录（完整复制，复制时按 IGNORE_PATTERNS 过滤）
TOP_DIRS = [
    "im_app",
    "scripts",
    "docs",
]

# 复制目录时需要跳过的相对子路径（按目录名匹配）
SKIP_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".git",
    ".idea",
    ".vscode",
    "egg-info",
}

# im_app/standard_library/materials 中同时存在 .csv 和 .txt，
# .txt 是当前默认格式；保留 .txt 以减小体积，但 .csv 也保留（data_loader 都能读）。
# 这里不做剔除，两种都保留以兼容老工作流。

# 标准库中已知不需要打包的子目录
SKIP_STANDARD_SUBDIRS = {"validators"}  # validators 目录是开发用，目前为空


def _ignore_patterns(directory, names: list[str]) -> set[str]:
    """shutil.copytree 的 ignore 回调，过滤缓存/IDE 目录。"""
    ignored = set()
    for name in names:
        if name in SKIP_DIR_NAMES:
            ignored.add(name)
    # 跳过标准库里的 validators 子目录
    dir_name = Path(directory).name
    if dir_name == "standard_library":
        for sub in SKIP_STANDARD_SUBDIRS:
            if sub in names:
                ignored.add(sub)
    return ignored


def stage_files(stage_root: Path) -> list[Path]:
    """把所有需要的文件复制到暂存目录，返回已复制的顶层条目列表。"""
    staged: list[Path] = []

    for name in TOP_FILES:
        src = PROJECT_ROOT / name
        if not src.exists():
            print(f"  ! 跳过缺失文件: {name}")
            continue
        dst = stage_root / name
        shutil.copy2(src, dst)
        staged.append(dst)

    for name in TOP_DIRS:
        src = PROJECT_ROOT / name
        if not src.exists():
            print(f"  ! 跳过缺失目录: {name}")
            continue
        dst = stage_root / name
        shutil.copytree(src, dst, ignore=_ignore_patterns, dirs_exist_ok=False)
        staged.append(dst)

    return staged


def write_quickstart(stage_root: Path, version: str) -> Path:
    """写入面向最终用户的 快速开始.md。"""
    content = f"""# IM Tool v{version} 快速开始

本压缩包是 **IM Tool（阻抗匹配分析工具）** 的发布版本，已内置完整材料库，
解压后即可运行。下面是首次使用的最短路径。

---

## 1. 环境要求

- **Python 3.9 及以上**（推荐 3.10 / 3.11）
- 操作系统：Windows / macOS / Linux 均可
- 建议使用干净的虚拟环境，避免依赖冲突

## 2. 安装步骤

### Windows 用户

解压后进入目录，**双击 `run_app.bat`** 即可（首次运行前需先安装依赖）。

或手动操作：

```bat
:: 在解压后的目录中打开 cmd
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
run_app.bat
```

### macOS / Linux 用户

```bash
cd /path/to/im-tool-v{version}
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_app.py
```

> 国内网络可加镜像源加速：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 3. 验证安装

成功启动后会弹出一个最大化窗口，左侧出现材料选择面板，**默认勾选若干材料**
（Al、Quartz 等），右侧 P-Up 图自动绘制出对应 Hugoniot 曲线。若看到曲线，则说明安装成功。

## 4. 内置材料库

材料库位于 `im_app/standard_library/materials/`，启动时通过
`im_app/standard_library/metadata.json` 自动索引。当前包含 10 种材料：

- Aluminum（SESAME 3717 / 3720、Celliers 2005、FEOS）
- Alpha Quartz（SESAME 7360 / 7385、Hamel 2012）
- BN（LEA SESAME）
- CH foam（理想等离子体解析模型）

参考曲线位于 `im_app/standard_library/reference_curves/`。

## 5. 想添加自己的材料？

- **方式一**：在 GUI 中点击左侧面板的「添加材料」按钮，跟随向导导入原始数据文件。
- **方式二**：把符合标准格式的 `.txt` 文件放入 `im_app/standard_library/materials/`，
  并在 `metadata.json` 中登记一条记录。格式规范见
  `im_app/standard_library/FORMAT_SPECIFICATION.md`。

## 6. 常见问题

| 现象 | 解决方法 |
|------|---------|
| 启动时报 `ModuleNotFoundError: No module named 'PyQt5'` | 依赖未装，回到第 2 步执行 `pip install -r requirements.txt` |
| 中文显示成方块 | 安装中文字体或检查 matplotlib 字体配置（`im_app/core/plot_style.py`） |
| 启动后窗口白屏 | 显卡驱动问题，尝试 `QT_OPENGL=software python run_app.py` |
| 想恢复默认视图 | 在图上点一下获取焦点，按 `a` 键重置 |

## 7. 完整文档

更详细的功能说明请阅读同目录下的 **`README.md`**。

数据格式规范、用户手册位于 `im_app/standard_library/` 下：
- `FORMAT_SPECIFICATION.md`
- `USER_GUIDE.md`

理论背景与算法实现可参考 `docs/` 目录。

---

祝科研顺利！如有问题请附上 `README.md` 中的作者信息联系方式反馈。
"""
    dst = stage_root / "快速开始.md"
    dst.write_text(content, encoding="utf-8")
    return dst


def make_zip(stage_root: Path, zip_path: Path) -> None:
    """把暂存目录打包成 zip，保留目录结构。"""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(stage_root.rglob("*")):
            if path.is_file():
                arcname = path.relative_to(stage_root.parent)
                zf.write(path, arcname)


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def main() -> int:
    parser = argparse.ArgumentParser(description="打包 IM Tool 发布版")
    parser.add_argument("--version", default="1.1.0", help="版本号（默认 1.1.0）")
    args = parser.parse_args()

    version = args.version
    pkg_name = f"im-tool-v{version}"
    dist_dir = PROJECT_ROOT / "dist"
    stage_root = dist_dir / pkg_name
    zip_path = dist_dir / f"{pkg_name}.zip"

    print(f"==> 打包 IM Tool v{version}")
    print(f"    暂存目录: {stage_root}")

    if stage_root.exists():
        print(f"    清理旧暂存目录...")
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True)

    print(f"==> 复制文件...")
    staged = stage_files(stage_root)
    for entry in staged:
        rel = entry.relative_to(stage_root)
        kind = "目录" if entry.is_dir() else "文件"
        print(f"    [{kind}] {rel}")

    print(f"==> 生成 快速开始.md ...")
    write_quickstart(stage_root, version)

    print(f"==> 统计文件数...")
    total_files = sum(1 for _ in stage_root.rglob("*") if _.is_file())
    total_size = sum(p.stat().st_size for p in stage_root.rglob("*") if p.is_file())
    print(f"    共 {total_files} 个文件，{human_size(total_size)}")

    print(f"==> 压缩为 zip: {zip_path}")
    make_zip(stage_root, zip_path)
    zip_size = zip_path.stat().st_size
    print(f"    zip 大小: {human_size(zip_size)}")

    print(f"==> 清理暂存目录...")
    shutil.rmtree(stage_root)

    print()
    print(f"完成! 发布包位于: {zip_path}")
    print(f"     压缩率: {zip_size / total_size * 100:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
