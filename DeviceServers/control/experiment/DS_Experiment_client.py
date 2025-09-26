#!/usr/bin/env python3
"""Experiment Client using general DS panel framework"""
import sys
from pathlib import Path

app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from bin.DS_General_Client import main
from gui.Panels import ExperimentPanel
from DeviceServers.control.experiment.DS_Experiment_Widget import Experiment

# Layouts from legacy
layouts = {
    "Pulse-Probe": {"selection": ["manip/cr/pulse-probe"], "width": 1},
    "3P": {"selection": ["manip/cr/pulse-repump-probe"], "width": 1},
    "Streak-Camera": {"selection": ["manip/cr/pulse-probe-streak"], "width": 1},
}


def start_experiment_client(instance: str = "Pulse-Probe", vis_type=None, standalone: bool = True):
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        ExperimentPanel,
        "Experiment",
        Experiment,
        "bin/icons/experiment.svg",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    sys.exit(start_experiment_client())
