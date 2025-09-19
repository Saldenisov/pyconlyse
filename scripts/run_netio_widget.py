#!/usr/bin/env python3
"""Run a single NETIO PDU widget as a standalone window.

Usage:
    python scripts/run_netio_widget.py manip/V0/PDU_VO

Notes:
- Requires Taurus/Tango environment (conda env: pyconlyse39).
- The widget will tolerate missing device server and show a status message.

"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from DeviceServers.power.netio.DS_NETIO_Widget import Netio_pdu
from DeviceServers.shared.DS_Widget import VisType
from taurus.qt.qtgui.application import TaurusApplication


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_netio_widget.py <device_name>")
        print("Example: python scripts/run_netio_widget.py manip/V0/PDU_VO")
        return 2

    device_name = sys.argv[1]

    app = TaurusApplication(sys.argv, cmd_line_parser=None)

    # Create widget without parent so it is a top-level window
    widget = Netio_pdu(device_name, parent=None, vis_type=VisType.FULL)
    widget.setWindowTitle(f"NETIO PDU - {device_name}")
    widget.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
