"""Separate Python 3.4 window: Initialize / Deinitialize / Stop server only."""
import argparse
import json
import os
import threading

from .acquisition_gui import AcquisitionWindow, load_configuration
from .acquisition_backend import CardBackend, DemoBackend
from .acquisition_control_runtime import AcquisitionControlRuntime, control_identity
from .acquisition_recovery import OwnershipMarker
from .acquisition_remote import ControlHTTPServer
from .chroma_focal_command import ChromaFocalCommand
from .chroma_focal_stop import DEFAULT_DLL
from .cooling_safety import CoolingSafety
from .dual_mode_telemetry import DualModeTelemetryPublisher

BUTTON_LABELS = ("Initialize", "Deinitialize", "Stop server")


def load_control_configuration(path):
    folder = os.path.dirname(os.path.abspath(path))
    with open(path, "r") as stream:
        value = json.load(stream)
    required = {"remote_control_enabled", "command_key_file", "cooling_safety"}
    if (type(value) is not dict or set(value) not in (required, required | {"telemetry"})
            or type(value["remote_control_enabled"]) is not bool):
        raise ValueError("Exact separate control configuration required")
    telemetry = value.get("telemetry", dict(enabled=False, host="10.20.30.202", port=8767, period_seconds=.2))
    if (type(telemetry) is not dict or set(telemetry) != {"enabled", "host", "port", "period_seconds"}
            or type(telemetry["enabled"]) is not bool or telemetry["host"] != "10.20.30.202"
            or telemetry["port"] != 8767 or type(telemetry["period_seconds"]) not in (int, float)
            or not .05 <= telemetry["period_seconds"] <= 10):
        raise ValueError("Explicit fixed Everest telemetry configuration required")
    value["telemetry"] = telemetry
    cooling = value["cooling_safety"]
    if (type(cooling) is not dict or set(cooling) != {"polarity_verified", "journal_file"}
            or type(cooling["polarity_verified"]) is not bool
            or not isinstance(cooling["journal_file"], str) or not cooling["journal_file"]):
        raise ValueError("Explicit cooling polarity and journal configuration required")
    base, read_key = load_configuration(os.path.join(folder, "config.acquisition.json"))
    command_key = None
    if not isinstance(value["command_key_file"], str) or not value["command_key_file"]:
        raise ValueError("Explicit command key path required")
    if value["remote_control_enabled"]:
        key_path = os.path.join(folder, value["command_key_file"])
        with open(key_path, "rb") as stream:
            command_key = stream.read().strip()
        if len(command_key) < 32 or command_key == read_key:
            raise ValueError("Separate command key of at least 32 bytes required")
    value["cooling_safety"] = dict(cooling, journal_file=os.path.join(folder, cooling["journal_file"]))
    return base, read_key, command_key, value


class ControlWindow(AcquisitionWindow):
    """Reuses guarded lifecycle actions, not the old multi-button constructor."""
    def __init__(self, root, runtime, server, config_path, entrypoint, demo=False):
        import tkinter as tk
        from tkinter import messagebox
        self.tk, self.messagebox = tk, messagebox
        self.root, self.runtime, self.server = root, runtime, server
        self.config_path, self.entrypoint, self.demo = config_path, entrypoint, demo
        self.closing = False
        root.title("ELYSE Acquisition Control - Python 3.4" + (" - DEMO / NO HARDWARE" if demo else ""))
        root.geometry("1000x680")
        self.status, self.link, self.alarm = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for variable in (self.status, self.link):
            tk.Label(root, textvariable=variable, anchor="w").pack(fill="x", padx=12, pady=5)
        tk.Label(root, textvariable=self.alarm, fg="red", anchor="w", wraplength=960,
                 justify="left").pack(fill="x", padx=12)
        controls = tk.Frame(root)
        controls.pack(fill="x", padx=12, pady=10)
        self.init_button = tk.Button(controls, text=BUTTON_LABELS[0], command=self.initialize)
        self.deinit_button = tk.Button(controls, text=BUTTON_LABELS[1], command=self.deinitialize)
        self.close_button = tk.Button(controls, text=BUTTON_LABELS[2], command=self.request_close)
        for button in (self.init_button, self.deinit_button, self.close_button):
            button.pack(side="left", padx=6)
        tk.Label(root, text="Stage control belongs to the Everest Tango Device Server. Opening this window does not initialize cards.\n"
                 "Deinitialize releases tasks; it is NOT electrical shutdown. Failed or unconfirmed stops retain ownership.\n"
                 "Dirty ownership requires separate qualified local recovery; no automatic replay/reinitialization.",
                 justify="left", anchor="w").pack(fill="x", padx=12)
        self.display = tk.Text(root, wrap="none", font=("Courier", 9))
        self.display.pack(fill="both", expand=True, padx=12, pady=10)
        root.protocol("WM_DELETE_WINDOW", self.request_close)
        root.after(200, self.refresh)

    def refresh(self):
        state = self.runtime.snapshot()
        self.status.set("{0} | NI tasks: {1} | {2}".format(state["state"], state["resource_count"], state["error"]))
        age = state["everest_read_age_seconds"]
        delivery = state.get("telemetry_delivery", {})
        self.link.set("{0} | Everest telemetry ACK: {1} | {2} | ".format(delivery.get("source_mode", "DISABLED"), delivery.get("everest_acknowledged", 0),
                      delivery.get("publisher_error") or delivery.get("last_error", "publisher disabled")) +
                      ("command channel not seen" if age is None else "last signed read {0:.1f}s ago".format(age)) +
                      " | Commands: " + ("enabled / commissioned gates still apply" if state["control"]["enabled"] else "DISABLED"))
        alarm = state["cooling_safety"]
        self.alarm.set(("COOLING FAULT: " + ", ".join(item["circuit"] for item in alarm["circuits"]) +
                        " | countdown: {0:.0f}s | stop: {1}".format(alarm["remaining_seconds"], alarm["stop_state"]) +
                        (" | AUTOMATIC STOP UNAVAILABLE" if not alarm["automatic_stop_available"] else ""))
                       if alarm["active"] else alarm["journal_error"])
        self.init_button.configure(state="normal" if state["state"] == "IDLE" and not self.closing else "disabled")
        self.deinit_button.configure(state="normal" if state["resource_count"] and not self.closing
                                     and state["state"] not in ("DEINITIALIZING", "INITIALIZING", "EXECUTING") else "disabled")
        self.display.delete("1.0", "end")
        self.display.insert("end", json.dumps(state, sort_keys=True, indent=2))
        if self.closing and state["state"] == "STOPPED" and self.runtime.join(0):
            publisher = getattr(self.runtime, "telemetry_publisher", None)
            if publisher is not None:
                try:
                    publisher.close()
                except Exception as error:
                    self.alarm.set(str(error))
                    self.root.after(1000, self.refresh)
                    return
            self.server.shutdown()
            self.server.server_close()
            self.root.destroy()
            return
        if self.closing and state["state"] == "FAULT":
            self.closing = False
        self.root.after(250, self.refresh)


def main(entrypoint, argv=None):
    import tkinter as tk
    from tkinter import messagebox
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.path.join(os.path.dirname(entrypoint), "config.acquisition.control.json"))
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args(argv)
    root = tk.Tk()
    runtime = server = thread = publisher = None
    try:
        base, read_key, command_key, control = load_control_configuration(args.config)
        flags = {name: base.get(name, False) for name in (
            "stage_controls_verified", "cooling_trip_verified", "ht_controls_verified", "focal_controls_verified",
            "counter_controls_verified", "counter_timing_controls_verified", "ht_voltage_controls_verified", "outer_stop_verified")}
        ht, focal = base.get("ht_shutdown", {}), base.get("focal_stop", {})
        profile = base.get("control_profile", "legacy_full")
        if args.demo:
            factory = lambda: DemoBackend(control_profile=profile, **flags)
        else:
            focal_command = ChromaFocalCommand(focal.get("dll_path", DEFAULT_DLL),
                                               focal.get("resources_verified", False), focal.get("timeout_seconds", 10))
            factory = lambda: CardBackend(read_timeout=base["read_timeout_seconds"], control_profile=profile,
                ht_feedback_verified=ht.get("feedback_verified", False), ht_zero_tolerance_kv=ht.get("zero_tolerance_kv", 0),
                ht_zero_timeout=ht.get("timeout_seconds", 10), focal_command=focal_command, **flags)
        identity = control_identity()
        guard = None if args.demo else OwnershipMarker(os.path.abspath(args.config) + ".ownership",
                                                       identity["session_id"], identity["build_id"])
        cooling = CoolingSafety() if args.demo else CoolingSafety.with_journal(
            control["cooling_safety"]["journal_file"], "xp_acquisition_control")
        runtime = AcquisitionControlRuntime(factory, period=base["period_seconds"], identity=identity,
            recovery_guard=guard, remote_enabled=control["remote_control_enabled"], cooling=cooling,
            cooling_polarity_verified=control["cooling_safety"]["polarity_verified"])
        server = ControlHTTPServer((base["bind_host"], base["port"]), runtime, read_key, command_key)
        runtime.start()
        if control["telemetry"]["enabled"]:
            publisher = DualModeTelemetryPublisher(runtime,
                (control["telemetry"]["host"], control["telemetry"]["port"]), read_key,
                period=control["telemetry"]["period_seconds"])
            runtime.telemetry_publisher = publisher
            publisher.start()
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.1))
        thread.daemon = True
        thread.start()
        ControlWindow(root, runtime, server, args.config, entrypoint, args.demo)
    except Exception as error:
        if publisher is not None:
            try:
                publisher.close()
            except Exception:
                pass  # Preserve the original startup error; no hardware action here.
        if runtime is not None:
            runtime.request_shutdown()
            runtime.join(3)
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        messagebox.showerror("Acquisition Control not started", str(error), parent=root)
        root.destroy()
        return 1
    root.mainloop()
    return 0
