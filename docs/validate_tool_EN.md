# Hugoniot Data Format Validation Tool

Validate Hugoniot data files for compliance with the standard library format specification.

## Usage

```bash
python -m im_app.tools.validate_hugoniot <file_path>
```

## Examples

### Validate a standard library file

```bash
python -m im_app.tools.validate_hugoniot im_app/standard_library/materials/Al_3717_sesame.txt
```

Output:
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

### Validation failure example

If the file has format issues, errors and warnings are displayed:

```
[FAIL] Format validation failed

Errors:
  [ERROR] Missing required column: Us(km/s)
  [ERROR] Negative particle velocity detected (Up < 0)

Warnings:
  [WARN] Up column is not monotonically increasing
  [WARN] CRLF line endings detected (5 occurrences), LF recommended
```

## Check Items

### Basic Checks
- ✓ File existence
- ✓ File encoding (UTF-8)

### Header Checks
- ✓ File identifier (`# Hugoniot Data File`)
- ✓ Required metadata fields (Material, Reference, Initial Density)

### Data Checks
- ✓ Required column existence (Up, Us, P, rho, compression)
- ✓ Column name format (no leading/trailing whitespace)
- ✓ Non-empty data
- ✓ Numerical validity
  - Up ≥ 0 (non-negative particle velocity)
  - P ≥ 0 (non-negative pressure)
  - compression ≥ 1 (compressed state)
  - Up is monotonically increasing

### Format Checks
- ✓ Line endings (LF, not CRLF)
- ✓ Missing value detection
- ✓ Duplicate row detection

## Return Codes

- `0` — Validation passed
- `1` — Validation failed

## Integration into Workflow

### Validate before adding new materials

```bash
# Validate a newly created file
python -m im_app.tools.validate_hugoniot materials/MyNewMaterial.txt

# If validation passes, add to metadata.json
# If validation fails, fix the file based on error messages
```

### Batch validate all materials

```bash
# Linux/Mac
for file in im_app/standard_library/materials/*.txt; do
    python -m im_app.tools.validate_hugoniot "$file"
done

# Windows PowerShell
Get-ChildItem im_app\standard_library\materials\*.txt | ForEach-Object {
    python -m im_app.tools.validate_hugoniot $_.FullName
}
```

## Common Errors and Fixes

### Missing required column

**Error**: `[ERROR] Missing required column: Us(km/s)`

**Fix**: Check that column names are spelled correctly and separated by tabs

### Negative particle velocity

**Error**: `[ERROR] Negative particle velocity detected (Up < 0)`

**Fix**: Check the data for negative values; delete or correct anomalous points

### Line ending issues

**Warning**: `[WARN] CRLF line endings detected`

**Fix**: Set line endings to LF (Unix style) in your text editor

### Encoding issues

**Error**: `File encoding is not UTF-8`

**Fix**: Re-save the file in your text editor, selecting UTF-8 encoding

## Technical Support

For questions, please refer to:
- [FORMAT_SPECIFICATION_EN.md](../im_app/standard_library/FORMAT_SPECIFICATION_EN.md) — Full format specification
- [USER_GUIDE_EN.md](../im_app/standard_library/USER_GUIDE_EN.md) — Guide for manually adding data
