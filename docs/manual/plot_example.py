"""Rebuild the cover from the same library tables and measured speeds as the GUI."""
import json
from pathlib import Path
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

MANUAL = Path(__file__).resolve().parent
ROOT = MANUAL.parents[1]
sys.path.insert(0, str(ROOT))
from im_app.core.physics import find_intersections, rayleigh_line, reflect_hugoniot


def state(curve, reference):
    """Use the desktop solver and read pressure from the ascending reference line."""
    up, = find_intersections(*curve, *reference, ignore_first=True)
    return up, np.interp(up, *reference)


def main():
    app = ROOT / "im_app"
    workflow = json.loads((app / "resources/practice/Hicks-29400.json").read_text(encoding="utf-8"))
    fits, rays = {}, {}
    ray_up = np.linspace(0, 40, 500)
    for line in workflow["rayleigh_lines"]:
        mid = line["material_id"]
        table = pd.read_csv(app / "standard_library/materials" / f"{mid}.txt", sep="\t", comment="#")
        fits[mid] = (table["Up(km/s)"].to_numpy(), table["P(Mbar)"].to_numpy())
        rays[mid] = (ray_up, rayleigh_line(ray_up, line["rho0"], line["D"]))

    al, quartz = "Al_Celliers2005", "Quartz_Hamel2012"
    a = state(fits[al], rays[al])
    q = state(fits[quartz], rays[quartz])
    mirror = reflect_hugoniot(*fits[al], a[0])
    match = state(mirror, rays[quartz])
    fig, ax = plt.subplots(figsize=(5.2, 3.2), layout="constrained")
    for curve, color, style, label in (
        (fits[al], "#164e58", "-", "Al (Celliers)"),
        (fits[quartz], "#aa522d", "-", r"$\alpha$-quartz (Hamel)"),
        (mirror, "#164e58", "--", "Al (reflected)"),
        (rays[quartz], "#aa522d", ":", "Quartz Rayleigh"),
    ):
        ax.plot(*curve, color=color, linestyle=style, lw=1.6, label=label)
    for point, label, color, marker, offset in (
        (a, "A", "#164e58", "o", (-5, 14)),
        (q, "Q", "#aa522d", "s", (10, -13)),
        (match, "M", "#243537", "D", (-16, -16)),
    ):
        ax.plot(*point, marker=marker, ms=5.5, color=color, markeredgecolor="white")
        ax.annotate(label, point, offset, textcoords="offset points", color=color, weight="bold",
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.4})
    ax.set(xlim=(9.35, 10.65), ylim=(4.32, 5.28), xlabel=r"$u_p$ (km/s)", ylabel=r"$P$ (Mbar)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#dce4e3", linewidth=0.6)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), frameon=False,
              ncol=2, fontsize=8, columnspacing=1.4, borderaxespad=0.1)
    fig.savefig(MANUAL / "figures/tutorial-plot.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()
