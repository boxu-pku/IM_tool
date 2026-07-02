import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QListWidget
from PyQt5.QtCore import Qt

app = QApplication(sys.argv)
from im_app.gui.main_window import MainWindow

proj = Path('D:/My_app/IM_tool')
mw = MainWindow(str(proj/'im_app'/'standard_library'), str(proj/'im_app'/'workflows'))

# Check methods
for name, plot in [('P-Up', mw.hugoniot_plot), ('Us-Up', mw.us_up_plot), ('P-CR', mw.eos_plot)]:
    print(f'{name}: update_plot={hasattr(plot, "update_plot")}')

# Check + uncheck
for mat_id in ['Al_3717_sesame', 'Quartz_Hamel2012']:
    for i in range(mw.material_panel.material_list.count()):
        item = mw.material_panel.material_list.item(i)
        if item.data(Qt.UserRole) == mat_id:
            item.setCheckState(Qt.Checked); break

print(f'After check 2 hugoniot: P-Up lines={len(mw.hugoniot_plot.ax.get_lines())}, Us-Up lines={len(mw.us_up_plot.ax.get_lines())}')

for i in range(mw.material_panel.material_list.count()):
    item = mw.material_panel.material_list.item(i)
    if item.data(Qt.UserRole) == 'Quartz_Hamel2012':
        item.setCheckState(Qt.Unchecked); break

print(f'After uncheck Quartz: P-Up lines={len(mw.hugoniot_plot.ax.get_lines())}, Us-Up lines={len(mw.us_up_plot.ax.get_lines())}')

# Reference curve
lw = mw.reference_curve_panel.findChildren(QListWidget)[0]
lw.item(0).setCheckState(Qt.Checked)
print(f'After check ref: P-T lines={len(mw.p_t_plot.ax.get_lines())}')
lw.item(0).setCheckState(Qt.Unchecked)
print(f'After uncheck ref: P-T lines={len(mw.p_t_plot.ax.get_lines())}')
