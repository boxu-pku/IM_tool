# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Scientific analysis tool for **Impedance Matching** in shock physics (HEDP). Computes pressure and compression ratios in multi-layer targets from measured shock velocities using Hugoniot equations of state. Comments and markdown are written in Chinese throughout.

The GUI presents **8 plot tabs** (P-Up, P-CR, Us-Up, P-T, rho-Up, T-Up, E-Up, P-Us) with click-to-select elements, right-click context menus for per-element style editing, scatter points, reverse impedance matching, and JSON workflow save/load.

## Running the Application

**GUI Application**

From the repository root in an active virtual environment:

```bash
python -m pip install -e .
im-tool                       # GUI, also available as python -m im_app.main
```

**Headless / AI operator interface** (drive the analysis without the GUI — full manual in `docs/AI_GUIDE.md`):
```bash
python -m im_app.cli materials search quartz          # query the material library (pure JSON)
python -m im_app.cli template impedance               # two-layer impedance-matching workflow template
python -m im_app.cli run im_app/workflows/AC_shot384-L.json --out runs/AC_shot384-L/   # recompute + MC + export figures/results
```
Engine: `im_app/api/headless.py` (offscreen MainWindow — same code path as the GUI).
CLI stdout is always pure JSON; debug output goes to stderr. Regression test: `python tests/smoke_test_headless.py`.

Build desktop installers with `packaging/build_desktop.py` as described in [the packaging guide](packaging/README.md).

**Scripts**:
```bash
python scripts/convert_to_standard.py    # raw data → standard library format
python scripts/convert_csv_to_txt.py     # legacy .csv → .txt format
python -m im_app.tools.validate_hugoniot --help  # Hugoniot file validation
```

## Architecture

### `im_app/` — Application Package

```
im_app/
├── main.py                          # Entry point (Fusion style, window maximized)
├── cli.py                           # Headless CLI (`python -m im_app.cli`, AI/agent interface)
├── api/
│   └── headless.py                  # HeadlessSession engine (offscreen MainWindow; drives the same code path as the GUI)
├── core/
│   ├── data_loader.py                # Standard format loader (auto-detects .csv/.txt/.hug)
│   ├── data_converter.py             # Raw → standard format converter; read/write .txt
│   ├── physics.py                    # MaterialData, RayleighLine, Intersection + math
│   ├── reference_curve.py            # Reference curve CSV loader + variable mapping
│   ├── element_style.py              # ElementStyle + style editor dialogs (color/linewidth/marker/scatter)
│   ├── plot_style.py                 # PRL matplotlib style (font size constants exposed)
│   └── plotter.py                    # DragZoomMixin + ElementInteractionMixin + 3 plot classes
├── gui/
│   ├── main_window.py                # Main window (~2500 lines, orchestrates everything)
│   ├── material_panel.py             # Material checkbox selection + refresh/validate buttons
│   ├── material_wizard.py            # Multi-step wizard to add material from raw file
│   ├── validation_dialog.py          # File-validation dialog (background thread)
│   ├── ideal_plasma_dialog.py        # Generate ideal-γ-law plasma Hugoniot
│   ├── rayleigh_panel.py             # Rayleigh line creation/management + edit dialog
│   ├── intersection_panel.py         # Intersection table + reflection + reverse match + auto-update
│   ├── scatter_panel                 # [embedded in main_window] Scatter points from intersection or manual
│   ├── reference_curve_panel.py      # Reference curve selection checkboxes
│   ├── reference_curve_dialog.py     # Create new reference curve
│   └── reference_curve_manager.py    # Manage (list/edit/delete) saved reference curves
├── tools/
│   └── validate_hugoniot.py          # Hugoniot data file validator (validate_file, ValidationResult)
├── standard_library/
│   ├── metadata.json                 # Material index (10 materials)
│   ├── materials/*.{txt,csv,hug}     # Standardized Hugoniot data
│   ├── reference_curves/*.csv        # Reference curves (e.g., CH_sesame7592.csv)
│   ├── validators/                   # (empty, reserved)
│   ├── FORMAT_SPECIFICATION.md
│   ├── README.md
│   └── USER_GUIDE.md
└── workflows/                        # Saved analysis states (.json)
```

### Outside `im_app/`

```text
docs/             User guides, theory and manual sources
packaging/        Linux, Windows and macOS desktop installer builds
ref/              Reference material
scripts/          Data conversion and maintenance tools
tests/            GUI and headless regression tests
pyproject.toml    Python packaging and GUI/CLI entry points
```

### Standard Hugoniot Data Formats

`data_loader.load_standard_hugoniot_auto()` dispatches by file extension:

- **`.csv`** — original tab-separated format with 7 `#`-comment header lines (Material, Reference, rho0, Source, Date, Notes, Columns). Columns: `Up(km/s)`, `Us(km/s)`, `P(Mbar)`, `rho(g/cm3)`, `compression`, optional `T(eV)`, `E(MJ/g)`, `source`.
- **`.txt`** — same logical format as `.csv` but parsed by `data_converter.read_standard_txt()`. This is the **current default** for new materials.
- **`.hug`** — FEOS binary-ish text format. First line comment header; subsequent lines space-separated scientific notation: `rho, T, P, E, Us, Up`. Units: rho (g/cm³), T (eV), P (Mbar), E (erg/g → divide by 1e10 for MJ/g), Us/Up (km/s). Compression derived as `rho / rho[0]`.

**Reference curves** (`reference_curves/*.csv`): 3-row CSV — row 1 column names (must match `Up`, `Us`, `P`, `rho`, `compression`, `T`, `E`), row 2 units, row 3+ data. Loaded by `reference_curve.load_reference_curve()`.

### Material Library (metadata.json)

10 materials indexed by `{Name}_{Source}` ID:
- `Al_3717_sesame`, `Al_3720_sesame` — Aluminum SESAME tables
- `Quartz_7360_sesame`, `Quartz_7385_sesame` — Alpha Quartz SESAME
- `BN_LEA` — Boron Nitride (LEA SESAME)
- `Al_Celliers2005` — Aluminum (Celliers et al. 2005 analytical fit)
- `Quartz_Hamel2012` — Alpha Quartz (Hamel et al. 2012 analytical fit)
- `Al_FEOS` — Aluminum FEOS table (`.hug`)
- `CH_foam_ideal_plasma` — CH foam via ideal-γ-law generator

### Core Data Flow

1. **Material selection** → checkboxes load from standard library via `data_loader.py`. IDs starting with `ref_` are reference curves, excluded from material-only operations.
2. **Rayleigh lines** → user inputs D (km/s), rho0 (g/cm³); computed as `P = rho0 * up * D * 0.01` (Mbar). Double-click a Rayleigh line to edit parameters in `RayleighEditDialog`.
3. **Find intersections** → `physics.find_intersections()` via sign-change detection on a fine common grid; first intersection near zero is ignored by default.
4. **Select intersection** → click on plot (zorder-priority pick) or table row.
5. **Reflect Hugoniot** → choose curve + intersection center; reflected up `up_r = 2*center - up`.
6. **Reverse impedance match** → given known (up, p) target, scan reflection centers, solve `P(2*center - target_up) = target_p` with `brentq` (`physics.reverse_impedance_match`).
7. **Compression ratio** → `D / (D - up)`, or interpolated from material's `compression` column.
8. **Scatter points** → create from selected intersection or manual X/Y entry; editable style via right-click.

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

- `InteractiveHugoniotPlot` (P-Up) supports intersections / Rayleigh lines / reflected curves / click-selection.
- All other plots (`EOSPlot`, `GenericHugoniotPlot`) display material Hugoniots and support **inverse axes** toggle + right-click style editing.
- Generic plots support an **"Inverse Axes"** toggle that recreates the plot with swapped X/Y.

### Interactive Element Model

Every drawable element has an `element_id` of the form `{prefix}_{data_id}`:
- `mat_{material_id}` — material Hugoniot
- `rl_{rayleigh_id}` — Rayleigh line
- `refl_{reflected_id}` — reflected Hugoniot
- `ix_{intersection_id}` — intersection point
- `sc_{scatter_id}` — scatter point

**Artist registration system** (shared via `ElementInteractionMixin`):
- `_artist_map` — `artist` → `element_id`
- `_element_meta` — `element_id` → `{type, style, data_id}`
- `_element_zorder` — `element_id` → zorder (intersections zorder 10–15 > lines at 1)
- `_selected_element_id` — currently selected element

`InteractiveHugoniotPlot` also inherits `_material_color_map` for persisting material colors across refresh cycles.

**Right-click context menu** (all plots):
- **Edit Style...** — opens `StyleEditorDialog` (color, alpha, linewidth, linestyle, marker)
- **Change Color** — submenu with quick color choices (`QuickColorDialog`)
- **Delete** — removes element (routed via `MainWindow._on_element_deleted`)

**Selection visual feedback**: selected lines are drawn at 1.5× their base linewidth.

### Interactive Plot Navigation (drag-zoom + 'a' reset)

All 8 plot tabs inherit `DragZoomMixin` (in `core/plotter.py`):

- **Drag-to-zoom**: left-click drag rectangle > 5 px (display pixels). Red translucent rubber-band drawn during drag; on release sets xlim/ylim and emits `zoom_applied(xmin, xmax, ymin, ymax)`. Drags ≤ 5 px fall through to click handling.
- **'a' key reset**: press `a` (canvas must have focus → click plot first) emits `reset_view()`, restoring hardcoded default range from `PLOT_DEFAULTS` in `main_window.py`.
- **State sync**: `MainWindow._on_plot_zoom_applied` updates `_plot_settings[key]`, applies limits, syncs spinboxes. State persists across tab switches and is saved in workflow JSON.

**Click handling**: `InteractiveHugoniotPlot._handle_click_release(event)` — left-click selects, right-click shows context menu. Selection fires on **release** (not press) so the 5 px drag-vs-click threshold works.

### Scatter Points System

Embedded in `main_window.py` (no separate panel file):
- "From Intersection" combo + Add button — creates scatter point from currently selected intersection
- "Manual" entry with X/Y `QDoubleSpinBox` + Add button
- `QListWidget` listing all scatter points with Delete Selected / Clear All buttons

Scatter points use a **dual-artist trick**: invisible large-pick-radius marker for hit detection + visible styled marker. Stored in `_scatter_points` dict. Right-click → Edit Style supports marker shape, size, edge color, edge width.

### Auto-Refresh

- Rayleigh panel changes emit signals → `MainWindow` auto-refreshes all intersections
- `intersection_panel.py` has an **Auto-update checkbox** — when checked, intersection computation runs automatically whenever curves change
- Legend properly shows/hides on tab switch

### Plot Settings

Per-plot settings in `MainWindow._plot_settings` dict keyed by short name (`P-Up`, `P-CR`, etc.). Each entry holds `xlim`, `ylim`, `show_legend`, `inverse` flag. `P-Up` additionally holds `linestyle` and `linewidth`. Module-level `PLOT_DEFAULTS` dict holds hardcoded initial ranges for 'a' key reset.

Plot-settings control panel at bottom of left pane syncs with active tab via combo box.

### Plot Style

All plots use PRL style (Physical Review Letters). Configured in `core/plot_style.py`:

**Module constants** (exposed for consistency):
- `LEGEND_FONTSIZE = 14`
- `BASE_FONTSIZE = 18`
- `TICK_LABELSIZE = 16`
- `AXES_LABELSIZE = 20`
- `AXES_TITLESIZE = 20`

Lines: serif fonts, inward ticks, colorblind-friendly palette (`PRL_COLORS`), axes linewidth 1.2, tick width 1.2, line linewidth 1.5, marker size 6. Export via `save_prl_figure()` at 300 DPI.

### Conventions

- **Units**: density (g/cm³), velocity (km/s), pressure (Mbar; 1 Mbar = 100 GPa), temperature (eV), energy (MJ/g).
- **Column names**: full names with units in parentheses, e.g. `Up(km/s)`, `P(Mbar)`.
- **Material IDs**: `{Name}_{Source}` format. Reference curves use `ref_` prefix when added to plots.
- **Chinese comments**: code comments and dialog strings are predominantly Chinese; module docstrings are bilingual.
- Run the standalone smoke tests under `tests/` from the repository root, for example `python tests/smoke_test_visibility.py` or `python tests/smoke_test_practice_workspace.py`.

## Packaging

```bash
python -m build                           # Python wheel and source distribution in dist/
python packaging/build_desktop.py linux   # Debian and RPM packages in dist/desktop/
python packaging/build_desktop.py macos   # Native disk image on Apple silicon or Intel macOS
python packaging/build_desktop.py windows # Windows installer on an x64 Windows host
```

See [desktop installation and build requirements](packaging/README.md).
