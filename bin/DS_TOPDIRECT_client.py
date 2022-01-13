import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))

from taurus.qt.qtgui.application import TaurusApplication
from PyQt5.QtGui import QIcon
from gui.Panels import TopDirectPanel
from DeviceServers.TopDirect.DS_TOPDIRECT_Widget import TopDirect_Motor
from bin.DS_General_Client import main



layouts = {'all': {'selection': ['elyse/motorized_devices/Lense260', 'manip/V0/DL_SC1'],'width': 1}}


if __name__ == '__main__':
    main(TopDirectPanel, 'TopDIRECT', TopDirect_Motor, 'icons//TopDirect.svg', layouts)
