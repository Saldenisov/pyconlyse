import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from gui.Panels import StandaPanel
from DeviceServers.STANDA.DS_STANDA_Widget import Standa_motor
from bin.DS_General_Client import main


layouts = {'ELYSE': {'selection': ['elyse/motorized_devices/de1', 'elyse/motorized_devices/de2',
                         'elyse/motorized_devices/mme_x', 'elyse/motorized_devices/mme_y',
                         'elyse/motorized_devices/mm1_x', 'elyse/motorized_devices/mm1_y',
                         'elyse/motorized_devices/mm2_x', 'elyse/motorized_devices/mm2_y'], 'width': 4},
           'V0': {'selection': ['manip/V0/mm3_x', 'manip/V0/mm3_y', 'manip/V0/mm4_x', 'manip/V0/mm4_y',
                      'manip/V0/dv01', 'manip/V0/dv02', 'manip/V0/dv03', 'manip/V0/dv04',
                      'manip/V0/s1', 'manip/V0/s2', 'manip/V0/s3', 'manip/V0/L-2_1',
                      'manip/V0/opa_x', 'manip/V0/opa_y', 'manip/v0/ts_sc_m', 'manip/v0/ts_opa_m'], 'width': 4},
           'V0_short': {'selection': ['manip/V0/dv04', 'manip/V0/L-2_1'], 'width': 2},
           'alignment': {'selection': ['elyse/motorized_devices/de1', 'elyse/motorized_devices/de2',
                            'manip/V0/dv01', 'manip/V0/dv02',
                            'elyse/motorized_devices/mm1_x', 'elyse/motorized_devices/mm1_y',
                            'elyse/motorized_devices/mm2_x', 'elyse/motorized_devices/mm2_y',
                            'manip/V0/mm3_x', 'manip/V0/mm3_y', 'manip/V0/mm4_x', 'manip/V0/mm4_y',
                            'manip/V0/s1', 'manip/V0/s2', 'manip/V0/L-2_1', 'manip/V0/dv03'], 'width': 4},
           'test': {'selection': ['elyse/motorized_devices/mm1_x', 'elyse/motorized_devices/mm1_y'], 'width': 4}
           }


if __name__ == '__main__':
    main(StandaPanel, 'STANDA', Standa_motor, 'icons//STANDA.svg', layouts)
