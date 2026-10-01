#!/usr/bin/env python3
"""Vision-assisted recovery for LASL SHD materials whose OCR text layer is
too damaged for import_shd_database.py (see ref/shd_md/import_report.md).

Workflow:
  1. `list`   - print the worklist of materials that failed import, with
                pdf page, book page, average rho0 and rejected-row count.
  2. `render` - render given pdf pages to grayscale PNG (~300 dpi) under
                ref/shd_md/img/ for visual reading.
  3. `import` - take a JSON of visually transcribed rows and run them
                through the same Rankine-Hugoniot gates as the OCR importer
                before anything is written to the library.

JSON schema (default ref/shd_md/visual_rows.json):
{
  "materials": [
    {"name": "GOLD", "rho0": 19.24, "book_page": 81, "pdf_pages": [97],
     "rows": [[rho0, us, up, p_gpa, V(cm3/g), rho, V/V0], ...],
     "drop_rows": []}
  ]
}
Row values may be partial: null fields are derived from the Rankine-Hugoniot
relations first; a row is accepted only when EVERY available relation closes
(2% tolerance, at least 2 relations). One bad row rejects the whole material
so nothing half-read ever reaches the database.
"""

import argparse
import io
import json
import sys
from pathlib import Path

import fitz

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from import_shd_database import (  # noqa: E402
    PDF_PATH, LASL_DIR, analyze, resolve_name, parse_toc, slugify,
    rh_checks, rows_to_df,
)
from im_app.core.data_converter import (  # noqa: E402
    write_standard_txt, validate_standard_format)

IMG_DIR = PROJECT_ROOT / "ref" / "shd_md" / "img"
META_PATH = (PROJECT_ROOT / "im_app" / "standard_library" /
             "metadata.json")


def fill_row(vals, header_rho0):
    """Complete a partially transcribed row via the R-H relations."""
    rho0, us, up, p, v, rho, vv0 = (None if x is None else float(x)
                                    for x in vals)
    if rho0 is None:
        rho0 = header_rho0
    if vv0 is None and up is not None and us:
        vv0 = 1.0 - up / us
    if rho is None and rho0 and vv0:
        rho = rho0 / vv0
    if v is None and rho:
        v = 1.0 / rho
    if p is None and None not in (rho0, up, us):
        p = rho0 * up * us
    return rho0, us, up, p, v, rho, vv0


def cmd_list(_args):
    doc = fitz.open(PDF_PATH)
    toc = parse_toc(doc)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    have = {m["id"] for m in meta["materials"]}
    print(f"{'pdf':>4} {'book':>4} {'rho0':>7} {'rows':>4} {'rej':>4}  name")
    for sec, rows, failed in analyze(doc):
        if not rows and not failed:
            continue
        name, bp = resolve_name(sec, toc)
        sid = slugify(name) + (f"_p{bp}" if bp else "") + "_lasl"
        if sid in have:
            continue
        tag = " REFLECTED" if sec["reflected"] else ""
        print(f"{sec['pages'][0] + 1:>4} {str(bp):>4} "
              f"{(sec['rho0'] or 0):>7.3f} {len(rows):>4} {failed:>4}  "
              f"{name[:58]}{tag}")


def cmd_render(args):
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    pages = [int(v) for v in str(args.pages).split(",") if v.strip()]
    clip = None
    suffix = ""
    if args.clip:
        clip = fitz.Rect(*[float(v) for v in args.clip.split(",")])
        suffix = f"_{int(clip.y0)}-{int(clip.y1)}"
    for pno in pages:
        page = doc[pno - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(args.zoom, args.zoom),
                              colorspace=fitz.csGRAY, clip=clip)
        out = IMG_DIR / f"p{pno:03d}{suffix}.png"
        pix.save(str(out))
        print(f"{out.name} {pix.width}x{pix.height}")


def cmd_import(args):
    spec = json.loads(Path(args.json).read_text(encoding="utf-8"))
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    have = {m["id"] for m in meta["materials"]}
    imported, failures = [], []
    for entry in spec["materials"]:
        name, rho0, bp = entry["name"], entry.get("rho0"), \
            entry.get("book_page")
        sid = slugify(name) + (f"_p{bp}" if bp else "") + "_lasl"
        if sid in have:
            print(f"SKIP {sid}: already present")
            continue
        good, bad = [], []
        drops = set(entry.get("drop_rows", []))
        for i, vals in enumerate(entry["rows"]):
            if i in drops:
                continue
            filled = fill_row(vals, rho0)
            rho0r, us, up, p, v, rho, vv0 = filled
            np_, nt = rh_checks(rho0r, up, us, p, vv0, rho, v)
            if np_ == nt and np_ >= 2:
                rho0r, us, up, p, v, rho, vv0 = filled
                good.append(dict(rho0=rho0r, up=up, us=us, p=p, v=v,
                                 rho=rho, vv0=vv0))
            else:
                bad.append((i, vals, f"{np_}/{nt} checks pass"))
        if bad:
            failures.append(name)
            print(f"FAIL {name}: {len(bad)} row(s) violate the R-H gates, "
                  f"nothing written")
            for i, vals, why in bad:
                print(f"   row {i}: {vals}  [{why}]")
            continue
        df = rows_to_df(good, rho0)
        if len(df) < 2 or not (df["Up(km/s)"] > 0.05).any():
            failures.append(name)
            print(f"FAIL {name}: usable rows below minimum")
            continue
        pdfs = ", ".join(str(p) for p in entry.get("pdf_pages", []))
        info = {
            "material": name,
            "reference": "LASL Shock Hugoniot Data (Marsh, 1980)",
            "rho0": rho0,
            "data_source": f"ref/shd.pdf book p.{bp} (pdf p.{pdfs})",
            "notes": "Transcribed visually from the page image (OCR text "
                     "layer unusable); every row Rankine-Hugoniot validated",
        }
        out_path = LASL_DIR / f"{sid}.txt"
        write_standard_txt(str(out_path), df, info)
        val = validate_standard_format(str(out_path))
        if not val["valid"]:
            out_path.unlink(missing_ok=True)
            failures.append(name)
            print(f"FAIL {name}: format validation {val['errors'][:1]}")
            continue
        stats = val.get("stats", {})
        e = {"id": sid, "name": name, "source": "LASL SHD 1980",
             "rho0": rho0, "file": f"materials/lasl_shd/{sid}.txt",
             "tags": ["lasl-shd", "experimental", "visual"],
             "points": stats.get("rows", len(df))}
        if "up_range" in stats:
            e["up_range"] = list(stats["up_range"])
            e["p_range"] = list(stats["p_range"])
            e["compression_range"] = list(stats["compression_range"])
        meta["materials"].append(e)
        have.add(sid)
        imported.append((sid, len(df)))
        print(f"OK   {sid}: {len(df)} points")
    if imported:
        META_PATH.write_text(json.dumps(meta, indent=4,
                                        ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(f"\nimported {len(imported)}, failed {len(failures)}")


def main():
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace", write_through=True)
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("render")
    r.add_argument("--pages", required=True,
                   help="comma-separated 1-based pdf page numbers")
    r.add_argument("--zoom", type=float, default=4.5)
    r.add_argument("--clip", default=None,
                   help="optional x0,y0,x1,y1 in pdf points")
    i = sub.add_parser("import")
    i.add_argument("--json", default="ref/shd_md/visual_rows.json")
    args = ap.parse_args()
    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "render":
        cmd_render(args)
    elif args.cmd == "import":
        cmd_import(args)


if __name__ == "__main__":
    main()
