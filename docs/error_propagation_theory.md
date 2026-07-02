# 阻抗匹配误差传播 — 理论与算法

## 概述

本文档说明 IM Tool 中 Hugoniot 不确定度从材料数据到交点、反射曲线、反向阻抗匹配的完整误差传播算法。

### 误差来源

当前有两种材料带有 Hugoniot 拟合参数的不确定度：

| 材料 | 模型 | 来源 |
|------|------|------|
| Al (Celliers 2005) | 单段线性 Us-Up 拟合 | Celliers et al., J. Appl. Phys. 98, 113529 (2005) |
| α-石英 (Hamel 2012) | 分段二次 Us-Up 拟合 | Hamel et al. 2012 (论文正文) |

---

## 1. Hugoniot 误差带计算

### 1.1 通用公式

所有模型的误差传播起点相同：
```
P = ρ₀ · Us · Up · 0.01   [Mbar]

σ_P² = (∂P/∂Us)² · σ_Us² + (∂P/∂Up)² · σ_Up²
     = (ρ₀ · Up · 0.01)² · σ_Us² + (ρ₀ · Us · 0.01)² · σ_Up²
```

其中 σ_Up 来自实验测量不确定度（目前未纳入，设为零），σ_Us 来自拟合参数的不确定度。

### 1.2 Al — 线性模型

**拟合公式：**
```
Us = a₀ + a₁ · (Up − β)

参数:
  a₀ = 17.992 ± 0.078 km/s
  a₁ =  1.167 ± 0.026
  β  =  9.838 km/s
```

**Us 的不确定度传播：**
```
σ_Us² = (∂Us/∂a₀)² · σ_a₀² + (∂Us/∂a₁)² · σ_a₁²
      = 1² · σ_a₀² + (Up − β)² · σ_a₁²
      = 0.078² + (Up − 9.838)² · 0.026²
```

由于 β 的选取使 a₀ 和 a₁ 的协方差为零，上述公式是精确的。

**P 的不确定度：**
```
σ_P = ρ₀ · Up · 0.01 · σ_Us
    = 2.7 · Up · 0.01 · σ_Us
```

### 1.3 α-石英 — 分段二次模型

**拟合公式：**

```
Up < 15 km/s:
  Us = a + b · Up + c · Up²

Up ≥ 15 km/s:
  Us = (a − c · Up₁²) + b · Up + 2c · Up₁ · Up
  (其中 Up₁ = 15 km/s)

参数:
  a =  2.4     ± 0.1     km/s
  b =  1.68    ± 0.02
  c = −0.0155  ± 0.001   1/km/s
  Up₁ = 15 km/s
```

**偏导数：**

| 偏导 | Up < 15 | Up ≥ 15 |
|------|---------|---------|
| ∂Us/∂a | 1 | 1 |
| ∂Us/∂b | Up | Up |
| ∂Us/∂c | Up² | 2·Up₁·Up − Up₁² = 30·Up − 225 |

**Us 的不确定度：**
```
σ_Us² = (∂Us/∂a)² · σ_a² + (∂Us/∂b)² · σ_b² + (∂Us/∂c)² · σ_c²
```

**P 的不确定度：**
```
σ_P = ρ₀ · Up · 0.01 · σ_Us
    = 2.65 · Up · 0.01 · σ_Us
```

### 1.4 典型误差量级

| Up (km/s) | Al σ_P (Mbar) | 石英 σ_P (Mbar) |
|:---------:|:-------------:|:---------------:|
| 5 | 0.014 | 0.007 |
| 10 | 0.039 | 0.032 |
| 20 | 0.164 | 0.212 |
| 30 | 0.371 | 0.580 |
| 50 | 1.070 | 2.151 |

---

## 2. 交点误差传播

### 2.1 问题描述

两曲线在交点处满足：
```
P₁(up_int) = P₂(up_int) = p_int
```

当 P₁ 和 P₂ 各自带误差 σ_P₁(up) 和 σ_P₂(up) 时，交点的坐标 (up_int, p_int) 也会产生不确定度。

### 2.2 方法 — 局部线性近似

在交点附近，将两曲线线性化：
```
P₁(up) ≈ p_int + s₁ · (up − up_int)   其中 s₁ = dP₁/dup
P₂(up) ≈ p_int + s₂ · (up − up_int)   其中 s₂ = dP₂/dup
```

定义差值函数：
```
f(up) = P₁(up) − P₂(up)
f(up_int) = 0
df/dup = s₁ − s₂
```

误差传播：
```
σ_f² = σ_P₁² + σ_P₂²    (在 up_int 处插值)

σ_up² = σ_f² / (df/dup)² = (σ_P₁² + σ_P₂²) / (s₁ − s₂)²
```

然后通过曲线 1（或曲线 2）的斜率将 up 误差传播到 p：
```
σ_p² = σ_P₁² + (s₁ · σ_up)²
```

### 2.3 特殊情形

| 情形 | σ_up | σ_p |
|------|------|-----|
| 仅曲线 1 有误差，曲线 2 精确 | σ_P₁ / \|s₁ − s₂\| | 见 2.2 |
| 两曲线均无误差 | `None` | `None` |
| s₁ = s₂（平行或相切） | ∞（奇异，不可靠） | ∞ |

### 2.4 斜率估计

在交点 up_int 处使用局部线性回归估计斜率：
```
窗口 = 0.01 × (up_max − up_min)
取 up_int ± 窗口内的点做 OLS 线性回归
```

---

## 3. 反射 Hugoniot 误差传播

### 3.1 反射操作

```
up_r = 2 · center_up − up_orig
P_r  = P_orig
```

其中 `center_up` 来自交点（因此带有 σ_center_up）。

### 3.2 误差传播

```
σ_up_r² = (∂up_r/∂center_up)² · σ_center_up²
        = 4 · σ_center_up²

σ_P_r² = σ_P_orig²    (P 值不变，误差与源材料相同)
```

注：up_r 的误差是**常数**（对所有反射点相同），仅由中心点不确定度决定。

---

## 4. 反向阻抗匹配误差传播

### 4.1 问题描述

已知目标点 (target_up, target_p) 位于反射 Hugoniot 上，求解反射中心 center_up 使得：
```
P(2 · center_up − target_up) = target_p
```

其中 P(up) 是材料 Hugoniot 的插值函数。

反向阻抗匹配的误差传播涉及三个层次：

1. **反射中心误差** — center_up 的不确定度
2. **反射曲线误差** — 以 center_up 为中心的镜像曲线的不确定度
3. **交点误差** — 反射曲线与原 Hugoniot 的交点的不确定度

### 4.2 反射中心误差

#### 输入误差来源

| 来源 | 符号 | 说明 |
|------|------|------|
| 目标点 up | σ_target_up | 由用户输入的 target_up 精度决定（目前为 0） |
| 目标点 p | σ_target_p | 由用户输入的 target_p 精度决定（目前为 0） |
| Hugoniot 误差 | σ_P_hug(up_orig) | 材料 Hugoniot 在 up_orig 处的压力不确定度 |

其中 `up_orig = 2 · center_up − target_up` 是反射中心在原始 Hugoniot 上对应的 up。

#### 有限差分敏感度

使用有限差分估算 center_up 对 target_up 和 target_p 的敏感度：

```
δ = max(ε · |target|, 10⁻⁶),  ε = 10⁻⁴

∂center/∂target_up ≈ [f(target_up + δ, target_p) − f(target_up − δ, target_p)] / (2δ)
∂center/∂target_p ≈ [f(target_up, target_p + δ) − f(target_up, target_p − δ)] / (2δ)

其中 f(target_up, target_p) 是 reverse_impedance_match 的解算函数
```

#### 合成不确定度

```
σ_center² = (∂center/∂target_up)² · σ_target_up²
          + (∂center/∂target_p)² · σ_target_p²
          + σ_center_from_hug²
```

Hugoniot 误差对反射中心的贡献：

```
σ_center_from_hug = σ_P_hug(up_orig) / (2 · |s(up_orig)|)

其中 s(up_orig) = dP/dup 是原始 Hugoniot 在 up_orig 处的斜率
```

### 4.3 反射曲线误差

反射操作定义为：
```
up_r = 2 · center_up − up_orig
P_r  = P_orig
```

反射曲线的不确定度来自两方面：

```
σ_up_r = 2 · σ_center_up    (对所有反射点相同的常数)
σ_P_r  = σ_P_orig           (反射不改变 P，误差与源材料相同)
```

其中 σ_center_up 来自 4.2 节的计算结果。

### 4.4 交点误差（反射曲线 × 原始 Hugoniot）

反向匹配找到的反射曲线与原始 Hugoniot 的交点即匹配解。该交点涉及的两条曲线为：

- **曲线 1**：反射曲线，携带误差 σ_P_r（来自 4.3）
- **曲线 2**：原始 Hugoniot，携带误差 σ_P_mat

交点误差使用第 2 节的标准方法计算：

```
σ_f² = σ_P_r²(up_int) + σ_P_mat²(up_int)

s₁ = dP_reflected/dup    ≈ −s₂（因镜像对称）
s₂ = dP_hugoniot/dup

σ_up² = σ_f² / (s₁ − s₂)²
σ_p²  = σ_P_r² + (s₁ · σ_up)²
```

由于反射曲线与原始曲线在交点处近似镜像对称（s₁ ≈ −s₂），因此 |s₁ − s₂| ≈ 2|s₂|，相比两条无关曲线的交点，不确定度约为其一半。

### 4.5 自适应刷新时的误差重算

当触发 `_auto_refresh_intersections()` 自适应刷新时：

1. **Pass 1**：非反射依赖的交点（如 Hugoniot×Rayleigh）重算位置 + 误差
2. **Pass 2**：反射曲线跟随锚交点移动 → 重算 `up_err` / `p_err`（调用 `reflect_error_propagation`）
3. **Pass 3**：反射依赖的交点（含 reverse-match 交点）重算位置 + 误差（调用 `recompute_ix`，含 `intersection_error_propagation`）
4. **Pass 4**：清理孤儿交点/曲线

### 4.6 完整传播链路图

```
target_up, target_p (±σ)
        │
        ▼
reverse_impedance_match()
        │
        ├──→ 4.2: reverse_match_error_propagation()
        │        有限差分 → σ_center_up
        │
        ├──→ 4.3: reflect_error_propagation()
        │        σ_up_r = 2·σ_center, σ_P_r = σ_P_mat
        │
        └──→ 4.4: intersection_error_propagation()
                  反射曲线 × 原始 Hugoniot
                  → σ_up, σ_p (交点误差)
```

---

## 5. 代码实现结构

```
数据文件 (.txt / .csv)
  │  头部 # Error Model / # Error Formula / # Error Params
  ▼
data_loader.py
  ├── _parse_error_metadata()       解析 # Error 头行 → fit_params dict
  ├── _read_header_lines()           读取文件前 N 行
  └── compute_material_error_bands() 从 fit_params 计算 p_err / us_err
                                          │
                                          ▼
MaterialData                          存储 p_err, us_err, fit_params
                                          │
                                          ▼
error_propagation.py
  ├── intersection_error_propagation()  交点 σ_up, σ_p
  ├── reflect_error_propagation()       反射 σ_up_r, σ_p_r
  └── reverse_match_error_propagation()  反向匹配 σ_center
                                          │
                                          ▼
plotter.py                             可视化
  ├── fill_between()                    Hugoniot 误差带（半透明）
  └── errorbar()                        交点误差棒（十字线）
                                          │
                                          ▼
intersection_panel.py                    UI 展示
  └── 交点表新增 Up err / P err 列         + 误差棒显隐开关
```

---

## 6. 局限与未来扩展

### 当前局限

1. **Rayleigh 线无误差**：当前仅 Hugoniot 曲线有误差，Rayleigh 线的 D（冲击波速度）和 ρ₀（初始密度）视为精确值
2. **σ_Up = 0**：粒子速度不确定度未纳入传播（可忽略或来自实验）
3. **仅 P-Up 图支持交点 errorbar**：其他标签页暂未添加交点误差棒
4. **一次一阶传播**：未使用完整 Monte Carlo 方法，在非线性较强处可能低估

### 可扩展方向

- Rayleigh 线的 D 和 ρ₀ 添加用户可输入的 ± 值
- 三次拟合 + 协方差矩阵（Cholesky 分解 + Monte Carlo）用于更复杂的误差模型
- 拟合参数协方差（当前 Celliers 线性模型的协方差为零，但一般情况需计入）

---

## 7. 参考文献

1. Celliers, P. M., et al. "Systematic uncertainties in shock-wave impedance-match analysis and the high-pressure equation of state of Al." *J. Appl. Phys.* **98**, 113529 (2005).
2. Kraus, R. G., et al. "Shock vaporization of silica and the thermodynamics of planetary impact events." *J. Geophys. Res.* **117**, E09009 (2012).
3. Brygoo, S., et al. "Analysis of laser shock experiments on precompressed samples using a quartz reference and comparison with ab initio calculations." *J. Appl. Phys.* **118**, 195901 (2015).
4. Knudson, M. D. & Desjarlais, M. P. "Shock compression of quartz to 1.6 TPa: redefining a pressure standard." *Phys. Rev. Lett.* **111**, 195501 (2013).

---

*文档版本 1.0 — 2026-07-02*
