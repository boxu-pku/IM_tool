# IM Tool 桌面安装 · Desktop installation

| 系统 / Platform | 1.2.4 安装包 / Installer | 安装和启动 / Install and launch |
| --- | --- | --- |
| Windows 10 / 11 x64 | `IM-Tool-Setup-1.2.4-x64.exe` | 双击，选择简体中文或英语，完成向导并从“开始”菜单启动。Double-click, choose a language, then launch IM Tool from Start. |
| Debian / Ubuntu | `im-tool_1.2.4-1_all.deb` | 用软件安装器打开或运行 `sudo apt install ./im-tool_1.2.4-1_all.deb`。Open the package in the software installer or use APT. |
| Fedora | `im-tool-1.2.4-1.noarch.rpm` | 用软件安装器打开或运行 `sudo dnf install ./im-tool-1.2.4-1.noarch.rpm`。Open the package in the software installer or use DNF. |
| macOS · Apple silicon | [IM-Tool-1.2.4-macOS-arm64.dmg](https://github.com/boxu-pku/IM_tool/releases/download/macos-v1.2.4/IM-Tool-1.2.4-macOS-arm64.dmg) | 拖入“应用程序”。Drag the app to Applications. |
| macOS · Intel | [IM-Tool-1.2.4-macOS-x86_64.dmg](https://github.com/boxu-pku/IM_tool/releases/download/macos-v1.2.4/IM-Tool-1.2.4-macOS-x86_64.dmg) | 拖入“应用程序”。Drag the app to Applications. |

在 Linux 应用菜单中搜索 **IM Tool**，也可在图形桌面的终端运行 `im-tool`。桌面初始库含 13 条常用参考表。软件首次启动时为当前用户创建可写副本。选择 **Help → Open Working Folder** 可找到当前材料库。通过 **Help → Open Practice Workspace** 可打开 `Al_Celliers2005` 与 `Quartz_Hamel2012` 两条标准曲线及 Hicks 第 29400 号实验的两条瑞利线，练习文件保存在 `Practice/Celliers-Hamel`。

On Linux, search the application menu for **IM Tool** or run `im-tool` in a desktop terminal. The desktop edition seeds a writable per-user library with 13 reference tables. **Help → Open Working Folder** opens the active library. **Help → Open Practice Workspace** opens the Celliers aluminum and Hamel alpha-quartz standards with the measured-speed lines for Hicks shot 29400 in `Practice/Celliers-Hamel`. Both manuals are available in Help. [中文手册](../im_app/resources/manuals/im-tool-zh.pdf) · [English manual](../im_app/resources/manuals/im-tool-en.pdf)

## macOS

在苹果菜单的“关于本机”中查看芯片。Apple M 系列选 `arm64`，Intel 选 `x86_64`。双击磁盘映像，将 **IM Tool.app** 拖到窗口中的 **Applications** 快捷方式。拷贝完成后推出映像，从“应用程序”打开软件。两个版本均自带 Python、Qt、中英文手册和铝–石英练习。

Check **About This Mac** in the Apple menu. Choose `arm64` for an Apple M-series chip or `x86_64` for Intel. Open the DMG, drag **IM Tool.app** onto **Applications**, eject the image, then launch the installed app. The Python runtime, Qt, manuals and practice workspace are bundled.

本版采用临时签名，未经 Apple 公证。如果系统阻止首次打开，核对来源后可在“系统设置 → 隐私与安全性”中为 IM Tool 选择“仍要打开”。The app is ad hoc signed and has no Apple notarization. If Gatekeeper blocks a trusted copy, use **System Settings → Privacy & Security → Open Anyway** for this app. [Apple 说明（中文）](https://support.apple.com/zh-cn/102445) · [Apple instructions (English)](https://support.apple.com/en-us/102445)

## Run from source

在图形桌面环境中克隆仓库，在仓库根目录执行对应命令。请使用 Python 3.9 或更高版本。

Clone the repository on a graphical desktop and run the commands for your platform from the repository root with Python 3.9 or later.

**Linux / macOS**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/im-tool
```

**Windows PowerShell**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\im-tool.exe
```

激活环境后用 `im-tool` 启动图形界面，用 `imt --help` 查看命令行用法。两者分别对应 `python -m im_app.main` 和 `python -m im_app.cli`。

With the environment active, use `im-tool` for the GUI and `imt --help` for the CLI. Their module entry points are `python -m im_app.main` and `python -m im_app.cli`.

## Build from the checkout

Build tools require Python 3.11 or later and Pillow. The packaging script reads the version from `pyproject.toml`. Output goes to `dist/desktop/`.

- **Linux packages**. Put nFPM on PATH, install Pillow in the build environment, then run `python packaging/build_desktop.py linux`. This produces both packages. At installation time, APT or DNF resolves the desktop runtime dependencies.
- **macOS disk image**. On a Mac, install the application requirements, Pillow and PyInstaller 6 in a virtual environment. Run `python packaging/build_desktop.py macos` under a Python interpreter of the desired architecture. The [Build macOS installers workflow](../.github/workflows/macos-installers.yml) builds on Apple silicon and Intel, mounts each DMG, copies the app, ejects the image and launches the installed application.
- **Windows wizard**. On x64 Windows, install the application requirements, Pillow and PyInstaller. Install Inno Setup 6 with its Simplified Chinese message file (`Languages/ChineseSimplified.isl`). Run `python packaging/build_desktop.py windows`. The script freezes the application, adds its reference and practice libraries and compiles the bilingual wizard. If needed, set `ISCC` to the compiler path.
- **Manuals**. The PDFs are included in the checkout. To update them after editing the manual, run XeLaTeX twice from `docs/manual/` for each source, then copy the PDFs to `im_app/resources/manuals/` before building. For example, use `xelatex -halt-on-error -jobname=im-tool-zh zh.tex` and `xelatex -halt-on-error -jobname=im-tool-en en.tex`. The layout uses xeCJK, TeX Gyre, Latin Modern and either the specified Windows fonts or Fandol.
