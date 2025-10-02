#!/usr/bin/env python3
"""Client app for iTest PSU using the Itest_PSU widget."""
import sys
from pathlib import Path

# Ensure repo root on path
app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from taurus.qt.qtgui.application import TaurusApplication
from DeviceServers.power.iTest.DS_iTest_PSU_Widget import Itest_PSU


def main():
    if len(sys.argv) < 2:
        print("Usage: DS_iTest_PSU_client.py <tango_device_name>")
        print("Example: DS_iTest_PSU_client.py ITestPSU/test")
        return 1

    dev_name = sys.argv[1]
    app = TaurusApplication(sys.argv, cmd_line_parser=None)
    w = Itest_PSU(dev_name, None)
    w.setWindowTitle(f"iTest PSU - {dev_name}")
    try:
        w.resize(900, 500)
    except Exception:
        pass
    w.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
