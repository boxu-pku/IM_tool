# Hugoniot 数据格式验证工具

验证 Hugoniot 数据文件是否符合标准库格式规范。

## 用法

### 方法一：作为模块运行

```bash
python -m im_app.tools.validate_hugoniot <文件路径>
```

### 方法二：使用独立脚本

```bash
python scripts/validate_hugoniot.py <文件路径>
```

## 示例

### 验证标准库文件

```bash
python scripts/validate_hugoniot.py im_app/standard_library/materials/Al_3717_sesame.txt
```

输出：
```
============================================================
File: im_app/standard_library/materials/Al_3717_sesame.txt
============================================================
[OK] Format validation passed

File Info:
  Material: Aluminum
  Reference: SESAME 3717
  Initial Density (g/cm^3): 2.7
  Number of points: 1000
  Number of columns: 8
  Up range (km/s): [0.01118, 52.893]
  P range (Mbar): [0.001, 100]
  Compression ratio range: [1.0021, 4.0877]

============================================================
```

### 验证失败示例

如果文件格式有问题，会显示错误和警告：

```
[FAIL] Format validation failed

Errors:
  [ERROR] 缺少必需列: Us(km/s)
  [ERROR] 存在负粒子速度 (Up < 0)

Warnings:
  [WARN] Up 列非单调递增
  [WARN] 检测到 CRLF 行尾符 (5 处)，建议使用 LF
```

## 检查项目

### 基础检查
- ✓ 文件存在性
- ✓ 文件编码（UTF-8）

### 头部检查
- ✓ 文件标识（`# Hugoniot Data File`）
- ✓ 必需元数据字段（Material, Reference, Initial Density）

### 数据检查
- ✓ 必需列存在性（Up, Us, P, rho, compression）
- ✓ 列名格式（无前后空格）
- ✓ 数据非空
- ✓ 数值合理性
  - Up ≥ 0（粒子速度非负）
  - P ≥ 0（压力非负）
  - compression ≥ 1（压缩状态）
  - Up 单调递增

### 格式检查
- ✓ 行尾符（LF，非 CRLF）
- ✓ 缺失值检查
- ✓ 重复行检查

## 返回码

- `0` - 验证通过
- `1` - 验证失败

## 集成到工作流

### 在添加新材料前验证

```bash
# 验证新创建的文件
python scripts/validate_hugoniot.py materials/MyNewMaterial.txt

# 如果验证通过，添加到 metadata.json
# 如果验证失败，根据错误信息修改文件
```

### 批量验证所有材料

```bash
# Linux/Mac
for file in im_app/standard_library/materials/*.txt; do
    python scripts/validate_hugoniot.py "$file"
done

# Windows PowerShell
Get-ChildItem im_app\standard_library\materials\*.txt | ForEach-Object {
    python scripts\validate_hugoniot.py $_.FullName
}
```

## 常见错误及修复

### 缺少必需列

**错误**: `[ERROR] 缺少必需列: Us(km/s)`

**修复**: 检查列名是否正确拼写，确保 Tab 分隔

### 存在负粒子速度

**错误**: `[ERROR] 存在负粒子速度 (Up < 0)`

**修复**: 检查数据是否有负值，删除或修正异常点

### 行尾符问题

**警告**: `[WARN] 检测到 CRLF 行尾符`

**修复**: 在文本编辑器中将行尾符设置为 LF（Unix 风格）

### 编码问题

**错误**: `文件编码不是 UTF-8`

**修复**: 使用文本编辑器重新保存，选择 UTF-8 编码

## 技术支持

如有问题，请查看：
- [FORMAT_SPECIFICATION.md](../standard_library/FORMAT_SPECIFICATION.md) - 完整格式规范
- [USER_GUIDE.md](../standard_library/USER_GUIDE.md) - 手动添加数据指南
