# 理想等离子体 Hugoniot 曲线 — 理论推导

## 1. 背景

在冲击波阻抗匹配分析中，低密度泡沫材料（如 CH foam）在强冲击加载下通常处于完全电离状态，其状态方程可用**理想气体（γ律）模型**近似。与需要查表或经验拟合的固体 Hugoniot 不同，理想等离子体的 Hugoniot 具有解析形式，仅需两个参数即可完整描述：初始密度 $\rho_0$ 和绝热指数 $\gamma$。

---

## 2. Rankine-Hugoniot 跳跃关系（一般形式）

对于正冲击波，守恒方程给出三个跳跃条件：

| 守恒律 | 方程 |
|--------|------|
| 质量 | $\rho_0 U_s = \rho (U_s - U_p)$ |
| 动量 | $P - P_0 = \rho_0 U_s U_p$ |
| 能量 | $E - E_0 = \dfrac{P + P_0}{2}\left(\dfrac{1}{\rho_0} - \dfrac{1}{\rho}\right)$ |

其中：
- $\rho_0$ — 初始密度 (g/cm³)
- $\rho$ — 冲击后密度 (g/cm³)
- $U_s$ — 冲击波速度 (km/s)
- $U_p$ — 粒子速度 (km/s)
- $P$ — 压力 (Mbar)
- $P_0$ — 初始压力
- $E$ — 比内能 (MJ/g)

---

## 3. 理想气体（γ律）状态方程

理想气体的热状态方程为：

$$P = (\gamma - 1) \rho e$$

其中 $e$ 为比内能（单位质量内能），$\gamma$ 为绝热指数（比热比 $C_p / C_v$）。

对于**单原子理想气体 / 完全电离等离子体**，只有平动自由度（3个），因此：

$$\gamma = \frac{f + 2}{f} = \frac{5}{3} \approx 1.667$$

---

## 4. 强冲击波极限下的 Hugoniot 推导

### 4.1 基本假设

对于**强冲击波**（$P \gg P_0$），做以下近似：

1. **$P_0 \approx 0$**：初始压力远小于冲击后压力，可忽略
2. **$E_0 \approx 0$**：初始比内能远小于冲击后比内能，可忽略
3. **材料行为满足 γ 律状态方程**：$P = (\gamma - 1)\rho e$

### 4.2 推导：压缩比 $\rho / \rho_0$

由能量方程，在强冲击极限下：

$$E = \frac{P}{2}\left(\frac{1}{\rho_0} - \frac{1}{\rho}\right) = \frac{P(\rho - \rho_0)}{2\rho\rho_0}$$

代入 γ 律状态方程 $E = e = \dfrac{P}{(\gamma - 1)\rho}$：

$$\frac{P}{(\gamma - 1)\rho} = \frac{P(\rho - \rho_0)}{2\rho\rho_0}$$

消去 $P$ 和 $\rho$：

$$\frac{1}{\gamma - 1} = \frac{\rho - \rho_0}{2\rho_0}$$

$$2\rho_0 = (\gamma - 1)(\rho - \rho_0)$$

$$2\rho_0 + (\gamma - 1)\rho_0 = (\gamma - 1)\rho$$

$$\rho_0(\gamma + 1) = (\gamma - 1)\rho$$

$$\boxed{\frac{\rho}{\rho_0} = \frac{\gamma + 1}{\gamma - 1}}$$

对于 $\gamma = 5/3$：

$$\frac{\rho}{\rho_0} = \frac{5/3 + 1}{5/3 - 1} = \frac{8/3}{2/3} = 4$$

即**强冲击波极限下，压缩比恒为 4，与冲击强度无关**。这是 γ 律气体的一个重要特征。

### 4.3 推导：$U_s$-$U_p$ 关系

由质量守恒方程：

$$\rho_0 U_s = \rho(U_s - U_p)$$

$$U_s = \frac{\rho U_p}{\rho - \rho_0} = \frac{(\rho/\rho_0) U_p}{(\rho/\rho_0) - 1}$$

代入强冲击极限压缩比 $\rho/\rho_0 = (\gamma+1)/(\gamma-1)$：

$$U_s = \frac{(\gamma+1)/(\gamma-1)}{(\gamma+1)/(\gamma-1) - 1} \cdot U_p = \frac{(\gamma+1)/(\gamma-1)}{2/(\gamma-1)} \cdot U_p$$

$$\boxed{U_s = \frac{\gamma + 1}{2} U_p}$$

对于 $\gamma = 5/3$：$U_s = \frac{4}{3} U_p$

**注意**：$U_s$-$U_p$ 关系是**线性**的，斜率为 $(\gamma+1)/2$。这与固体材料的线性 $U_s$-$U_p$ 关系（$U_s = C_0 + s \cdot U_p$）形式上相似，但理想气体的截距 $C_0 = 0$。

### 4.4 推导：$P$-$U_p$ 关系（Hugoniot 曲线）

由动量方程，强冲击极限下：

$$P = \rho_0 U_s U_p$$

代入 $U_s = \frac{\gamma+1}{2} U_p$：

$$P = \rho_0 \cdot \frac{\gamma + 1}{2} \cdot U_p^2$$

**单位换算**：$\rho_0$ 的单位为 g/cm³，$U_s$ 和 $U_p$ 的单位为 km/s。

$$P \text{ [Mbar]} = \rho_0 \text{ [g/cm}^3\text{]} \times U_s \text{ [km/s]} \times U_p \text{ [km/s]} \times 0.01$$

其中因子 0.01 来源于：

$$1 \text{ Mbar} = 10^{12} \text{ dyn/cm}^2 = 10^6 \text{ bar}$$
$$\rho_0 \text{ [g/cm}^3] \times U_s \text{ [10}^5 \text{ cm/s]} \times U_p \text{ [10}^5 \text{ cm/s]} = \rho_0 U_s U_p \times 10^{10} \text{ dyn/cm}^2 = \rho_0 U_s U_p \times 0.01 \text{ Mbar}$$

因此：

$$\boxed{P \text{ [Mbar]} = \rho_0 \cdot \frac{\gamma + 1}{2} \cdot U_p^2 \times 0.01}$$

在 $U_p$-$P$ 平面上，理想等离子体的 Hugoniot 曲线是一条**抛物线**（$P \propto U_p^2$）。

---

## 5. 汇总：理想等离子体 Hugoniot 公式

给定参数：
- $\rho_0$：初始密度 (g/cm³)
- $\gamma$：绝热指数（默认 $5/3$）

对 $U_p \in [0, U_{p,\max}]$ 生成 Hugoniot 数据点：

| 物理量 | 公式 |
|--------|------|
| 冲击波速度 $U_s$ | $U_s = \dfrac{\gamma+1}{2} U_p$ |
| 压力 $P$ | $P = \rho_0 \cdot \dfrac{\gamma+1}{2} \cdot U_p^2 \times 0.01$ (Mbar) |
| 密度 $\rho$ | $\rho = \rho_0 \cdot \dfrac{\gamma+1}{\gamma-1}$（常数，与 $U_p$ 无关） |
| 压缩比 | $\rho/\rho_0 = \dfrac{\gamma+1}{\gamma-1}$（常数，与 $U_p$ 无关） |

---

## 6. 模型适用条件与局限性

### 6.1 适用场景

- **完全电离等离子体**：温度足够高，所有电子已脱离原子束缚
- **低密度泡沫材料**：如 CH foam ($\rho_0 \sim 0.1$ g/cm³) 在 T > 几十 eV 时
- **强冲击波**：$P \gg P_0$，即冲击后压力远大于初始压力

### 6.2 模型假设

1. **理想气体行为**：粒子间无相互作用势，仅有动能贡献
2. **3 自由度**：仅考虑平动自由度，忽略电子激发、辐射等
3. **强冲击极限**：$P_0 \approx 0$, $E_0 \approx 0$
4. **化学平衡**：电离度不随冲击状态变化（完全电离）

### 6.3 局限性

1. **不适用于弱冲击**：当 $P$ 与 $P_0$ 可比时，压缩比不再是常数，需使用完整 Rankine-Hugoniot 方程
2. **不适用于部分电离**：若有未完全电离的成分，$\gamma$ 会偏离 5/3
3. **不适用于高简并区**：若电子简并效应显著，状态方程偏离理想气体
4. **不适用于辐射主导区**：极高温度下辐射压贡献显著时，有效 $\gamma$ 会降低

---

## 7. 与现有程序的兼容性

### 7.1 数据结构兼容

理想等离子体 Hugoniot 生成的数据应与现有 `MaterialData` 数据结构完全兼容：

```
Up(km/s)  — 粒子速度数组
Us(km/s)  — 冲击波速度数组
P(Mbar)   — 压力数组
rho(g/cm3) — 密度数组（常数 = ρ₀ × (γ+1)/(γ-1)）
compression — 压缩比数组（常数 = (γ+1)/(γ-1)）
```

### 7.2 物理计算兼容

生成后的理想等离子体曲线可直接用于现有所有工作流：

1. **Rayleigh 线求交**：`find_intersections()` — 与一般 Hugoniot 无异
2. **Hugoniot 反射**：`reflect_hugoniot()` — 镜面对称操作与材料类型无关
3. **压缩比计算**：`compression_ratio(D, up)` — 注意对于理想等离子体，由 Rayleigh 线和 Hugoniot 交点确定的压缩比在强冲击极限下应接近理论值 $(\gamma+1)/(\gamma-1)$，可作为自洽性检验

### 7.3 需要新增的参数

用户创建理想等离子体材料时，需要输入：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| $\rho_0$ | 初始密度 (g/cm³) | 无默认值，必须指定 |
| $\gamma$ | 绝热指数 | $5/3$ |
| $U_{p,\max}$ | 最大粒子速度 (km/s) | 200 |
| 材料名称 | 用于标识 | 无默认值 |

---

## 8. 验证

以参考 notebook 中的 CH foam 为例：

- $\rho_0 = 0.089$ g/cm³, $\gamma = 5/3$
- 理论压缩比：$\rho/\rho_0 = 4$
- $U_s = \frac{4}{3} U_p$
- 取 $U_p = 10$ km/s：
  - $U_s = 13.33$ km/s
  - $P = 0.089 \times 13.33 \times 10 \times 0.01 = 0.1187$ Mbar
  - 或直接用 $P = 0.089 \times \frac{4}{3} \times 100 \times 0.01 = 0.1187$ Mbar ✓
