"""
Interactive Hugoniot-Rayleigh plot canvas.

Embeddable matplotlib FigureCanvas with PRL styling.  Supports adding
materials, Rayleigh lines, intersections, and reflected Hugoniot curves.
Click-to-select intersections via mpl_connect.
"""

from __future__ import annotations

import numpy as np
import re
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.artist import Artist
from matplotlib.patches import Rectangle
from PyQt5.QtCore import pyqtSignal, QPoint, Qt
from PyQt5.QtWidgets import QMenu, QAction, QDialog
from PyQt5.QtGui import QCursor

from im_app.core.plot_style import (
    PRL_FIGSIZE_DOUBLE, PRL_COLORS,
    LABEL_UP, LABEL_P, LABEL_COMP, LABEL_US, LABEL_RHO, LABEL_T, LABEL_E,
    apply_prl_style, save_prl_figure,
    GUI_LEGEND_FONTSIZE,
    pressure_label, pressure_factor,
)
from im_app.core.element_style import (
    ElementStyle, TYPE_MATERIAL, TYPE_RAYLEIGH, TYPE_REFLECTED, TYPE_INTERSECTION,
    TYPE_SCATTER, DEFAULT_SCATTER_STYLE,
    QuickColorDialog, StyleEditorDialog, COLOR_MAP,
)

# Square figure size for canvas
PRL_FIGSIZE_SQUARE = (6.0, 6.0)

# Scatter point zorder：介于材料曲线 (1) 和交点 (10-15) 之间
SCATTER_ZORDER = 6

from im_app.core.physics import (
    MaterialData, RayleighLine, Intersection,
    rayleigh_line, find_intersections, reflect_hugoniot,
)


def _mask_nonpositive(*arrs) -> np.ndarray:
    """返回所有非 None 数组都 >0 的布尔 mask（用于 log 模式过滤 ≤0 点）。

    None 参数跳过（用于「该轴不是 log」的情形）。非 finite 视为无效。
    输入长度必须一致；返回值长度等于任一非 None 数组长度。
    无任何数组时返回空。
    """
    real = [np.asarray(a) for a in arrs if a is not None]
    if not real:
        return np.array([], dtype=bool)
    n = real[0].size
    mask = np.ones(n, dtype=bool)
    for a in real:
        if a.size != n:
            return np.array([], dtype=bool)
        mask &= np.isfinite(a) & (a > 0)
    return mask


def is_scatter_material(mid: str) -> bool:
    """LASL SHD 实验散点数据（id 以 _lasl 结尾）按散点绘制，不连线。"""
    return str(mid).endswith("_lasl")


# 光标坐标读数用：变量 -> 单位串（与 plot_style.LABEL_* 同源；P 跟 p_unit 走）
_VAR_UNITS = {
    "Up": "km/s",
    "Us": "km/s",
    "rho": "g/cm^3",
    "compression": "",      # 无量纲
    "T": "eV",
    "E": "MJ/g",
}


def _var_unit(var: str, p_unit: str = "Mbar") -> str:
    """变量 -> 坐标读数单位。P 跟 p_unit（GPa 切换后读数即 GPa）。"""
    if var == "P":
        return "GPa" if (p_unit or "Mbar").lower().startswith("g") else "Mbar"
    return _VAR_UNITS.get(var, "")


class DragZoomMixin:
    """拖拽框选缩放 + 'a' 键重置的纯 Python mixin。

    Host 类必须满足：
    - 继承自 FigureCanvas（或其他提供 mpl_connect 的类）
    - 定义类属性 ``zoom_applied = pyqtSignal(float, float, float, float)``
      （参数：xmin, xmax, ymin, ymax，data 坐标）
    - 定义类属性 ``reset_view = pyqtSignal()``
    - 定义类属性 ``cursor_moved = pyqtSignal(str)``（光标坐标读数，
      见 ``_dz_emit_hover``）
    - 有 ``self.ax``（matplotlib Axes 实例）
    - 在 ``__init__`` 中调用 ``self.setup_drag_zoom()`` 一次
    - 可选：重写 ``_handle_click_release(event)`` 处理非拖拽的点击（默认 no-op）

    交互：
    - 左键按下后位移 > 5 px 视为拖拽，松开时 emit ``zoom_applied``
    - 左键按下后位移 ≤ 5 px 松开视为点击，调 ``_handle_click_release``
    - 非 1 号键（右键、中键）一律走 ``_handle_click_release``，不触发拖拽
    - 按 ``a`` 键 emit ``reset_view``
    """

    DRAG_THRESHOLD_PX = 5

    def setup_drag_zoom(self):
        """在 host 类 __init__ 末尾调用一次，绑定 mpl 事件。"""
        self._zoom_start = None          # (x_display, y_display) 或 None
        self._zoom_start_data = None     # (x_data, y_data) 或 None
        self._is_zoom_dragging = False
        self._zoom_rect_patch = None     # patches.Rectangle 或 None

        self.mpl_connect('button_press_event', self._dz_on_press)
        self.mpl_connect('motion_notify_event', self._dz_on_motion)
        self.mpl_connect('button_release_event', self._dz_on_release)
        self.mpl_connect('key_press_event', self._dz_on_key)

        # canvas 默认 NoFocus，key_press_event 不会触发；让 canvas 接受键盘焦点，
        # 用户点击 plot 后按 'a' 才能触发 reset_view。
        self.setFocusPolicy(Qt.StrongFocus)

    def _dz_on_press(self, event):
        """记录按下位置（display 坐标）。仅在左键且在 axes 内时记录。"""
        if event.button != 1 or event.inaxes != self.ax:
            self._zoom_start = None
            return
        self._zoom_start = (event.x, event.y)
        self._zoom_start_data = None
        self._is_zoom_dragging = False

    def _dz_on_motion(self, event):
        """移动超过阈值时创建/更新红色半透明 Rectangle；同时刷新光标坐标读数。"""
        self._dz_emit_hover(event)
        if self._zoom_start is None or event.x is None or event.y is None:
            return

        dx = abs(event.x - self._zoom_start[0])
        dy = abs(event.y - self._zoom_start[1])

        if not self._is_zoom_dragging:
            if dx <= self.DRAG_THRESHOLD_PX and dy <= self.DRAG_THRESHOLD_PX:
                return
            # 首次跨阈值：把起点转 data 坐标，创建 patch
            if event.xdata is None or event.ydata is None:
                return
            self._is_zoom_dragging = True
            self._zoom_start_data = self.ax.transData.inverted().transform_point(self._zoom_start)
            sx, sy = self._zoom_start_data
            self._zoom_rect_patch = Rectangle(
                (sx, sy), 0, 0,
                edgecolor='red', facecolor='red', alpha=0.2,
                linewidth=1, zorder=100,
            )
            self.ax.add_patch(self._zoom_rect_patch)

        if event.xdata is None or event.ydata is None:
            return  # 鼠标移出 axes，保持上次的矩形不变

        sx, sy = self._zoom_start_data
        ex, ey = event.xdata, event.ydata
        x0, y0 = min(sx, ex), min(sy, ey)
        w, h = abs(ex - sx), abs(ey - sy)
        self._zoom_rect_patch.set_xy((x0, y0))
        self._zoom_rect_patch.set_width(w)
        self._zoom_rect_patch.set_height(h)
        self.draw_idle()

    def _dz_emit_hover(self, event):
        """光标坐标读数：data 坐标格式化后 emit ``cursor_moved``（str）。

        axes 数据坐标就是显示单位坐标（p_unit 选 GPa 时画布上即 GPa），
        直接读 event.xdata/ydata；变量名取 host 的 ``x_var``/``y_var``
        （未定义时按 P-Up 主图默认 Up/P）。光标不在 axes 内时发空串清位。
        """
        if event.xdata is None or event.ydata is None:
            self.cursor_moved.emit("")
            return
        p_unit = getattr(self, "p_unit", "Mbar")
        parts = []
        for var, val in (
            (getattr(self, "x_var", "Up"), event.xdata),
            (getattr(self, "y_var", "P"), event.ydata),
        ):
            unit = _var_unit(var, p_unit)
            parts.append(f"{var} = {val:.4f} {unit}" if unit else f"{var} = {val:.4f}")
        self.cursor_moved.emit("    ".join(parts))

    def _dz_on_release(self, event):
        """松开时：若曾拖拽则 emit zoom_applied；否则调 _handle_click_release。"""
        was_dragging = self._is_zoom_dragging
        start_data = self._zoom_start_data

        # 清理拖拽状态
        self._zoom_start = None
        self._zoom_start_data = None
        self._is_zoom_dragging = False
        if self._zoom_rect_patch is not None:
            self._zoom_rect_patch.remove()
            self._zoom_rect_patch = None
            self.draw_idle()

        if (was_dragging and start_data is not None
                and event.xdata is not None and event.ydata is not None):
            sx, sy = start_data
            ex, ey = event.xdata, event.ydata
            xmin, xmax = sorted([sx, ex])
            ymin, ymax = sorted([sy, ey])
            if xmax > xmin and ymax > ymin:
                self.zoom_applied.emit(
                    float(xmin), float(xmax), float(ymin), float(ymax)
                )
                return

        # 非拖拽：交给 host 的点击处理
        self._handle_click_release(event)

    def _dz_on_key(self, event):
        """按 'a' 重置。"""
        if event.key == 'a':
            self.reset_view.emit()

    def _handle_click_release(self, event):
        """Host 类可重写。默认 no-op。"""
        pass


# ---------------------------------------------------------------------------
# Element interaction mixin：pick + 右键上下文菜单 + Edit Style
# 复用给 InteractiveHugoniotPlot / EOSPlot / GenericHugoniotPlot
# 纯 Python mixin，不继承 QObject；signals 必须定义在 host 类
# ---------------------------------------------------------------------------

class ElementInteractionMixin:
    """元素选中 + 右键菜单 mixin。

    Host 类必须：
    - 定义 pyqtSignals: element_selected(str, str), element_deleted(str, str), style_changed(str, dict)
    - 在 __init__ 调用 self._init_element_interaction()
    - 画材料曲线时调 self._register_artist(artist, element_id, element_type, style, data_id, zorder)
    - 调用 render_scatter_points(..., artist_map=self._artist_map, ...) 让 scatter 也注册进交互模型
    """

    def _init_element_interaction(self):
        self._artist_map = {}
        self._element_meta = {}
        self._artist_zorder = {}
        self._selected_element_id = None
        self._picked_elements = []
        self.mpl_connect('pick_event', self._ei_on_pick)

    def _ei_on_pick(self, event):
        artist = event.artist
        if artist in self._artist_map:
            element_id = self._artist_map[artist]
            zorder = self._artist_zorder.get(artist, 0)
            self._picked_elements.append((element_id, zorder, event.mouseevent))

    def _ei_process_pick(self):
        if not self._picked_elements:
            return None
        def sort_key(item):
            element_id, zorder, _ = item
            type_priority = 0
            if element_id.startswith("ix_"):
                type_priority = 100
            elif element_id.startswith("scat_"):
                type_priority = 50
            elif element_id.startswith("mat_"):
                type_priority = 25  # 材料线优先级低于scatter但高于其他
            return (zorder + type_priority, element_id)
        sorted_items = sorted(self._picked_elements, key=sort_key, reverse=True)
        best = sorted_items[0]
        element_id, _, mouse_event = best
        self._picked_elements.clear()
        return element_id, mouse_event

    def _ei_handle_click_release(self, event):
        """供 DragZoomMixin 的 _handle_click_release 调用。"""
        if event.inaxes != self.ax:
            return
        pick_result = self._ei_process_pick()
        if pick_result:
            element_id, _ = pick_result
            if event.button == 1:
                self._ei_handle_selection(element_id)
            elif event.button == 3:
                self._ei_show_context_menu(element_id, event.xdata, event.ydata)
        else:
            if event.button == 1 and self._selected_element_id is not None:
                self._selected_element_id = None
                self._ei_redraw()

    def _ei_handle_selection(self, element_id):
        meta = self._element_meta.get(element_id)
        self._selected_element_id = element_id
        if meta:
            self.element_selected.emit(element_id, meta["type"])
        self._ei_redraw()

    def _ei_show_context_menu(self, element_id, xdata, ydata):
        meta = self._element_meta.get(element_id)
        if not meta:
            return
        x_pixel, y_pixel = self.ax.transData.transform([xdata, ydata])
        global_pos = self.mapToGlobal(QPoint(int(x_pixel), int(self.height() - y_pixel)))

        menu = QMenu(self)
        element_type = meta["type"]

        edit_style_action = QAction("Edit Style...", self)
        edit_style_action.triggered.connect(lambda: self._ei_edit_style(element_id))
        menu.addAction(edit_style_action)

        color_menu = menu.addMenu("Change Color")
        for color_name, color_hex in COLOR_MAP.items():
            color_action = QAction(color_name.capitalize(), self)
            color_action.triggered.connect(
                lambda checked, c=color_hex: self._ei_change_color(element_id, c)
            )
            color_menu.addAction(color_action)

        # Delete 仅对 scatter / intersection 提供；材料删除走 Material Panel
        if element_type in (TYPE_SCATTER, TYPE_INTERSECTION):
            menu.addSeparator()
            delete_action = QAction("Delete", self)
            delete_action.triggered.connect(
                lambda: self._ei_delete_element(element_id, element_type)
            )
            menu.addAction(delete_action)

        menu.exec_(global_pos)

    def _ei_edit_style(self, element_id):
        meta = self._element_meta.get(element_id)
        if not meta:
            return
        dialog = StyleEditorDialog(element_id, meta["type"], meta["style"], self)
        if dialog.exec_() == QDialog.Accepted:
            new_style = dialog.get_updated_style()
            # 用 update 保持引用（scatter 的 style dict 在多 plot 间共享）
            meta["style"].update(new_style)
            self.style_changed.emit(element_id, meta["style"])
            self._ei_redraw()

    def _ei_change_color(self, element_id, color):
        meta = self._element_meta.get(element_id)
        if meta and "style" in meta:
            meta["style"]["color"] = color
            self.style_changed.emit(element_id, meta["style"])
            self._ei_redraw()

    def _ei_delete_element(self, element_id, element_type):
        self._element_meta.pop(element_id, None)
        if self._selected_element_id == element_id:
            self._selected_element_id = None
        self.element_deleted.emit(element_id, element_type)

    def _ei_redraw(self):
        """统一的 redraw 接口：refresh 优先，否则 update_plot。"""
        if hasattr(self, 'refresh'):
            self.refresh()
        elif hasattr(self, 'update_plot'):
            self.update_plot()

    def _register_artist(self, artist, element_id, element_type, style_dict,
                          data_id, zorder, picker=10, pickradius=15):
        """统一注册：把 artist 加入 _artist_map / _artist_zorder / _element_meta。"""
        artist.set_picker(picker)
        try:
            artist.set_pickradius(pickradius)
        except Exception:
            pass
        self._artist_map[artist] = element_id
        self._artist_zorder[artist] = zorder
        if element_id not in self._element_meta:
            self._element_meta[element_id] = {
                "type": element_type,
                "data_id": data_id,
                "style": style_dict,
            }


class InteractiveHugoniotPlot(FigureCanvas, DragZoomMixin):
    """P-Up interactive plot with click-to-select intersections + drag-to-zoom."""

    intersection_selected = pyqtSignal(str)   # emits intersection ID
    element_selected = pyqtSignal(str, str)  # emits (element_id, element_type)
    element_deleted = pyqtSignal(str, str)   # emits (element_id, element_type)
    style_changed = pyqtSignal(str, dict)     # emits (element_id, new_style)
    zoom_applied = pyqtSignal(float, float, float, float)   # xmin, xmax, ymin, ymax
    reset_view = pyqtSignal()
    cursor_moved = pyqtSignal(str)            # 光标坐标读数（DragZoomMixin._dz_emit_hover）

    def __init__(self, parent=None):
        self.fig = Figure(figsize=PRL_FIGSIZE_SQUARE, dpi=150)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        # State
        self.materials: dict[str, MaterialData] = {}
        self.rayleigh_lines: dict[str, RayleighLine] = {}
        self.intersections: list[Intersection] = []
        self.selected_intersection_id: str | None = None
        self.reflected_curves: list[dict] = []   # [{id, up, p, source_id, center_up}]

        # Visibility flags
        self._mat_visible: dict[str, bool] = {}
        self._rl_visible: dict[str, bool] = {}

        # Interactive selection
        self._artist_map: dict[Artist, str] = {}  # artist -> element_id
        self._element_meta: dict[str, dict] = {}  # element_id -> {type, style}
        self._selected_element_id: str | None = None
        self._picked_element_id: str | None = None  # For pick event handling

        # Plot settings with defaults（None = auto：按数据自适应范围）
        self.xlim = None
        self.ylim = None
        self.show_legend = True
        self.show_ix_errorbars = True    # 交点误差棒开关
        self.linewidth = 1.2
        self.linestyle = "-"
        # Pressure 单位（"Mbar" / "GPa"）与轴 log 模式（P-Up 的 X=Up, Y=P）
        self.p_unit = "Mbar"
        self.x_log = False
        self.y_log = False

        self._counter = 0
        self._material_color_map: dict[str, str] = {}  # mat_id -> color, persistent
        self._color_counter = 0

        # Scatter points (注入式，由 main_window 调 set_scatter_points 设置)
        self._scatter_points = []

        # Matplotlib events
        # 注意：button_press/release/motion/key 由 DragZoomMixin.setup_drag_zoom 绑定。
        # pick_event 用于辅助元素选中（highest-zorder 选择）。
        self.mpl_connect("pick_event", self._on_pick)
        self.setup_drag_zoom()

        # Store zorder for each artist
        self._artist_zorder: dict[Artist, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_material(self, mat: MaterialData):
        self.materials[mat.id] = mat
        self._mat_visible[mat.id] = True
        self.refresh()

    def remove_material(self, mat_id: str):
        self.materials.pop(mat_id, None)
        self._mat_visible.pop(mat_id, None)
        self.refresh()

    def set_material_visible(self, mat_id: str, visible: bool):
        self._mat_visible[mat_id] = visible
        self.refresh()

    def add_rayleigh(self, rl: RayleighLine):
        self.rayleigh_lines[rl.id] = rl
        self._rl_visible[rl.id] = True
        self.refresh()

    def remove_rayleigh(self, rl_id: str):
        self.rayleigh_lines.pop(rl_id, None)
        self._rl_visible.pop(rl_id, None)
        self.refresh()

    def set_rayleigh_visible(self, rl_id: str, visible: bool):
        self._rl_visible[rl_id] = visible
        self.refresh()

    def compute_intersections(self):
        from im_app.core.physics import find_all_intersections as _find
        self.intersections = _find(self.materials, self.rayleigh_lines)
        self.refresh()

    def select_intersection(self, ix_id: str):
        self.selected_intersection_id = ix_id
        self.refresh()

    def add_reflected(self, source_mat_id: str, center_up: float, explicit_id: str | None = None) -> str:
        mat = self.materials.get(source_mat_id)
        if mat is None:
            return ""
        up_r, p_r = reflect_hugoniot(mat.up, mat.p, center_up)

        # 计算反射曲线的误差带
        up_r_err = None
        p_r_err = None
        if hasattr(mat, "p_err") and mat.p_err is not None:
            from im_app.core.error_propagation import reflect_error_propagation
            center_up_err = 0.0  # 默认无中心误差；由调用方通过 anchor_ix_id 传递时更新
            up_r_err, p_r_err = reflect_error_propagation(mat.p_err, center_up_err)

        if explicit_id:
            # workflow 加载路径：保留原 id（含 refl_ai_* 等任意命名），
            # 仅尽力恢复计数器，避免后续自动 id 撞车
            rid = explicit_id
            try:
                n = int(re.search(r"(\d+)$", explicit_id).group(1))
                if n > self._counter:
                    self._counter = n
            except AttributeError:
                self._counter += 1
        else:
            self._counter += 1
            rid = f"refl_{self._counter}"
        self.reflected_curves.append({
            "id": rid,
            "up": up_r,
            "p": p_r,
            "source_id": source_mat_id,
            "center_up": center_up,
            "visible": True,
            "up_err": up_r_err,
            "p_err": p_r_err,
        })
        self.refresh()
        return rid

    def remove_reflected(self, refl_id: str):
        self.reflected_curves = [r for r in self.reflected_curves if r["id"] != refl_id]
        self.refresh()

    # ------------------------------------------------------------------
    # Plot settings control
    # ------------------------------------------------------------------

    def set_xlim(self, xmin: float, xmax: float):
        self.xlim = (xmin, xmax)
        self.refresh()

    def set_ylim(self, ymin: float, ymax: float):
        self.ylim = (ymin, ymax)
        self.refresh()

    def auto_scale(self):
        """恢复 auto 视图：清除显式范围，按当前数据自适应（'a' 键 / 默认）。"""
        self.xlim = None
        self.ylim = None
        self.refresh()

    def set_legend_visible(self, visible: bool):
        self.show_legend = visible
        self.refresh()

    def set_linewidth(self, width: float):
        self.linewidth = width
        self.refresh()

    def set_linestyle(self, style: str):
        self.linestyle = style
        self.refresh()

    def set_p_unit(self, unit: str):
        """切换 Pressure 显示单位（Mbar / GPa）。"""
        self.p_unit = unit or "Mbar"
        self.refresh()

    def set_xscale(self, log: bool):
        self.x_log = bool(log)
        self.refresh()

    def set_yscale(self, log: bool):
        self.y_log = bool(log)
        self.refresh()

    def set_scatter_points(self, points):
        """注入 scatter 点列表（refresh 时读取）。"""
        self._scatter_points = points or []

    # ------------------------------------------------------------------
    # Plot refresh
    # ------------------------------------------------------------------

    _COLOR_LIST = [PRL_COLORS["blue"], PRL_COLORS["red"],
                   PRL_COLORS["green"], PRL_COLORS["orange"],
                   PRL_COLORS["purple"], PRL_COLORS["black"]]

    _IX_MARKERS = ["o", "s", "D", "^", "v", "P", "*", "X"]
    _IX_COLORS = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3",
                  "#ff7f00", "#a65628", "#f781bf", "#999999"]

    def refresh(self, xlim=None, ylim=None, show_legend=None):
        self.ax.clear()

        # Clear artist map for redraw
        self._artist_map.clear()
        self._artist_zorder.clear()

        # Build material color map (persistent per material ID)
        material_colors = {}
        for mid in self.materials:
            if mid not in self._material_color_map:
                self._material_color_map[mid] = self._COLOR_LIST[
                    self._color_counter % len(self._COLOR_LIST)
                ]
                self._color_counter += 1
        # 清理已移除材料的颜色
        for old_mid in list(self._material_color_map):
            if old_mid not in self.materials:
                del self._material_color_map[old_mid]

        for mid, mat in self.materials.items():
            if not self._mat_visible.get(mid, True):
                continue
            # 防御：参考曲线等可能缺失 up 或 p（如只有 P-T 的参考曲线），跳过避免崩溃
            if mat.up is None or mat.p is None or len(mat.up) == 0 or len(mat.up) != len(mat.p):
                continue
            color = self._material_color_map[mid]
            material_colors[mid] = color

            # Get element style if exists
            element_id = f"mat_{mid}"
            style = self._element_meta.get(element_id, {}).get("style", {})
            line_color = style.get("color", color)
            linewidth = style.get("linewidth", self.linewidth)
            linestyle = style.get("linestyle", self.linestyle)
            alpha = style.get("alpha", 1.0)

            # Check if selected
            is_selected = (self._selected_element_id == element_id)
            if is_selected:
                linewidth *= 1.5

            # Extract source from material id if it contains underscore
            label = mat.name
            if "_" in mid:
                source = mid.split("_", 1)[1] if len(mid.split("_")) > 1 else ""
                if source and source not in label.lower():
                    label = f"{mat.name} ({source})"

            # P 单位转换（内部 Mbar → 渲染 GPa 时 ×100）
            pf = pressure_factor(self.p_unit)
            up_arr = np.asarray(mat.up)
            p_arr = np.asarray(mat.p) * pf
            # log 模式过滤 ≤0 点（X=Up, Y=P）
            if self.x_log or self.y_log:
                vmask = _mask_nonpositive(up_arr if self.x_log else None,
                                          p_arr if self.y_log else None)
                if vmask.size:
                    up_arr = up_arr[vmask]
                    p_arr = p_arr[vmask]

            if is_scatter_material(mid):
                line, = self.ax.plot(
                    up_arr, p_arr, linestyle="None",
                    marker="o", markersize=4,
                    markerfacecolor=line_color, markeredgecolor=line_color,
                    label=label, alpha=alpha,
                    picker=10, pickradius=15, zorder=1)
            else:
                line, = self.ax.plot(up_arr, p_arr, color=line_color, linewidth=linewidth,
                                     linestyle=linestyle, label=label, alpha=alpha,
                                     picker=10, pickradius=15, zorder=1)

            # 绘制 Hugoniot 误差带（如果材料有 p_err）
            if hasattr(mat, "p_err") and mat.p_err is not None and len(mat.p_err) > 0:
                p_err_arr = np.asarray(mat.p_err) * pf
                valid = np.isfinite(p_err_arr) & np.isfinite(up_arr) & np.isfinite(p_arr)
                if self.x_log or self.y_log:
                    pos = _mask_nonpositive(up_arr if self.x_log else None,
                                            p_arr if self.y_log else None,
                                            (p_arr - p_err_arr) if self.y_log else None,
                                            (p_arr + p_err_arr) if self.y_log else None)
                    if pos.size == len(valid):
                        valid &= pos
                if valid.sum() > 1:
                    self.ax.fill_between(
                        up_arr[valid],
                        p_arr[valid] - p_err_arr[valid],
                        p_arr[valid] + p_err_arr[valid],
                        alpha=0.12,
                        color=line_color,
                        zorder=0,
                    )

            # Store mapping
            self._artist_map[line] = element_id
            self._artist_zorder[line] = 1
            if element_id not in self._element_meta:
                self._element_meta[element_id] = {
                    "type": TYPE_MATERIAL,
                    "style": ElementStyle(TYPE_MATERIAL, color=line_color,
                                        linewidth=linewidth, linestyle=linestyle,
                                        alpha=alpha).to_dict(),
                    "data_id": mid,
                }

        # Rayleigh lines - match color to corresponding Hugoniot if exists
        for i, (rid, rl) in enumerate(self.rayleigh_lines.items()):
            if not self._rl_visible.get(rid, True):
                continue

            element_id = f"rl_{rid}"
            style = self._element_meta.get(element_id, {}).get("style", {})

            # Find matching material color
            if rl.material_id in material_colors:
                color = material_colors[rl.material_id]
                # Get material name for legend
                mat = self.materials.get(rl.material_id)
                mat_name = mat.name if mat else rl.material_id
                label = f"{mat_name} Rayleigh Line, D={rl.D:.2f} km/s"
            else:
                # Use custom color for standalone Rayleigh lines
                color = self._COLOR_LIST[i % len(self._COLOR_LIST)]
                label = f"{rl.material_id} Rayleigh Line, D={rl.D:.2f} km/s"

            line_color = style.get("color", color)
            linewidth = style.get("linewidth", 0.9)
            linestyle = style.get("linestyle", "--")
            alpha = style.get("alpha", 1.0)

            is_selected = (self._selected_element_id == element_id)
            if is_selected:
                linewidth *= 1.5

            # P 单位转换 + log 过滤
            pf = pressure_factor(self.p_unit)
            rl_up = np.asarray(rl.up)
            rl_p = np.asarray(rl.p) * pf
            if self.x_log or self.y_log:
                vmask = _mask_nonpositive(rl_up if self.x_log else None,
                                          rl_p if self.y_log else None)
                if vmask.size and vmask.size == rl_up.size:
                    rl_up = rl_up[vmask]
                    rl_p = rl_p[vmask]

            line, = self.ax.plot(rl_up, rl_p, linestyle=linestyle, color=line_color,
                                 linewidth=linewidth, label=label, alpha=alpha,
                                 picker=10, pickradius=15, zorder=1)

            # 绘制 Rayleigh 线误差带（若 sigma_D 或 sigma_rho0 > 0）
            try:
                from im_app.core.physics import rayleigh_p_err
                rl_p_err = rayleigh_p_err(rl.up, rl.rho0, rl.D,
                                          getattr(rl, 'sigma_D', 0.0) or 0.0,
                                          getattr(rl, 'sigma_rho0', 0.0) or 0.0)
                if rl_p_err is not None:
                    rl_p_err = np.asarray(rl_p_err) * pf
                    valid = np.isfinite(rl_p_err) & np.isfinite(rl_up) & np.isfinite(rl_p)
                    if self.y_log and valid.size == rl_p.size:
                        valid &= (rl_p - rl_p_err) > 0
                    if valid.sum() > 1:
                        self.ax.fill_between(
                            rl_up[valid],
                            rl_p[valid] - rl_p_err[valid],
                            rl_p[valid] + rl_p_err[valid],
                            alpha=0.10, color=line_color, zorder=0,
                        )
            except Exception:
                pass

            self._artist_map[line] = element_id
            self._artist_zorder[line] = 1
            if element_id not in self._element_meta:
                self._element_meta[element_id] = {
                    "type": TYPE_RAYLEIGH,
                    "style": ElementStyle(TYPE_RAYLEIGH, color=line_color,
                                        linewidth=linewidth, linestyle=linestyle,
                                        alpha=alpha).to_dict(),
                    "data_id": rid,
                }

        # Reflected curves - use source material color, different linestyle
        for rc in self.reflected_curves:
            if not rc.get("visible", True):
                continue

            element_id = f"refl_{rc['id']}"
            style = self._element_meta.get(element_id, {}).get("style", {})

            source_id = rc["source_id"]
            # Get color from source material
            if source_id in material_colors:
                color = material_colors[source_id]
                mat = self.materials.get(source_id)
                source_name = mat.name if mat else source_id
            else:
                color = "blue"
                source_name = source_id

            is_release = (rc.get("kind") == "release")

            line_color = style.get("color", color)
            linewidth = style.get("linewidth", 0.9)
            # release 线默认用 dash-dot，与交点反射线的 dotted 区分
            linestyle = style.get("linestyle", "-." if is_release else ":")
            alpha = style.get("alpha", 1.0)

            is_selected = (self._selected_element_id == element_id)
            if is_selected:
                linewidth *= 1.5

            order = np.argsort(rc["up"])
            label = f"{source_name} release" if is_release else f"{source_name} reflected Hugoniot"

            # P 单位转换 + log 过滤（反射线可能含负 up）
            pf = pressure_factor(self.p_unit)
            refl_up = np.asarray(rc["up"])[order]
            refl_p = np.asarray(rc["p"])[order] * pf
            if self.x_log or self.y_log:
                vmask = _mask_nonpositive(refl_up if self.x_log else None,
                                          refl_p if self.y_log else None)
                if vmask.size and vmask.size == refl_up.size:
                    refl_up = refl_up[vmask]
                    refl_p = refl_p[vmask]

            line, = self.ax.plot(refl_up, refl_p, linestyle=linestyle,
                                 linewidth=linewidth, color=line_color, label=label,
                                 alpha=alpha, picker=10, pickradius=15, zorder=1)

            self._artist_map[line] = element_id
            self._artist_zorder[line] = 1
            if element_id not in self._element_meta:
                self._element_meta[element_id] = {
                    "type": TYPE_REFLECTED,
                    "style": ElementStyle(TYPE_REFLECTED, color=line_color,
                                        linewidth=linewidth, linestyle=linestyle,
                                        alpha=alpha).to_dict(),
                    "data_id": rc["id"],
                }

        # Intersections - each with unique color/marker, info in legend
        for idx, ix in enumerate(self.intersections):
            element_id = f"ix_{ix.id}"
            style = self._element_meta.get(element_id, {}).get("style", {})

            is_ix_selected = (ix.id == self.selected_intersection_id)
            is_element_selected = (self._selected_element_id == element_id)

            marker_size = style.get("markersize", 12 if is_ix_selected else 8)
            if is_element_selected:
                marker_size *= 1.3

            marker = style.get("marker", self._IX_MARKERS[idx % len(self._IX_MARKERS)])
            face_color = style.get("color", self._IX_COLORS[idx % len(self._IX_COLORS)])
            edge_color = "black" if (is_ix_selected or is_element_selected) else face_color
            edge_width = 2.0 if (is_ix_selected or is_element_selected) else 1.0
            alpha = style.get("alpha", 1.0)

            # P 单位转换
            pf = pressure_factor(self.p_unit)
            ix_p = ix.p * pf
            p_unit_str = "GPa" if pf > 1 else "Mbar"

            # Build legend label with units
            label_parts = [f"Up={ix.up:.2f} km/s", f"P={ix_p:.3f} {p_unit_str}"]
            if hasattr(ix, 'compression_ratio') and ix.compression_ratio:
                label_parts.append(f"CR={ix.compression_ratio:.2f}")
            legend_label = ", ".join(label_parts)

            # log 模式下若 up 或 p ≤0 则跳过该交点（log 无法绘制）
            skip_ix = (self.x_log and ix.up <= 0) or (self.y_log and ix_p <= 0)

            if not skip_ix:
                # Plot a large invisible point for easy picking, then the visible point
                # Invisible large point (click target) - higher zorder than lines
                target, = self.ax.plot(ix.up, ix_p, 'o', markersize=30,
                                       alpha=0,  # Invisible
                                       picker=10, pickradius=20,
                                       zorder=10)  # Higher than lines (zorder=1)
                self._artist_map[target] = element_id
                self._artist_zorder[target] = 10

                # Visible point (actual marker) - even higher zorder
                line, = self.ax.plot(ix.up, ix_p, marker, markersize=marker_size,
                                     markerfacecolor=face_color,
                                     markeredgecolor=edge_color,
                                     markeredgewidth=edge_width,
                                     linestyle='None',
                                     label=legend_label,
                                     zorder=15, alpha=alpha)  # Highest zorder
                self._artist_zorder[line] = 15
                self._artist_map[line] = element_id
            else:
                line = None

            # 绘制交点 errorbar（如果有误差数据且开关打开）
            if (line is not None
                    and self.show_ix_errorbars
                    and getattr(ix, 'up_err', None) is not None
                    and getattr(ix, 'p_err', None) is not None
                    and np.isfinite(ix.up_err) and np.isfinite(ix.p_err)
                    and ix.up_err > 0 and ix.p_err > 0):
                self.ax.errorbar(
                    ix.up, ix_p,
                    xerr=ix.up_err, yerr=ix.p_err,
                    fmt='none',
                    ecolor=face_color,
                    capsize=3,
                    capthick=1.2,
                    alpha=0.7,
                    zorder=14,  # 在可见标记之下但高于不可见点击区域
                )

            if line is not None:
                self._artist_map[line] = element_id
            if element_id not in self._element_meta:
                self._element_meta[element_id] = {
                    "type": TYPE_INTERSECTION,
                    "style": ElementStyle(TYPE_INTERSECTION, color=face_color,
                                        marker=marker, markersize=marker_size,
                                        alpha=alpha).to_dict(),
                    "data_id": ix.id,
                }

        apply_prl_style(self.fig, self.ax,
                         xlabel=LABEL_UP, ylabel=pressure_label(self.p_unit),
                         xlim=xlim or self.xlim, ylim=ylim or self.ylim,
                         xscale="log" if self.x_log else "linear",
                         yscale="log" if self.y_log else "linear")
        # auto 轴：重新开启自适应（之前的 set_xlim 会关闭它）
        if self.xlim is None:
            self.ax.set_autoscalex_on(True)
        if self.ylim is None:
            self.ax.set_autoscaley_on(True)

        if (self.materials or self.rayleigh_lines or self.intersections) and (show_legend if show_legend is not None else self.show_legend):
            self.ax.legend(loc="best", fontsize=GUI_LEGEND_FONTSIZE)

        # Render scatter points (interactive on P-Up)
        if self._scatter_points:
            render_scatter_points(
                self.ax, self._scatter_points,
                    x_var="Up", y_var="P", tab_key="P-Up",
                    artist_map=self._artist_map,
                    element_meta=self._element_meta,
                    element_zorder=self._artist_zorder,
                    p_unit=self.p_unit,
                    x_log=self.x_log, y_log=self.y_log,
                )

        self.draw_idle()

    def update_plot(self):
        """update_plot 接口，等同 refresh()，用于外部统一调用。"""
        self.refresh()

    # ------------------------------------------------------------------
    # Click handler
    # ------------------------------------------------------------------

    def _on_pick(self, event):
        """Handle pick event from matplotlib picker."""
        artist = event.artist
        if artist in self._artist_map:
            element_id = self._artist_map[artist]
            zorder = self._artist_zorder.get(artist, 0)
            if not hasattr(self, '_picked_elements'):
                self._picked_elements = []
            self._picked_elements.append((element_id, zorder, event.mouseevent))

    def _process_pick(self):
        """Process picked elements and select the one with highest zorder."""
        if not hasattr(self, '_picked_elements') or not self._picked_elements:
            return None

        # Sort by zorder (descending), then by element type (prefer intersections)
        def sort_key(item):
            element_id, zorder, mouse_event = item
            # Prioritize intersections (TYPE_INTERSECTION)
            type_priority = 0
            if element_id.startswith("ix_"):
                type_priority = 100
            elif element_id.startswith("scat_"):
                type_priority = 50
            elif element_id.startswith("mat_"):
                type_priority = 25  # 材料线优先级低于scatter但高于其他
            return (zorder + type_priority, element_id)

        sorted_items = sorted(self._picked_elements, key=sort_key, reverse=True)
        best = sorted_items[0]  # Highest zorder (and intersection priority)

        element_id, zorder, mouse_event = best
        self._picked_elements.clear()

        return element_id, mouse_event

    def _handle_click_release(self, event):
        """松开时若不是拖拽则触发：选中元素或弹出右键菜单。

        由 DragZoomMixin._dz_on_release 在非拖拽场景下调用。
        """
        if event.inaxes != self.ax:
            return

        pick_result = self._process_pick()

        if pick_result:
            element_id, _ = pick_result
            if event.button == 1:
                self._handle_selection_by_id(element_id)
            elif event.button == 3:
                self._show_context_menu_by_id(element_id, event.xdata, event.ydata)
        else:
            if event.button == 1:
                self._selected_element_id = None
                self.refresh()

    def _handle_selection_by_id(self, element_id: str):
        """Handle selection by element ID (from pick event)."""
        meta = self._element_meta.get(element_id)

        if meta and meta["type"] == TYPE_INTERSECTION:
            # For intersections, also emit the old signal for compatibility
            data_id = meta["data_id"]
            self.selected_intersection_id = data_id
            self.intersection_selected.emit(data_id)

        # Emit element selection signal
        self._selected_element_id = element_id
        if meta:
            self.element_selected.emit(element_id, meta["type"])

        # Redraw to show selection
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        self.refresh(xlim=xlim, ylim=ylim)

    def _show_context_menu_by_id(self, element_id: str, xdata: float, ydata: float):
        """Show context menu for element by ID."""
        meta = self._element_meta.get(element_id)
        if not meta:
            return

        # Convert matplotlib coordinates to screen coordinates
        # transform takes (x, y) as an array-like and returns pixel coordinates
        x_pixel, y_pixel = self.ax.transData.transform([xdata, ydata])
        global_pos = self.mapToGlobal(QPoint(int(x_pixel), int(self.height() - y_pixel)))

        menu = QMenu(self)

        element_type = meta["type"]

        # Edit style action
        edit_style_action = QAction("Edit Style...", self)
        edit_style_action.triggered.connect(lambda: self._edit_element_style(element_id))
        menu.addAction(edit_style_action)

        # Quick color change
        color_menu = menu.addMenu("Change Color")
        for color_name, color_hex in COLOR_MAP.items():
            color_action = QAction(color_name.capitalize(), self)
            color_action.triggered.connect(lambda checked, c=color_hex: self._change_color(element_id, c))
            color_menu.addAction(color_action)

        # Delete action (for all types)
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self._delete_element(element_id, element_type))
        menu.addAction(delete_action)

        menu.exec_(global_pos)

    def _edit_element_style(self, element_id: str):
        """Open style editor dialog for element."""
        meta = self._element_meta.get(element_id)
        if not meta:
            return

        dialog = StyleEditorDialog(element_id, meta["type"], meta["style"], self)
        if dialog.exec_() == QDialog.Accepted:
            new_style = dialog.get_updated_style()
            self._element_meta[element_id]["style"] = new_style
            self.style_changed.emit(element_id, new_style)
            self.refresh()

    def _change_color(self, element_id: str, color: str):
        """Quick color change."""
        meta = self._element_meta.get(element_id)
        if meta and "style" in meta:
            meta["style"]["color"] = color
            self.style_changed.emit(element_id, meta["style"])
            self.refresh()

    def _delete_element(self, element_id: str, element_type: str):
        """Delete element from plot."""
        # Remove from metadata
        self._element_meta.pop(element_id, None)

        # Emit deletion signal for main window to handle
        self.element_deleted.emit(element_id, element_type)

        # Clear selection if deleted element was selected
        if self._selected_element_id == element_id:
            self._selected_element_id = None

        self.refresh()


class EOSPlot(FigureCanvas, DragZoomMixin, ElementInteractionMixin):
    """P-compression ratio plot with scatter points + drag-to-zoom + element interaction."""

    zoom_applied = pyqtSignal(float, float, float, float)   # xmin, xmax, ymin, ymax
    reset_view = pyqtSignal()
    cursor_moved = pyqtSignal(str)            # 光标坐标读数（DragZoomMixin._dz_emit_hover）
    element_selected = pyqtSignal(str, str)
    element_deleted = pyqtSignal(str, str)
    style_changed = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        self.fig = Figure(figsize=PRL_FIGSIZE_SQUARE, dpi=150)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        self._material_color_map: dict[str, str] = {}
        self._color_counter = 0

        # Save last parameters for refresh（None = auto：按数据自适应范围）
        self._last_materials = None
        self._last_scatter_points = None
        self._last_xlim = None
        self._last_ylim = None

        # Pressure 单位与轴 log 模式（X=compression, Y=P）
        # x_var 供光标读数用（DragZoomMixin._dz_emit_hover）；Y 恒为 P
        self.x_var = "compression"
        self.p_unit = "Mbar"
        self.x_log = False
        self.y_log = False

        # 启用拖拽缩放 + 'a' 重置
        self.setup_drag_zoom()
        # 启用元素交互（pick + 右键菜单）
        self._init_element_interaction()

    def set_p_unit(self, unit: str):
        self.p_unit = unit or "Mbar"
        self.refresh()

    def set_xscale(self, log: bool):
        self.x_log = bool(log)
        self.refresh()

    def set_yscale(self, log: bool):
        self.y_log = bool(log)
        self.refresh()

    def auto_scale(self):
        """恢复 auto 视图：清除显式范围，按当前数据自适应（'a' 键 / 默认）。"""
        self._last_xlim = None
        self._last_ylim = None
        self.update_plot()

    def update_plot(
        self,
        materials: dict[str, MaterialData] | None = None,
        scatter_points: list[dict] | None = None,
        xlim=None,
        ylim=None,
    ):
        """Update EOS plot with reference curves and scatter points."""
        # Save parameters for refresh
        self._last_materials = materials
        self._last_scatter_points = scatter_points
        self._last_xlim = xlim
        self._last_ylim = ylim

        self.ax.clear()
        # 清空 artist map（每次重画时重新注册）
        self._artist_map.clear()
        self._artist_zorder.clear()
        # _element_meta 保留（用户的 style 编辑需要持久化），但删除已不存在的元素
        # 注意：scatter 的 _element_meta 由 render_scatter_points 维护

        has_content = False

        # Plot reference curves if materials provided
        if materials:
            _color_list = [PRL_COLORS["blue"], PRL_COLORS["red"],
                           PRL_COLORS["green"], PRL_COLORS["orange"],
                           PRL_COLORS["purple"], PRL_COLORS["black"]]
            for mid in materials:
                if mid not in self._material_color_map:
                    self._material_color_map[mid] = _color_list[
                        self._color_counter % len(_color_list)
                    ]
                    self._color_counter += 1
            for old_mid in list(self._material_color_map):
                if old_mid not in materials:
                    del self._material_color_map[old_mid]

            for mid, mat in materials.items():
                # 防御：compression 和 p 都要存在且长度一致；参考曲线可能缺这两列
                if (mat.compression is None or len(mat.compression) == 0
                        or mat.p is None or len(mat.p) != len(mat.compression)):
                    continue
                color = self._material_color_map[mid]
                label = mat.name
                if "_" in mid:
                    source = mid.split("_", 1)[1] if len(mid.split("_")) > 1 else ""
                    if source and source not in label.lower():
                        label = f"{mat.name} ({source})"

                # 选中状态：加粗线条
                element_id = f"mat_{mid}"
                is_selected = (self._selected_element_id == element_id)

                style_dict = self._element_meta.get(element_id, {}).get(
                    "style",
                    ElementStyle(TYPE_MATERIAL, color=color, linewidth=1.2,
                                 alpha=0.6).to_dict()
                )
                line_color = style_dict.get("color", color)
                lw = style_dict.get("linewidth", 1.2)
                ls = style_dict.get("linestyle") or "-"
                if is_selected:
                    lw *= 1.5

                # P 单位转换（Y 轴为 P）+ log 过滤
                pf = pressure_factor(self.p_unit)
                comp_arr = np.asarray(mat.compression)
                p_arr = np.asarray(mat.p) * pf
                if self.x_log or self.y_log:
                    vmask = _mask_nonpositive(comp_arr if self.x_log else None,
                                              p_arr if self.y_log else None)
                    if vmask.size and vmask.size == comp_arr.size:
                        comp_arr = comp_arr[vmask]
                        p_arr = p_arr[vmask]

                if is_scatter_material(mid):
                    line, = self.ax.plot(
                        comp_arr, p_arr, linestyle="None",
                        marker="o", markersize=4,
                        markerfacecolor=line_color, markeredgecolor=line_color,
                        label=label, alpha=style_dict.get("alpha") or 0.6,
                        picker=10, pickradius=15, zorder=1)
                else:
                    line, = self.ax.plot(comp_arr, p_arr, color=line_color,
                                         linewidth=lw, linestyle=ls,
                                         label=label, alpha=style_dict.get("alpha") or 0.6,
                                         picker=10, pickradius=15, zorder=1)

                # 绘制误差带（P-CR 图纵轴为 P）
                if hasattr(mat, "p_err") and mat.p_err is not None and len(mat.p_err) > 0:
                    p_err_arr = np.asarray(mat.p_err) * pf
                    valid = (np.isfinite(p_err_arr) & np.isfinite(comp_arr)
                             & np.isfinite(p_arr))
                    if self.y_log and valid.size == p_arr.size:
                        valid &= (p_arr - p_err_arr) > 0
                    if valid.sum() > 1:
                        self.ax.fill_between(
                            comp_arr[valid],
                            p_arr[valid] - p_err_arr[valid],
                            p_arr[valid] + p_err_arr[valid],
                            alpha=0.12, color=line_color, zorder=0,
                        )

                # 注册到交互模型（Edit Style / Change Color 可用）
                self._register_artist(
                    line, element_id, TYPE_MATERIAL, style_dict,
                    data_id=mid, zorder=1, picker=10, pickradius=15,
                )
                has_content = True

        # Plot scatter points via shared helper（注册到交互模型）
        if scatter_points:
            has_scatter = render_scatter_points(
                self.ax, scatter_points,
                x_var="compression", y_var="P", tab_key="P-CR",
                artist_map=self._artist_map,
                element_meta=self._element_meta,
                element_zorder=self._artist_zorder,
                p_unit=self.p_unit,
                x_log=self.x_log, y_log=self.y_log,
            )
            has_content = has_content or has_scatter

        apply_prl_style(self.fig, self.ax,
                         xlabel=LABEL_COMP, ylabel=pressure_label(self.p_unit),
                         xlim=xlim, ylim=ylim,
                         xscale="log" if self.x_log else "linear",
                         yscale="log" if self.y_log else "linear")
        # auto 轴：重新开启自适应（之前的 set_xlim 会关闭它）
        if xlim is None:
            self.ax.set_autoscalex_on(True)
        if ylim is None:
            self.ax.set_autoscaley_on(True)

        # Add legend if there's content
        if has_content:
            self.ax.legend(loc="best", fontsize=GUI_LEGEND_FONTSIZE)

        self.draw_idle()

    def refresh(self, xlim=None, ylim=None, show_legend=None):
        """Refresh plot using current state (for element interaction)."""
        self.update_plot(
            materials=self._last_materials,
            scatter_points=self._last_scatter_points,
            xlim=xlim if xlim is not None else self._last_xlim,
            ylim=ylim if ylim is not None else self._last_ylim,
        )

    # DragZoomMixin hook：松开非拖拽时进入元素交互
    def _handle_click_release(self, event):
        self._ei_handle_click_release(event)


class GenericHugoniotPlot(FigureCanvas, DragZoomMixin, ElementInteractionMixin):
    """
    Generic Hugoniot plot supporting arbitrary X-Y variable combinations + drag-to-zoom.

    This class displays material curves only (no Rayleigh lines or intersections).
    Designed for plotting different physical variable combinations like Us-Up, P-T, etc.
    """

    zoom_applied = pyqtSignal(float, float, float, float)   # xmin, xmax, ymin, ymax
    reset_view = pyqtSignal()
    cursor_moved = pyqtSignal(str)            # 光标坐标读数（DragZoomMixin._dz_emit_hover）
    element_selected = pyqtSignal(str, str)
    element_deleted = pyqtSignal(str, str)
    style_changed = pyqtSignal(str, dict)

    # Variable mapping: name -> (label_attr, data_key)
    VARIABLE_MAP = {
        "Up": (LABEL_UP, "up"),
        "Us": (LABEL_US, "us"),
        "P": (LABEL_P, "p"),
        "rho": (LABEL_RHO, "rho"),
        "compression": (LABEL_COMP, "compression"),
        "T": (LABEL_T, "temperature"),
        "E": (LABEL_E, "energy"),
    }

    # Default axis limits for each variable
    DEFAULT_LIMITS = {
        "Up": (0, 30),
        "Us": (0, 30),
        "P": (0, 1e6),
        "rho": (0, 20),
        "compression": (1, 5),
        "T": (0, 10),
        "E": (0, 20),
    }

    def __init__(self, x_var: str, y_var: str, tab_key: str = "", parent=None):
        """
        Initialize generic plot with specified X and Y variables.

        Parameters
        ----------
        x_var : str
            X-axis variable name, must be in VARIABLE_MAP keys.
        y_var : str
            Y-axis variable name, must be in VARIABLE_MAP keys.
        tab_key : str, optional
            Tab identifier for scatter point filtering (e.g., "P-T", "Us-Up").
        parent : QWidget, optional
            Parent widget.
        """
        if x_var not in self.VARIABLE_MAP:
            raise ValueError(f"Unknown X variable: {x_var}. Must be one of {list(self.VARIABLE_MAP.keys())}")
        if y_var not in self.VARIABLE_MAP:
            raise ValueError(f"Unknown Y variable: {y_var}. Must be one of {list(self.VARIABLE_MAP.keys())}")

        self.x_var = x_var
        self.y_var = y_var
        self.tab_key = tab_key
        self.x_label_attr, self.x_data_key = self.VARIABLE_MAP[x_var]
        self.y_label_attr, self.y_data_key = self.VARIABLE_MAP[y_var]

        self.fig = Figure(figsize=PRL_FIGSIZE_SQUARE, dpi=150)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

        # State
        self.materials: dict[str, MaterialData] = {}
        self._mat_visible: dict[str, bool] = {}
        self._material_color_map: dict[str, str] = {}
        self._color_counter = 0
        self._scatter_points: list[dict] = []

        # Plot settings（None = auto：按数据自适应范围）
        self.xlim = None
        self.ylim = None
        self.show_legend = True
        self.linewidth = 1.2
        self.linestyle = "-"
        # Pressure 单位（仅当 x_var 或 y_var 为 "P" 时生效）与轴 log 模式
        self.p_unit = "Mbar"
        self.x_log = False
        self.y_log = False

        # Save last parameters for refresh (already stored in self.materials and self._scatter_points)

        # 启用拖拽缩放 + 'a' 重置（由 DragZoomMixin 提供）
        self.setup_drag_zoom()
        # 启用元素交互（pick + 右键菜单）
        self._init_element_interaction()

    def set_p_unit(self, unit: str):
        self.p_unit = unit or "Mbar"
        self.refresh()

    def set_xscale(self, log: bool):
        self.x_log = bool(log)
        self.refresh()

    def set_yscale(self, log: bool):
        self.y_log = bool(log)
        self.refresh()

    def update_plot(
        self,
        materials: dict[str, MaterialData] | None = None,
        scatter_points: list[dict] | None = None,
        xlim: tuple | None = None,
        ylim: tuple | None = None,
    ):
        """
        Update generic plot with materials and scatter points.

        Parameters
        ----------
        materials : dict, optional
            Materials to plot Hugoniot curves for. If None, uses self.materials.
        scatter_points : list of dict, optional
            Scatter points to plot. Each dict should contain:
            - id: str
            - label: str
            - scope: "global" or "local"
            - target_tab: str (for local scope)
            - style: dict with color, marker, s, etc.
            - Variable data (e.g., P, T, Up, Us, rho, etc.)
        xlim, ylim : tuple, optional
            Axis limits. If None, uses current self.xlim / self.ylim.
        """
        self.ax.clear()
        # 清空 artist map（每次重画时重新注册）
        self._artist_map.clear()
        self._artist_zorder.clear()

        # Update internal state when explicitly provided
        if materials is not None:
            self.materials = materials
        if scatter_points is not None:
            self._scatter_points = scatter_points
        if xlim is not None:
            self.xlim = xlim
        if ylim is not None:
            self.ylim = ylim

        # Use current state for rendering
        materials = self.materials
        scatter_points = self._scatter_points
        xlim = self.xlim
        ylim = self.ylim

        has_content = False

        # Build material color map and plot curves
        color_list = [PRL_COLORS["blue"], PRL_COLORS["red"],
                      PRL_COLORS["green"], PRL_COLORS["orange"],
                      PRL_COLORS["purple"], PRL_COLORS["black"]]

        # Persistent color assignment per material ID
        for mid in materials:
            if mid not in self._material_color_map:
                self._material_color_map[mid] = color_list[
                    self._color_counter % len(color_list)
                ]
                self._color_counter += 1
        for old_mid in list(self._material_color_map):
            if old_mid not in materials:
                del self._material_color_map[old_mid]

        for mid, mat in materials.items():
            if not self._mat_visible.get(mid, True):
                continue

            # Get X data
            x_data = getattr(mat, self.x_data_key, None)
            if x_data is None or len(x_data) == 0:
                continue

            # Get Y data
            y_data = getattr(mat, self.y_data_key, None)
            if y_data is None or len(y_data) == 0:
                continue

            # Ensure data is numpy array and has same length
            import numpy as np
            x_data = np.array(x_data)
            y_data = np.array(y_data)

            if len(x_data) != len(y_data):
                # Truncate to shorter length
                min_len = min(len(x_data), len(y_data))
                x_data = x_data[:min_len]
                y_data = y_data[:min_len]

            # Pressure 单位转换（仅 P 轴）
            pf = pressure_factor(self.p_unit)
            if self.x_var == "P":
                x_data = x_data * pf
            if self.y_var == "P":
                y_data = y_data * pf

            # Filter out NaN values
            valid_mask = ~(np.isnan(x_data) | np.isnan(y_data))
            x_data = x_data[valid_mask]
            y_data = y_data[valid_mask]

            # log 模式过滤 ≤0 点
            if self.x_log or self.y_log:
                pos_mask = _mask_nonpositive(x_data if self.x_log else None,
                                             y_data if self.y_log else None)
                if pos_mask.size and pos_mask.size == x_data.size:
                    x_data = x_data[pos_mask]
                    y_data = y_data[pos_mask]

            if len(x_data) == 0:
                continue

            color = self._material_color_map[mid]

            # Build label
            label = mat.name
            if "_" in mid:
                source = mid.split("_", 1)[1] if len(mid.split("_")) > 1 else ""
                if source and source not in label.lower():
                    label = f"{mat.name} ({source})"

            # 选中状态：加粗线条
            element_id = f"mat_{mid}"
            is_selected = (self._selected_element_id == element_id)

            style_dict = self._element_meta.get(element_id, {}).get(
                "style",
                ElementStyle(TYPE_MATERIAL, color=color, linewidth=self.linewidth,
                             linestyle=self.linestyle).to_dict()
            )
            line_color = style_dict.get("color", color)
            lw = style_dict.get("linewidth") or self.linewidth
            ls = style_dict.get("linestyle") or self.linestyle
            if is_selected:
                lw *= 1.5

            if is_scatter_material(mid):
                line, = self.ax.plot(
                    x_data, y_data, linestyle="None",
                    marker="o", markersize=4,
                    markerfacecolor=line_color, markeredgecolor=line_color,
                    label=label, alpha=style_dict.get("alpha", 1.0),
                    picker=10, pickradius=15, zorder=1)
            else:
                line, = self.ax.plot(x_data, y_data, color=line_color, linewidth=lw,
                                    linestyle=ls, label=label,
                                    picker=10, pickradius=15, zorder=1)

            # 绘制误差带（仅当 y 轴变量为 P 时，p_err 才有意义）
            if self.y_var == "P" and hasattr(mat, "p_err") and mat.p_err is not None:
                ee = np.array(mat.p_err[:len(x_data)]) * pf
                # 使用与 x_data/y_data 相同的有效掩码
                valid_mask2 = ~(np.isnan(x_data) | np.isnan(y_data) | np.isnan(ee))
                if self.y_log and valid_mask2.size == y_data.size:
                    valid_mask2 &= (y_data - ee) > 0
                if valid_mask2.sum() > 1:
                    xe = x_data[valid_mask2]
                    ye = y_data[valid_mask2]
                    self.ax.fill_between(
                        xe, ye - ee[valid_mask2], ye + ee[valid_mask2],
                        alpha=0.12, color=line_color, zorder=0,
                    )

            # 注册到交互模型（Edit Style / Change Color 可用）
            self._register_artist(
                line, element_id, TYPE_MATERIAL, style_dict,
                data_id=mid, zorder=1, picker=10, pickradius=15,
            )
            has_content = True

        # Render scatter points via shared helper（注册到交互模型）
        has_scatter = render_scatter_points(
            self.ax, scatter_points,
            x_var=self.x_var, y_var=self.y_var, tab_key=self.tab_key,
            artist_map=self._artist_map,
            element_meta=self._element_meta,
            element_zorder=self._artist_zorder,
            p_unit=self.p_unit,
            x_log=self.x_log, y_log=self.y_log,
        )
        has_content = has_content or has_scatter

        # Apply PRL style
        from im_app.core.plot_style import apply_prl_style
        # 当对应轴是 P 时，按单位替换标签
        xlabel = self.x_label_attr
        ylabel = self.y_label_attr
        if self.x_var == "P":
            xlabel = pressure_label(self.p_unit)
        if self.y_var == "P":
            ylabel = pressure_label(self.p_unit)
        apply_prl_style(self.fig, self.ax,
                       xlabel=xlabel, ylabel=ylabel,
                       xlim=xlim, ylim=ylim,
                       xscale="log" if self.x_log else "linear",
                       yscale="log" if self.y_log else "linear")
        # auto 轴：重新开启自适应（之前的 set_xlim 会关闭它）
        if xlim is None:
            self.ax.set_autoscalex_on(True)
        if ylim is None:
            self.ax.set_autoscaley_on(True)

        # Add legend
        if has_content and self.show_legend:
            self.ax.legend(loc="best", fontsize=GUI_LEGEND_FONTSIZE)

        self.draw_idle()

    def refresh(self, xlim=None, ylim=None, show_legend=None):
        """Refresh plot using current state (for element interaction)."""
        # Use current state by default
        self.update_plot(
            materials=self.materials,
            scatter_points=self._scatter_points,
            xlim=xlim if xlim is not None else self.xlim,
            ylim=ylim if ylim is not None else self.ylim,
        )
        if show_legend is not None:
            self.show_legend = show_legend

    # DragZoomMixin hook：松开非拖拽时进入元素交互
    def _handle_click_release(self, event):
        self._ei_handle_click_release(event)

    def set_scatter_points(self, points: list[dict] | None):
        """注入 scatter 点列表（update_plot 时读取）。"""
        self._scatter_points = points or []

    def add_material(self, mat: MaterialData):
        self.materials[mat.id] = mat
        self._mat_visible[mat.id] = True
        self.update_plot()

    def remove_material(self, mat_id: str):
        self.materials.pop(mat_id, None)
        self._mat_visible.pop(mat_id, None)
        self.update_plot()

    def set_material_visible(self, mat_id: str, visible: bool):
        self._mat_visible[mat_id] = visible
        self.update_plot()

    def set_xlim(self, xmin: float, xmax: float):
        self.xlim = (xmin, xmax)
        self.update_plot()

    def set_ylim(self, ymin: float, ymax: float):
        self.ylim = (ymin, ymax)
        self.update_plot()

    def auto_scale(self):
        """恢复 auto 视图：清除显式范围，按当前数据自适应（'a' 键 / 默认）。"""
        self.xlim = None
        self.ylim = None
        self.update_plot()

    def set_legend_visible(self, visible: bool):
        self.show_legend = visible
        self.update_plot()

    def set_linewidth(self, width: float):
        self.linewidth = width
        self.update_plot()

    def set_linestyle(self, style: str):
        self.linestyle = style
        self.update_plot()


# 各 tab 上 scatter 点的误差键映射
_SCATTER_ERR_KEYS = {
    "P-Up":   ("Up_err", "P_err"),
    "P-CR":   ("compression_err", "P_err"),
    "P-rho":  ("rho_err", "P_err"),
    "Us-Up":  ("Us_err", "Up_err"),
    "rho-Up": ("rho_err", "Up_err"),
    "P-Us":   ("P_err", "Us_err"),
}


def render_scatter_points(
    ax,
    points,
    x_var: str,
    y_var: str,
    tab_key: str,
    artist_map=None,
    element_meta=None,
    element_zorder=None,
    p_unit: str = "Mbar",
    x_log: bool = False,
    y_log: bool = False,
) -> bool:
    """
    在指定 ax 上为特定 tab 渲染 scatter 点。

    过滤规则：
    - scope == "global" → 在所有 tab 尝试画
    - scope == "local"  → 仅当 target_tab == tab_key 时画
    - 若 point[x_var] 或 point[y_var] 为 None → 该点跳过
    - log 模式下若对应坐标 ≤0 → 该点跳过（log 无法绘制）

    若提供 artist_map / element_meta / element_zorder（dict 引用），
    会将 scatter artist 注册进交互模型（前缀 "scat_"），支持右键 pick。

    Parameters
    ----------
    points : list of dict
        每个 dict 是 scatter_point（见 spec 第 1 节 schema）。
    x_var, y_var : str
        VARIABLE_MAP 中的 key，例如 "Up"、"P"、"compression"。
    tab_key : str
        当前 tab 的 short name，例如 "P-T"。
    p_unit : str
        Pressure 显示单位（"Mbar"/"GPa"）。当 x_var 或 y_var 为 "P" 时，
        把对应坐标及误差值乘以 pressure_factor(p_unit)。
    x_log, y_log : bool
        是否处于对数刻度模式（用于过滤 ≤0 点）。

    Returns
    -------
    bool
        True 表示至少画了一个点。
    """
    has_drawn = False
    pf = pressure_factor(p_unit)
    x_is_p = (x_var == "P")
    y_is_p = (y_var == "P")

    for point in points or []:
        # scope 过滤
        if point.get("scope") == "local" and point.get("target_tab") != tab_key:
            continue

        x_val = point.get(x_var)
        y_val = point.get(y_var)
        if x_val is None or y_val is None:
            continue

        # Pressure 单位转换
        x_val = float(x_val) * (pf if x_is_p else 1.0)
        y_val = float(y_val) * (pf if y_is_p else 1.0)

        # log 模式过滤 ≤0 点
        if (x_log and x_val <= 0) or (y_log and y_val <= 0):
            continue

        s = point.get("style", {}) or {}
        color = s.get("color")
        marker = s.get("marker", "o")
        markersize = s.get("markersize", 10)
        markeredgecolor = s.get("markeredgecolor", "black")
        markeredgewidth = s.get("markeredgewidth", 1.5)
        alpha = s.get("alpha", 1.0)
        label = point.get("label", "")

        # 若注册到交互模型，用双 artist 技巧：不可见大点击目标 + 可见小 marker
        # （与 intersection 一致；否则 markersize=10 的点击容差太小难以选中）
        if artist_map is not None:
            element_id = f"scat_{point['id']}"
            # 不可见大点击目标（容易点中）
            target, = ax.plot(
                [x_val], [y_val],
                "o",
                markersize=30,
                alpha=0,
                picker=10, pickradius=20,
                zorder=SCATTER_ZORDER,
                linestyle="None",
            )
            artist_map[target] = element_id
            if element_zorder is not None:
                element_zorder[target] = SCATTER_ZORDER

        # 可见 marker（始终画）
        artist, = ax.plot(
            [x_val], [y_val],
            marker,
            color=color,
            markersize=markersize,
            markeredgecolor=markeredgecolor,
            markeredgewidth=markeredgewidth,
            alpha=alpha,
            label=label,
            zorder=SCATTER_ZORDER + 0.5,  # 略高于不可见 target
            linestyle="None",
        )

        # 注册可见 artist 到交互模型（仅当调用方提供 dict）
        if artist_map is not None:
            artist_map[artist] = element_id
            if element_zorder is not None:
                element_zorder[artist] = SCATTER_ZORDER + 0.5
                element_zorder[element_id] = SCATTER_ZORDER + 0.5
            if element_meta is not None and element_id not in element_meta:
                element_meta[element_id] = {
                    "type": "scatter",
                    "data_id": point["id"],
                    "style": s,
                }

        # ── 误差棒 ─────────────────────────────────────────────
        # 从 _SCATTER_ERR_KEYS 查找当前 tab 的 x/y 误差键
        err_keys = _SCATTER_ERR_KEYS.get(tab_key)
        if err_keys:
            x_err_key, y_err_key = err_keys
            x_err = point.get(x_err_key)
            y_err = point.get(y_err_key)
            x_err_val = abs(x_err) if (x_err is not None and np.isfinite(x_err) and x_err > 0) else None
            y_err_val = abs(y_err) if (y_err is not None and np.isfinite(y_err) and y_err > 0) else None
            # Pressure 单位转换误差
            if x_err_val is not None and x_is_p:
                x_err_val *= pf
            if y_err_val is not None and y_is_p:
                y_err_val *= pf
            if x_err_val is not None or y_err_val is not None:
                ecolor = s.get("markeredgecolor", "black")
                ax.errorbar(
                    [x_val], [y_val],
                    xerr=x_err_val, yerr=y_err_val,
                    fmt='none',
                    ecolor=ecolor,
                    capsize=2,
                    capthick=1,
                    alpha=min(alpha, 0.7),
                    zorder=SCATTER_ZORDER + 0.3,
                )

        has_drawn = True

    return has_drawn
