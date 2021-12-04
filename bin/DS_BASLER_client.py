import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from taurus.qt.qtgui.application import TaurusApplication
from PyQt5.QtGui import QIcon
from gui.Panels import Basler_Panel
from DeviceServers.BASLER.DS_BASLER_Widget import Basler_camera



layouts = {'V0': ['manip/V0/Cam1_V0', 'manip/V0/Cam2_V0', 'manip/V0/Cam3_V0'],
           'all': ['manip/V0/Cam1_V0', 'manip/V0/Cam2_V0', 'manip/V0/Cam3_V0'],
           'test': ['manip/V0/Cam2_V0']}


def main():

    if len(sys.argv) >= 2:
        try:
            choice = layouts[sys.argv[1]]
            app = TaurusApplication(sys.argv, cmd_line_parser=None, )
            if len(sys.argv) >= 3:
                try:
                    width = int(sys.argv[2])
                except ValueError:
                    width = len(choice)
            elif len(sys.argv) == 2:
                width = len(choice)
            panel = Basler_Panel(choice=choice, widget_class=Basler_camera, title='Basler',
                                    icon=QIcon('icons//basler.svg'), width=width)
            panel.show()
            sys.exit(app.exec_())
        except KeyError:
            print(f'Arg {sys.argv[1]} does not present in {layouts.keys()}')


if __name__ == '__main__':
    main()
