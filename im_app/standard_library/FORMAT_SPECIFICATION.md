# Hugoniot 数据格式规范

**版本**：1.0  
**日期**：2026-05-30

## 概述

本规范定义 Hugoniot 数据文件的格式标准。**标准库当前使用 TXT 格式作为默认格式**。

支持两种格式：
1. **TXT 格式** (.txt) - 人类可读，便于手动编辑，**当前默认格式**
2. **CSV 格式** (.csv) - 简洁的机器可读格式，已弃用

两种格式数据内容等价，程序可正确解析任一格式。

---

## CSV 格式规范

### 文件结构

CSV 文件由两部分组成：

1. **元数据头部**（7 行，以 `#` 开头）
2. **数据区域**（Tab 分隔的表格数据）

### 完整示例

```csv
# Material: Aluminum
# Reference: SESAME 3717
# Initial Density (g/cm³): 2.70
# Data Source: Los Alamos National Laboratory
# Date Created: 2026-05-30
# Notes: Principal Hugoniot from SESAME EOS table
# Columns: Up(km/s), Us(km/s), P(Mbar), rho(g/cm³), compression, T(eV), E(MJ/g), source
Up(km/s)	Us(km/s)	P(Mbar)	rho(g/cm³)	compression	T(eV)	E(MJ/g)	source
0.0111795	5.22691	0.001	2.70579	1.00214	0.0259596	0.00188365	SESAME3717
0.61119	6.16144	0.101099	2.99732	1.11012	0.0333359	0.186521	SESAME3717
...
```

### 元数据头部（必需）

| 行号 | 格式 | 说明 | 示例 |
|------|------|------|------|
| 1 | `# Material: <名称>` | 材料名称 | `# Material: Aluminum` |
| 2 | `# Reference: <来源>` | 参考文献或数据源 | `# Reference: SESAME 3717` |
| 3 | `# Initial Density (g/cm³): <值>` | 初始密度 | `# Initial Density (g/cm³): 2.70` |
| 4 | `# Data Source: <来源>` | 数据提供者 | `# Data Source: LANL` |
| 5 | `# Date Created: <YYYY-MM-DD>` | 创建日期 | `# Date Created: 2026-05-30` |
| 6 | `# Notes: <备注>` | 备注信息 | `# Notes: Principal Hugoniot` |
| 7 | `# Columns: <列名列表>` | 列名声明 | `# Columns: Up(km/s), Us...` |

### 数据列定义

| 列名 | 单位 | 必需 | 说明 |
|------|------|:----:|------|
| `Up(km/s)` | km/s | ✓ | 粒子速度 |
| `Us(km/s)` | km/s | ✓ | 冲击波速度 |
| `P(Mbar)` | Mbar | ✓ | 压力（1 Mbar = 100 GPa） |
| `rho(g/cm³)` | g/cm³ | ✓ | 密度 |
| `compression` | - | ✓ | 压缩比 (rho/rho0) |
| `T(eV)` | eV | ✗ | 温度（可选） |
| `E(MJ/g)` | MJ/g | ✗ | 比内能（可选） |
| `source` | - | ✗ | 数据来源标识（可选） |

### CSV 格式技术要求

| 项目 | 要求 | 说明 |
|------|------|------|
| **编码** | UTF-8 | 必须使用 UTF-8 编码，避免乱码 |
| **行尾符** | LF (`\n`) | 不要使用 CRLF (`\r\n`) |
| **分隔符** | Tab (`\t`) | 列之间使用制表符分隔 |
| **小数点** | 点 (`.`) | 使用小数点，不要使用逗号 |
| **科学计数法** | `E` 表示 | 如 `1.11795E-02` |
| **空值** | 空字符串 | 缺失值留空，不要使用 `NaN` 或 `NULL` |

### 常见错误

❌ **错误示例**：
```csv
# Initial Density (g/cm³): 2,70        # 使用逗号作小数点
Up(km/s);Us(km/s);P(Mbar)             # 使用分号分隔
0.0111795;5.22691;0.001               # 使用分号分隔
```

✅ **正确示例**：
```csv
# Initial Density (g/cm³): 2.70       # 使用小数点
Up(km/s)	Us(km/s)	P(Mbar)         # 使用 Tab 分隔
0.0111795	5.22691	0.001            # 使用 Tab 分隔
```

---

## TXT 格式规范

### 设计原则

- **人类可读**：清晰的注释和格式说明
- **避免编码问题**：使用 ASCII 字符（如 `^3` 代替 `³`）
- **易于编辑**：支持手动添加数据点
- **自描述**：文件内包含完整的格式说明

### 完整示例

```
# =============================================================================
# Hugoniot Data File
# Format Version: 1.0
# =============================================================================
# Material:          Aluminum
# Reference:         SESAME 3717
# Initial Density:   2.70 g/cm^3
# Data Source:       Los Alamos National Laboratory
# Date Created:      2026-05-30
# Notes:             Principal Hugoniot from SESAME EOS table 3717
# =============================================================================
# Column Units:
#   Up      km/s       - Particle velocity
#   Us      km/s       - Shock velocity
#   P       Mbar       - Pressure (1 Mbar = 100 GPa)
#   rho     g/cm^3     - Density
#   eta     -          - Compression ratio (rho/rho0)
#   T       eV         - Temperature (optional)
#   E       MJ/g       - Internal energy (optional)
# =============================================================================
# Data Columns (tab-separated):
# Up(km/s)    Us(km/s)    P(Mbar)     rho(g/cm^3)  compression T(eV)       E(MJ/g)     source
# =============================================================================
0.01117950    5.226910    0.001000    2.705790    1.002140    0.0259596   0.0018837  SESAME3717
0.61119000    6.161440    0.101099    2.997320    1.110120    0.0333359   0.1865210  SESAME3717
1.21121000    7.098030    0.201399    3.290460    1.218690    0.0408213   0.3963890  SESAME3717
# =============================================================================
# End of Data
# Total Points: 1000
# Up Range: [0.0111795, 52.893] km/s
# P Range: [0.001, 100.0] Mbar
# Compression Range: [1.00214, 4.08774]
# =============================================================================
```

### TXT 格式特点

1. **ASCII 友好**：使用 `^3` 代替上标 `³`，`cm^3` 代替 `cm³`
2. **块注释**：使用 `# ===` 分隔的注释块
3. **单位说明**：清晰的列单位说明
4. **统计信息**：文件末尾包含数据范围统计

### TXT 格式技术要求

与 CSV 格式相同：
- 编码：UTF-8
- 行尾符：LF (`\n`)
- 分隔符：Tab (`\t`)

---

## 数据要求

### 数值范围

| 参数 | 合理范围 | 说明 |
|------|----------|------|
| Up | > 0 km/s | 粒子速度必须为正 |
| Us | > Up km/s | 冲击波速度大于粒子速度 |
| P | ≥ 0 Mbar | 压力非负 |
| rho | ≥ 0 g/cm³ | 密度非负 |
| compression | ≥ 1 | 压缩比 ≥ 1（压缩状态） |

### 数据质量

- **单调性**：Up 列应单调递增
- **精度**：建议使用至少 6 位有效数字
- **完整性**：必需列不能有空值

---

## 格式转换

### CSV → TXT

使用转换脚本：

```bash
python scripts/convert_to_standard.py
```

### 手动转换

1. 在文本编辑器中打开 CSV 文件
2. 添加 TXT 格式的头部注释块
3. 添加尾部统计信息
4. 另存为 `.txt` 文件

---

## 验证

### 使用验证工具

```bash
python -m im_app.core.data_converter validate <文件路径>
```

### 验证项目

- 文件存在性
- 头部行数（≥ 7 行）
- 必需元数据字段
- 必需列存在性
- 数值合理性
- Up 列单调性

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-05-30 | 初始版本 |

---

## 参考资料

- SESAME 数据库：Los Alamos National Laboratory
- Celliers et al. 2005：J. Appl. Phys. 97, 103529
- Hamel et al. 2012：物理学报

---

如有疑问或建议，请联系项目维护者。
