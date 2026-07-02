# Standard Hugoniot Library

Standard Hugoniot database for the Impedance Matching Tool (IM_tool).

## Introduction

This directory stores standardized Hugoniot curve data, containing shock compression data for various materials. All data follows a unified format specification to ensure correct parsing and display by the program.

## Current Material Library

| ID | Name | Source | Initial Density (g/cm³) |
|---|---|---|---|
| Al_3717_sesame | Aluminum | SESAME 3717 | 2.70 |
| Al_3720_sesame | Aluminum | SESAME 3720 | 2.70 |
| Al_Celliers2005 | Aluminum | Celliers et al. 2005 | 2.70 |
| Al_FEOS | Aluminum | FEOS | 2.70 |
| BN_LEA | Hexagonal boron nitride | LEA | 2.04 |
| CH_foam_ideal_plasma | CH foam | Ideal Plasma (gamma=1.667) | 0.089 |
| Quartz_7360_sesame | Alpha Quartz | SESAME 7360 | 2.65 |
| Quartz_7385_sesame | Alpha Quartz | SESAME 7385 | 2.65 |
| Quartz_Hamel2012 | Alpha Quartz | Hamel et al. 2012 | 2.65 |

Detailed material information can be found in [`metadata.json`](metadata.json).

## Data Format

**This library currently uses TXT format** as the default data format.

TXT format advantages:
- Human-readable, easy to edit manually
- Includes complete comments and unit descriptions
- Uses ASCII characters to avoid encoding issues (e.g., `g/cm^3` instead of `g/cm³`)
- Contains statistical information at the end of the file

For detailed format specifications, see [`FORMAT_SPECIFICATION.md`](FORMAT_SPECIFICATION.md).

## Adding New Materials

To add new Hugoniot data, please refer to:

**[`USER_GUIDE.md`](USER_GUIDE.md)** — Complete guide for manually adding Hugoniot data

### Quick Start

1. Prepare data (Up, Us, P, rho, etc.)
2. Create a `.txt` or `.csv` file according to the format specification
3. Place the file in the `materials/` directory
4. Add a material entry to `metadata.json`
5. Restart the IM_tool application

## Directory Structure

```
standard_library/
├── README.md                    # This file
├── FORMAT_SPECIFICATION.md      # Format specification document
├── USER_GUIDE.md                # User guide
├── metadata.json                # Material metadata index
└── materials/                   # Data file directory
    ├── *.csv                    # CSV format data
    └── *.txt                    # TXT format data
```

## Format Validation

Use the validation tool to check data file formats:

```bash
python -m im_app.core.data_converter validate <file_path>
```

## FAQ

**Q: Why does my data file show garbled characters?**

A: Ensure the file is saved with UTF-8 encoding and that the line endings use LF (`\n`) rather than CRLF (`\r\n`). Check the file encoding settings in your text editor.

**Q: What is the difference between TXT and CSV formats?**

A: The content is identical; the differences are:
- TXT format includes more comments and formatting notes, making it more suitable for human reading and editing
- CSV format is more concise and suitable for programmatic processing

**Q: How do I convert data from Excel?**

A: See the Excel conversion method in [`USER_GUIDE.md`](USER_GUIDE.md).

---

Last updated: 2026-05-30
