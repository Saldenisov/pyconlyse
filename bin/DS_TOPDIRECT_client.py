import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from taurus.qt.qtgui.application import TaurusApplication
from PyQt5.QtGui import QIcon
from gui.Panels import TopDirect_Panel
from DeviceServers.TopDirect.DS_TOPDIRECT_Widget import TopDirect_Motor



layouts = {'all': ['elyse/motorized_devices/Lense260', 'manip/V0/DL_SC1'],}


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
                width = 2
            panel = TopDirect_Panel(choice=choice, widget_class=TopDirect_Motor, title='TopDirect',
                                    icon=QIcon('icons//TopDirect.svg'), width=width)
            panel.show()
            sys.exit(app.exec_())
        except KeyError:
            print(f'Arg {sys.argv[1]} does not present in {layouts.keys()}')


if __name__ == '__main__':
    main()
