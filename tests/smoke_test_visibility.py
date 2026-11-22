"""Check that toggling materials and a reference curve redraws the affected plots."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from im_app.desktop import prepare_workspace
from im_app.gui.main_window import MainWindow


def check_visibility(directory):
    ids = ("Al_Celliers2005", "Quartz_Hamel2012")
    source = ROOT / "im_app" / "standard_library"
    library, workflows = prepare_workspace(directory, source, ids)
    references = Path(library) / "reference_curves"
    references.mkdir()
    (references / "test_ref.csv").write_text("P,T\nMbar,eV\n1,0.25\n2,0.5\n", encoding="utf-8")
    window = MainWindow(library, workflows)
    try:
        materials = window.material_panel.material_list
        items = {materials.item(i).data(Qt.UserRole): materials.item(i)
                 for i in range(materials.count())}
        plots = (window.hugoniot_plot, window.us_up_plot)
        for material in ids:
            items[material].setCheckState(Qt.Checked)
            for plot in plots:
                assert material in plot.materials
        with_quartz = [len(plot.ax.lines) for plot in plots]

        items["Quartz_Hamel2012"].setCheckState(Qt.Unchecked)
        for plot, line_count in zip(plots, with_quartz):
            assert "Al_Celliers2005" in plot.materials
            assert "Quartz_Hamel2012" not in plot.materials
            assert len(plot.ax.lines) < line_count

        curve = window.reference_curve_panel.curve_list.item(0)
        pt = window.p_t_plot
        before = len(pt.ax.lines)
        curve.setCheckState(Qt.Checked)
        assert "ref_test_ref" in pt.materials and len(pt.ax.lines) > before
        curve.setCheckState(Qt.Unchecked)
        assert "ref_test_ref" not in pt.materials and len(pt.ax.lines) == before
    finally:
        window.close()


if __name__ == "__main__":
    app = QApplication([])
    with TemporaryDirectory() as temp:
        check_visibility(Path(temp))
    print("Material and reference curve visibility passed.")
