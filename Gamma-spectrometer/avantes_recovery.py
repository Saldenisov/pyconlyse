"""Persist an active collection and supervise the viewer without a network."""

import argparse
from contextlib import suppress
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from avantes_emulator import should_use_avantes_emulator


def recovery_directory():
    override = os.environ.get("AVANTES_RECOVERY_DIRECTORY")
    if override:
        return Path(override).resolve()
    mode = "emulated" if should_use_avantes_emulator() else "real"
    return Path(__file__).resolve().parent / "logs" / f"recovery-{mode}"


class CollectionRecovery:
    def __init__(self):
        self.directory = recovery_directory()
        self.active_path = self.directory / "active.json"

    def load(self):
        try:
            return json.loads(self.active_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def write(self, state):
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.directory, prefix="active-", suffix=".tmp")
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(state, file)
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(self.active_path)
        finally:
            temporary.unlink(missing_ok=True)

    def arm(self, run, settings, demo):
        prior = self.load()
        self.directory.mkdir(parents=True, exist_ok=True)
        checkpoint = self.directory / f"calibration-{uuid4().hex}.h5"
        try:
            run.create_continuation_checkpoint(checkpoint)
            self.write(dict(path=str(run.path.resolve()), checkpoint=str(checkpoint),
                            settings=settings, demo=demo))
        except Exception:
            checkpoint.unlink(missing_ok=True)
            raise
        if prior:
            with suppress(OSError):
                Path(prior["checkpoint"]).unlink(missing_ok=True)

    def disarm(self):
        prior = self.load()
        self.active_path.unlink(missing_ok=True)
        if prior:
            with suppress(OSError):
                Path(prior["checkpoint"]).unlink(missing_ok=True)

    def continue_in_new_file(self, state, run, path):
        destination = run.suggest_continuation_path(path)
        with Path(state["checkpoint"]).open("rb") as source:
            try:
                target = destination.open("xb")
            except OSError:
                destination = run.suggest_continuation_path(self.directory / path.name)
                target = destination.open("xb")
            try:
                with target:
                    shutil.copyfileobj(source, target)
                    target.flush()
                    os.fsync(target.fileno())
            except OSError:
                with suppress(OSError):
                    destination.unlink()
                raise
        return type(run)(destination)


def supervise():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recover-only", action="store_true")
    args = parser.parse_args()
    recovery = CollectionRecovery()
    if args.recover_only and not recovery.active_path.exists():
        return 0
    directory = recovery.directory
    directory.mkdir(parents=True, exist_ok=True)
    viewer = Path(__file__).with_name("avantes_dual_viewer.py")
    delay = 2
    with (directory / "supervisor.log").open("a", buffering=1, encoding="utf-8") as log:
        while True:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} Launching viewer", file=log)
            began = time.monotonic()
            # Tracebacks from native faults persist even if the console disappears.
            process = subprocess.Popen([sys.executable, "-E", "-s", "-X", "faulthandler", str(viewer)],
                                       stderr=log, env=dict(os.environ, AVANTES_SUPERVISED="1"))
            print(f"Viewer PID {process.pid}", file=log)
            try:
                status = process.wait()
            except KeyboardInterrupt:
                process.terminate()
                process.wait()
                return 130
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} Viewer exit {status}", file=log)
            if not status or not recovery.active_path.exists():
                return status
            if time.monotonic() - began >= 60:
                delay = 2
            print(f"Restarting active collection in {delay} s", file=log)
            time.sleep(delay)
            delay = min(60, delay * 2)


if __name__ == "__main__":
    sys.exit(supervise())
