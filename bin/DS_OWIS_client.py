import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from taurus.qt.qtgui.application import TaurusApplication
from PyQt5.QtGui import QIcon
from gui.Panels import OWIS_Panel
from DeviceServers.OWIS.DS_OWIS_widget import OWIS_motor


layouts = {'V0': [('manip/general/DS_OWIS_PS90', [2, 3, 4])],
           'VD2': [('manip/general/DS_OWIS_PS90', [1])],
           'all': [('manip/general/DS_OWIS_PS90', [1, 2, 3, 4])]}


def main():
    if len(sys.argv) >= 2:
        try:
            choice = layouts[sys.argv[1]]
            app = TaurusApplication(sys.argv, cmd_line_parser=None, )
            if len(sys.argv) >= 3:
                try:
                    width = int(sys.argv[2])
                except ValueError:
                    width = 2
            elif len(sys.argv) == 2:
                width = 1

            panel = OWIS_Panel(choice=choice, widget_class=OWIS_motor, title='OWIS', icon=QIcon('icons//OWIS.png'),
                               width=width)
            panel.show()
            sys.exit(app.exec_())
        except KeyError:
            print(f'Arg {sys.argv[1]} does not present in {layouts.keys()}')


if __name__ == '__main__':
    main()
