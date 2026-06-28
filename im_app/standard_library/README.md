# Standard Hugoniot Library

标准 Hugoniot 数据库，用于阻抗匹配工具（IM_tool）。

## 简介

本目录存储标准化的 Hugoniot 曲线数据，包含多种材料的冲击压缩数据。所有数据遵循统一的格式规范，确保程序可正确解析和显示。

## 当前材料库

| ID | 名称 | 来源 | 初始密度 (g/cm³) |
|---|---|---|---|
| Al_3717_sesame | Aluminum | SESAME 3717 | 2.70 |
| Al_3720_sesame | Aluminum | SESAME 3720 | 2.70 |
| Al_Celliers2005 | Aluminum | Celliers et al. 2005 | 2.70 |
| BN_LEA | 六方氮化硼 | LEA | 2.04 |
| Quartz_7360_sesame | Alpha Quartz | SESAME 7360 | 2.65 |
| Quartz_7385_sesame | Alpha Quartz | SESAME 7385 | 2.65 |
| Quartz_Hamel2012 | Alpha Quartz | Hamel et al. 2012 | 2.65 |

详细材料信息请查看 [`metadata.json`](metadata.json)。

## 数据格式

**本库当前使用 TXT 格式**作为默认数据格式。

TXT 格式优势：
- 人类可读，便于手动编辑
- 包含完整注释和单位说明
- 使用 ASCII 字符避免编码问题（如 `g/cm^3` 代替 `g/cm³`）
- 文件末尾包含统计信息

详细格式规范请查看 [`FORMAT_SPECIFICATION.md`](FORMAT_SPECIFICATION.md)。

## 添加新材料

如需添加新的 Hugoniot 数据，请参考：

**[`USER_GUIDE.md`](USER_GUIDE.md)** - 手动添加 Hugoniot 数据完整指南

### 快速开始

1. 准备数据（Up, Us, P, rho 等）
2. 按照格式规范创建 `.txt` 或 `.csv` 文件
3. 将文件放入 `materials/` 目录
4. 在 `metadata.json` 中添加材料条目
5. 重启 IM_tool 应用

## 目录结构

```
standard_library/
├── README.md                    # 本文件
├── FORMAT_SPECIFICATION.md      # 格式规范文档
├── USER_GUIDE.md                # 用户指南
├── metadata.json                # 材料元数据索引
└── materials/                   # 数据文件目录
    ├── *.csv                    # CSV 格式数据
    └── *.txt                    # TXT 格式数据
```

## 格式验证

使用验证工具检查数据文件格式：

```bash
python -m im_app.core.data_converter validate <文件路径>
```

## 常见问题

**Q: 为什么我的数据文件显示乱码？**

A: 请确保文件使用 UTF-8 编码保存，且行尾符为 LF（\n）而非 CRLF（\r\n）。在文本编辑器中检查文件编码设置。

**Q: TXT 格式和 CSV 格式有什么区别？**

A: 内容完全相同，区别在于：
- TXT 格式包含更多注释和格式说明，更适合人工阅读和编辑
- CSV 格式更简洁，适合程序处理

**Q: 如何从 Excel 数据转换？**

A: 请查看 [`USER_GUIDE.md`](USER_GUIDE.md) 中的 Excel 转换方法。

---

最后更新：2026-05-30
