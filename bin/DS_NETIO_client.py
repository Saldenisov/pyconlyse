import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from bin.DS_General_Client import main
from gui.Panels import NetioPanel
from DeviceServers.NETIO.DS_NETIO_Widget import Netio_pdu


layouts = {'V0': {'selection': ['manip/V0/PDU_VO', 'manip/SD1/PDU_SD1', 'manip/SD2/PDU_SD2'], 'width': 1},
           'VD2': {'selection': ['manip/VD2/PDU_VD2', 'manip/SD2/PDU_SD2'], 'width': 1},
           'all': {'selection': ['manip/V0/PDU_VO', 'manip/VD2/PDU_VD2', 'manip/SD1/PDU_SD1', 'manip/SD2/PDU_SD2',
                   'manip/ELYSE/PDU_ELYSE'], 'width': 1}
          }


if __name__ == '__main__':
    main(NetioPanel, 'NETIO', Netio_pdu, 'icons//NETIO.ico', layouts)
