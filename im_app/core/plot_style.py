"""
Physical Review Letters (PRL) academic paper style for matplotlib.

Provides a standardized plotting style suitable for publication in
Physical Review Letters and similar journals. Includes serif fonts,
proper sizing, colorblind-friendly palette, and export settings.

Usage:
    from core.plot_style import apply_prl_style, PRL_FIGSIZE_SINGLE

    fig, ax = plt.subplots(figsize=PRL_FIGSIZE_SINGLE)
    apply_prl_style(fig, ax)
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

# ---------------------------------------------------------------------------
# Figure sizes (inches)
# ---------------------------------------------------------------------------
PRL_FIGSIZE_SINGLE = (3.375, 3.375 * 0.75)   # PRL single-column width
PRL_FIGSIZE_DOUBLE = (6.75, 6.75 * 0.5)      # PRL double-column width

# ---------------------------------------------------------------------------
# 字体大小（pt）—— 改这里就能全局调整。
# Mac 上字体渲染比 Windows 略大，若觉得 legend / 标签偏大可整体下调。
# ---------------------------------------------------------------------------
LEGEND_FONTSIZE    = 12   # 图例字号（被 plotter.py 的 ax.legend() 引用）
BASE_FONTSIZE      = 18   # 全局基础字号
TICK_LABELSIZE     = 16   # 坐标轴刻度数字
AXES_LABELSIZE     = 20   # 坐标轴标签（如 "Up (km/s)"）
AXES_TITLESIZE     = 20   # 图标题

# ---------------------------------------------------------------------------
# Colorblind-friendly palette
# ---------------------------------------------------------------------------
PRL_COLORS = {
    "blue":   "#1f77b4",
    "red":    "#d62728",
    "green":  "#2ca02c",
    "orange": "#ff7f0e",
    "purple": "#9467bd",
    "black":  "#000000",
}

# ---------------------------------------------------------------------------
# Default rcParams for PRL style
# ---------------------------------------------------------------------------
PRL_STYLE = {
    # 字体
    "font.family":        "serif",
    "font.serif":         ["Times New Roman", "DejaVu Serif", "Computer Modern Roman"],
    "font.size":          BASE_FONTSIZE,

    # 坐标轴
    "axes.linewidth":     1.2,     # 增大线宽：1.0 -> 1.2
    "axes.labelsize":     AXES_LABELSIZE,
    "axes.titlesize":     AXES_TITLESIZE,
    "axes.grid":          False,

    # 刻度线 — 朝内
    "xtick.direction":    "in",
    "ytick.direction":    "in",
    "xtick.major.size":   6,       # 增大刻度：5 -> 6
    "ytick.major.size":   6,
    "xtick.minor.size":   4,       # 增大次刻度：3 -> 4
    "ytick.minor.size":   4,
    "xtick.major.width":  1.2,     # 增大线宽：1.0 -> 1.2
    "ytick.major.width":  1.2,
    "xtick.minor.width":  0.8,     # 增大线宽：0.6 -> 0.8
    "ytick.minor.width":  0.8,
    "xtick.labelsize":    TICK_LABELSIZE,
    "ytick.labelsize":    TICK_LABELSIZE,
    "xtick.top":          True,
    "ytick.right":        True,

    # 图例
    "legend.fontsize":    LEGEND_FONTSIZE,
    "legend.frameon":     False,
    "legend.handlelength": 1.5,

    # 线条
    "lines.linewidth":    1.5,     # 增大线宽：1.2 -> 1.5
    "lines.markersize":   6,       # 增大标记：5 -> 6

    # 数学文本用 serif 字体
    "mathtext.fontset":   "dejavuserif",

    # 保存设置
    "savefig.dpi":        300,
    "savefig.bbox":       "tight",
    "savefig.pad_inches": 0.02,
}

# ---------------------------------------------------------------------------
# 标准轴标签（含 LaTeX）
# ---------------------------------------------------------------------------
LABEL_UP   = r"Particle velocity $u_p$ (km/s)"
LABEL_P    = r"Pressure $P$ (Mbar)"
LABEL_RHO  = r"Density $\rho$ (g/cm$^3$)"
LABEL_COMP = r"Compression $\rho/\rho_0$"
LABEL_US   = r"Shock velocity $U_s$ (km/s)"
LABEL_T    = r"Temperature $T$ (eV)"
LABEL_E    = r"Internal energy $E$ (MJ/g)"


# ---------------------------------------------------------------------------
# 公共接口
# ---------------------------------------------------------------------------

def apply_prl_style(
    fig: Figure,
    ax: Axes,
    *,
    xlabel: str | None = None,
    ylabel: str | None = None,
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
) -> None:
    """
    Apply PRL publication style to a matplotlib Figure/Axes pair.

    Parameters
    ----------
    fig : Figure
        The matplotlib figure to style.
    ax : Axes
        The axes to style.
    xlabel, ylabel : str, optional
        Axis labels.  Pass ``LABEL_UP``, ``LABEL_P``, etc. from this module.
    xlim, ylim : tuple, optional
        Axis limits.
    """
    # 全局 rcParams
    mpl.rcParams.update(PRL_STYLE)

    # 刻度朝内 + 开启 minor ticks
    ax.tick_params(
        axis="both",
        which="both",
        direction="in",
        top=True,
        right=True,
    )
    ax.minorticks_on()

    # 轴标签
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if ylabel is not None:
        ax.set_ylabel(ylabel)

    # 范围
    if xlim is not None:
        ax.set_xlim(xlim)
    if ylim is not None:
        ax.set_ylim(ylim)

    # 紧凑布局
    fig.tight_layout()


def save_prl_figure(
    fig: Figure,
    filepath: str,
    *,
    dpi: int = 300,
) -> None:
    """
    Save a figure with PRL-compatible settings.

    Parameters
    ----------
    fig : Figure
        The figure to save.
    filepath : str
        Output path (extension determines format: .png, .pdf, .eps, .svg).
    dpi : int
        Resolution for raster formats.  Default 300.
    """
    fig.savefig(
        filepath,
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0.02,
    )


def get_color(name: str) -> str:
    """
    Retrieve a hex color from the PRL palette.

    Parameters
    ----------
    name : str
        One of: "blue", "red", "green", "orange", "purple", "black".

    Returns
    -------
    str
        Hex color string.

    Raises
    ------
    KeyError
        If *name* is not in the palette.
    """
    return PRL_COLORS[name]
