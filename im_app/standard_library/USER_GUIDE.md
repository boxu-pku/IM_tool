# 手动添加 Hugoniot 数据指南

本指南详细介绍如何手动添加新的 Hugoniot 数据到标准库。

## 目录

- [方法一：使用 TXT 格式（推荐）](#方法一使用-txt-格式推荐)
- [方法二：使用 CSV 格式](#方法二使用-csv-格式)
- [从 Excel 转换](#从-excel-转换)
- [更新元数据索引](#更新元数据索引)
- [常见问题](#常见问题)

---

## 方法一：使用 TXT 格式（推荐）

TXT 格式人类可读，便于手动编辑和验证。

### 步骤 1：准备数据

准备您的 Hugoniot 数据，至少包含以下列：

| 列名 | 说明 | 示例 |
|------|------|------|
| Up | 粒子速度 (km/s) | 0.5, 1.0, 1.5... |
| Us | 冲击波速度 (km/s) | 5.2, 5.8, 6.4... |
| P | 压力 (Mbar) | 0.07, 0.15, 0.23... |
| rho | 密度 (g/cm³) | 2.85, 3.02, 3.18... |
| compression | 压缩比 (rho/rho0) | 1.05, 1.12, 1.18... |

### 步骤 2：创建 TXT 文件

在 `standard_library/materials/` 目录下创建新文件，例如 `MyMaterial.txt`：

```
# =============================================================================
# Hugoniot Data File
# Format Version: 1.0
# =============================================================================
# Material:          My Material
# Reference:         Smith et al. 2020
# Initial Density:   2.70 g/cm^3
# Data Source:       Experimental data from Laboratory X
# Date Created:      2026-05-30
# Notes:             Principal Hugoniot, measured with laser interferometry
# =============================================================================
# Column Units:
#   Up      km/s       - Particle velocity
#   Us      km/s       - Shock velocity
#   P       Mbar       - Pressure
#   rho     g/cm^3     - Density
#   eta     -          - Compression ratio
# =============================================================================
# Data Columns (tab-separated):
# Up(km/s)    Us(km/s)    P(Mbar)     rho(g/cm^3)  compression
# =============================================================================
0.500    5.200    0.070    2.850    1.056
1.000    5.800    0.150    3.020    1.118
1.500    6.400    0.230    3.180    1.178
2.000    7.000    0.310    3.340    1.237
# =============================================================================
# End of Data
# Total Points: 4
# Up Range: [0.5, 2.0] km/s
# P Range: [0.07, 0.31] Mbar
# Compression Range: [1.056, 1.237]
# =============================================================================
```

### 步骤 3：计算统计信息

在文件末尾添加统计信息：

```
# Total Points: <数据行数>
# Up Range: [<最小值>, <最大值>] km/s
# P Range: [<最小值>, <最大值>] Mbar
# Compression Range: [<最小值>, <最大值>]
```

### 步骤 4：保存文件

确保文件保存设置：
- **编码**：UTF-8
- **行尾符**：LF（Unix 风格）

### 步骤 5：验证格式

使用验证工具检查文件：

```bash
python -m im_app.core.data_converter validate materials/MyMaterial.txt
```

---

## 方法二：使用 CSV 格式

CSV 格式更简洁，适合程序处理。

### 步骤 1：创建 CSV 文件

创建 `MyMaterial.csv`：

```csv
# Material: My Material
# Reference: Smith et al. 2020
# Initial Density (g/cm³): 2.70
# Data Source: Experimental data from Laboratory X
# Date Created: 2026-05-30
# Notes: Principal Hugoniot, measured with laser interferometry
# Columns: Up(km/s), Us(km/s), P(Mbar), rho(g/cm³), compression
Up(km/s)	Us(km/s)	P(Mbar)	rho(g/cm³)	compression
0.500	5.200	0.070	2.850	1.056
1.000	5.800	0.150	3.020	1.118
1.500	6.400	0.230	3.180	1.178
2.000	7.000	0.310	3.340	1.237
```

### 步骤 2：保存文件

确保：
- **编码**：UTF-8
- **行尾符**：LF（\n）
- **分隔符**：Tab（\t）

---

## 从 Excel 转换

如果您的数据在 Excel 中：

### 方法 A：复制粘贴（推荐）

1. 在 Excel 中整理数据，列名按标准格式
2. 选择数据区域（包括列名）
3. 复制（Ctrl+C）
4. 打开文本编辑器（如 VS Code、Notepad++）
5. 粘贴数据
6. 添加元数据头部（见 TXT 或 CSV 格式）
7. 保存为 `.txt` 或 `.csv`

**注意**：Excel 粘贴的数据通常使用 Tab 分隔，可以直接使用。

### 方法 B：导出 CSV

1. 在 Excel 中：文件 → 另存为 → CSV UTF-8（逗号分隔）*.csv
2. 在文本编辑器中打开导出的 CSV
3. 将逗号分隔符替换为 Tab
4. 添加元数据头部
5. 保存

---

## 更新元数据索引

添加文件后，需要更新 `metadata.json`：

### 步骤 1：打开 metadata.json

```json
{
  "version": "1.0",
  "materials": [
    {
      "id": "Al_3717_sesame",
      "name": "Aluminum",
      ...
    }
  ]
}
```

### 步骤 2：添加新材料条目

在 `materials` 数组中添加：

```json
{
  "id": "MyMaterial_Smith2020",
  "name": "My Material",
  "source": "Smith et al. 2020",
  "rho0": 2.70,
  "file": "materials/MyMaterial.txt",
  "tags": ["experimental", "2020"],
  "points": 4,
  "up_range": [0.5, 2.0],
  "p_range": [0.07, 0.31],
  "compression_range": [1.056, 1.237]
}
```

### 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| id | 唯一标识符 | `MyMaterial_Smith2020` |
| name | 显示名称 | `My Material` |
| source | 数据来源 | `Smith et al. 2020` |
| rho0 | 初始密度 | `2.70` |
| file | 相对路径 | `materials/MyMaterial.txt` |
| tags | 标签数组 | `["experimental", "2020"]` |
| points | 数据点数 | `4` |
| up_range | Up 范围 | `[0.5, 2.0]` |
| p_range | P 范围 | `[0.07, 0.31]` |
| compression_range | 压缩比范围 | `[1.056, 1.237]` |

### 步骤 3：验证 JSON

确保 JSON 格式正确：

```bash
python -m json.tool standard_library/metadata.json
```

---

## 重启应用

完成以上步骤后：

1. 重启 IM_tool 应用
2. 在材料面板中找到新添加的材料
3. 勾选材料，添加到图表中
4. 验证数据正确显示

---

## 常见问题

### Q: 上标字符显示为乱码怎么办？

**A**: TXT 格式使用 `^3` 表示立方，避免编码问题：
- `g/cm^3` 而非 `g/cm³`
- `km/s` 而非 `km·s⁻¹`

### Q: 如何确保使用正确的行尾符？

**A**: 在文本编辑器中：
- VS Code：右下角选择 "LF"
- Notepad++：编辑 → 文档格式转换 → Unix (LF)
- 保存时选择 UTF-8 编码

### Q: 压缩比（compression）如何计算？

**A**: 压缩比 = rho / rho0

例如：
- rho0 = 2.70 g/cm³（初始密度）
- rho = 3.02 g/cm³（某点的密度）
- compression = 3.02 / 2.70 = 1.118

### Q: 数据点数量有限制吗？

**A**: 没有严格限制，建议：
- 最少：5-10 个点（能描绘基本曲线）
- 推荐：50-100 个点（平滑曲线）
- 上限：无（但注意文件大小）

### Q: 可选列（T, E, source）必须填写吗？

**A**: 不是。可选列可以：
- 完全省略（不在列名中出现）
- 留空（列名存在但数据为空）

### Q: 如何验证我的数据文件？

**A**: 使用验证工具：
```bash
python -m im_app.core.data_converter validate <文件路径>
```

或者手动检查：
- 文件编码是否为 UTF-8
- 行尾符是否为 LF
- 必需列是否都存在
- 数值是否在合理范围内

### Q: 我的数据来自论文，只有图像没有表格怎么办？

**A**: 可以使用数据提取工具：
- WebPlotDigitizer：https://automeris.io/WebPlotDigitizer/
- Engauge Digitizer：https://markummitchell.github.io/engauge-digitizer/

提取数据后按本指南添加到库中。

---

## 示例文件

完整的示例文件可在 `standard_library/materials/` 目录中找到：

- `Al_3717_sesame.csv` - SESAME 数据库格式
- `Quartz_Hamel2012.csv` 汇集 Hamel 等的 α-石英拟合采样。
- `BN_LEA.csv` - 简化格式

参考这些文件的格式创建您自己的数据文件。

---

## 技术支持

如有问题：
1. 查看 [`FORMAT_SPECIFICATION.md`](FORMAT_SPECIFICATION.md) 了解详细格式规范
2. 使用验证工具检查文件格式
3. 参考现有材料文件作为模板

---

最后更新：2026-05-30
