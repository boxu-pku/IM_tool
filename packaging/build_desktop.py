"""Build native desktop installers from the checkout. Build tools use Python 3.11+."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from im_app.core.library_files import copy_material_subset

PKG = ROOT / "im_app"
ASSETS = PKG / "resources"
OUT = ROOT / "dist" / "desktop"
BUILD = ROOT / "build" / "desktop"
APP_ID = "io.github.boxu_pku.IMTool"
LINUX_DIR = "/usr/share/im-tool"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

# Ship reference tables for common calibration materials with the desktop edition.
STARTER_IDS = (
    "Al_3717_sesame", "Al_3720_sesame", "Al_Celliers2005", "Al_FEOS",
    "Quartz_7360_sesame", "Quartz_7385_sesame", "Quartz_Hamel2012", "Quartz_FEOS",
    "BN_LEA", "C_diam_rho3.157",
    "copper_p57_lasl", "aluminum_6061_p182_lasl", "lithium_fluoride_single_crystal_loo_p296_lasl",
)


def build_library(destination):
    copy_material_subset(PKG / "standard_library", destination, STARTER_IDS)


def desktop_files():
    for name in ("im-tool.png", "manuals/im-tool-en.pdf", "manuals/im-tool-zh.pdf",
                 "practice/Hicks-29400.json"):
        file = ASSETS / name
        if not file.is_file():
            raise FileNotFoundError(file)
        yield file, Path("resources") / name


def freeze_windows():
    win = BUILD / "windows"
    win.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
        "--name", "IMTool", "--icon", str(ASSETS / "im-tool.ico"), "--paths", str(ROOT),
        "--hidden-import", "xlrd", "--hidden-import", "openpyxl",
        "--hidden-import", "matplotlib.backends.backend_qt5agg",
        "--exclude-module", "PySide6", "--exclude-module", "PyQt6", "--exclude-module", "tkinter",
        "--exclude-module", "torch", "--exclude-module", "IPython",
        "--workpath", str(win / "freeze"), "--distpath", str(win / "bundle"),
        "--specpath", str(win), str(ROOT / "run_app.py"),
    ], cwd=ROOT, check=True)


def windows_installer():
    bundle = BUILD / "windows" / "bundle" / "IMTool"
    package = bundle / "_internal" / "im_app"
    for file, relative in desktop_files():
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
    build_library(package / "desktop_library")
    guesses = [shutil.which("ISCC"), os.environ.get("ISCC")]
    for variable in ("LOCALAPPDATA", "ProgramFiles(x86)", "ProgramFiles"):
        if os.environ.get(variable):
            parent = Path(os.environ[variable])
            if variable == "LOCALAPPDATA":
                parent /= "Programs"
            guesses.append(parent / "Inno Setup 6" / "ISCC.exe")
    compiler = next((str(p) for p in guesses if p and Path(p).is_file()), None)
    if not compiler:
        raise FileNotFoundError("Install Inno Setup 6 or set ISCC to the compiler path.")
    art = BUILD / "windows" / "wizard"
    art.mkdir(parents=True, exist_ok=True)
    with Image.open(ASSETS / "im-tool.png") as source:
        for name, canvas, side, top, background in (
            ("welcome", (328, 628), 254, 129, "#e5f0ec"),
            ("header", (110, 110), 94, 8, "#ffffff"),
        ):
            panel = Image.new("RGB", canvas, background)
            symbol = source.convert("RGBA").resize((side, side), Image.Resampling.LANCZOS)
            panel.paste(symbol, ((canvas[0] - side) // 2, top), symbol)
            panel.save(art / f"{name}.bmp")
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([compiler, f"/DAppVersion={VERSION}", f"/DBundle={bundle}",
                    f"/DWizardArt={art}", f"/DOutput={OUT}",
                    str(ROOT / "packaging/windows/installer.iss")], check=True)


def linux_installers(staging):
    contents = []
    def add(file, destination, mode=0o644):
        contents.append({"src": str(file), "dst": destination, "file_info": {"mode": mode}})

    gui_sources = [PKG / name for name in ("__init__.py", "main.py", "desktop.py")]
    for module in ("core", "gui", "tools"):
        gui_sources.extend(sorted((PKG / module).glob("*.py")))
    for file in gui_sources:
        add(file, f"{LINUX_DIR}/{file.relative_to(ROOT).as_posix()}")
    for file, relative in desktop_files():
        add(file, f"{LINUX_DIR}/im_app/{relative.as_posix()}")
    library = staging / "desktop_library"
    build_library(library)
    for file in sorted(library.rglob("*")):
        if file.is_file():
            add(file, f"{LINUX_DIR}/im_app/desktop_library/{file.relative_to(library).as_posix()}")
    add(ROOT / "run_app.py", f"{LINUX_DIR}/run_app.py")
    add(ROOT / "packaging/linux/im-tool", "/usr/bin/im-tool", 0o755)
    add(ROOT / f"packaging/linux/{APP_ID}.desktop", f"/usr/share/applications/{APP_ID}.desktop")
    add(ROOT / f"packaging/linux/{APP_ID}.metainfo.xml", f"/usr/share/metainfo/{APP_ID}.metainfo.xml")
    with Image.open(ASSETS / "im-tool.png") as icon:
        for size in (16, 24, 32, 48, 64, 128, 256, 512):
            image = staging / f"icon-{size}.png"
            icon.resize((size, size), Image.Resampling.LANCZOS).save(image)
            add(image, f"/usr/share/icons/hicolor/{size}x{size}/apps/{APP_ID}.png")
    manifest = {
        "name": "im-tool", "arch": "all", "platform": "linux", "version": VERSION, "release": "1",
        "section": "science", "priority": "optional", "maintainer": "Bo Xu <boxu25@stu.pku.edu.cn>",
        "description": "Desktop impedance matching plots and material table analysis",
        "homepage": "https://github.com/boxu-pku/IM_tool", "license": "Academic use",
        "contents": contents,
        "overrides": {
            "deb": {"depends": ["python3", "python3-pyqt5", "python3-numpy", "python3-scipy",
                                "python3-pandas", "python3-matplotlib", "python3-openpyxl", "python3-xlrd"]},
            "rpm": {"depends": ["python3", "python3-qt5", "python3-numpy", "python3-scipy",
                                "python3-pandas", "python3-matplotlib-qt5", "python3-openpyxl", "python3-xlrd"]},
        },
    }
    config = staging / "nfpm.json"
    config.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    for kind in ("deb", "rpm"):
        subprocess.run(["nfpm", "package", "--config", str(config), "--packager", kind,
                        "--target", str(OUT) + "/"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=("linux", "windows"))
    args = parser.parse_args()
    if args.platform == "linux":
        with TemporaryDirectory(prefix="im-tool-") as temp:
            linux_installers(Path(temp))
    else:
        freeze_windows()
        windows_installer()
