import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from gui.DS_General_Client import main
from DeviceServers.power.iTest.DS_iTest_PSU_Tabs import Itest_PSU
from gui.Panels import ITestPanel

# Device layouts for iTest PSU instances
layouts = {
    "ELYSE": {
        "selection": ["elyse/pdu/itest"],
        "width": 1,
    },
}


def start_itest_client(instance: Optional[str] = None, vis_type=None, standalone=True):
    """Start iTest client programmatically.

    Args:
        instance: Instance key in layouts (defaults to CLI arg if None)
        vis_type: Visualization type (VisType)
        standalone: Whether to run as standalone application

    Returns:
        Panel instance if not standalone, None otherwise
    """
    from DeviceServers.shared.DS_Widget import VisType

    if vis_type is None:
        vis_type = VisType.FULL

    return main(
        ITestPanel,
        "iTest PSU",
        Itest_PSU,
        "bin/icons/PSU.ico",
        layouts,
        instance=instance,
        vis_type=vis_type,
        standalone=standalone,
    )


if __name__ == "__main__":
    main(ITestPanel, "iTest PSU", Itest_PSU, "bin/icons/PSU.ico", layouts)