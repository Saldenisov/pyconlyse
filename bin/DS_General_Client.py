import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from taurus.qt.qtgui.application import TaurusApplication
from PyQt5.QtGui import QIcon
from DeviceServers.DS_Widget import VisType
from gui.Panels import General_Panel


def main(DS_Panel: General_Panel, title: str, widget_class, icon: str, layouts):
    if len(sys.argv) >= 2:
        try:
            choice = layouts[sys.argv[1]]['selection']
            app = TaurusApplication(sys.argv, cmd_line_parser=None, )
            width = layouts[sys.argv[1]]['width']
            vis_type = VisType.FULL
            if len(sys.argv) >= 3:
                try:
                    vis_type = VisType(sys.argv[2])
                except NameError:
                    pass
            panel = DS_Panel(choice=choice, widget_class=widget_class, title=title,
                             icon=QIcon('icons//NETIO.ico'), width=width, vis_type=vis_type)
            panel.show()
            sys.exit(app.exec_())
        except KeyError:
            print(f'Arg {sys.argv[1]} does not present in {layouts.keys()}')


if __name__ == '__main__':
    main()
