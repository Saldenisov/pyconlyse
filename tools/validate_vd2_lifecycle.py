"""Explicit operator validation: on, off, on, repeated on, off.

Default mode is read-only. --execute operates the VD2 supplies and software,
never starts acquisition or moves/homes a stage, and ends with safe shutdown.
The current web worker's HIS/save state is read before every lifecycle guard.
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from threading import Event


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

import pump_probe_vd2_api as api


class WebProtocolState:
    def __init__(self, base_url):
        self.url = base_url.rstrip("/") + "/api/pump-probe-vd2/protocol/state"

    def status(self):
        with urllib.request.urlopen(self.url, timeout=5) as response:
            state = json.load(response)
        if not state.get("success") or state.get("status") not in {
            "idle", "acquiring", "saving", "completed", "failed",
        }:
            raise RuntimeError("Cannot confirm current web HIS worker state")
        return state


def snapshot():
    result = {}
    for device in (api.VD2_PDU_DEVICE, api.ZABER_PDU_DEVICE, api.OWIS_PDU_DEVICE, api.STREAK_DEVICE):
        try:
            proxy = api.DeviceProxy(device)
            proxy.set_timeout_millis(2500)
            data = {"state": str(proxy.state())}
            if device == api.STREAK_DEVICE:
                data.update({key: api._value(proxy, key) for key in (
                    "connected", "application_running", "remoteex_status",
                    "streak_shutter", "spectrograph_shutter", "blaze", "ruling",
                )})
            else:
                data["outputs"] = {str(int(index)): int(value) for index, value in zip(
                    api._value(proxy, "ids"), api._value(proxy, "states"))}
            result[device] = data
        except Exception as exc:
            result[device] = {"error": str(exc)}
    return result


def emit(value, report=None):
    line = json.dumps(value, default=str)
    print(line, flush=True)
    if report:
        with report.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")


def run_phase(phase, operation, lifecycle, report):
    """Wait for actual worker exit, not just its terminal database snapshot."""
    released = Event()
    if not api._preparation_lock.acquire(False):
        raise RuntimeError("Another lifecycle operation owns the preparation lock")

    def release():
        api._preparation_lock.release()
        released.set()

    started = time.monotonic()
    last_event = max((event["id"] for event in lifecycle.events()), default=0)
    emit({"phase": phase, "status": "executing"}, report)
    try:
        lifecycle.start("shutdown" if operation == api._deinitialize_experiment else "prepare", operation, release)
    except Exception:
        release()
        raise
    interrupted = False
    while not released.is_set():
        try:
            released.wait(1)
        except KeyboardInterrupt:
            # Do not cut camera power concurrently with a still-running SDK
            # call. Finish this bounded operation, then run final shutdown.
            interrupted = True
        for event in lifecycle.events():
            if event["id"] > last_event:
                emit({"phase": phase, "event": event}, report)
                last_event = event["id"]
        if time.monotonic() - started > 900:
            # A worker cannot be safely cancelled in the middle of native I/O.
            # Refuse subsequent hardware commands, including blind power-off.
            raise TimeoutError("Lifecycle worker exceeded 900 s; hardware outcome unknown, no concurrent power-off attempted")
    job = lifecycle.snapshot()
    outcome = {"phase": phase, "success": job["status"] == "completed",
               "code": job.get("code", ""), "error": job.get("error", ""),
               "steps": job.get("steps", []), "result": job.get("result"),
               "elapsed_s": round(time.monotonic() - started, 2),
               "hardware": snapshot(), "job_id": job["job_id"]}
    outcome["expected_repeat_rejection"] = phase == "repeat_startup" and outcome["code"] == "experiment_already_on"
    emit(outcome, report)
    if interrupted:
        raise KeyboardInterrupt
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Operate the VD2 lifecycle; ends powered down")
    parser.add_argument("--web-url", default="http://10.20.30.202:5000")
    parser.add_argument("--report", type=Path, help="New JSONL report; never overwrites an existing report")
    args = parser.parse_args()
    report = args.report.resolve() if args.report else None
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open("x", encoding="utf-8"):
            pass
    # No new in-process protocol instance may hide an active worker in the
    # real web server. An unavailable/invalid worker state fails closed.
    api._measurement_protocol = WebProtocolState(args.web_url)
    state = api._measurement_protocol.status()
    before = snapshot()
    emit({"phase": "before", "web_protocol": state, "hardware": before}, report)
    if not args.execute:
        return 0
    if state["status"] in {"acquiring", "saving"}:
        raise RuntimeError("Active HIS worker: lifecycle validation refused")

    lifecycle = api._lifecycle()
    emit({"state_database": str(lifecycle.path)}, report)
    outcomes = []
    try:
        for phase, operation in (
            ("startup", api._initialize_experiment),
            ("shutdown_1", api._deinitialize_experiment),
            ("startup_2", api._initialize_experiment),
            ("repeat_startup", api._initialize_experiment),
            ("shutdown_2", api._deinitialize_experiment),
        ):
            outcomes.append(run_phase(phase, operation, lifecycle, report))
    finally:
        if (not outcomes or outcomes[-1]["phase"] != "shutdown_2") and not api._preparation_lock.locked():
            outcomes.append(run_phase("final_shutdown", api._deinitialize_experiment, lifecycle, report))
    after = snapshot()
    emit({"phase": "after", "hardware": after}, report)
    # Shared controller/control supplies and all unrelated outlets must stay
    # untouched. Individual off states are confirmed by the shutdown routine.
    verified = len(outcomes) == 5 and all(
        item["expected_repeat_rejection"] if item["phase"] == "repeat_startup"
        else item["success"] and not (item.get("result") or {}).get("warnings")
        for item in outcomes)
    shared_unchanged = before.get(api.OWIS_PDU_DEVICE) == after.get(api.OWIS_PDU_DEVICE)
    verified = verified and shared_unchanged
    emit({"phase": "summary", "complete_cycle_verified": verified,
          "shared_power_unchanged": shared_unchanged, "state_database": str(lifecycle.path)}, report)
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
