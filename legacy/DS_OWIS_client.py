import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from bin.DS_General_Client import main
from DeviceServers.motion.owis.DS_OWIS_widget import OWIS_motor
from DeviceServers.motion.owis.DS_OWIS_client import layouts
from gui.Panels import OWISPanel


if __name__ == "__main__":
    main(OWISPanel, "OWIS", OWIS_motor, "icons//OWIS.png", layouts)
