"""Install a DMG into a temporary Applications folder and launch it via macOS Launch Services."""
import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def check_contents(app, image):
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert info["CFBundleIdentifier"] == "io.github.boxu_pku.IMTool"
    assert info["CFBundleVersion"] == info["CFBundleShortVersionString"] == version
    executable = app / "Contents/MacOS" / info["CFBundleExecutable"]
    arch = platform.machine()
    assert subprocess.check_output(["lipo", "-archs", str(executable)], text=True).strip() == arch
    assert image.name == f"IM-Tool-{version}-macOS-{arch}.dmg"
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)

    resources = app / "Contents/Resources"
    assert (resources / info["CFBundleIconFile"]).is_file()
    package = resources / "im_app"
    for name in ("im-tool.png", "manuals/im-tool-en.pdf", "manuals/im-tool-zh.pdf",
                 "practice/Hicks-29400.json"):
        assert (package / "resources" / name).read_bytes() == (ROOT / "im_app/resources" / name).read_bytes()
    seed = package / "desktop_library"
    catalog = json.loads((seed / "metadata.json").read_text(encoding="utf-8"))
    entries = {row["id"]: row for row in catalog["materials"]}
    assert len(entries) == 13 and {"Al_Celliers2005", "Quartz_Hamel2012"} <= entries.keys()
    for row in entries.values():
        assert (seed / row["file"]).read_bytes() == (ROOT / "im_app/standard_library" / row["file"]).read_bytes()
    return info["CFBundleIdentifier"], catalog


def check_launch(app, identifier, catalog, home):
    from AppKit import NSRunningApplication
    import Quartz

    home.mkdir()
    command = ["open", "-n", "--env", f"HOME={home}", "--env", f"CFFIXED_USER_HOME={home}",
               "--env", f"MPLCONFIGDIR={home}/matplotlib", str(app)]
    subprocess.run(command, check=True)
    running = None
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            for candidate in NSRunningApplication.runningApplicationsWithBundleIdentifier_(identifier):
                if Path(candidate.bundleURL().path()).resolve() == app.resolve():
                    running = candidate
                    break
            if running is not None:
                windows = Quartz.CGWindowListCopyWindowInfo(
                    Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
                for window in windows:
                    bounds = window["kCGWindowBounds"]
                    if (window["kCGWindowOwnerPID"] == running.processIdentifier()
                            and window["kCGWindowLayer"] == 0
                            and bounds["Width"] > 400 and bounds["Height"] > 300):
                        metadata, = home.rglob("standard_library/metadata.json")
                        assert json.loads(metadata.read_text(encoding="utf-8")) == catalog
                        assert os.access(metadata, os.W_OK)
                        assert (metadata.parents[1] / "workflows").is_dir()
                        return
            time.sleep(0.5)
        raise RuntimeError("The installed app did not display its main window.")
    finally:
        if running is not None:
            running.terminate()
            for _ in range(40):
                if running.isTerminated():
                    break
                time.sleep(0.25)
            if not running.isTerminated():
                running.forceTerminate()


def check_image(image):
    with TemporaryDirectory(prefix="im-tool-install-") as temporary:
        root = Path(temporary).resolve()
        mount = root / "volume"
        mount.mkdir()
        app = root / "Applications" / "IM Tool.app"
        app.parent.mkdir()
        subprocess.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint",
                        str(mount), str(image)], check=True)
        try:
            assert os.readlink(mount / "Applications") == "/Applications"
            subprocess.run(["ditto", str(mount / app.name), str(app)], check=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)], check=True)
        identifier, catalog = check_contents(app, image)
        check_launch(app, identifier, catalog, root / "profile")
    print(f"Installed and opened {image.name} after ejecting the disk image.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Run the disk image installation test on macOS.")
    check_image(args.image.resolve())
