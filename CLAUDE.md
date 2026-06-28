# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scientific analysis tool for **Impedance Matching** in shock physics (HEDP). Computes pressure and compression ratios in multi-layer targets from measured shock velocities using Hugoniot equations of state. Comments and markdown are written in Chinese throughout.

The GUI presents **8 plot tabs** (P-Up, P-CR, Us-Up, P-T, rho-Up, T-Up, E-Up, P-Us) with click-to-select elements, right-click context menus for per-element style editing, reverse impedance matching, and JSON workflow save/load.

## Running the Application

**GUI Application** (primary workflow):
```bash
cd D:/My_app/IM_tool
python -m im_app.main        # primary entry point
python run_app.py            # alternative launcher (sets PYTHONPATH)
```

Dependencies: `pip install -r requirements.txt` (PyQt5, numpy, pandas, matplotlib, scipy, xlrd, openpyxl)

**Legacy notebooks** (preserved under `reference/`):
- `reference/Impedance_matching.ipynb` — SESAME EOS tables
- `reference/Impedance_matching_zhangHugoniot.ipynb` — Celliers 2005 / Hamel 2012 analytical fits

**Scripts**:
```bash
python scripts/convert_to_standard.py    # converts raw data to standard library format
python scripts/convert_csv_to_txt.py     # converts legacy .csv to .txt format
python scripts/validate_hugoniot.py      # CLI entry to Hugoniot file validation
```

## Architecture

### `im_app/` — Application Package

```
im_app/
├── main.py                          # Entry point (window maximized)
├── core/
│   ├── data_loader.py                # Standard format loader (auto-detects .csv/.txt/.hug)
│   ├── data_converter.py             # Raw → standard format converter; read/write standard .txt
│   ├── physics.py                    # MaterialData, RayleighLine, Intersection + math
│   ├── reference_curve.py            # Reference curve CSV loader + variable mapping
│   ├── element_style.py              # ElementStyle + style editor dialogs (color/linewidth/marker)
│   ├── plot_style.py                 # Physical Review Letters matplotlib style
│   └── plotter.py                    # DragZoomMixin + InteractiveHugoniotPlot, EOSPlot, GenericHugoniotPlot
├── gui/
│   ├── main_window.py                # Main window (QSplitter, ~1700 lines, orchestrates everything)
│   ├── material_panel.py             # Material checkbox selection + add-material menu
│   ├── material_wizard.py            # Multi-step wizard to add a new material from raw file
│   ├── validation_dialog.py          # File-validation dialog (uses tools/validate_hugoniot)
│   ├── ideal_plasma_dialog.py        # Generate ideal-γ-law plasma Hugoniot analytically
│   ├── rayleigh_panel.py             # Rayleigh line creation/management
│   ├── intersection_panel.py         # Intersection table + reflection + reverse match controls
│   ├── reference_curve_panel.py      # Reference curve selection checkboxes
│   ├── reference_curve_dialog.py     # Create new reference curve
│   └── reference_curve_manager.py    # Manage (list/edit/delete) saved reference curves
├── tools/
│   └── validate_hugoniot.py          # Hugoniot data file validator (validate_file, ValidationResult)
├── standard_library/
│   ├── metadata.json                 # Material index (10 materials)
│   ├── materials/*.{txt,csv,hug}     # Standardized Hugoniot data
│   ├── reference_curves/*.csv        # Reference curves (e.g., CH_sesame7592.csv)
│   ├── FORMAT_SPECIFICATION.md
│   ├── README.md
│   └── USER_GUIDE.md
└── workflows/                        # Saved analysis states (.json)
```

**Legacy / unused GUI files** (still present but **not imported anywhere**; their imports reference symbols that no longer exist — `HugoniotRayleighPlot`, `ImpedanceResult`):
- `gui/param_panel.py`
- `gui/plot_panel.py`
- `gui/result_panel.py`

These can be deleted in a cleanup pass; do not assume they are wired into the app.

### Standard Hugoniot Data Formats

`data_loader.load_standard_hugoniot_auto()` dispatches by file extension:

- **`.csv`** — original tab-separated format with 7 `#`-comment header lines (Material, Reference, rho0, Source, Date, Notes, Columns). Columns: `Up(km/s)`, `Us(km/s)`, `P(Mbar)`, `rho(g/cm3)`, `compression`, optional `T(eV)`, `E(MJ/g)`, `source`.
- **`.txt`** — same logical format as `.csv` but parsed by `data_converter.read_standard_txt()`. This is the **current default** for new materials (see `metadata.json`).
- **`.hug`** — FEOS binary-ish text format. First line is a comment header; subsequent lines are space-separated scientific notation in column order: `rho, T, P, E, Us, Up`. Units: rho (g/cm³), T (eV), P (Mbar), E (erg/g → divide by 1e10 for MJ/g), Us/Up (km/s). Compression is derived as `rho / rho[0]`.

**Reference curves** (`reference_curves/*.csv`): a simpler 3-row CSV — row 1 column names (must match `Up`, `Us`, `P`, `rho`, `compression`, `T`, `E`), row 2 units, row 3+ data. Loaded by `reference_curve.load_reference_curve()`.

### Material Library (metadata.json)

10 materials indexed by `{Name}_{Source}` ID:
- `Al_3717_sesame`, `Al_3720_sesame` — Aluminum SESAME tables
- `Quartz_7360_sesame`, `Quartz_7385_sesame` — Alpha Quartz SESAME
- `BN_LEA` — Boron Nitride (LEA SESAME)
- `Al_Celliers2005` — Aluminum (Celliers et al. 2005 analytical fit)
- `Quartz_Hamel2012` — Alpha Quartz (Hamel et al. 2012 analytical fit)
- `Al_FEOS` — Aluminum FEOS table (`.hug` format)
- `CH_foam_ideal_plasma` — CH foam via ideal-γ-law generator

### Core Data Flow

1. **Material selection** → checkboxes load from standard library via `data_loader.py`. IDs starting with `ref_` are reference curves and are excluded from material-only operations.
2. **Rayleigh lines** → user inputs D, rho0; computed as `P = rho0 * up * D * 0.01` (Mbar).
3. **Find intersections** → `physics.find_intersections()` via sign-change detection on a fine common grid; first intersection near zero is ignored by default.
4. **Select intersection** → click on plot (zorder-priority pick) or table row.
5. **Reflect Hugoniot** → choose curve + intersection center; `up_r = 2*center - up`.
6. **Reverse impedance match** → given a known (up, p) target, scan reflection centers and solve `P(2*center - target_up) = target_p` with `brentq` (`physics.reverse_impedance_match`).
7. **Compression ratio** → `D / (D - up)`, or interpolated from the material's `compression` column when available.

### Plot Tabs and Variable Mapping

Eight tabs in `plot_tabs` (QTabWidget), each backed by a `FigureCanvas` subclass:

| Tab | Class | X var | Y var |
|-----|-------|-------|-------|
| P-Up Diagram | `InteractiveHugoniotPlot` | Up | P |
| P-CR Diagram | `EOSPlot` | compression | P |
| Us-Up Diagram | `GenericHugoniotPlot("Us","Up")` | Us | Up |
| P-T Diagram | `GenericHugoniotPlot("P","T")` | P | T |
| rho-Up Diagram | `GenericHugoniotPlot("rho","Up")` | rho | Up |
| T-Up Diagram | `GenericHugoniotPlot("T","Up")` | T | Up |
| E-Up Diagram | `GenericHugoniotPlot("E","Up")` | E | Up |
| P-Us Diagram | `GenericHugoniotPlot("P","Us")` | P | Us |

Only `InteractiveHugoniotPlot` supports intersections / Rayleigh lines / reflected curves / click-selection. The generic plots display material Hugoniots only. Generic plots support an "Inverse Axes" toggle that recreates the plot with swapped X/Y.

### Interactive Element Model

Every drawable element has an `element_id` of the form `{prefix}_{data_id}`:
- `mat_{material_id}` — material Hugoniot
- `rl_{rayleigh_id}` — Rayleigh line
- `refl_{reflected_id}` — reflected Hugoniot
- `ix_{intersection_id}` — intersection point

`InteractiveHugoniotPlot` maintains `_artist_map` (Artist → element_id), `_element_zorder` (for pick priority; intersections have zorder 10–15 to win over lines at zorder 1), and `_element_meta` (element_id → `{type, style, data_id}`). Right-click opens a `QMenu` with **Edit Style...**, **Change Color** (submenu), and **Delete**.

`MainWindow._on_element_deleted` routes deletion back to the appropriate panel (material panel checkbox, rayleigh panel, intersection table, reflected list).

### Interactive Plot Navigation (drag-zoom + 'a' reset)

All 8 plot tabs inherit `DragZoomMixin` (defined in `core/plotter.py`, pure-Python mixin — host classes own the `zoom_applied(float, float, float, float)` and `reset_view()` pyqtSignals; the mixin calls `self.zoom_applied.emit(...)` / `self.reset_view.emit()`):

- **Drag-to-zoom**: left-click and drag a rectangle > 5 px (display pixels). A red translucent rubber-band `Rectangle` patch is drawn during drag; on release the plot's xlim/ylim are set to the dragged region and `zoom_applied(xmin, xmax, ymin, ymax)` is emitted. Drags ≤ 5 px fall through to click handling.
- **'a' key reset**: when the canvas has keyboard focus (click the plot first), pressing `a` emits `reset_view()`, which restores the plot's hardcoded default range from `PLOT_DEFAULTS` in `main_window.py`. `setup_drag_zoom()` calls `self.setFocusPolicy(Qt.StrongFocus)` so the canvas can actually receive key events (default is `Qt.NoFocus`).
- **State sync**: `MainWindow._on_plot_zoom_applied` updates `_plot_settings[key]`, applies limits to the plot instance (note: `EOSPlot` uses `update_plot()` instead of `set_xlim/set_ylim` because it doesn't define those methods), and syncs the 4 spinboxes in the Plot Settings panel when the current tab matches. State persists across tab switches and is saved in workflow JSON via the existing `_save_workflow` path.

`InteractiveHugoniotPlot` overrides `_handle_click_release(event)` (renamed from `_on_click`) to do element selection on left-click and context menu on right-click. Selection fires on **release** rather than press so the 5 px drag-vs-click threshold can be evaluated first.

### Plot Settings

Per-plot settings stored in `MainWindow._plot_settings` dict keyed by short name (`P-Up`, `P-CR`, `Us-Up`, `P-T`, `rho-Up`, `T-Up`, `E-Up`, `P-Us`). Each entry holds `xlim`, `ylim`, `show_legend`. `P-Up` additionally holds `linestyle` and `linewidth`. The plot-settings control panel at the bottom of the left pane edits whichever plot is currently selected in the combo (synced with the active tab). Module-level `PLOT_DEFAULTS` dict holds the hardcoded initial ranges (one per plot key) used by the 'a' key reset.

### Plot Style

All plots use Physical Review Letters (PRL) style: serif fonts, inward ticks, colorblind-friendly palette, 300 DPI export. Configured in `core/plot_style.py` via `apply_prl_style()` and `save_prl_figure()`.

### Conventions

- **Units**: density (g/cm³), velocity (km/s), pressure (Mbar; 1 Mbar = 100 GPa), temperature (eV), energy (MJ/g).
- **Column names**: use full names with units in parentheses, e.g. `Up(km/s)`, `P(Mbar)`.
- **Material IDs**: `{Name}_{Source}` format, e.g. `Al_3717_sesame`, `Quartz_Hamel2012`. Reference curves use `ref_` prefix when added to plots.
- **Chinese comments**: code comments and dialog strings are predominantly Chinese; module docstrings are bilingual.
- **No build system or test suite** — validate by running the GUI and comparing with notebook results.
