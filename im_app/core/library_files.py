"""Copy named entries and their original tables into a smaller material library."""
import json
from pathlib import Path
import shutil


def copy_material_subset(source, destination, material_ids):
    source = Path(source).resolve()
    catalog = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry for entry in catalog["materials"]}
    materials = [by_id[mid] for mid in material_ids]
    destination.mkdir(parents=True, exist_ok=True)
    for entry in materials:
        table = (source / entry["file"]).resolve()
        relative = table.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(table, target)
    (destination / "metadata.json").write_text(
        json.dumps({**catalog, "materials": materials}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
