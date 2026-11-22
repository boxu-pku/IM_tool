"""
Impedance Matching Tool - Entry point.

Launches the QApplication with the new interactive GUI.
Window starts maximized.
"""

import sys
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMessageBox

from im_app.desktop import ICON, application_paths
from im_app.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IM Tool")
    app.setDesktopFileName("io.github.boxu_pku.IMTool")
    app.setWindowIcon(QIcon(str(ICON)))
    app.setStyle("Fusion")

    try:
        lib_dir, workflows_dir = application_paths()
    except OSError as error:
        QMessageBox.critical(None, "IM Tool", f"Could not open the working directory.\n{error}")
        return 1

    window = MainWindow(lib_dir=lib_dir, workflows_dir=workflows_dir)
    window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
