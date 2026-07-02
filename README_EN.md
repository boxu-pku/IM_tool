# IM Tool - Impedance Matching Analysis Tool

A professional GUI application for **Impedance Matching** analysis in shock physics (HEDP). Computes pressure and compression ratios in multi-layer targets from measured shock velocities using Hugoniot equations of state, providing accurate data analysis tools for shock wave experiments.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)
![License](https://img.shields.io/badge/License-Academic%20Use-yellow.svg)

---

## Table of Contents

- [Features](#features)
- [Screenshot](#screenshot)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [User Guide](#user-guide)
  - [Main Interface Layout](#main-interface-layout)
  - [Material Panel](#material-panel)
  - [Rayleigh Line Panel](#rayleigh-line-panel)
  - [Intersection Panel](#intersection-panel)
  - [Reflected Hugoniot Panel](#reflected-hugoniot-panel)
  - [Reference Curve Panel](#reference-curve-panel)
  - [Plot Area](#plot-area)
- [Data Format Specification](#data-format-specification)
- [Physical Model](#physical-model)
- [Project Architecture](#project-architecture)
- [FAQ](#faq)
- [Version History](#version-history)
- [Author](#author)

---

## Features

### Core Analysis

- **Hugoniot Curve Plotting**
  - Multiple Hugoniot EOS curves from the standard material library
  - Automatic loading of pressure, density, compression, temperature, energy data
  - User-defined reference curves

- **Rayleigh Line Management**
  - Create any number of Rayleigh lines for shock front modeling
  - Custom material parameters (shock velocity D, initial density rho0)
  - Rayleigh line equation: P = rho0 * up * D * 0.01

- **Automatic Intersection Finding**
  - Compute intersections between all material curves and Rayleigh lines
  - Visual selection (click on plot or table)
  - Highlighted selected intersection

- **Reflected Hugoniot Computation**
  - Compute reflected Hugoniot from a selected intersection center
  - Reflection formula: up' = 2 * up_center - up
  - Automatic color matching with distinct linestyle

- **Real-time Compression Ratio**
  - Formula: CR = D / (D - up)
  - Automatically displayed when an intersection is selected
  - Multi-layer target impedance matching analysis

### Multi-Variable Visualization

**8 different** data plane plots for comprehensive shock physics analysis:

| Plot Type | X Axis | Y Axis | Description |
|-----------|--------|--------|-------------|
| **P-Up** | Particle velocity (km/s) | Pressure (Mbar) | Main plot with full analysis |
| **P-CR** | Compression ratio | Pressure (Mbar) | EOS state relation |
| **Us-Up** | Particle velocity (km/s) | Shock velocity (km/s) | Shock velocity relation |
| **P-T** | Temperature (eV) | Pressure (Mbar) | Pressure-temperature state |
| **rho-Up** | Particle velocity (km/s) | Density (g/cm3) | Compression process |
| **T-Up** | Particle velocity (km/s) | Temperature (eV) | Temperature evolution |
| **E-Up** | Particle velocity (km/s) | Internal energy (MJ/g) | Energy deposition |
| **P-Us** | Shock velocity (km/s) | Pressure (Mbar) | Shock velocity-pressure |

### Plot Interaction

- **Auto Range**
  - One-click zoom to data range
  - Automatic 10% margin
  - Quick overview of all data

- **Inverse Axes**
  - Swap X/Y axis display
  - Available for generic plots (Us-Up, P-T, etc.)
  - Multiple analytical perspectives

- **Interactive Selection**
  - Click on plot to select intersections
  - Click table row to select intersections
  - Plot and table stay synchronized

- **Publication-Quality Figures**
  - PRL (Physical Review Letters) style
  - Serif fonts, inward ticks
  - Colorblind-friendly palette
  - 300 DPI high-resolution export

### Data Format Support

- **Standard TXT/CSV Format**
  - 7-line comment header + tab-separated data
  - Required and optional columns
  - Automatic format validation

- **FEOS .hug Format**
  - Direct FEOS program output reading
  - Automatic unit conversion
  - 6-column standard output support

- **Reference Curve CSV Format**
  - Simplified CSV format
  - Custom column names and units
  - Partial variable support (only Up and P required)

---

## Screenshot

The application interface consists of the following main areas:

```
+----------------------------------------------------------------+
|  Menu Bar: File | View | Help                                   |
+-----------+------------------------------------------------------+
|           |  Plot Tabs: P-Up | P-CR | Us-Up | P-T | ...        |
|           +------------------------------------------------------+
|  Material |                                                      |
|  Panel    |                                                      |
|           |                 Plot Area                            |
|           |                                                      |
|           |                                                      |
+-----------+                                                      |
| Rayleigh  |                                                      |
| Panel     |                                                      |
|           |                                                      |
+-----------+                                                      |
| Intersec  |                                                      |
| Panel     |                                                      |
|           |                                                      |
+-----------+                                                      |
| Reflected |                                                      |
| Panel     |                                                      |
|           |                                                      |
+-----------+                                                      |
| Reference |                                                      |
| Curves    |                                                      |
|           +------------------------------------------------------+
+------------------------------------------------------------------+
```

---

## Installation

### System Requirements

- **OS**: Windows 10/11 (recommended), Linux, macOS
- **Python**: 3.8 or higher
- **Memory**: At least 4 GB RAM
- **Display**: 1920x1080 or higher recommended

### Install from Source

1. **Clone or download the project**
```bash
git clone <repository-url>
cd IM_tool
```

2. **Create a virtual environment (recommended)**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

### Run Directly

If Python and PyQt5 are already installed:

```bash
python -m im_app.main
```

Or use the launcher script:

**Windows**:
```cmd
run_app.bat
```

**Linux/macOS**:
```bash
chmod +x run_app.py
./run_app.py
```

### Dependency List

```
PyQt5 >= 5.15.0    # GUI framework
numpy >= 1.21.0    # Numerical computation
pandas >= 1.3.0    # Data processing
matplotlib >= 3.5.0  # Plotting
scipy >= 1.7.0     # Scientific computing
xlrd >= 2.0.0      # Old Excel (.xls) reading
openpyxl >= 3.0.0  # New Excel (.xlsx) reading
```

### Common Installation Issues

**Issue 1: Slow pip installation**
```bash
# Use a mirror
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**Issue 2: PyQt5 installation fails**
```bash
# For Windows, try installing SIP first
pip install SIP
pip install PyQt5
```

**Issue 3: Missing Qt libraries on Linux**
```bash
# Ubuntu/Debian
sudo apt-get install python3-pyqt5

# CentOS/RHEL
sudo yum install python3-qt5
```

---

## Quick Start

### First Run

1. **Launch the application**
```bash
python -m im_app.main
```

2. **Load materials**
   - In the left "Material Library" panel
   - Check the materials you want to analyze (e.g., "Aluminum (SESAME 3717)")
   - The plot automatically shows the material's Hugoniot curve

3. **Create a Rayleigh line**
   - Switch to the "Rayleigh Lines" panel
   - Enter parameters (or keep defaults)
   - Click the "Add" button

4. **Find intersections**
   - Switch to the "Intersections" panel
   - Click the "Find Intersections" button
   - All intersections appear in the table

5. **Select an intersection**
   - Click an intersection marker on the plot
   - Or click a row in the table
   - The selected intersection is highlighted

6. **Compute compression ratio**
   - After selecting an intersection, the compression ratio is automatically computed
   - Displayed in the intersection panel

### Typical Workflow

**Impedance Matching Analysis Flow:**

```
1. Load Hugoniot curves for standard materials
   |
2. Create Rayleigh lines (input shock velocity D)
   |
3. Find intersections between curves and Rayleigh lines
   |
4. Select an intersection to view pressure and particle velocity
   |
5. Create reflected Hugoniot (if needed)
   |
6. Compute compression ratio CR = D / (D - up)
   |
7. Switch between plot tabs for multi-variable relationships
   |
8. Export plots and data
```

---

## User Guide

### Main Interface Layout

The application window is divided into the following areas:

| Area | Position | Function |
|------|----------|----------|
| **Material Panel** | Top left | Select and manage material Hugoniot curves |
| **Rayleigh Line Panel** | Upper middle left | Create and manage Rayleigh lines |
| **Intersection Panel** | Lower middle left | Find and select intersections |
| **Reflected Hugoniot Panel** | Bottom left | Compute reflected curves |
| **Reference Curve Panel** | Bottom left | Manage custom reference curves |
| **Plot Tabs** | Top | Switch between different variable combinations |
| **Plot Area** | Right | Display curves, intersections, data |

---

### Material Panel

**Location**: Top of the left panel

#### Overview

The material panel loads and manages Hugoniot EOS curves from the material library. All material data is stored in the `standard_library/materials/` directory.

#### Panel Components

```
+------------------------------------------+
|  Material Library                        |
+------------------------------------------+
| [Add New Material] [Validate File]       |
|            [Refresh]                     |
+------------------------------------------+
| [ ] Aluminum (SESAME 3717)              |
| [ ] Aluminum (SESAME 3720)              |
| [x] Alpha Quartz (SESAME 7360)          |
| [ ] Al (FEOS)                           |
| ...                                      |
+------------------------------------------+
| [Select All] [Deselect All]             |
|                                          |
| 8 materials available                    |
+------------------------------------------+
```

#### Operations

| Button | Function | Description |
|--------|----------|-------------|
| **Add New Material** | Open material creation wizard | Create new material data file |
| **Validate File** | Open file validation dialog | Validate data file format |
| **Refresh** | Refresh material list | Re-scan material library directory |
| **Select All** | Select all | Check all materials |
| **Deselect All** | Deselect all | Uncheck all materials |

#### Material List

- Display format: `Material Name (Data Source)`
- Checked materials automatically load curves into all plots
- Different materials use different colors
- Colors follow a predefined colorblind-friendly palette

#### Adding a New Material

1. Click the **Add New Material** button
2. Fill in information in the wizard:
   - **Material Name**: e.g., "Copper"
   - **Reference**: e.g., "SESAME 3330"
   - **Initial Density**: rho0 (g/cm3)
3. Choose data input method:
   - **From Clipboard**: Paste from clipboard (recommended)
   - **From File**: Load from file
4. Paste or enter data (two or more columns, tab-separated)
5. Click **Next** to preview data
6. Click **Finish** to save

#### Data Format Example

**Clipboard format** (two columns: Up, P):
```
0.0    0.0
0.5    0.05
1.0    0.12
1.5    0.22
...
```

**Multi-column format** (Up, Us, P, rho, compression):
```
0.011   5.227   0.001   2.706   1.002
0.611   6.161   0.101   2.997   1.110
...
```

#### Refresh

Clicking **Refresh** will:
1. Clear current material data in memory
2. Re-read `metadata.json`
3. Scan the `materials/` folder
4. Automatically add new files to metadata
5. Remove entries for deleted files
6. Reload the material list

---

### Rayleigh Line Panel

**Location**: Upper middle of the left panel

#### Overview

Rayleigh lines describe the shock front state and are an essential tool in impedance matching analysis. The Rayleigh line equation is:

**P = rho0 * up * D * 0.01**

where:
- P: Pressure (Mbar)
- rho0: Initial density (g/cm3)
- up: Particle velocity (km/s)
- D: Shock velocity (km/s)

#### Panel Components

```
+------------------------------------------+
|  Rayleigh Lines                          |
+------------------------------------------+
| Material: [Aluminum          v]           |
| D (km/s): [    8.0    ]                  |
| rho0 (g/cm3): [  2.7   ] (optional)      |
|                                          |
| [Add] [Clear] [Clear All]               |
+------------------------------------------+
| [x] Aluminum RL, D=8.00 km/s            |
| [x] Quartz RL, D=10.00 km/s             |
| ...                                      |
+------------------------------------------+
```

#### Creating a Rayleigh Line

1. **Select material**
   - Choose from the dropdown menu
   - Or select "Custom" for custom parameters

2. **Enter parameters**
   - **D (km/s)**: Shock velocity (required)
   - **rho0 (g/cm3)**: Initial density (optional, defaults to material value)

3. **Add the Rayleigh line**
   - Click the **Add** button
   - The Rayleigh line appears on the plot (dashed line)
   - A new entry is added to the list

4. **Manage Rayleigh lines**
   - Check/uncheck entries to show/hide
   - Click **Clear** to delete the selected line
   - Click **Clear All** to delete all lines

#### Rayleigh Line Properties

| Property | Description | Default |
|----------|-------------|---------|
| **Color** | Same as corresponding material Hugoniot | Auto-assigned |
| **Linestyle** | Dashed (`--`) | Fixed |
| **Linewidth** | 0.9 | Fixed |
| **Legend** | "{Material} Rayleigh Line, D=xx km/s" | Auto-generated |

#### Use Cases

1. **Single-layer target analysis**
   - Create one Rayleigh line
   - Find intersection with standard material
   - Obtain shock state (P, up)

2. **Multi-layer target analysis**
   - Create Rayleigh lines for each layer
   - Track shock wave propagation between layers
   - Compute compression ratio for each layer

3. **Impedance matching**
   - Compare Rayleigh lines of different materials
   - Find impedance matching points
   - Optimize material combinations

---

### Intersection Panel

**Location**: Lower middle of the left panel

#### Overview

Automatically computes intersections between all material Hugoniot curves and Rayleigh lines. This is the core functionality of impedance matching analysis. An intersection represents the material state when the shock wave arrives.

#### Panel Components

```
+------------------------------------------+
|  Intersections                           |
+------------------------------------------+
| [Find Intersections]                     |
+------------------------------------------+
| Selected Intersection:                   |
| +--------------------------------------+ |
| | Up:  2.45 km/s                       | |
| | P:   0.85 Mbar                       | |
| | CR:  1.44                            | |
| +--------------------------------------+ |
+------------------------------------------+
| +--------------------------------------+ |
| | Up      P       Curve1   Curve2      | |
| | 2.45   0.85    Al_371   RL_1         | |
| | 3.12   1.23    Quartz   RL_2         | |
| | ...                                  | |
| +--------------------------------------+ |
+------------------------------------------+
```

#### Finding Intersections

1. **Prepare data**
   - Ensure at least one material is checked
   - Ensure at least one Rayleigh line is added

2. **Find intersections**
   - Click the **Find Intersections** button
   - The system automatically computes all intersections
   - Intersections appear in the table

3. **Select an intersection**
   - Method 1: Click an intersection marker on the plot
   - Method 2: Click a row in the table
   - The selected intersection is highlighted

4. **View information**
   - The top of the panel shows details of the selected intersection
   - Including: Up, P, CR (compression ratio)

#### Intersection Algorithm

The system uses **sign-change detection** to find intersections:

1. For each curve and each Rayleigh line pair
2. Compute P_curve(up) - P_Rayleigh(up)
3. Find intervals where the sign changes
4. Use linear interpolation to precisely locate the intersection

#### Intersection Fields

| Field | Description | Unit |
|-------|-------------|------|
| **Up** | Particle velocity | km/s |
| **P** | Pressure | Mbar |
| **CR** | Compression ratio | dimensionless |
| **Curve1** | First curve ID | - |
| **Curve2** | Second curve ID | - |

#### Compression Ratio

After selecting an intersection, the compression ratio is automatically computed:

**CR = D / (D - up)**

where D is the Rayleigh line shock velocity and up is the intersection particle velocity.

**Note**: When up approaches D, CR becomes very large. This is normal physics (approaching the limiting compression).

---

### Reflected Hugoniot Panel

**Location**: Bottom of the left panel

#### Overview

When a shock wave travels from a high-impedance material into a low-impedance material, a reflected wave is generated. The reflected Hugoniot describes the material state after reflection.

#### Panel Components

```
+------------------------------------------+
|  Reflected Hugoniot                      |
+------------------------------------------+
| Selected Intersection:                   |
| Up: 2.45 km/s  P: 0.85 Mbar              |
|                                          |
| Curve: [Aluminum (SESAME 3717) v]        |
|                                          |
| [Add Reflected Curve]                    |
| [Clear] [Clear All]                      |
+------------------------------------------+
| [x] Al_3717 reflected, center: Al_371   |
| [x] Quartz reflected, center: Quartz    |
| ...                                      |
+------------------------------------------+
```

#### Creating a Reflected Hugoniot

1. **Select an intersection** (required)
   - Select in the intersection panel or on the plot
   - Intersection info appears at the top of the panel

2. **Choose a material**
   - Select from the dropdown menu
   - Typically one of the materials involved in the intersection

3. **Add reflected curve**
   - Click the **Add Reflected Curve** button
   - The reflected curve appears on the plot (dash-dot style)
   - Color matches the original curve

#### Reflection Principle

For a Hugoniot reflected from intersection point (up_center, P_center):

**up' = 2 * up_center - up**

where:
- up_center: Particle velocity at the intersection
- up: Particle velocity on the original curve
- up': Particle velocity on the reflected curve

#### Reflected Curve Properties

| Property | Description |
|----------|-------------|
| **Color** | Same as original curve |
| **Linestyle** | Dash-dot (`-.`) |
| **Linewidth** | 0.9 |
| **Legend** | "{Material name} reflected Hugoniot" |

#### Use Cases

1. **Free surface reflection**
   - State after the shock reaches a free surface
   - Used to compute particle velocity

2. **Inter-layer reflection**
   - Analyze reflected waves in multi-layer targets
   - Evaluate shock wave attenuation

3. **Impedance mismatch analysis**
   - Study reflection behavior at material interfaces
   - Optimize multi-layer target design

---

### Reference Curve Panel

**Location**: Bottom of the left panel

#### Overview

Reference curves are simplified custom curves for comparison with standard materials. Unlike full materials, reference curves may contain only partial variables.

#### Panel Components

```
+------------------------------------------+
|  Reference Curves                        |
+------------------------------------------+
| [Create New] [Manage] [Refresh]          |
+------------------------------------------+
| [x] Experimental Data (Up, P)           |
| [x] Simulation Result (Up, Us, P)       |
| ...                                      |
+------------------------------------------+
| [Select All] [Deselect All]             |
|                                          |
| 2 curves available                       |
+------------------------------------------+
```

#### Reference Curve Format

Reference curves use a simplified CSV format:

```
# Column names
Up,Us,P,rho,compression,T,E

# Units (optional)
km/s,km/s,Mbar,g/cm^3,-,eV,MJ/g

# Data
0.5,5.5,0.15,2.85,1.06,0.035,0.06
1.0,6.0,0.30,3.00,1.11,0.045,0.12
...
```

**Rules**:
- Row 1: Column names (supported: Up, Us, P, rho, compression, T, E)
- Row 2 (optional): Units
- Row 3+: Data values
- Required columns: Up, P (others optional)

#### Creating a Reference Curve

**Method 1: Using the creation dialog**

1. Click **Create New**
2. Enter curve name
3. Select variables (check needed columns)
4. Enter or paste data
5. Click **Save**

**Method 2: Manual file creation**

1. Create a CSV file in `reference_curves/`
2. Write data in the format above
3. Click **Refresh** to load

#### Managing Reference Curves

Click **Manage** to open the management dialog:

- View all reference curves
- Edit curve data and metadata
- Delete unwanted curves
- Export curves to file

#### Reference Curves vs Standard Materials

| Feature | Standard Material | Reference Curve |
|---------|-------------------|-----------------|
| **File location** | `standard_library/materials/` | `reference_curves/` |
| **Format** | 7-line header + data | Simplified CSV |
| **Required columns** | Up, Us, P, rho, compression | Up, P |
| **Optional columns** | T, E, source | Us, rho, compression, T, E |
| **Metadata** | Full (name, source, density, etc.) | Simplified (name only) |
| **Purpose** | Standard EOS data | Experimental data, simulation results |

---

### Plot Area

**Location**: Right main area

#### Overview

The plot area visualizes Hugoniot curves, Rayleigh lines, intersections, and reflected curves. Supports switching between multiple variable combinations.

#### Plot Tabs

Top tabs provide 8 plot types:

| Tab | X Axis | Y Axis | Content |
|-----|--------|--------|---------|
| **P-Up** | Up | P | Full analysis (curves, Rayleigh, intersections, reflected) |
| **P-CR** | compression | P | Material curves + scatter |
| **Us-Up** | Up | Us | Material curves |
| **P-T** | T | P | Material curves |
| **rho-Up** | Up | rho | Material curves |
| **T-Up** | Up | T | Material curves |
| **E-Up** | Up | E | Material curves |
| **P-Us** | Us | P | Material curves |

#### Plot Control Buttons

Each plot has control buttons above it:

| Button | Function | Description |
|--------|----------|-------------|
| **Auto Range** | Auto zoom | Set axis range to data range (1.1x margin) |
| **Inverse Axes** | Swap axes | Swap X/Y axes (generic plots) |
| **Show Legend** | Toggle legend | Show or hide legend |
| **Export** | Export plot | Save as PNG or PDF |

#### P-Up Plot (Main)

This is the most detailed plot, showing all analysis content:

- **Solid lines**: Material Hugoniot curves
- **Dashed lines (`--`)**: Rayleigh lines
- **Dash-dot lines (`-.`)**: Reflected Hugoniot
- **Circle markers (`o`)**: Intersections
- **Diamond markers**: Selected intersection
- **Legend**: Names and parameters of all curves

#### Other Plots

The remaining plots focus on material curves (no Rayleigh lines or intersections). Used for:
- Viewing relationships between different variables
- Verifying physical plausibility of data
- Preparing publication figures

#### Interaction

**Click to select intersections**:
- Click an intersection marker on the plot
- The nearest intersection is selected
- The intersection panel and table update simultaneously

**Plot zoom**:
- Mouse wheel zoom
- Drag to pan
- 'a' key to reset view

**Export plots**:
- Click the **Export** button
- Choose format (PNG/PDF)
- Choose resolution (default 300 DPI)
- Save file

---

## Data Format Specification

### Standard TXT/CSV Format (Recommended)

This is the standard format for the material library, with a 7-line comment header and tab-separated data columns.

#### File Structure

```
# Material: Aluminum
# Reference: SESAME 3717
# Initial Density: 2.7 g/cm^3
# Data Source: Los Alamos National Laboratory
# Date: 2024-01-01
# Notes: Principal Hugoniot from SESAME EOS table 3717
# Columns: Up(km/s)	Us(km/s)	P(Mbar)	rho(g/cm^3)	compression
0.0111795	5.22691	0.001	2.70579	1.00214
0.61119	6.16144	0.101099	2.99732	1.11012
1.23456	7.12345	0.234567	3.23456	1.19876
...
```

#### Header Lines

| Line | Format | Description |
|------|--------|-------------|
| 1 | `# Material: <name>` | Material name |
| 2 | `# Reference: <source>` | Data source |
| 3 | `# Initial Density: <value> g/cm^3` | Initial density |
| 4 | `# Data Source: <description>` | Source description |
| 5 | `# Date: <YYYY-MM-DD>` | Creation date |
| 6 | `# Notes: <text>` | Notes |
| 7 | `# Columns: <col1>\t<col2>...` | Column names |

#### Required Columns

| Column name | Unit | Description |
|-------------|------|-------------|
| `Up(km/s)` | km/s | Particle velocity |
| `Us(km/s)` | km/s | Shock velocity |
| `P(Mbar)` | Mbar | Pressure |
| `rho(g/cm^3)` | g/cm3 | Density |
| `compression` | - | Compression ratio (rho/rho0) |

#### Optional Columns

| Column name | Unit | Description |
|-------------|------|-------------|
| `T(eV)` | eV | Temperature |
| `E(MJ/g)` | MJ/g | Internal energy |
| `source` | - | Data point source |

#### Data Row Rules

- **Separator**: Tab (`\t`)
- **Decimal point**: Dot (`.`)
- **Scientific notation**: Supported (e.g., `1.23e-5`)
- **Empty lines**: Automatically ignored
- **Comment lines**: Lines starting with `#`

#### Complete Example

**File**: `standard_library/materials/Al_3717_sesame.txt`

```
# Material: Aluminum
# Reference: SESAME 3717
# Initial Density: 2.7 g/cm^3
# Data Source: Los Alamos National Laboratory
# Date: 2024-01-01
# Notes: Principal Hugoniot from SESAME EOS table 3717
# Columns: Up(km/s)	Us(km/s)	P(Mbar)	rho(g/cm^3)	compression	T(eV)	E(MJ/g)	source
0.0111795	5.22691	0.001	2.70579	1.00214	0.0259596	0.00188365	SESAME3717
0.61119	6.16144	0.101099	2.99732	1.11012	0.0333359	0.186521	SESAME3717
1.23456	7.12345	0.234567	3.23456	1.19876	0.0456789	0.345678	SESAME3717
2.34567	8.23456	0.456789	3.56789	1.32103	0.0567890	0.567890	SESAME3717
3.45678	9.34567	0.678901	3.90123	1.44527	0.0678901	0.789012	SESAME3717
...
```

---

### FEOS .hug Format

The output format of the FEOS (Free Equation of State) program, readable directly.

#### File Structure

```
# Rho [1.000000e+00 g/cm^3]  T [1.000000e+00 eV]  P [1.000000e+12 dyne/cm^2]  E [1.000000e+00 erg/g]  Us [1.000000e+05 cm/s]  Up [1.000000e+05 cm/s]
2.700000e+00  2.585257e-02  2.578641e-04  1.041546e+05  0.000000e+00  0.000000e+00
2.762324e+00  2.598183e-02  1.876615e-02  7.959303e+07  5.512012e+00  1.243633e-01
2.770417e+00  2.611174e-02  2.121301e-02  1.011632e+08  5.525820e+00  1.404527e-01
...
# eof.
```

#### Format Notes

**First line**: Comment header with column names and unit factors
- Format: `# Var1 [factor unit1]  Var2 [factor unit2]  ...`
- The factor in brackets indicates the data value unit

**Data lines**: Scientific notation, space-separated
- Column order: rho, T, P, E, Us, Up
- Separator: Space

#### Unit Conversion

| Column | Original unit | Factor meaning | Converted to | Conversion |
|--------|-------------|----------------|--------------|------------|
| rho | g/cm3 | `1.000000e+00` | g/cm3 | Direct read |
| T | eV | `1.000000e+00` | eV | Direct read |
| P | dyne/cm2 | `1.000000e+12` | Mbar | Direct read (already Mbar) |
| E | erg/g | `1.000000e+00` | MJ/g | Divide by 1e10 |
| Us | cm/s | `1.000000e+05` | km/s | Direct read (already km/s) |
| Up | cm/s | `1.000000e+05` | km/s | Direct read (already km/s) |

**Important**:
- `P [1.000000e+12 dyne/cm^2]` means the data values are in units of 1e12 dyne/cm2
- Since 1 Mbar = 1e12 dyne/cm2, the numerical value is already in Mbar
- Similarly, `Us [1.000000e+05 cm/s]` means the values are in 1e5 cm/s = 1 km/s

#### Example File

**File**: `standard_library/materials/Al_FEOS.hug`

```
# Rho [1.000000e+00 g/cm^3]  T [1.000000e+00 eV]  P [1.000000e+12 dyne/cm^2]  E [1.000000e+00 erg/g]  Us [1.000000e+05 cm/s]  Up [1.000000e+05 cm/s]
2.700000e+00  2.585257e-02  2.578641e-04  1.041546e+05  0.000000e+00  0.000000e+00
2.762324e+00  2.598183e-02  1.876615e-02  7.959303e+07  5.512012e+00  1.243633e-01
2.770417e+00  2.611174e-02  2.121301e-02  1.011632e+08  5.525820e+00  1.404527e-01
2.783347e+00  2.637351e-02  2.514512e-02  1.409700e+08  5.548098e+00  1.661380e-01
...
# eof.
```

---

### Reference Curve CSV Format

A simplified CSV format for quickly adding custom reference curves.

#### File Structure

```
Up,Us,P,rho,compression,T,E
0.5,5.5,0.15,2.85,1.06,0.035,0.06
1.0,6.0,0.30,3.00,1.11,0.045,0.12
1.5,6.5,0.48,3.18,1.18,0.055,0.20
...
```

#### Format Rules

1. **Row 1**: Column names (comma-separated)
   - Supported variables: Up, Us, P, rho, compression, T, E
   - Required columns: Up, P
   - Other columns optional

2. **Row 2** (optional): Units
   - e.g., `km/s,km/s,Mbar,g/cm^3,-,eV,MJ/g`
   - If omitted, default units are used

3. **Data rows**: Values (comma-separated)
   - Missing values: leave empty or use `NaN`

#### Minimum Format (Up and P only)

```
Up,P
0.5,0.15
1.0,0.30
1.5,0.48
2.0,0.70
```

#### Full Format Example

```
Up,Us,P,rho,compression,T,E
km/s,km/s,Mbar,g/cm^3,-,eV,MJ/g
0.5,5.5,0.15,2.85,1.06,0.035,0.06
1.0,6.0,0.30,3.00,1.11,0.045,0.12
1.5,6.5,0.48,3.18,1.18,0.055,0.20
2.0,7.0,0.70,3.40,1.26,0.068,0.32
```

---

## Physical Model

### Rayleigh Line Equation

The Rayleigh line describes the shock front state relation:

**P = rho0 * up * D * 0.01**

**Derivation**:

From mass and momentum conservation:
- Mass: rho0 * D = rho * (D - up)
- Momentum: P = rho0 * D * up

Unit conversion:
- D, up: km/s -> cm/s (x 1e5)
- rho0: g/cm3
- P: dyne/cm2 -> Mbar (/ 1e12)

Combined:
```
P (Mbar) = rho0 (g/cm3) * D (km/s) * up (km/s) * 0.01
```

**Physical meaning**:
- For fixed D and rho0, P is linear in up
- Rayleigh line slope: dP/dup = rho0 * D * 0.01
- Passes through origin (up = 0, P = 0)

### Compression Ratio

The compression ratio is the ratio of shocked density to initial density:

**CR = rho / rho0 = D / (D - up)**

**Derivation**:

From mass conservation:
```
rho0 * D = rho * (D - up)
rho / rho0 = D / (D - up)
```

**Physical meaning**:
- CR >= 1 (shock compression always increases density)
- As up -> D, CR -> infinity (limiting compression)
- Typical CR range for metals: 1.0 - 4.0

### Reflected Hugoniot

When a shock wave travels from high-impedance to low-impedance material:

**up' = 2 * up_center - up**

where:
- up_center: Particle velocity at the intersection (shock arrival at interface)
- up: Particle velocity on the original curve
- up': Particle velocity on the reflected curve

**Physical meaning**:
- The reflected curve is the mirror image of the original about up = up_center
- At the intersection point: up' = up_center (continuity)
- Free surface reflection: up_FS = 2 * up_center

### Unit Conversion Table

| Quantity | Symbol | Common unit | SI unit | Conversion |
|----------|--------|-------------|---------|------------|
| **Pressure** | P | Mbar | Pa | 1 Mbar = 100 GPa = 10^11 Pa |
| **Particle velocity** | up | km/s | m/s | 1 km/s = 1000 m/s |
| **Shock velocity** | D, Us | km/s | m/s | 1 km/s = 1000 m/s |
| **Density** | rho | g/cm3 | kg/m3 | 1 g/cm3 = 1000 kg/m3 |
| **Temperature** | T | eV | K | 1 eV ~ 11605 K |
| **Internal energy** | E | MJ/g | J/kg | 1 MJ/g = 10^6 J/kg |

**Practical conversions**:
- 1 Mbar = 100 GPa
- 1 GPa = 10 kbar
- 1 kbar = 0.1 GPa

---

## Project Architecture

### Directory Structure

```
IM_tool/
+-- im_app/                      # Application package
|   +-- main.py                  # Application entry point
|   +-- core/                    # Core computation modules
|   |   +-- data_loader.py       # Data loader (TXT/CSV/FEOS)
|   |   +-- data_converter.py    # Format converter
|   |   +-- physics.py           # Physical models (MaterialData, etc.)
|   |   +-- plot_style.py        # PRL plot style definition
|   |   +-- plotter.py           # Plot components (HugoniotPlot, etc.)
|   |   +-- element_style.py     # Element style editor
|   |   +-- reference_curve.py   # Reference curve loader
|   +-- gui/                     # GUI modules
|   |   +-- main_window.py       # Main window (layout, event handling)
|   |   +-- material_panel.py    # Material selection panel
|   |   +-- rayleigh_panel.py    # Rayleigh line panel
|   |   +-- intersection_panel.py # Intersection panel
|   |   +-- scatter_panel.py     # Scatter points panel
|   |   +-- reference_curve_panel.py # Reference curve panel
|   |   +-- material_wizard.py   # Material creation wizard
|   |   +-- validation_dialog.py # File validation dialog
|   |   +-- ideal_plasma_dialog.py # Ideal plasma Hugoniot generator
|   |   +-- reference_curve_dialog.py # Reference curve dialog
|   |   +-- reference_curve_manager.py # Curve management
|   +-- standard_library/        # Standard material library
|   |   +-- metadata.json        # Material index
|   |   +-- materials/           # Material data files
|   |   |   +-- *.txt            # Standard format files
|   |   |   +-- *.hug            # FEOS format files
|   |   +-- reference_curves/    # Reference curves
|   |   +-- FORMAT_SPECIFICATION.md # Format spec
|   |   +-- USER_GUIDE.md        # User guide
|   +-- workflows/               # Saved analysis states
+-- scripts/                     # Data conversion scripts
|   +-- convert_to_standard.py   # Raw data to standard format
|   +-- package_release.py       # Distribution package builder
+-- docs/                        # Documentation
|   +-- ideal_plasma_hugoniot_theory.md  # Theory doc
|   +-- validate_tool.md         # Validation tool guide
+-- requirements.txt             # Python dependencies
+-- run_app.py                   # Application launcher
+-- run_app.bat                  # Windows launcher
+-- README.md                    # This file
+-- README_EN.md                 # English README
```

### Core Data Model

#### MaterialData

```python
@dataclass
class MaterialData:
    id: str                      # Unique identifier (e.g., "Al_3717_sesame")
    name: str                    # Display name (e.g., "Aluminum")
    rho0: float                  # Initial density (g/cm3)
    up: np.ndarray               # Particle velocity (km/s) [required]
    p: np.ndarray                # Pressure (Mbar) [required]
    us: np.ndarray | None        # Shock velocity (km/s) [optional]
    compression: np.ndarray | None  # Compression ratio [optional]
    rho: np.ndarray | None       # Density (g/cm3) [optional]
    temperature: np.ndarray | None   # Temperature (eV) [optional]
    energy: np.ndarray | None    # Internal energy (MJ/g) [optional]
```

**Usage example**:
```python
from im_app.core.physics import MaterialData
import numpy as np

mat = MaterialData(
    id="Al_3717",
    name="Aluminum",
    rho0=2.7,
    up=np.array([0.0, 0.5, 1.0, ...]),
    p=np.array([0.0, 0.1, 0.2, ...]),
    us=np.array([5.0, 5.5, 6.0, ...]),
    compression=np.array([1.0, 1.1, 1.2, ...]),
    rho=np.array([2.7, 2.85, 3.0, ...])
)
```

#### RayleighLine

```python
@dataclass
class RayleighLine:
    id: str                      # Unique identifier
    material_id: str             # Material ID
    D: float                     # Shock velocity (km/s)
    rho0: float                  # Initial density (g/cm3)
    up: np.ndarray               # Particle velocity array
    p: np.ndarray                # Pressure array (P = rho0*up*D*0.01)
```

**Computation example**:
```python
from im_app.core.physics import RayleighLine
import numpy as np

rl = RayleighLine(
    id="RL_Al_8km",
    material_id="Al_3717",
    D=8.0,
    rho0=2.7,
    up=np.linspace(0, 5, 100)
)
# p array is computed automatically
```

#### Intersection

```python
@dataclass
class Intersection:
    id: str                      # Unique identifier
    curve1_id: str               # First curve ID
    curve2_id: str               # Second curve ID
    up: float                    # Particle velocity (km/s)
    p: float                     # Pressure (Mbar)
    compression_ratio: float     # Compression ratio
```

### Module Dependencies

```
main.py
  +-- main_window.py
      +-- material_panel.py
      |   +-- data_loader.py
      |   +-- physics.py
      +-- rayleigh_panel.py
      |   +-- physics.py
      +-- intersection_panel.py
      |   +-- physics.py (find_intersections)
      |   +-- plotter.py
      +-- reference_curve_panel.py
      |   +-- reference_curve.py
      +-- plotter.py
          +-- physics.py
          +-- plot_style.py
          +-- matplotlib
```

---

## FAQ

### Q1: Why is my material not showing up in the list?

**Possible causes and solutions**:

1. **Wrong file location**
   - Make sure the file is in `im_app/standard_library/materials/`
   - Check the file extension (`.txt` or `.hug`)

2. **Wrong file format**
   - Use **Validate File** to check the format
   - Ensure 7-line comment header (standard format)
   - Check column names match

3. **Not refreshed**
   - Click the **Refresh** button to reload
   - Restart the application

4. **metadata.json not updated**
   - Check if `metadata.json` contains the material entry
   - Add manually or use Refresh to auto-add

### Q2: Why is my plot showing a horizontal line?

**Cause**: Data unit conversion error

**Solutions**:

1. **Check data units**
   - Confirm pressure column is in Mbar, not GPa or Pa
   - Confirm velocity columns are in km/s

2. **If using FEOS .hug format**
   - Check the file header comment is correct
   - P column should already be in Mbar units
   - Us, Up columns should already be in km/s units

3. **Validate the file**
   - Use the **Validate File** feature
   - Check if data ranges are reasonable

### Q3: How do I export high-resolution figures for publication?

**Steps**:

1. Click the **Export** button in the plot area
2. Choose format:
   - **PNG**: Bitmap, suitable for document insertion
   - **PDF**: Vector, suitable for journal submission
3. Choose resolution (default 300 DPI)
4. Save the file

**Recommendations**:
- Journal submission: Use PDF format
- Presentations: Use PNG (300 DPI)
- Web publishing: Use PNG (150 DPI)

### Q4: What's the difference between reference curves and standard materials?

| Feature | Standard Material | Reference Curve |
|---------|-------------------|-----------------|
| **Format** | 7-line header + data | Simplified CSV |
| **Required columns** | Up, Us, P, rho, compression | Up, P |
| **Metadata** | Full (name, source, density) | Simplified (name only) |
| **Purpose** | Standard EOS equation of state | Experimental data, comparison |

**Selection guide**:
- Complete EOS data -> Standard material
- Experimental measurements -> Reference curve
- Simulation result comparison -> Reference curve

### Q5: Why is my compression ratio abnormally large?

**Checklist**:

1. **Is the shock velocity D correct?**
   - Confirm D is in km/s
   - Check Rayleigh line parameters

2. **Is the intersection particle velocity up reasonable?**
   - Check the up value
   - Confirm units are km/s

3. **Physical plausibility**
   - When up approaches D, CR becomes very large (normal)
   - Check if close to the limiting compression

**Reference values**:
- Metals: CR ~ 1.0 - 4.0
- Limiting compression: CR -> infinity (theoretically)

### Q6: What file encodings are supported?

**Recommended encoding**: UTF-8

**Problem**:
- Chinese or special characters display as garbled text
- Comment lines cannot be parsed correctly

**Solution**:
1. Open the file in a text editor (e.g., Notepad++)
2. Convert encoding to UTF-8
3. Save the file
4. Reload

**Supported encodings**:
- UTF-8 (recommended)
- UTF-8 with BOM
- ASCII

### Q7: How do I batch-convert data files?

**Method 1: Using the conversion script**

```bash
python scripts/convert_to_standard.py --input raw_data.csv --output materials/Al_new.txt
```

**Method 2: Using Python**

```python
from im_app.core.data_converter import convert_to_standard

convert_to_standard(
    input_path="raw_data.csv",
    output_path="materials/Al_new.txt",
    material_name="Aluminum",
    reference="Experimental 2024",
    rho0=2.7
)
```

**Method 3: Using the material wizard**
- Supports pasting from clipboard
- Supports loading from file
- Automatic formatting

### Q8: The legend is incomplete or overlapping. What should I do?

**Solutions**:

1. **Manual adjustment**
   - Click the legend on the plot
   - Drag to a suitable position

2. **Reduce the number of materials**
   - Uncheck some materials
   - Analyze in batches

3. **Use abbreviations**
   - Edit material names (modify `metadata.json`)
   - Use short names (e.g., "Al" instead of "Aluminum")

4. **Adjust font size**
   - Edit the `fontsize` parameter in `plotter.py`
   - Restart the application

---

## Version History

### v1.0.0 (2026-05-30)

**Initial release**

Core features:
- Hugoniot curve plotting and display
- Rayleigh line creation and management
- Automatic intersection computation and selection
- Reflected Hugoniot computation
- Real-time compression ratio calculation

Data format support:
- Standard TXT/CSV format (7-line comment header)
- FEOS .hug format
- Reference curve CSV format

Plot features:
- 8 variable combination plots (P-Up, P-CR, Us-Up, P-T, rho-Up, T-Up, E-Up, P-Us)
- Auto Range zoom
- Inverse Axes swap
- Interactive intersection selection

Material management:
- Automatic material library refresh
- Material creation wizard
- File format validation

UI features:
- PRL-style publication-grade plots
- High-resolution export (300 DPI)
- Multi-language interface preparation

---

## Author

**BoXu**
- Email: boxu25@stu.pku.edu.cn
- Affiliation: Peking University

**About the project**:
This project is an impedance matching analysis tool developed for shock physics (HEDP) research, designed to streamline experimental data processing and analysis workflow, improving research efficiency.

---

## License

This project is for academic research and educational use only.

---

## Acknowledgments

Thanks to the following projects and resources:
- PyQt5 GUI framework
- matplotlib plotting library
- PRL journal plot style guide
- SESAME EOS database

---

*Last updated: 2026-05-30*
