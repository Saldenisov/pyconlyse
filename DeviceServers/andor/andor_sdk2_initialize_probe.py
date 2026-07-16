"""Minimal, no-Tango probe for the Andor SDK2 initialization sequence.

This intentionally calls only Initialize() and ShutDown(). It does not create
an AndorSDK2Camera object, so pylablib's camera default setup is not run.
"""

from pathlib import Path

import pylablib as pll


SDK_DIR = Path(r"C:\Program Files\Andor SDK")


def main() -> None:
    if not SDK_DIR.is_dir():
        raise RuntimeError(f"Andor SDK directory does not exist: {SDK_DIR}")

    pll.par["devices/dlls/andor_sdk2"] = str(SDK_DIR)
    from pylablib.devices.Andor import AndorSDK2

    AndorSDK2.libctl.preinit()
    initialized = False
    try:
        print("STEP 1: calling SDK2 Initialize() now...", flush=True)
        AndorSDK2.lib.Initialize(str(SDK_DIR).encode())
        initialized = True
        print("STEP 2: Initialize() succeeded; SDK is held open.", flush=True)
        input("Leave this window open and report the beep count in Codex. Press Enter to call ShutDown(). ")
    finally:
        if initialized:
            print("STEP 3: calling SDK2 ShutDown() now...", flush=True)
            AndorSDK2.lib.ShutDown()
            print("STEP 4: ShutDown() completed.", flush=True)


if __name__ == "__main__":
    main()
