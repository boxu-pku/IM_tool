"""Desktop resources and writable working libraries."""
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from PyQt5.QtCore import QStandardPaths
from im_app.core.library_files import copy_material_subset


PACKAGE = Path(__file__).resolve().parent
RESOURCES = PACKAGE / "resources"
ICON = RESOURCES / "im-tool.png"
PRACTICE_WORKFLOW = RESOURCES / "practice" / "Hicks-29400.json"


def user_directory():
    location = QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    if not location:
        raise OSError("Qt could not locate the user data directory.")
    return Path(location)


def prepare_workspace(directory, seed, material_ids=None):
    """Publish a complete first-run library without replacing a user's edits."""
    directory.mkdir(parents=True, exist_ok=True)
    library = directory / "standard_library"
    if not library.exists():
        with TemporaryDirectory(prefix=".im-tool-", dir=directory) as temp:
            staged = Path(temp) / "standard_library"
            if material_ids is None:
                shutil.copytree(seed, staged)
            else:
                copy_material_subset(seed, staged, material_ids)
            # Some system packages ship read-only data. The private copy is editable.
            for path in [staged, *staged.rglob("*")]:
                path.chmod(path.stat().st_mode | (0o700 if path.is_dir() else 0o600))
            try:
                staged.rename(library)
            except OSError:
                if not (library / "metadata.json").is_file():
                    raise
    workflows = directory / "workflows"
    workflows.mkdir(exist_ok=True)
    return os.fspath(library), os.fspath(workflows)


def application_paths():
    seed = PACKAGE / "desktop_library"
    if seed.is_dir():
        return prepare_workspace(user_directory(), seed)
    return os.fspath(PACKAGE / "standard_library"), os.fspath(PACKAGE / "workflows")


def practice_workspace():
    workflow = json.loads(PRACTICE_WORKFLOW.read_text(encoding="utf-8"))
    seed = PACKAGE / "desktop_library"
    if not seed.is_dir():
        seed = PACKAGE / "standard_library"
    ids = [material["id"] for material in workflow["materials"]]
    library, workflows = prepare_workspace(user_directory() / "Practice" / "Celliers-Hamel", seed, ids)
    return library, workflows, workflow
