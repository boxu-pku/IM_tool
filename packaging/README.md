# IM Tool 桌面安装 · Desktop installation

| 系统 / Platform | 1.2.4 安装包 / Installer | 安装和启动 / Install and launch |
| --- | --- | --- |
| Windows 10 / 11 x64 | `IM-Tool-Setup-1.2.4-x64.exe` | 双击，选择简体中文或英语，完成向导并从“开始”菜单启动。Double-click, choose a language, then launch IM Tool from Start. |
| Debian / Ubuntu | `im-tool_1.2.4-1_all.deb` | 用软件安装器打开或运行 `sudo apt install ./im-tool_1.2.4-1_all.deb`。Open the package in the software installer or use APT. |
| Fedora | `im-tool-1.2.4-1.noarch.rpm` | 用软件安装器打开或运行 `sudo dnf install ./im-tool-1.2.4-1.noarch.rpm`。Open the package in the software installer or use DNF. |

在 Linux 应用菜单中搜索 **IM Tool**，也可在图形桌面的终端运行 `im-tool`。桌面初始库含 13 条常用参考表。软件首次启动时为当前用户创建可写副本。选择 **Help → Open Working Folder** 可找到当前材料库。通过 **Help → Open Practice Workspace** 可打开 `Al_Celliers2005` 与 `Quartz_Hamel2012` 两条标准曲线及 Hicks 第 29400 号实验的两条瑞利线，练习文件保存在 `Practice/Celliers-Hamel`。

On Linux, search the application menu for **IM Tool** or run `im-tool` in a desktop terminal. The desktop edition seeds a writable per-user library with 13 reference tables. **Help → Open Working Folder** opens the active library. **Help → Open Practice Workspace** opens the Celliers aluminum and Hamel alpha-quartz standards with the measured-speed lines for Hicks shot 29400 in `Practice/Celliers-Hamel`. Both manuals are available in Help. [中文手册](../im_app/resources/manuals/im-tool-zh.pdf) · [English manual](../im_app/resources/manuals/im-tool-en.pdf)

## Build from the checkout

Build tools require Python 3.11 or later and Pillow. The packaging script reads the version from `pyproject.toml`. Output goes to `dist/desktop/`.

- **Linux packages**. Put nFPM on PATH, install Pillow in the build environment, then run `python packaging/build_desktop.py linux`. This produces both packages. At installation time, APT or DNF resolves the desktop runtime dependencies.
- **Windows wizard**. On x64 Windows, install the application requirements, Pillow and PyInstaller. Install Inno Setup 6 with its Simplified Chinese message file (`Languages/ChineseSimplified.isl`). Run `python packaging/build_desktop.py windows`. The script freezes the application, adds its reference and practice libraries and compiles the bilingual wizard. If needed, set `ISCC` to the compiler path.
- **Manuals**. The PDFs are included in the checkout. To update them after editing the manual, run XeLaTeX twice from `docs/manual/` for each source, then copy the PDFs to `im_app/resources/manuals/` before building. For example, use `xelatex -halt-on-error -jobname=im-tool-zh zh.tex` and `xelatex -halt-on-error -jobname=im-tool-en en.tex`. The layout uses xeCJK, TeX Gyre, Latin Modern and either the specified Windows fonts or Fandol.
