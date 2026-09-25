"""Standalone PyQt operator client for ``manip/VD2/Zaber``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

if __package__ in (None, ""):
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from DeviceServers.motion.zaber.DS_Zaber_Widget import ZaberStageWidget


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", nargs="?", default="manip/VD2/Zaber")
    parser.add_argument("vis", nargs="?", default="FULL")
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    device = "manip/VD2/Zaber" if args.device.upper() == "VD2" else args.device
    widget = ZaberStageWidget(device)
    widget.resize(600, 220)
    widget.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
