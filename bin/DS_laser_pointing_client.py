import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from gui.Panels import LaserPointingPanel
from DeviceServers.LaserPointing.DS_LaserPointing_Widget import LaserPointing
from bin.DS_General_Client import main


layouts = {'V0': {'selection': ['manip/v0/laserpointing-cam1', 'manip/v0/laserpointing-cam2'], 'width': 2},
           '3P': {'selection': ['manip/v0/laserpointing-cam1', 'manip/v0/laserpointing-cam2',
                                'manip/v0/laserpointing-cam3'], 'width': 3},
           'Cam1': {'selection': ['manip/v0/laserpointing-cam1'], 'width': 1},
           'Cam2': {'selection': ['manip/v0/laserpointing-cam2'], 'width': 1},
           'Cam3': {'selection': ['manip/v0/laserpointing-cam3'], 'width': 1}
           }

if __name__ == '__main__':
    main(LaserPointingPanel, 'LaserPointing', LaserPointing, 'icons//laser_pointing.svg', layouts)
