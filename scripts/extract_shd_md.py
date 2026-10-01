#!/usr/bin/env python3
"""Extract the LASL Shock Hugoniot Data book (ref/shd.pdf) page by page into
AI-friendly Markdown files under ref/shd_md/.

Each page becomes pNNN.md with YAML-ish front matter (material name, average
rho0, sound velocities, references, garble score) followed by the normalized
OCR text layer. An index.md maps materials to pages.

The text layer of this 1999 scan is noisy: this script keeps the text faithful
(light whitespace normalization only). Numeric repair happens later in the
import pipeline, where every row is checked against the Rankine-Hugoniot
relations instead of being trusted blindly.
"""

import io
import os
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(PROJECT_ROOT, "ref", "shd.pdf")
OUT_DIR = os.path.join(PROJECT_ROOT, "ref", "shd_md")

# all output files are written below this verified constant directory
_OUT_BASE = Path(OUT_DIR).resolve()


def out_file(filename: str) -> Path:
    """Resolve an output path and refuse anything that leaves OUT_DIR."""
    p = (_OUT_BASE / filename).resolve()
    if _OUT_BASE not in p.parents:
        raise ValueError(f"path escapes output dir: {filename!r}")
    return p


# "Average p,, = 6.670 g/cm3" and OCR variants of the mangled subscript 0
RHO0_RE = re.compile(
    r"Average\s+P?\s*[,.:;o0qO]{0,4}\s*=?\s*(\d{1,3}\.\d+)\s*g\s*/?\s*cm",
    re.IGNORECASE,
)
SOUND_RE = re.compile(r"Sound velocities?.{0,80}", re.IGNORECASE | re.DOTALL)
REFS_RE = re.compile(r"References?\s*[^\n]{0,60}", re.IGNORECASE)
CONTINUED_RE = re.compile(r"\(\s*Continued\s*\)", re.IGNORECASE)
# tokens that are pure OCR debris (used for the garble score)
GARBAGE_RE = re.compile(r"^[;:,.\|l1iI\-oO'\"]{1,6}$")
NUMBERISH_RE = re.compile(r"^[-+]?[\d.,]+$")


def normalize_text(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"\s{2,}", " ", line)
        lines.append(line)
    return "\n".join(lines)


def token_stats(text: str):
    tokens = text.split()
    if not tokens:
        return 0.0, 0, 0
    n_garbage = sum(1 for t in tokens if GARBAGE_RE.match(t))
    n_numbers = sum(1 for t in tokens if NUMBERISH_RE.match(t))
    return n_garbage / len(tokens), n_garbage, n_numbers


def find_book_page(text: str):
    """Printed page number usually survives as a standalone short token near
    the end of the page text."""
    words = text.split()
    tail = words[-8:] if len(words) >= 8 else words
    for tok in reversed(tail):
        if re.fullmatch(r"\d{1,3}", tok):
            n = int(tok)
            if 1 <= n <= 700:
                return n
    return None


def guess_material(lines):
    """Return (name, is_continuation). The material title is the run of
    mostly-uppercase lines that appear before the 'Average rho0' line."""
    rho_line_idx = None
    for i, line in enumerate(lines[:15]):
        if RHO0_RE.search(line) or "Average" in line:
            rho_line_idx = i
            break
    if rho_line_idx is None:
        rho_line_idx = 0
    name_parts = []
    for line in lines[:max(rho_line_idx, 1)]:
        letters = [c for c in line if c.isalpha()]
        if not letters:
            continue
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.6 and len(letters) >= 2:
            name_parts.append(line)
        elif name_parts:
            break
    # strip leading OCR debris lines (e.g. "2 m T \a E")
    cleaned = []
    for part in name_parts:
        words = [w for w in part.split() if re.search(r"[A-Za-z]{2,}", w)]
        if words:
            cleaned.append(" ".join(words))
    name = ", ".join(cleaned)[:120]
    full = "\n".join(lines)
    is_continuation = bool(CONTINUED_RE.search(full))
    return name, is_continuation


def main():
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace")

    doc = fitz.open(PDF_PATH)
    os.makedirs(OUT_DIR, exist_ok=True)

    index_rows = []
    for pno in range(doc.page_count):
        raw = doc[pno].get_text("text")
        text = normalize_text(raw)
        lines = text.splitlines()
        garble, n_garb, n_num = token_stats(text)
        book_page = find_book_page(text)
        name, is_cont = guess_material(lines)

        m = RHO0_RE.search(text)
        rho0 = m.group(1) if m else ""
        snd_m = SOUND_RE.search(text)
        snd = " ".join(snd_m.group(0).split()) if snd_m else ""
        refs_m = REFS_RE.search(text)
        refs = " ".join(refs_m.group(0).split()) if refs_m else ""

        has_table = n_num >= 8

        md = []
        md.append("---")
        md.append(f"pdf_page: {pno + 1}")
        if book_page is not None:
            md.append(f"book_page: {book_page}")
        if name:
            md.append(f"material: \"{name}\"")
        if is_cont:
            md.append("continued: true")
        if rho0:
            md.append(f"rho0_avg_g_cm3: {rho0}")
        if snd:
            md.append(f"sound: \"{snd[:100]}\"")
        if refs:
            md.append(f"references: \"{refs[:80]}\"")
        md.append(f"numeric_tokens: {n_num}")
        md.append(f"garble_score: {garble:.3f}")
        md.append(f"has_data_table: {str(has_table).lower()}")
        md.append("---")
        md.append("")
        md.append("```text")
        md.append(text if text else "(no text layer)")
        md.append("```")
        out_file(f"p{pno + 1:03d}.md").write_text(
            "\n".join(md) + "\n", encoding="utf-8", newline="\n")

        if name and (rho0 or is_cont or has_table):
            index_rows.append((name, rho0, pno + 1, book_page,
                               "cont" if is_cont else "", n_num,
                               round(garble, 2)))

    parts = [
        "# LASL Shock Hugoniot Data — page index\n\n",
        "Source: ref/shd.pdf (Marsh, ed., 1980). Material names are "
        "recovered from the OCR layer and may contain scan errors; "
        "verify against the page image before citing.\n\n",
        "| material | rho0 avg | pdf page | book page | cont | "
        "num tokens | garble |\n",
        "|---|---|---|---|---|---|---|\n",
    ]
    for row in index_rows:
        parts.append("| " + " | ".join(str(x) for x in row) + " |\n")
    out_file("index.md").write_text("".join(parts), encoding="utf-8",
                                    newline="\n")

    print(f"wrote {doc.page_count} pages to {OUT_DIR}")
    print(f"index rows: {len(index_rows)}")


if __name__ == "__main__":
    main()
