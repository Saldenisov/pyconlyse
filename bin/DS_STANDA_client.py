import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from taurus.qt.qtgui.application import TaurusApplication
from PyQt5.QtGui import QIcon
from gui.Panels import Standa_Panel
from DeviceServers.STANDA.DS_STANDA_Widget import Standa_motor



layouts = {'ELYSE': ['elyse/motorized_devices/de1', 'elyse/motorized_devices/de2',
                         'elyse/motorized_devices/mme_x', 'elyse/motorized_devices/mme_y',
                         'elyse/motorized_devices/mm1_x', 'elyse/motorized_devices/mm1_y',
                         'elyse/motorized_devices/mm2_x', 'elyse/motorized_devices/mm2_y'
                         ],
           'V0': ['manip/V0/mm3_x', 'manip/V0/mm3_y', 'manip/V0/mm4_x', 'manip/V0/mm4_y',
                      'manip/V0/dv01', 'manip/V0/dv02', 'manip/V0/dv03', 'manip/V0/dv04',
                      'manip/V0/s1', 'manip/V0/s2', 'manip/V0/s3', 'manip/V0/L-2_1',
                      'manip/V0/opa_x', 'manip/V0/opa_y', None, None
                      ],
           'V0_short': ['manip/V0/dv04', 'manip/V0/L-2_1',  None, None],
           'alignment': ['elyse/motorized_devices/de1', 'elyse/motorized_devices/de2',
                            'manip/V0/dv01', 'manip/V0/dv02',
                            'elyse/motorized_devices/mm1_x', 'elyse/motorized_devices/mm1_y',
                            'elyse/motorized_devices/mm2_x', 'elyse/motorized_devices/mm2_y',
                            'manip/V0/mm3_x', 'manip/V0/mm3_y', 'manip/V0/mm4_x', 'manip/V0/mm4_y',
                            'manip/V0/s1', 'manip/V0/s2', 'manip/V0/L-2_1', 'manip/V0/dv03'
               ],
           'test': ['elyse/motorized_devices/mm1_x', 'elyse/motorized_devices/mm1_y']}


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
                width = 4
            panel = Standa_Panel(choice=choice, widget_class=Standa_motor, title='STANDA', icon=QIcon('icons//STANDA.svg'),
                                 width=width)
            panel.show()
            sys.exit(app.exec_())
        except KeyError:
            print(f'Arg {sys.argv[1]} does not present in {layouts.keys()}')


if __name__ == '__main__':
    main()
