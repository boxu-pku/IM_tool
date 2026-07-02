# 蒙特卡洛误差传播 — 理论与实现

## 为什么需要蒙特卡洛？

阻抗匹配误差传播的挑战在于它是一个**多层耦合**的过程：

```
材料 Hugoniot 误差带
    ↓
交点 1（Hugoniot × Rayleigh）
    ↓
反射 Hugoniot（中心 = 交点 1）
    ↓
交点 2（反射 Hugoniot × Rayleigh）
    ↓
Reverse match（从目标点反推反射中心）
```

当前的解析微分法（`error_propagation.py`）在每一层做局部线性近似，存在三个根本问题：

1. **反射曲线的 P 误差不完整**：`σ_P_r = σ_P_source` 忽略了反射中心不确定度通过 `up_orig = 2·center − up_r` 传递到 P 的贡献
2. **水平误差被忽略**：反射曲线的 `up_err` 未参与交点误差计算，`intersection_error_propagation` 只接受垂直误差 `p_err`
3. **非线性耦合丢失**：多层链式传播中，每步独立做线性化，非线性和相关性被完全忽略

蒙特卡洛方法通过直接抽样求解以上所有问题。

---

## 方法概述

### 核心思想

```
参数层（误差源）           计算层（确定性）              结果层（统计）

对 i = 1..N：
  从 fit_params 分布
  抽取随机参数
    │
    ├─→ 生成 Hugoniot 曲线
    ├─→ 找交点（Hugoniot × Rayleigh）
    ├─→ 计算反射曲线
    ├─→ 找交点（反射 × Rayleigh）
    ├─→ Reverse match
    │
    保存本轮所有交点和反射曲线
    
N 轮完成后：
  每个交点 → up_std, p_std（N 次结果的标准差）
  每条反射曲线 → 逐点 p_std
```

### 误差源

当前有误差模型的两个材料：

| 材料 | 模型 | 抽样参数 |
|------|------|---------|
| Al (Celliers 2005) | 线性 `Us = a₀ + a₁·(up − β)` | a₀ ~ N(17.992, 0.078), a₁ ~ N(1.167, 0.026) |
| 石英 (Hamel 2012) | 分段二次型 | a ~ N(2.4, 0.1), b ~ N(1.68, 0.02), c ~ N(-0.0155, 0.001) |

Rayleigh 线（D, ρ₀ 为用户输入）和无 `fit_params` 的材料（SESAME 表等）始终保持确定。

---

## 算法步骤

### 第 1 步：随机 Hugoniot 生成

对每个有 `fit_params` 的材料，根据其误差模型生成一条扰动曲线：

**线性模型（Al）：**
```
a₀_s = N(17.992, 0.078)
a₁_s = N(1.167, 0.026)
Us = a₀_s + a₁_s · (up − 9.838)
P  = ρ₀ · up · Us · 0.01
```

**分段二次型（石英）：**
```
a_s = N(2.4, 0.1)
b_s = N(1.68, 0.02)
c_s = N(-0.0155, 0.001)

Up < 15:  Us = a_s + b_s·Up + c_s·Up²
Up ≥ 15:  Us = (a_s − c_s·225) + b_s·Up + 30·c_s·Up
P  = ρ₀ · up · Us · 0.01
```

up 网格复用原材料的 `mat.up` 数组，只扰动 P 值。

### 第 2 步：计算链

每轮抽样中，用与 `_auto_refresh_intersections` 相同的依赖顺序运行完整计算：

1. **PASS 1 — 不依赖反射线的交点**：Hugoniot × Rayleigh 类的交点
2. **PASS 2 — 反射曲线**：从 PASS 1 交点的本轮值计算反射曲线
3. **PASS 3 — 依赖反射线的交点**：反射曲线 × Rayleigh / 其他曲线的交点

每步调用现有的确定性函数：
- `find_intersections(up1, p1, up2, p2)`
- `reflect_hugoniot(up, p, center_up)`
- `reverse_impedance_match(target_up, target_p, hugoniot_up, hugoniot_p)`

### 第 3 步：统计聚合

N 轮完成后：

**交点：**
```
up_std = std(up₁, up₂, ..., up_N)   # 样本标准差 (ddof=1)
p_std  = std(p₁, p₂, ..., p_N)
n_valid = 有效轮数（交点存在且有限）
```

**反射曲线：**
```
对每个数组索引 j：
  p_std[j] = std(p_r₁[j], p_r₂[j], ..., p_r_N[j])

up_err = 2 · std(center_up₁, ..., center_up_N)   # 常数数组
```

有效样本数不足 10 时不报告误差（避免小样本统计不可靠）。

### 第 4 步：应用结果

MC 结果写回交点对象和反射曲线字典的 `up_err` / `p_err` 字段，与现有绘图/表格渲染完全兼容：

- `InteractiveHugoniotPlot.refresh()` — `errorbar(xerr=ix.up_err, yerr=ix.p_err)`
- `IntersectionPanel.set_intersections()` — 表格第 6-7 列显示误差值
- 反射曲线的 `fill_between` 绘制误差带

交点坐标本身（`ix.up`, `ix.p`）**保持不变** — MC 只修改误差估计，不改变名义解。

---

## 实现文件

| 文件 | 功能 |
|------|------|
| `im_app/core/monte_carlo.py` | MC 引擎：`MonteCarloEngine`, `generate_random_hugoniot`, `MonteCarloResult` |
| `im_app/gui/main_window.py` | UI 集成：`_run_monte_carlo_for_scene()` 在 4 个入口被调用 |

### MonteCarloEngine.run() 参数

```python
def run(
    self,
    materials: dict[str, MaterialData],
    intersections: list[Intersection],
    reflected_curves: list[dict],
    rayleigh_lines: dict[str, RayleighLine],
    n_samples: int = 500,
    progress_callback: Callable[[int], bool] | None = None,
) -> MonteCarloResult:
```

### MonteCarloResult 结构

```python
@dataclass
class MonteCarloResult:
    intersection_stats: dict[str, IntersectionStats]
        # ix_id -> {up_mean, up_std, p_mean, p_std, n_valid}
    reflected_stats: dict[str, ReflectedStats]
        # rc_id -> {up_err: ndarray, p_err: ndarray}
    n_total: int
```

---

## 参数选择

### N=500 的权衡

| N | σ 估计误差 | 典型运行时间（3 材料 + 3 交点） |
|---|-----------|-------------------------------|
| 100 | ~10% | 1–2 秒 |
| **500** | **~4.5%** | **5–10 秒** |
| 1000 | ~3.2% | 10–20 秒 |
| 5000 | ~1.4% | 50–100 秒 |

N=500 在精度和交互响应之间取得平衡。进度对话框允许用户取消较长的运行。

### 随机数生成

使用 `numpy.random.default_rng()`（PCG-64 算法），每轮调用 `rng.normal(mean, sigma)`。

---

## 局限性

1. **参数独立假设**：当前假设各拟合参数之间协方差为零（`cov(a₀, a₁) = 0`）。如果原始文献提供了协方差矩阵，可扩展 `generate_random_hugoniot` 使用 `rng.multivariate_normal`。

2. **逐点 P 误差 vs 插值误差**：反射曲线的 `p_err` 按数组索引计算，而非按固定 `up_r` 网格插值。由于 `center_up` 变动幅度较小（σ ~0.4 km/s），`up_r` 的偏移可忽略。

3. **Rayleigh 线无误差**：D 和 ρ₀ 的测量误差暂未纳入。后续可为 Rayleigh 线添加可选的误差输入。

4. **未处理的奇异情形**：当某轮抽样的参数导致 Hugoniot 曲线物理上不合理（如 Us < Up）时，该轮结果被丢弃。在我们的参数范围内（σ 相对均值较小），这种情况极少发生。

---

## 参考文献

- Celliers et al., "Shock-induced melting of aluminum", J. Appl. Phys. 97, 103529 (2005)
- Hamel et al., "Equation of state of quartz", Acta Physica Sinica (2012)
- JCGM 100:2008, "Evaluation of measurement data — Guide to the expression of uncertainty in measurement"
- "Monte Carlo methods for uncertainty propagation", NIST/SEMATECH e-Handbook of Statistical Methods
