"""
Impedance Matching Tool - Entry point.

Launches the QApplication with the new interactive GUI.
Window starts maximized.
"""

import sys
import os

from PyQt5.QtWidgets import QApplication

from im_app.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Paths relative to im_app/main.py
    base = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.normpath(os.path.join(base, "standard_library"))
    workflows_dir = os.path.normpath(os.path.join(base, "workflows"))

    window = MainWindow(lib_dir=lib_dir, workflows_dir=workflows_dir)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
