import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from taurus.qt.qtgui.application import TaurusApplication
from PyQt5.QtGui import QIcon
from gui.Panels import Netio_Panel
from DeviceServers.NETIO.DS_NETIO_Widget import Netio_pdu

layouts = {'V0': ['manip/V0/PDU_VO', 'manip/SD1/PDU_SD1', 'manip/SD2/PDU_SD2'],
           'VD2': ['manip/VD2/PDU_VD2', 'manip/SD2/PDU_SD2'],
           'all': ['manip/V0/PDU_VO', 'manip/VD2/PDU_VD2', 'manip/SD1/PDU_SD1', 'manip/SD2/PDU_SD2',
                   'manip/ELYSE/PDU_ELYSE']
          }


def main():

    if len(sys.argv) >= 2:
        try:
            choice = layouts[sys.argv[1]]
            app = TaurusApplication(sys.argv, cmd_line_parser=None, )
            if len(sys.argv) >= 3:
                try:
                    width = int(sys.argv[2])
                except ValueError:
                    width = 1
            elif len(sys.argv) == 2:
                width = 1
            panel = Netio_Panel(choice=choice, widget_class=Netio_pdu, title='NETIO', icon=QIcon('icons//NETIO.ico'),
                                width=width)
            panel.show()
            sys.exit(app.exec_())
        except KeyError:
            print(f'Arg {sys.argv[1]} does not present in {layouts.keys()}')


if __name__ == '__main__':
    main()
