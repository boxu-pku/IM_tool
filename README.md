# IM Tool

<img src="im_app/resources/im-tool.png" alt="IM Tool" width="72">

IM Tool 用于冲击波实验的阻抗匹配分析。选取材料的 Hugoniot 曲线，输入实测波速，即可在图上求出界面压强和粒子速度。

IM Tool determines interface pressure and particle velocity from measured shock speeds and material Hugoniot curves.

## 桌面安装 · Desktop installation

| 平台 / Platform | 安装与启动 / Install and launch |
| --- | --- |
| Debian / Ubuntu | 用软件安装器打开 `.deb`，从应用菜单启动 **IM Tool**。Open the `.deb` in the software installer, then launch **IM Tool** from Applications. |
| Fedora | 用软件安装器打开 `.rpm`，从应用菜单启动 **IM Tool**。Open the `.rpm` in the software installer, then launch **IM Tool** from Applications. |
| macOS · Apple 芯片 / Apple silicon | [下载 arm64 磁盘映像 / Download DMG](https://github.com/boxu-pku/IM_tool/releases/download/macos-v1.2.4-r2/IM-Tool-1.2.4-macOS-arm64.dmg) |
| macOS · Intel | [下载 Intel 磁盘映像 / Download DMG](https://github.com/boxu-pku/IM_tool/releases/download/macos-v1.2.4-r2/IM-Tool-1.2.4-macOS-x86_64.dmg) |
| Windows 10 / 11 x64 | [下载 Windows 安装程序 / Download Windows installer (.exe)](https://github.com/boxu-pku/IM_tool/releases/download/windows-v1.2.4/IM-Tool-Setup-1.2.4-x64.exe) |

在 Windows 上双击下载的 `.exe`，完成向导后从“开始”菜单启动 **IM Tool**。On Windows, double-click the installer and launch **IM Tool** from Start.

在 Mac 上打开对应的 `.dmg`，将 **IM Tool.app** 拖入 **Applications**，推出磁盘映像，再从“应用程序”启动。On Mac, open the DMG, drag the app to **Applications**, eject the image and launch **IM Tool**. [首次打开 / First launch](packaging/README.md#macos)

[安装包构建与安装命令 / Build and install the packages](packaging/README.md) · [从源码运行 / Run from source](packaging/README.md#run-from-source)

## 手册与算例 · Manuals and worked example

[中文手册（PDF）](im_app/resources/manuals/im-tool-zh.pdf) · [English manual (PDF)](im_app/resources/manuals/im-tool-en.pdf)

选择 **Help → Open Practice Workspace**，用 Celliers 铝、Hamel 石英和 Hicks 第 29400 号实验的实测波速重现界面压强 **4.7787 Mbar**。

Choose **Help → Open Practice Workspace** to reproduce the **4.7787 Mbar** interface pressure using Celliers aluminum, Hamel quartz and the measured shock speeds from Hicks shot 29400. [实验数据 / Experimental inputs, Table I](https://doi.org/10.1063/1.2009528)

[中文详细指南](docs/user-guide-zh.md) · [Detailed English guide](docs/user-guide-en.md) · [命令行指南 / CLI guide](docs/AI_GUIDE.md)
