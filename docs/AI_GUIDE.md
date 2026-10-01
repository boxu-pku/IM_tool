# IM Tool AI 接入指南（AI_GUIDE）

面向 AI agent（ZCode / Claude / 任意能执行 shell 的 agent）**操作** IM Tool
的无头（headless）接口。不涉及如何修改 IM Tool 代码本身——那是 CLAUDE.md
的职责。

## 1. 核心概念

- **会话即 workflow JSON 文件**。一个 workflow 描述一次完整的阻抗匹配
  分析：勾选哪些材料、几条 Rayleigh 线、哪些反射/release 线、哪些交点。
  AI 生成或修改的会话，用户可以用 GUI 直接打开；GUI 保存的会话
  （`im_app/workflows/*.json`）AI 可以直接跑。格式见 §4。
- **headless 引擎与 GUI 走同一条代码路径**（offscreen 实例化真实的
  MainWindow），所以自动重算交点、release/reflect 语义、蒙特卡洛误差的
  行为与 GUI 完全一致。
- **stdout 永远是纯 JSON**（UTF-8）。库内调试输出（如 `[MC DEBUG]`）会被
  引到 stderr。解析 stdout 即可，不要解析 stderr。
- **不遥控已打开的 GUI 实例**。headless 与 GUI 是各自独立的进程，通过
  workflow 文件衔接。

## 2. 调用方式

仓库根目录下（推荐）：

```bash
python -m im_app.cli <子命令> ...
```

或安装后使用短命令（`pip install -e .`）：

```bash
imt <子命令> ...
```

以下示例统一用 `python -m im_app.cli`。**全部命令默认在仓库根目录执行**；
材料库默认路径 `im_app/standard_library`（可用 `--lib` 覆盖）。

## 3. 命令参考

### 3.1 `materials` —— 查询标准材料库（不启动 Qt，毫秒级）

```bash
# 列出全部材料（id/name/source/rho0/tags/points/数据范围）
python -m im_app.cli materials list --limit 500

# 按 id / name / tag 模糊搜索（大小写不敏感）
python -m im_app.cli materials search quartz

# 单个材料详情；--data 附带全部数据行（rows，列同库文件）
python -m im_app.cli materials show Quartz_Hamel2012 --data
```

标准库数据文件的列名固定为：
`Up(km/s)`, `Us(km/s)`, `P(Mbar)`, `rho(g/cm3)`, `compression`, `T(eV)`,
`E(MJ/g)`, `source`（缺测列值为 `null`）。

### 3.2 `template` —— 生成 workflow 模板

```bash
# 打印两层阻抗匹配模板 JSON（占位符见 §4.3）
python -m im_app.cli template impedance

# 直接落盘（created 字段自动填当前时间）
python -m im_app.cli template impedance --out my_shot.json
```

### 3.3 `run` —— 执行 workflow（AI 主用命令）

```bash
python -m im_app.cli run <workflow.json> --out <目录> \
    [--no-refresh] [--find CURVE1,CURVE2 ...] [--dpi 200]
```

流程：加载 workflow →（默认）自动重算全部交点 + 蒙特卡洛误差 → 导出。

- `--no-refresh`：按 workflow 里存的数值原样输出（跳过重算，一般不用）。
- `--find C1,C2`：加载后额外找一对交点（可重复多次）。同对交点已存在时
  会被去重拒绝（GUI 同款行为，状态在 stderr）。
- 输出目录内容：
  - `results.json` —— 全部数值结果（结构见 §5）
  - `intersections.csv` —— 交点平铺表（同 results.json 的 intersections）
  - `p_up.png` `p_cr.png` `p_rho.png` `us_up.png` `p_t.png` `rho_up.png`
    `t_up.png` `e_up.png` `p_us.png` —— 9 个绘图标签页（空页自动跳过，
    见返回 JSON 的 `skipped_empty`）
- stdout 返回概要 JSON：`ok / n_intersections / n_materials / warnings /
  figures / skipped_empty / results_json` 等路径。

退出码：0 成功；2 输入错误（文件不存在、JSON 非法、id 找不到）；
1 运行期错误。错误信息在 stdout 的 `error` 字段里。

### 3.4 `curves` —— 查看会话中某条曲线的数据

```bash
# 需要 workflow 提供场景；curve_id 可以是材料 id / rl_N / refl_N
python -m im_app.cli curves show rl_1 --workflow my_shot.json
python -m im_app.cli curves show refl_1 --workflow my_shot.json --max-points 100
```

返回 `{id, n_points, up_km_s[], p_mbar[], p_err_mbar|null}`。

## 4. workflow JSON schema（version 1.0）

顶层键：`version` `created` `materials` `rayleigh_lines` `intersections`
`reflected_curves` `plot_settings` `scatter_points`。

### 4.1 materials

```json
[{"id": "Quartz_Hamel2012", "visible": true}]
```

`id` 必须是标准库内真实存在的 id（用 `materials search` 查）。库中不
存在的 id 会在 `run` 返回的 `warnings` 里报 `material not found`。

### 4.2 rayleigh_lines

```json
[{"id": "rl_1", "material_id": "Quartz_Hamel2012",
  "D": 29.2, "rho0": 2.65, "sigma_D": 0.05, "sigma_rho0": 0.0}]
```

- `D`：冲击波速 Us（km/s）；`rho0`：初始密度（g/cm³）。
- `sigma_*` > 0 会触发蒙特卡洛误差传播（500 样本）。
- `material_id` 只是显示名关联，可以填任意文本；`id` 保持 `rl_N` 序列。

### 4.3 intersections 与 reflected_curves（关键）

交点的 `up`/`p` **只是占位**（模板里是 0），`run` 时按 `source_curve1_id`
× `source_curve2_id` 全部重算。**绝对不要删掉 source 字段**，否则该交点
不会重算（老 workflow 兼容行为）。

两层阻抗匹配的标准写法（`template impedance` 生成的结构）：

1. `ix_specific_0`：标准材料 Hugoniot × 自己的 Rayleigh 线
   （`source_curve1_id = 材料id`，`source_curve2_id = "rl_1"`）→ 得到
   标准件上的冲击状态。
2. `refl_1`：标准材料的反射线，`anchor_intersection_id = "ix_specific_0"`
   —— 反射中心自动跟随 ix_specific_0 的重算结果，`center_up` 可填 0
   占位。
3. `ix_specific_1`：样品 Rayleigh 线 × 反射线
   （`source_curve1_id = "rl_2"`，`source_curve2_id = "refl_1"`）→
   阻抗匹配得到的样品状态。

**release 线变体**（固定 Up 锚、不跟随交点）：`reflected_curves` 里设
`"kind": "release"` + `"anchor_up": <Up值>`，`anchor_intersection_id`
留 `null`。

**反演（reverse match）变体**：`source_ix_id` 指向某个交点、
`anchor_intersection_id` 为 `null` —— 反射线由该交点状态反解，加载与
刷新时同样自动重算。

### 4.4 plot_settings / scatter_points

GUI 显示设置与实验散点。headless 分析一般留空（`{}` / `[]`）即可，
`run` 导图时用数据自动范围。

## 5. results.json 结构

```jsonc
{
  "generated_at": "...",
  "workflow": "my_shot.json",
  "units": {"up": "km/s", "p": "Mbar", "rho0": "g/cm^3",
            "note": "内部压力单位一律 Mbar；换算 GPa 需 ×100"},
  "materials": [{"id", "name", "rho0_g_cm3", "n_points",
                  "up_range_km_s", "p_range_mbar"}],
  "rayleigh_lines": [{"id", "material_id", "D_km_s", "rho0_g_cm3",
                       "sigma_D_km_s", "sigma_rho0_g_cm3", "visible"}],
  "reflected_curves": [{"id", "source_id", "kind", "anchor_up_km_s",
                         "center_up_km_s", "anchor_intersection_id",
                         "source_ix_id", "up_err_km_s", "p_err_mbar"}],
  "intersections": [{"id", "curve1_id", "curve2_id",
                      "source_curve1_id", "source_curve2_id",
                      "up_km_s", "p_mbar", "compression_ratio",
                      "up_err_km_s", "p_err_mbar", "compression_err",
                      "rho_err_g_cm3"}],
  "warnings": ["material not found in library: ..."]
}
```

`*_err` 字段：无误差源或 MC 未收敛时为 `null`。

## 6. 单位与陷阱（务必读）

| 事项 | 约定 |
|---|---|
| 压力单位 | **内部一律 Mbar**（workflow、results、CSV 全部）。GPa = Mbar × 100 |
| 速度 | 全部 km/s（Up、Us、D） |
| 密度 | g/cm³ |
| 激波关系 | Rayleigh 线 `P = ρ₀·D·up`，内部按 Mbar 量纲存储 |
| `ignore_first_at_creation` | 找交点时忽略近零点交点，通常保持 `true` |
| 交点去重 | 已存在同曲线对交点时再次 find 会被拒绝（stderr 有提示） |
| 空图导出 | 无数据的标签页自动跳过，不产生空白 PNG |
| Windows | offscreen 模式的 Qt 字体告警（QFontDatabase）无害，忽略 |

## 7. 典型任务 recipe

### 7.1 两层阻抗匹配（最常用）

```bash
python -m im_app.cli materials search quartz        # 1. 找标准件材料 id
python -m im_app.cli template impedance --out s1.json  # 2. 生成模板
# 3. 编辑 s1.json：替换 MATERIAL_STANDARD/MATERIAL_SAMPLE 为真实 id，
#    填入两发的 D / rho0 / sigma（找交点结构不要动，见 §4.3）
python -m im_app.cli run s1.json --out runs/s1      # 4. 执行
# 结果：runs/s1/results.json 的 intersections[1] 即样品匹配点
```

### 7.2 在样品 Hugoniot 上加 release 线再匹配

在 workflow 的 `reflected_curves` 追加：

```json
{"id": "refl_2", "source_id": "SAMPLE_ID", "center_up": 0,
 "anchor_intersection_id": null, "source_ix_id": null,
 "kind": "release", "anchor_up": 2.5}
```

再声明一条 `source_curve2_id: "refl_2"` 的交点，`run` 即得匹配结果。
（GUI 里对应 "Release @ Up" 双击编辑锚点——headless 直接改 `anchor_up`。）

### 7.3 只查数据不动图

```bash
python -m im_app.cli materials show Al_Celliers2005 --data
python -m im_app.cli curves show refl_1 --workflow s1.json
```

### 7.4 误差分析

给 `rayleigh_lines` 的 `sigma_D`/`sigma_rho0` 填非零值（或选用带
`fit_params` 的材料），`run` 自动跑 500 样本蒙特卡洛，`*_err` 字段即回写
结果。

### 7.5 批量多发实验

对每发生成一个 workflow（可程序化批量改模板），循环
`run wf_i.json --out runs/shot_i/`，汇总各 `results.json`。

## 8. Python API（脚本内直接用引擎）

不想走子进程时：

```python
from im_app.api.headless import HeadlessSession

s = HeadlessSession()                 # 自动 offscreen
s.load_workflow("s1.json")
s.refresh()                           # 重算交点 + MC
s.find_intersection("Quartz_Hamel2012", "rl_1")
s.add_release("SAMPLE_ID", 2.5)
res = s.results()                     # dict → json.dump 即 §5 结构
s.export("runs/api_demo")             # results.json + 图 + CSV
s.save_workflow("s1_rerun.json")      # 回写会话（GUI 可打开）
s.close()
```

## 9. 已知边界

- 不支持也没有计划支持"遥控正在运行的 GUI 进程"。
- PyQt5 不与其他 Qt 绑定混用同一进程（会静默崩溃）。CLI 每次调用都是
  独立进程，天然规避；Python API 用户自己在同一进程里 import PyQt6
  会出事。
- `run` 单次执行的蒙特卡洛为 500 样本同步计算，带误差源时单发约几秒。
- workflow 里交点的 `curve1_id`/`curve2_id` 只是显示标签，重算后不更新；
  数值看 `source_curve*_id` + `up_km_s`/`p_mbar`。
