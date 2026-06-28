"""
Interactive Hugoniot-Rayleigh plot canvas.

Embeddable matplotlib FigureCanvas with PRL styling.  Supports adding
materials, Rayleigh lines, intersections, and reflected Hugoniot curves.
Click-to-select intersections via mpl_connect.
"""

from __future__ import annotations

import numpy as np
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
    LEGEND_FONTSIZE,
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


class DragZoomMixin:
    """拖拽框选缩放 + 'a' 键重置的纯 Python mixin。

    Host 类必须满足：
    - 继承自 FigureCanvas（或其他提供 mpl_connect 的类）
    - 定义类属性 ``zoom_applied = pyqtSignal(float, float, float, float)``
      （参数：xmin, xmax, ymin, ymax，data 坐标）
    - 定义类属性 ``reset_view = pyqtSignal()``
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
        """移动超过阈值时创建/更新红色半透明 Rectangle。"""
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

        # Plot settings with defaults
        self.xlim = (0, 30)
        self.ylim = (0, 30)
        self.show_legend = True
        self.linewidth = 1.2
        self.linestyle = "-"

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
        if explicit_id:
            # workflow 加载路径：保留原 id，避免 ix.source_curve*_id 失效
            rid = explicit_id
            try:
                n = int(explicit_id.split("_", 1)[1])
                if n > self._counter:
                    self._counter = n
            except (IndexError, ValueError):
                pass
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

    def set_legend_visible(self, visible: bool):
        self.show_legend = visible
        self.refresh()

    def set_linewidth(self, width: float):
        self.linewidth = width
        self.refresh()

    def set_linestyle(self, style: str):
        self.linestyle = style
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

            line, = self.ax.plot(mat.up, mat.p, color=line_color, linewidth=linewidth,
                                 linestyle=linestyle, label=label, alpha=alpha,
                                 picker=10, pickradius=15, zorder=1)

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

            line, = self.ax.plot(rl.up, rl.p, linestyle=linestyle, color=line_color,
                                 linewidth=linewidth, label=label, alpha=alpha,
                                 picker=10, pickradius=15, zorder=1)

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

            line_color = style.get("color", color)
            linewidth = style.get("linewidth", 0.9)
            linestyle = style.get("linestyle", ":")
            alpha = style.get("alpha", 1.0)

            is_selected = (self._selected_element_id == element_id)
            if is_selected:
                linewidth *= 1.5

            order = np.argsort(rc["up"])
            label = f"{source_name} reflected Hugoniot"

            line, = self.ax.plot(rc["up"][order], rc["p"][order], linestyle=linestyle,
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

            # Build legend label with units
            label_parts = [f"Up={ix.up:.2f} km/s", f"P={ix.p:.3f} Mbar"]
            if hasattr(ix, 'compression_ratio') and ix.compression_ratio:
                label_parts.append(f"CR={ix.compression_ratio:.2f}")
            legend_label = ", ".join(label_parts)

            # Plot a large invisible point for easy picking, then the visible point
            # Invisible large point (click target) - higher zorder than lines
            target, = self.ax.plot(ix.up, ix.p, 'o', markersize=30,
                                   alpha=0,  # Invisible
                                   picker=10, pickradius=20,
                                   zorder=10)  # Higher than lines (zorder=1)
            self._artist_map[target] = element_id
            self._artist_zorder[target] = 10

            # Visible point (actual marker) - even higher zorder
            line, = self.ax.plot(ix.up, ix.p, marker, markersize=marker_size,
                                 markerfacecolor=face_color,
                                 markeredgecolor=edge_color,
                                 markeredgewidth=edge_width,
                                 linestyle='None',
                                 label=legend_label,
                                 zorder=15, alpha=alpha)  # Highest zorder
            self._artist_zorder[line] = 15

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
                         xlabel=LABEL_UP, ylabel=LABEL_P,
                         xlim=xlim or self.xlim, ylim=ylim or self.ylim)

        if (self.materials or self.rayleigh_lines or self.intersections) and (show_legend if show_legend is not None else self.show_legend):
            self.ax.legend(loc="best", fontsize=LEGEND_FONTSIZE)

        # Render scatter points (interactive on P-Up)
        if self._scatter_points:
            render_scatter_points(
                self.ax, self._scatter_points,
                x_var="Up", y_var="P", tab_key="P-Up",
                artist_map=self._artist_map,
                element_meta=self._element_meta,
                element_zorder=self._artist_zorder,
            )

        self.draw_idle()

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

        # Save last parameters for refresh
        self._last_materials = None
        self._last_scatter_points = None
        self._last_xlim = (1, 5)
        self._last_ylim = (0, 10)

        # 启用拖拽缩放 + 'a' 重置
        self.setup_drag_zoom()
        # 启用元素交互（pick + 右键菜单）
        self._init_element_interaction()

    def update_plot(
        self,
        materials: dict[str, MaterialData] | None = None,
        scatter_points: list[dict] | None = None,
        xlim=(1, 5),
        ylim=(0, 10),
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

                line, = self.ax.plot(mat.compression, mat.p, color=line_color,
                                     linewidth=lw, linestyle=ls,
                                     label=label, alpha=style_dict.get("alpha") or 0.6,
                                     picker=10, pickradius=15, zorder=1)
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
            )
            has_content = has_content or has_scatter

        apply_prl_style(self.fig, self.ax,
                         xlabel=LABEL_COMP, ylabel=LABEL_P,
                         xlim=xlim, ylim=ylim)

        # Add legend if there's content
        if has_content:
            self.ax.legend(loc="best", fontsize=LEGEND_FONTSIZE)

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
        "P": (0, 30),
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

        # Plot settings
        self.xlim = self.DEFAULT_LIMITS.get(x_var, (0, 10))
        self.ylim = self.DEFAULT_LIMITS.get(y_var, (0, 10))
        self.show_legend = True
        self.linewidth = 1.2
        self.linestyle = "-"

        # Save last parameters for refresh (already stored in self.materials and self._scatter_points)

        # 启用拖拽缩放 + 'a' 重置（由 DragZoomMixin 提供）
        self.setup_drag_zoom()
        # 启用元素交互（pick + 右键菜单）
        self._init_element_interaction()

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

            # Filter out NaN values
            valid_mask = ~(np.isnan(x_data) | np.isnan(y_data))
            x_data = x_data[valid_mask]
            y_data = y_data[valid_mask]

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

            line, = self.ax.plot(x_data, y_data, color=line_color, linewidth=lw,
                                linestyle=ls, label=label,
                                picker=10, pickradius=15, zorder=1)
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
        )
        has_content = has_content or has_scatter

        # Apply PRL style
        from im_app.core.plot_style import apply_prl_style
        apply_prl_style(self.fig, self.ax,
                       xlabel=self.x_label_attr, ylabel=self.y_label_attr,
                       xlim=xlim, ylim=ylim)

        # Add legend
        if has_content and self.show_legend:
            self.ax.legend(loc="best", fontsize=LEGEND_FONTSIZE)

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

    def set_legend_visible(self, visible: bool):
        self.show_legend = visible
        self.update_plot()

    def set_linewidth(self, width: float):
        self.linewidth = width
        self.update_plot()

    def set_linestyle(self, style: str):
        self.linestyle = style
        self.update_plot()


def render_scatter_points(
    ax,
    points,
    x_var: str,
    y_var: str,
    tab_key: str,
    artist_map=None,
    element_meta=None,
    element_zorder=None,
) -> bool:
    """
    在指定 ax 上为特定 tab 渲染 scatter 点。

    过滤规则：
    - scope == "global" → 在所有 tab 尝试画
    - scope == "local"  → 仅当 target_tab == tab_key 时画
    - 若 point[x_var] 或 point[y_var] 为 None → 该点跳过

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

    Returns
    -------
    bool
        True 表示至少画了一个点。
    """
    has_drawn = False

    for point in points or []:
        # scope 过滤
        if point.get("scope") == "local" and point.get("target_tab") != tab_key:
            continue

        x_val = point.get(x_var)
        y_val = point.get(y_var)
        if x_val is None or y_val is None:
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

        has_drawn = True

    return has_drawn
