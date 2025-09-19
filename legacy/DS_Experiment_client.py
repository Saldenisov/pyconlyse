import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[1]
sys.path.append(str(app_folder))
from bin.DS_General_Client import main
from DeviceServers.control.experiment.DS_Experiment_Widget import Experiment
from gui.Panels import ExperimentPanel

layouts = {
    "Pulse-Probe": {"selection": ["manip/cr/pulse-probe"], "width": 1},
    "3P": {"selection": ["manip/cr/pulse-repump-probe"], "width": 1},
    "Streak-Camera": {"selection": ["manip/cr/pulse-probe-streak"], "width": 1},
}


if __name__ == "__main__":
    main(ExperimentPanel, "Experiment", Experiment, "icons//experiment.svg", layouts)
