"""Add the daily clock worker to the installed SuperVision VI bridge."""

import os
import shutil
import sys


def update_mount(source):
    module_import = b"from .supervision_clock import DailyClockSync\n"
    if module_import in source:
        return source
    changes = (
        (b"from contextlib import contextmanager\n", b"import os\n" + module_import),
        (b"        self.RequestHandlerClass = _MountedHandler\n",
         b"        self.clock_sync = None\n"
         b"        if address == ('10.20.30.2', 8772):\n"
         b"            report = os.path.join(os.path.dirname(profile), 'supervision-clock.json')\n"
         b"            self.clock_sync = DailyClockSync(keys[0], report)\n"),
        (b"        self.vi_context.dispatcher.start()\n",
         b"        if self.clock_sync is not None:\n"
         b"            self.clock_sync.start()\n"),
        (b"    def server_close(self):\n",
         b"        if self.clock_sync is not None:\n"
         b"            self.clock_sync.close()\n"),
    )
    if any(source.count(anchor) != 1 for anchor, _ in changes):
        raise ValueError("Unexpected installed SuperVision bridge layout")
    for anchor, code in changes:
        source = source.replace(anchor, anchor + code, 1)
    return source


def install(runtime):
    modules = os.path.join(runtime, "elyse_agent")
    mount = os.path.join(modules, "supervision_vi_mount.py")
    with open(mount, "rb") as stream:
        original = stream.read()
    updated = update_mount(original.replace(b"\r\n", b"\n"))
    source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "elyse_agent", "supervision_clock.py")
    backup = mount + ".before-clock-sync"
    if not os.path.exists(backup):
        shutil.copy2(mount, backup)
    clock_module = os.path.join(modules, "supervision_clock.py")
    shutil.copyfile(source, clock_module + ".new")
    os.replace(clock_module + ".new", clock_module)
    with open(mount + ".new", "wb") as stream:
        stream.write(updated)
    os.replace(mount + ".new", mount)
    print("Daily clock sync installed. Restart the SuperVision orchestrator to load it.")


if __name__ == "__main__":
    install(sys.argv[1] if len(sys.argv) > 1 else r"C:\SV_READY_20261030\runtime")
