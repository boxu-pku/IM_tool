#!/usr/bin/env python3
"""Import material Hugoniot tables from the LASL Shock Hugoniot Data book
(ref/shd.pdf, Marsh ed. 1980) into im_app/standard_library.

Why this is not a plain table scraper: the embedded OCR layer of the 1999
scan is noisy (garbled digits, column-major vs row-major output order,
graph-axis numbers interleaved with table numbers). Every candidate data row
is therefore validated against the Rankine-Hugoniot relations before it is
accepted:

    P[GPa] = rho0 * up * Us          (rho0 in g/cm^3, velocities in km/s)
    V/V0   = 1 - up/Us
    rho    = rho0 / (V/V0)           V[cm^3/g] = 1/rho

A row is kept only if at least two independent checks agree within tolerance
and none is violated. Rows whose raw OCR digits fail are retried with bounded
single-character repairs (digit swaps, misplaced decimal point); a repair is
accepted only when it makes all available checks pass. Anything that still
fails is dropped and reported, never silently imported.

Table geometry is rebuilt from word coordinates (cluster rows by y, order
columns by x), so the erratic token order of the OCR layer does not matter.

Usage:
    python scripts/import_shd_database.py --scan [--pages 115-130]
    python scripts/import_shd_database.py --import
"""

import argparse
import io
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import fitz  # PyMuPDF

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(PROJECT_ROOT, "ref", "shd.pdf")
LIB_DIR = Path(os.path.join(PROJECT_ROOT, "im_app", "standard_library"))
LASL_DIR = LIB_DIR / "materials" / "lasl_shd"
REPORT_PATH = Path(os.path.join(PROJECT_ROOT, "ref", "shd_md",
                                "import_report.md"))

sys.path.insert(0, PROJECT_ROOT)
from im_app.core.data_converter import (  # noqa: E402
    write_standard_txt, validate_standard_format)

TOL = 0.02          # 2% relative tolerance for R-H checks

RHO0_RE = re.compile(
    r"Average\s+P?\s*[,.:;o0qO]{0,4}\s*=?\s*(\d{1,3}\.\d+)\s*g\s*.{0,2}cm",
    re.IGNORECASE)
CONTINUED_RE = re.compile(r"\(\s*Continued\s*\)", re.IGNORECASE)
REFLECTED_RE = re.compile(r"Reflected", re.IGNORECASE)
FLAG_WORDS = {"iml", "iwl", "iql", "ssp", "ssb", "xl", "x", "xx", "exp",
              "exd", "exp.", "ekp"}
GARBAGE_RE = re.compile(r"^[;:,|\-l1iIoO'\"]{1,6}$")


# ----------------------------------------------------------------------------
# token level helpers
# ----------------------------------------------------------------------------

def clean_token(tok: str):
    """Normalize an OCR token. Returns ('num', value) / ('flag', s) /
    ('text', s) / ('debris', s)."""
    # strip quotes/semicolons anywhere at the ends, and a TRAILING , or .
    # (reference lists like "11,"), but never a leading decimal point
    t = tok.strip().strip("\"';:`").rstrip(".,")
    if not t or GARBAGE_RE.match(t):
        return ("debris", t)
    low = t.lower()
    if low in FLAG_WORDS and not re.search(r"\d", t):
        return ("flag", t)
    # bare 0/1 (no decimal point) are the Exp/impurity flag columns; real
    # data values in this book are always printed with decimals
    if t in ("0", "1"):
        return ("flag", t)
    core = t.replace("Q", "0").replace("q", "0")
    if re.fullmatch(r"[0-9oOolIi.,\-+]+", core):
        core = (core.replace("o", "0").replace("O", "0")
                    .replace("l", "1").replace("I", "1").replace("i", "1"))
        if core and core[0] in ",.":
            core = "0." + core[1:]
        if core in ("-", "+", ".", ""):
            return ("debris", t)
        core = core.replace(",", ".")
        core = re.sub(r"(?<=\d)-(?=\d)", ".", core)
        try:
            return ("num", float(core))
        except ValueError:
            return ("text", t)
    return ("text", t)


def number_variants(tok: str):
    """Bounded repair variants of a raw OCR token (digit swaps and decimal
    point shifts). Only used for rows that failed R-H validation outright."""
    t = tok.strip().strip("\"';:`").rstrip(".,").replace(",", ".")
    t = (t.replace("Q", "0").replace("o", "0").replace("O", "0")
          .replace("l", "1").replace("I", "1"))
    if not re.fullmatch(r"[0-9.\-]+", t):
        return []
    variants = set()
    subs = {"6": "8", "8": "6", "5": "3", "3": "5", "1": "7", "7": "1",
            "9": "0", "0": "9", "4": "1"}
    for i, ch in enumerate(t):
        if ch in subs:
            variants.add(t[:i] + subs[ch] + t[i + 1:])
    if "." not in t and t.isdigit() and len(t) <= 4:
        for pos in range(1, len(t)):
            variants.add(t[:pos] + "." + t[pos:])
        variants.add("0." + t)
    out = []
    for v in variants:
        try:
            f = float(v)
            if 0 < abs(f) < 1e5:
                out.append(f)
        except ValueError:
            continue
    return out


# ----------------------------------------------------------------------------
# page geometry: rebuild visual rows from word boxes
# ----------------------------------------------------------------------------

def visual_rows(page):
    """Group numeric/flag words into visual rows by y, columns ordered by x.
    Returns list of (y, [(x, kind, value_or_text, raw_tok), ...])."""
    words = page.get_text("words")
    items = []
    for w in words:
        x0, y0, x1, y1, tok = w[0], w[1], w[2], w[3], w[4]
        kind, val = clean_token(tok)
        if kind == "debris":
            continue
        items.append(((y0 + y1) / 2.0, x0, kind, val, tok))
    if not items:
        return []
    items.sort(key=lambda it: it[0])
    rows = []
    cur = [items[0]]
    for it in items[1:]:
        if it[0] - cur[-1][0] <= 4.5:
            cur.append(it)
        else:
            rows.append(cur)
            cur = [it]
    rows.append(cur)
    out = []
    for r in rows:
        r.sort(key=lambda it: it[1])
        out.append((float(np.mean([it[0] for it in r])),
                    [(it[1], it[2], it[3], it[4]) for it in r]))
    return out


# ----------------------------------------------------------------------------
# Rankine-Hugoniot validation
# ----------------------------------------------------------------------------

def rel(a, b):
    m = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / m


def rh_checks(rho0, up, us, p, vv0, rho, v):
    """(n_pass, n_total) over whatever values are available; a row is only
    acceptable when n_pass >= 2 and n_pass == n_total."""
    checks = []
    if up is not None and us is not None:
        checks.append(up < us * 1.0001)
        if vv0 is not None and abs(us) > 1e-9:
            checks.append(rel(1.0 - up / us, vv0) < TOL or
                          abs(1.0 - up / us - vv0) < 0.003)
    if None not in (rho0, up, us, p):
        checks.append(rel(rho0 * up * us, p) < TOL or
                      abs(rho0 * up * us - p) < 0.05)
    if None not in (rho0, vv0, rho) and vv0 > 1e-6:
        checks.append(rel(rho0 / vv0, rho) < TOL)
    if None not in (rho, v) and abs(rho) > 1e-9:
        checks.append(rel(1.0 / rho, v) < TOL)
    n_pass = sum(1 for ok in checks if ok)
    return n_pass, len(checks)


def consider(cands, rho0, up, us, p, v, rho, vv0, need=2):
    if up is None or us is None:
        return
    np_, nt = rh_checks(rho0, up, us, p, vv0, rho, v)
    if np_ == nt and np_ >= need:
        cands.append((np_, dict(rho0=rho0, up=up, us=us, p=p, v=v, rho=rho,
                                vv0=vv0)))


def try_row_assignment(pairs, header_rho0):
    """Try to interpret one visual row ((value, raw) pairs) as an SHD data
    row under the layouts used by the book. Returns best dict or None."""
    nums = [v for v, _r in pairs]
    n = len(nums)
    cands = []

    if n >= 7:  # rho0 Us up P V rho V/V0
        a, b, c, d, e, f, g = nums[:7]
        consider(cands, a, c, b, d, e, f, g)
        consider(cands, header_rho0, c, b, d, e, f, g)
    if n == 6:
        a, b, c, d, e, f = nums
        if e > 1e-6:
            consider(cands, a, c, b, d, e, f, None)      # rho0 Us up P V rho
            consider(cands, a, c, b, d, e, 1.0 / e, f)   # rho0 Us up P V V/V0
        if header_rho0:
            # a=Us b=up c=P d=V e=rho f=V/V0 (rho0 only in the page header)
            consider(cands, header_rho0, b, a, c, d, e, f)
            consider(cands, a, c, b, d, None, e, f)      # rho0 Us up P rho V/V0
    if n == 5:
        a, b, c, d, e = nums
        consider(cands, a, c, b, d, None, None, e)       # rho0 Us up P V/V0
        if header_rho0:
            consider(cands, header_rho0, c, b, d, None, None, e)
            # a=Us b=up c=P d=V e=rho|V/V0
            consider(cands, header_rho0, b, a, c, d, e, None)
            consider(cands, header_rho0, b, a, c, d, None, e)
    if n == 4:
        a, b, c, d = nums
        consider(cands, a, c, b, d, None, None, None)    # rho0 Us up P
        if header_rho0 and d > 1e-6:
            # Us up P V with V the specific volume (cm^3/g)
            consider(cands, header_rho0, c, b, d, d, 1.0 / d,
                     d * header_rho0)
    if n == 3:
        a, b, c = nums
        consider(cands, a, c, b, None, None, None, None)  # rho0 Us up
        if header_rho0:
            consider(cands, header_rho0, c, b, None, None, None, None)

    if not cands:
        return None
    cands.sort(key=lambda t: -t[0])
    return cands[0][1]


def repair_row(pairs, header_rho0):
    """Retry a failed row with bounded per-token variants; accept only when
    ALL checks pass with >= 3 agreements (stricter than raw rows)."""
    n = len(pairs)
    if not 3 <= n <= 7:
        return None
    for i in range(n):
        for val in number_variants(pairs[i][1]):
            cand = list(pairs)
            cand[i] = (val, pairs[i][1])
            res = try_row_assignment(cand, header_rho0)
            if res:
                np_, nt = rh_checks(res["rho0"], res["up"], res["us"],
                                    res["p"], res["vv0"], res["rho"],
                                    res["v"])
                if np_ == nt and np_ >= 3:
                    res["repaired"] = True
                    return res
    return None


# ----------------------------------------------------------------------------
# page parsing
# ----------------------------------------------------------------------------

def parse_page(page, header_rho0):
    """Return (rows, n_failed)."""
    rows, failed = [], 0
    for _y, cells in visual_rows(page):
        pairs = [(v, raw) for (_x, kind, v, raw) in cells if kind == "num"]
        if not 3 <= len(pairs) <= 9:
            continue
        res = try_row_assignment(pairs, header_rho0)
        if res:
            rows.append(res)
            continue
        res2 = repair_row(pairs, header_rho0)
        if res2:
            rows.append(res2)
        else:
            failed += 1
    return rows, failed


def page_header(page):
    """Extract (title, rho0, book_page, is_continued, reflected)."""
    text = page.get_text("text")
    rho0 = None
    m = RHO0_RE.search(text[:600])
    if m:
        rho0 = float(m.group(1))
    book_page = None
    words = text.split()
    for tok in reversed(words[-8:] if len(words) >= 8 else words):
        if re.fullmatch(r"\d{1,3}", tok):
            v = int(tok)
            if 1 <= v <= 700:
                book_page = v
                break
    title_lines = []
    for ln in [l.strip() for l in text.splitlines() if l.strip()][:14]:
        if RHO0_RE.search(ln) or ln.lower().startswith(("average", "sound",
                                                         "references")):
            break
        letters = [c for c in ln if c.isalpha()]
        if len(letters) >= 2:
            up = sum(1 for c in letters if c.isupper()) / len(letters)
            if up > 0.55:
                wc = [w for w in ln.split() if re.search(r"[A-Za-z]{2,}", w)]
                if wc:
                    title_lines.append(" ".join(wc))
    title = ", ".join(title_lines)[:100]
    return (title, rho0, book_page,
            bool(CONTINUED_RE.search(text)), bool(REFLECTED_RE.search(text)))


# ----------------------------------------------------------------------------
# section segmentation
# ----------------------------------------------------------------------------

def _title_key(title):
    return re.sub(r"[^A-Z0-9]", "", (title or "").upper())


def _substantial_title(title):
    """Titles like 'ALUMINUM, 2024' are trustworthy section boundaries;
    OCR debris like 'SE' or 'CD' is not."""
    return max((len(run) for run in re.findall(r"[A-Za-z]+", title)),
               default=0) >= 4


def build_sections(doc):
    """A section starts on a page with an 'Average rho0' header or with a
    substantial title different from the current section's; other pages
    are continuations."""
    import difflib
    sections, current = [], None
    for pno in range(doc.page_count):
        title, rho0, book_page, cont, refl = page_header(doc[pno])
        starts_new = False
        if title and (rho0 is not None or _substantial_title(title)):
            if current is None:
                starts_new = True
            else:
                same = (difflib.SequenceMatcher(
                            None, _title_key(current["title"]),
                            _title_key(title)).ratio() >= 0.75
                        and (rho0 is None or current["rho0"] is None
                             or abs(current["rho0"] - rho0) < 1e-9))
                starts_new = not same
        if starts_new:
            current = dict(title=title, rho0=rho0, pages=[pno],
                           book_pages={}, reflected=refl)
            sections.append(current)
        elif current is not None:
            current["pages"].append(pno)
        if current is not None and book_page is not None:
            current["book_pages"][pno] = book_page
    return sections


def section_name_cleanup(title):
    t = title.replace(" ,", ",")
    t = re.sub(r"\s{2,}", " ", t)
    keep = [w for w in t.split() if re.search(r"[A-Za-z]{2,}", w)]
    return " ".join(keep)


def slugify(name):
    s = name.lower()
    s = re.sub(r"[^a-z0-9.]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:60]


# ----------------------------------------------------------------------------
# table of contents: clean material names keyed by book page
# ----------------------------------------------------------------------------

def parse_toc(doc, first_page=5, last_page=20):
    """Parse the CONTENTS pages into {book_page: clean material name}.
    Visual TOC lines reduce to '<name tokens> <page number>' (the page
    number often carries a leftover leader dot, e.g. '.228'); entries
    wrapped over two lines are accumulated."""
    toc = {}
    for pno in range(first_page - 1, last_page):
        page = doc[pno]
        head = page.get_text("text")[:200].upper()
        if "CONTENTS" not in head:
            continue
        pending = []
        for _y, cells in visual_rows(page):
            toks = [raw for (_x, kind, val, raw) in cells
                    if kind in ("text", "num", "flag")]
            if not toks:
                continue
            joined = " ".join(toks)
            m = re.search(r"[\s.,]\s*(\d{1,3})\s*$", joined)
            if m:
                page_no = int(m.group(1))
                name = joined[:m.start()].strip()
                name = re.sub(r"\s*[.,]+\s*$", "", name)
                full = re.sub(r"\s{2,}", " ", " ".join(pending + [name]))
                pending = []
                if full and 13 <= page_no <= 830 and page_no not in toc:
                    toc[page_no] = full
            else:
                frag = re.sub(r"\s*[.,]+$", "", joined.strip())
                if frag and len(frag) > 3 and frag.upper() != "CONTENTS":
                    pending.append(frag)
    return toc


def resolve_name(sec, toc):
    """Prefer the TOC name keyed by the section's detected book pages, but
    only when it plausibly matches the section's own OCR title (a misread
    printed page number would otherwise hijack unrelated names)."""
    import difflib
    raw = section_name_cleanup(sec["title"])
    raw_weak = not any(len(w) >= 3 for w in re.findall(r"[A-Za-z]+", raw))
    for bp in sorted(sec.get("book_pages", {}).values()):
        cand = toc.get(bp)
        if not cand:
            continue
        ratio = difflib.SequenceMatcher(
            None, raw.lower(), cand.lower()).ratio()
        if ratio >= 0.45 or raw_weak:
            return cand, bp
        # token-prefix agreement also counts (handles 'MOLY BDEKUM')
        rt = {w.lower() for w in raw.split() if len(w) >= 3}
        ct = {w.lower() for w in cand.split() if len(w) >= 3}
        for a in rt:
            for b in ct:
                if a.startswith(b) or b.startswith(a):
                    return cand, bp
    return raw, None

def analyze(doc, page_range=None):
    results = []
    for sec in build_sections(doc):
        if page_range and not any(page_range[0] <= p + 1 <= page_range[1]
                                  for p in sec["pages"]):
            continue
        all_rows, failed = [], 0
        for pno in sec["pages"]:
            rows, f = parse_page(doc[pno], sec["rho0"])
            all_rows.extend(rows)
            failed += f
        # residual over-merge guard: rows carrying their own initial density
        # far from the section's average belong to a different material
        rho0 = sec["rho0"]
        if rho0 is None and all_rows:
            r0s = [r.get("rho0") for r in all_rows if r.get("rho0")]
            if r0s:
                rho0 = float(np.median(r0s))
        kept, foreign = [], 0
        for r in all_rows:
            r0 = r.get("rho0")
            if rho0 and r0 and abs(r0 - rho0) / rho0 > 0.15:
                foreign += 1
                continue
            kept.append(r)
        results.append((sec, kept, failed + foreign))
    return results


def rows_to_df(rows, rho0_avg):
    data = defaultdict(list)
    for r in rows:
        up, us = r["up"], r["us"]
        rho0 = r.get("rho0") or rho0_avg
        vv0 = r.get("vv0") if r.get("vv0") else 1.0 - up / us
        rho = r.get("rho") or rho0 / vv0
        p = r.get("p")
        if p is None:
            p = rho0 * up * us
        data["Up(km/s)"].append(up)
        data["Us(km/s)"].append(us)
        data["P(Mbar)"].append(p / 100.0)
        data["rho(g/cm3)"].append(rho)
        data["compression"].append(1.0 / vv0)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data).sort_values("Up(km/s)").reset_index(drop=True)
    df = df.drop_duplicates(subset=["Up(km/s)", "Us(km/s)"])
    return df.reset_index(drop=True)


def run_scan(doc, args, page_range):
    toc = parse_toc(doc)
    print(f"TOC entries: {len(toc)}")
    results = analyze(doc, page_range)
    print(f"{'material':<44} {'rho0':>6} {'pg':>4} {'rows':>5} {'fail':>5}")
    n_ok = n_bad = 0
    for sec, rows, failed in results:
        name, _bp = resolve_name(sec, toc)
        rho0 = sec["rho0"]
        if rows and not rho0:
            r0s = [r["rho0"] for r in rows if r.get("rho0")]
            rho0 = float(np.median(r0s)) if r0s else 0.0
        uniq = len({(round(r["up"], 4), round(r["us"], 4)) for r in rows})
        ok = uniq >= args.min_rows and any(r["up"] > 0.05 for r in rows)
        n_ok += ok
        n_bad += (not ok)
        mark = "" if ok else "  <-- LOW"
        print(f"{name[:44]:<44} "
              f"{rho0:>6.3f} {sec['pages'][0] + 1:>4} "
              f"{uniq:>5} {failed:>5}{mark}")
    print(f"\nsections ok: {n_ok}, low-yield: {n_bad}")


def run_import(doc, args, page_range):
    toc = parse_toc(doc)
    results = analyze(doc, page_range)
    LASL_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = LIB_DIR / "metadata.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    existing_ids = {m["id"] for m in metadata["materials"]}

    report = ["# LASL SHD import report", "",
              f"Generated: {datetime.now().isoformat(timespec='seconds')}",
              "Source: ref/shd.pdf. Every imported row passed "
              "Rankine-Hugoniot validation (P=rho0*up*Us, V/V0=1-up/Us); "
              "rejected rows are counted per material below.", ""]
    imported, skipped = [], []

    for sec, rows, failed in results:
        name, toc_bp = resolve_name(sec, toc)
        rho0 = sec["rho0"]
        if rho0 is None and rows:
            r0s = [r.get("rho0") for r in rows if r.get("rho0")]
            if r0s:
                rho0 = float(np.median(r0s))
        if sec["reflected"]:
            skipped.append((name, len(rows), failed, "reflected-shock data"))
            continue
        if not any(r["up"] > 0.05 for r in rows):
            skipped.append((name, len(rows), failed, "no real shock points"))
            continue
        if len(rows) < args.min_rows or rho0 is None:
            skipped.append((name, len(rows), failed,
                            "rows<min" if len(rows) < args.min_rows
                            else "no rho0"))
            continue
        df = rows_to_df(rows, rho0)
        if len(df) < args.min_rows:
            skipped.append((name, len(df), failed, "deduped below min"))
            continue

        bp = toc_bp or (min(sec["book_pages"].values())
                        if sec["book_pages"] else None)
        sid = slugify(name) + (f"_p{bp}" if bp is not None else "") + "_lasl"
        if sid in existing_ids:
            skipped.append((name, len(df), failed, "duplicate id"))
            continue
        out_path = LASL_DIR / (sid + ".txt")
        info = {
            "material": name,
            "reference": "LASL Shock Hugoniot Data (Marsh, 1980)",
            "rho0": rho0,
            "data_source": f"ref/shd.pdf book p.{bp} "
                           f"(pdf p.{sec['pages'][0] + 1})",
            "notes": (f"Experimental Hugoniot from LASL compendium; OCR rows "
                      f"validated via Rankine-Hugoniot relations; "
                      f"{sum(1 for r in rows if r.get('repaired'))} row(s) "
                      f"digit-repaired, {failed} row(s) rejected"),
        }
        write_standard_txt(str(out_path), df, info)
        val = validate_standard_format(str(out_path))
        if not val["valid"]:
            skipped.append((name, len(df), failed,
                            f"validation: {val['errors'][:1]}"))
            out_path.unlink(missing_ok=True)
            continue
        stats = val.get("stats", {})
        entry = {
            "id": sid,
            "name": name,
            "source": "LASL SHD 1980",
            "rho0": rho0,
            "file": f"materials/lasl_shd/{sid}.txt",
            "tags": ["lasl-shd", "experimental"],
            "points": stats.get("rows", len(df)),
        }
        if "up_range" in stats:
            entry["up_range"] = list(stats["up_range"])
            entry["p_range"] = list(stats["p_range"])
            entry["compression_range"] = list(stats["compression_range"])
        metadata["materials"].append(entry)
        existing_ids.add(sid)
        imported.append((sid, len(df), failed, bp))

    if imported and not args.dry_run:
        meta_path.write_text(json.dumps(metadata, indent=4,
                                        ensure_ascii=False) + "\n",
                             encoding="utf-8", newline="\n")

    report.append(f"## Imported: {len(imported)}")
    report.append("| id | points | rejected rows | book p. |")
    report.append("|---|---|---|---|")
    for sid, n, f_, bp in imported:
        report.append(f"| {sid} | {n} | {f_} | {bp} |")
    report.append(f"\n## Skipped / flagged: {len(skipped)}")
    report.append("| material | parsed rows | rejected | reason |")
    report.append("|---|---|---|---|")
    for name, n, f_, why in skipped:
        report.append(f"| {name} | {n} | {f_} | {why} |")
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8",
                           newline="\n")

    print(f"imported: {len(imported)} materials -> {LASL_DIR}")
    print(f"skipped/flagged: {len(skipped)} (see {REPORT_PATH})")
    if args.dry_run:
        print("DRY RUN: metadata.json left untouched")


def main():
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--import", dest="do_import", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pages", type=str, default=None,
                    help="restrict to pdf pages, e.g. 115-130")
    ap.add_argument("--min-rows", type=int, default=2)
    args = ap.parse_args()
    page_range = None
    if args.pages:
        a, b = args.pages.split("-")
        page_range = (int(a), int(b))
    doc = fitz.open(PDF_PATH)
    if args.scan:
        run_scan(doc, args, page_range)
    if args.do_import:
        run_import(doc, args, page_range)
    if not args.scan and not args.do_import:
        ap.print_help()


if __name__ == "__main__":
    main()
