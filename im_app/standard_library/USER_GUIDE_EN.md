# Guide to Manually Adding Hugoniot Data

This guide details how to manually add new Hugoniot data to the standard library.

## Table of Contents

- [Method 1: Using TXT Format (Recommended)](#method-1-using-txt-format-recommended)
- [Method 2: Using CSV Format](#method-2-using-csv-format)
- [Converting from Excel](#converting-from-excel)
- [Updating the Metadata Index](#updating-the-metadata-index)
- [Frequently Asked Questions](#frequently-asked-questions)

---

## Method 1: Using TXT Format (Recommended)

The TXT format is human-readable, making it convenient for manual editing and validation.

### Step 1: Prepare Data

Prepare your Hugoniot data, including at least the following columns:

| Column       | Description                        | Example              |
|--------------|------------------------------------|----------------------|
| Up           | Particle velocity (km/s)           | 0.5, 1.0, 1.5...    |
| Us           | Shock velocity (km/s)              | 5.2, 5.8, 6.4...    |
| P            | Pressure (Mbar)                    | 0.07, 0.15, 0.23... |
| rho          | Density (g/cm³)                    | 2.85, 3.02, 3.18... |
| compression  | Compression ratio (rho/rho0)       | 1.05, 1.12, 1.18... |

### Step 2: Create a TXT File

Create a new file in the `standard_library/materials/` directory, e.g., `MyMaterial.txt`:

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

### Step 3: Compute Statistics

Add statistics at the end of the file:

```
# Total Points: <number of data rows>
# Up Range: [<min>, <max>] km/s
# P Range: [<min>, <max>] Mbar
# Compression Range: [<min>, <max>]
```

### Step 4: Save the File

Ensure the following file saving settings:
- **Encoding**: UTF-8
- **Line endings**: LF (Unix style)

### Step 5: Validate the Format

Use the validation tool to check the file:

```bash
python -m im_app.core.data_converter validate materials/MyMaterial.txt
```

---

## Method 2: Using CSV Format

The CSV format is more compact and suitable for programmatic processing.

### Step 1: Create a CSV File

Create `MyMaterial.csv`:

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

### Step 2: Save the File

Ensure:
- **Encoding**: UTF-8
- **Line endings**: LF (\n)
- **Separator**: Tab (\t)

---

## Converting from Excel

If your data is in Excel:

### Method A: Copy-Paste (Recommended)

1. Organize the data in Excel with column names following the standard format
2. Select the data range (including column names)
3. Copy (Ctrl+C)
4. Open a text editor (e.g., VS Code, Notepad++)
5. Paste the data
6. Add metadata header (see TXT or CSV format)
7. Save as `.txt` or `.csv`

**Note**: Data pasted from Excel is usually Tab-separated and can be used directly.

### Method B: Export CSV

1. In Excel: File → Save As → CSV UTF-8 (comma delimited) *.csv
2. Open the exported CSV in a text editor
3. Replace commas with Tabs
4. Add metadata header
5. Save

---

## Updating the Metadata Index

After adding a file, you need to update `metadata.json`:

### Step 1: Open metadata.json

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

### Step 2: Add a New Material Entry

Add the following to the `materials` array:

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

### Field Descriptions

| Field              | Description          | Example                          |
|--------------------|----------------------|----------------------------------|
| id                 | Unique identifier    | `MyMaterial_Smith2020`           |
| name               | Display name         | `My Material`                    |
| source             | Data source          | `Smith et al. 2020`              |
| rho0               | Initial density      | `2.70`                           |
| file               | Relative path        | `materials/MyMaterial.txt`       |
| tags               | Tag array            | `["experimental", "2020"]`       |
| points             | Number of data points| `4`                              |
| up_range           | Up range             | `[0.5, 2.0]`                     |
| p_range            | P range              | `[0.07, 0.31]`                   |
| compression_range  | Compression ratio range| `[1.056, 1.237]`                |

### Step 3: Validate JSON

Ensure the JSON is well-formed:

```bash
python -m json.tool standard_library/metadata.json
```

---

## Restart the Application

After completing the above steps:

1. Restart the IM_tool application
2. Find the newly added material in the material panel
3. Check the material checkbox to add it to the plots
4. Verify that the data is displayed correctly

---

## Frequently Asked Questions

### Q: Superscript characters appear as garbled text. What should I do?

**A**: Use `^3` to denote powers in the TXT format to avoid encoding issues:
- `g/cm^3` instead of `g/cm³`
- `km/s` instead of `km·s⁻¹`

### Q: How do I ensure the correct line ending style?

**A**: In your text editor:
- VS Code: Select "LF" in the bottom-right corner
- Notepad++: Edit → EOL Conversion → Unix (LF)
- Save with UTF-8 encoding

### Q: How is the compression ratio calculated?

**A**: Compression ratio = rho / rho0

For example:
- rho0 = 2.70 g/cm³ (initial density)
- rho = 3.02 g/cm³ (density at a given point)
- compression = 3.02 / 2.70 = 1.118

### Q: Is there a limit on the number of data points?

**A**: There is no hard limit, but recommendations are:
- Minimum: 5–10 points (enough to describe the basic curve)
- Recommended: 50–100 points (smooth curve)
- Maximum: None (but be mindful of file size)

### Q: Are the optional columns (T, E, source) required?

**A**: No. Optional columns can be:
- Omitted entirely (not listed in the column names)
- Left empty (column names present but data fields blank)

### Q: How can I validate my data file?

**A**: Use the validation tool:
```bash
python -m im_app.core.data_converter validate <file_path>
```

Or check manually:
- Whether the file encoding is UTF-8
- Whether the line endings are LF
- Whether all required columns are present
- Whether numerical values are within reasonable ranges

### Q: My data comes from a paper that only has figures, not tables. What can I do?

**A**: You can use data extraction tools:
- WebPlotDigitizer: https://automeris.io/WebPlotDigitizer/
- Engauge Digitizer: https://markummitchell.github.io/engauge-digitizer/

After extracting the data, follow this guide to add it to the library.

---

## Example Files

Complete example files can be found in the `standard_library/materials/` directory:

- `Al_3717_sesame.csv` — SESAME database format
- `Quartz_Hamel2012.csv` — Experimental data format
- `BN_LEA.csv` — Simplified format

Refer to these files as templates when creating your own data files.

---

## Technical Support

If you have questions:
1. See [`FORMAT_SPECIFICATION.md`](FORMAT_SPECIFICATION.md) for detailed format specifications
2. Use the validation tool to check file format
3. Refer to existing material files as templates

---

Last updated: 2026-05-30
