# Hugoniot Data Format Specification

**Version**: 1.0  
**Date**: 2026-05-30

## Overview

This specification defines the format standard for Hugoniot data files. **The standard library currently uses TXT format as the default**.

Two formats are supported:

1. **TXT format** (.txt) - Human-readable, easy to manually edit, **current default format**
2. **CSV format** (.csv) - Compact machine-readable format, deprecated

The data content of both formats is equivalent, and the program can correctly parse either format.

---

## CSV Format Specification

### File Structure

A CSV file consists of two parts:

1. **Metadata header** (7 lines, prefixed with `#`)
2. **Data area** (Tab-separated tabular data)

### Complete Example

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

### Metadata Header (Required)

| Line | Format | Description | Example |
|------|--------|-------------|---------|
| 1 | `# Material: <name>` | Material name | `# Material: Aluminum` |
| 2 | `# Reference: <source>` | Reference or data source | `# Reference: SESAME 3717` |
| 3 | `# Initial Density (g/cm³): <value>` | Initial density | `# Initial Density (g/cm³): 2.70` |
| 4 | `# Data Source: <source>` | Data provider | `# Data Source: LANL` |
| 5 | `# Date Created: <YYYY-MM-DD>` | Creation date | `# Date Created: 2026-05-30` |
| 6 | `# Notes: <notes>` | Additional notes | `# Notes: Principal Hugoniot` |
| 7 | `# Columns: <column list>` | Column name declaration | `# Columns: Up(km/s), Us...` |

### Data Column Definitions

| Column Name | Unit | Required | Description |
|-------------|------|:--------:|-------------|
| `Up(km/s)` | km/s | ✓ | Particle velocity |
| `Us(km/s)` | km/s | ✓ | Shock velocity |
| `P(Mbar)` | Mbar | ✓ | Pressure (1 Mbar = 100 GPa) |
| `rho(g/cm³)` | g/cm³ | ✓ | Density |
| `compression` | - | ✓ | Compression ratio (rho/rho0) |
| `T(eV)` | eV | ✗ | Temperature (optional) |
| `E(MJ/g)` | MJ/g | ✗ | Specific internal energy (optional) |
| `source` | - | ✗ | Data source identifier (optional) |

### CSV Format Technical Requirements

| Item | Requirement | Description |
|------|-------------|-------------|
| **Encoding** | UTF-8 | Must use UTF-8 encoding to avoid garbled text |
| **Line ending** | LF (`\n`) | Do not use CRLF (`\r\n`) |
| **Delimiter** | Tab (`\t`) | Columns separated by tab characters |
| **Decimal point** | Dot (`.`) | Use decimal point, not comma |
| **Scientific notation** | `E` notation | e.g., `1.11795E-02` |
| **Empty values** | Empty string | Leave missing values blank, do not use `NaN` or `NULL` |

### Common Errors

❌ **Incorrect example**:
```csv
# Initial Density (g/cm³): 2,70        # Using comma as decimal point
Up(km/s);Us(km/s);P(Mbar)             # Using semicolon as delimiter
0.0111795;5.22691;0.001               # Using semicolon as delimiter
```

✅ **Correct example**:
```csv
# Initial Density (g/cm³): 2.70       # Using decimal point
Up(km/s)	Us(km/s)	P(Mbar)         # Using Tab as delimiter
0.0111795	5.22691	0.001            # Using Tab as delimiter
```

---

## TXT Format Specification

### Design Principles

- **Human-readable**: Clear comments and format descriptions
- **Avoid encoding issues**: Use ASCII characters (e.g., `^3` instead of `³`)
- **Easy to edit**: Supports manual addition of data points
- **Self-describing**: Includes complete format description within the file

### Complete Example

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

### TXT Format Features

1. **ASCII-friendly**: Uses `^3` instead of superscript `³`, `cm^3` instead of `cm³`
2. **Block comments**: Uses `# ===` delimited comment blocks
3. **Unit descriptions**: Clear column unit explanations
4. **Statistics**: Data range statistics at end of file

### TXT Format Technical Requirements

Same as CSV format:

- Encoding: UTF-8
- Line ending: LF (`\n`)
- Delimiter: Tab (`\t`)

---

## Data Requirements

### Numerical Ranges

| Parameter | Reasonable Range | Description |
|-----------|------------------|-------------|
| Up | > 0 km/s | Particle velocity must be positive |
| Us | > Up km/s | Shock velocity must be greater than particle velocity |
| P | ≥ 0 Mbar | Pressure must be non-negative |
| rho | ≥ 0 g/cm³ | Density must be non-negative |
| compression | ≥ 1 | Compression ratio ≥ 1 (compressed state) |

### Data Quality

- **Monotonicity**: Up column should be monotonically increasing
- **Precision**: At least 6 significant digits recommended
- **Completeness**: Required columns must not contain empty values

---

## Format Conversion

### CSV → TXT

Use the conversion script:

```bash
python scripts/convert_to_standard.py
```

### Manual Conversion

1. Open the CSV file in a text editor
2. Add TXT-format header comment blocks
3. Add footer statistics
4. Save as `.txt` file

---

## Validation

### Using the Validation Tool

```bash
python -m im_app.core.data_converter validate <file_path>
```

### Validation Items

- File existence
- Header line count (≥ 7 lines)
- Required metadata fields
- Required column existence
- Numerical validity
- Up column monotonicity

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-30 | Initial version |

---

## References

- SESAME database: Los Alamos National Laboratory
- Celliers et al. 2005: J. Appl. Phys. 97, 103529
- Hamel et al. 2012: Acta Physica Sinica

---

For questions or suggestions, please contact the project maintainer.
