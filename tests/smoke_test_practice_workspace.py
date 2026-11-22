"""Check the packaged Celliers/Hamel exercise using the GUI controls offscreen."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtWidgets import QApplication
from im_app import desktop
from im_app.gui.main_window import MainWindow


def select(combo, value):
    index = combo.findData(value)
    assert index >= 0, value
    combo.setCurrentIndex(index)


def check_example(profile):
    with patch.object(desktop, "user_directory", return_value=profile):
        library, workflows, starter = desktop.practice_workspace()
    window = MainWindow(library, workflows)
    panel = window.intersection_panel
    al, quartz = "Al_Celliers2005", "Quartz_Hamel2012"

    def find(curve, line, up, pressure):
        select(panel.curve1_combo, curve)
        select(panel.curve2_combo, line)
        panel.find_btn.click()
        result = window.hugoniot_plot.intersections[-1]
        assert abs(result.up - up) < 0.0001 and abs(result.p - pressure) < 0.0001
        assert (panel.curve1_combo.currentData(), panel.curve2_combo.currentData()) == (curve, line)
        return result

    # The fixed central values exercise matching independently of Monte Carlo sampling.
    with patch.object(window, "_run_monte_carlo_for_scene"):
        window._apply_workflow_dict(starter, run_mc=False)
        materials = window.hugoniot_plot.materials
        assert set(materials) == {al, quartz}
        assert all(len(m.up) == 500 and m.fit_params for m in materials.values())
        a = find(al, "rl_1", 9.9390, 4.8599)
        find(quartz, "rl_2", 10.2267, 4.8673)
        select(panel.reflect_curve_combo, al)
        select(panel.reflect_center_combo, a.id)
        panel.reflect_btn.click()
        reflected = window.hugoniot_plot.reflected_curves[-1]["id"]
        find(reflected, "rl_2", 10.0405, 4.7787)

        path = str(Path(workflows) / "replay.json")
        window.save_workflow_to(path)
        window.load_workflow_from(path)
        assert window.rayleigh_panel.line_list.count() == 2
        assert panel.refl_list.count() == 1 and panel.ix_table.rowCount() == 3
    window.close()


if __name__ == "__main__":
    app = QApplication([])
    with TemporaryDirectory() as temp:
        check_example(Path(temp))
    print("Celliers/Hamel practice matches Hicks shot 29400 and reopens without duplicate lines.")
