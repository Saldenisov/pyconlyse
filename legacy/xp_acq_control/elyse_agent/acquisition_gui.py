"""Operator window. Opening it starts a cold service, never NI tasks."""
import argparse
import json
import os
import threading

from .acquisition_backend import CardBackend, DemoBackend, CONTROL_PROFILES
from .acquisition_http import RuntimeHTTPServer
from .acquisition_runtime import AcquisitionRuntime
from .acquisition_startup import install_startup
from .chroma_focal_stop import DEFAULT_DLL
from .chroma_focal_command import ChromaFocalCommand
from .acquisition_ht_shutdown import validate_policy
from .acquisition_recovery import OwnershipMarker
from .runtime_identity import new_runtime_identity


def create_cold_runtime(factory, period, config_path, demo=False, quiescence_checker=None):
    """Production always installs the installation-local persistent guard.

    No guessed XP process verifier is installed. A prior marker therefore
    requires separately qualified local recovery before cards can initialize.
    The demo explicitly reports that persistent protection is inactive.
    """
    identity = new_runtime_identity()
    guard = None if demo else OwnershipMarker(
        os.path.abspath(config_path) + ".ownership", identity["session_id"], identity["build_id"],
        quiescence_checker=quiescence_checker)
    return AcquisitionRuntime(factory, period=period, identity=identity, recovery_guard=guard)


def load_configuration(path):
    with open(path, "r") as source:
        config = json.load(source)
    required = {"bind_host", "port", "key_file", "period_seconds", "read_timeout_seconds"}
    if (not required <= set(config) or set(config) - required
            - {"focal_stop", "control_profile", "ht_shutdown", "stage_controls_verified",
               "cooling_trip_verified", "ht_controls_verified", "focal_controls_verified",
               "counter_controls_verified", "ht_voltage_controls_verified", "outer_stop_verified",
               "counter_timing_controls_verified", "beamline_controls_verified", "operator_supervised_test",
               "native_isolation_mode"}):
        raise ValueError("Invalid acquisition configuration fields")
    if config.get("native_isolation_mode", "single_owner") not in ("single_owner", "per_card"):
        raise ValueError("Invalid native_isolation_mode")
    for flag in ("stage_controls_verified", "cooling_trip_verified", "ht_controls_verified",
                 "focal_controls_verified", "counter_controls_verified",
                 "ht_voltage_controls_verified", "outer_stop_verified", "counter_timing_controls_verified",
                 "beamline_controls_verified", "operator_supervised_test"):
        if type(config.get(flag, False)) is not bool:
            raise ValueError("Explicit Boolean " + flag + " required")
    if config.get("control_profile", "legacy_full") not in CONTROL_PROFILES:
        raise ValueError("Invalid control_profile")
    ht = config.get("ht_shutdown", {})
    if not isinstance(ht, dict) or set(ht) - {"feedback_verified", "zero_tolerance_kv", "timeout_seconds"}:
        raise ValueError("Invalid ht_shutdown configuration")
    validate_policy(ht.get("feedback_verified", False), ht.get("zero_tolerance_kv", 0.0),
                    ht.get("timeout_seconds", 10.0))
    focal = config.get("focal_stop", {})
    if (not isinstance(focal, dict) or set(focal) - {"dll_path", "resources_verified", "timeout_seconds"}
            or type(focal.get("resources_verified", False)) is not bool
            or not isinstance(focal.get("dll_path", DEFAULT_DLL), str)
            or type(focal.get("timeout_seconds", 10)) not in (int, float)
            or not 1 <= focal.get("timeout_seconds", 10) <= 30):
        raise ValueError("Invalid focal_stop configuration")
    if config["bind_host"] not in ("127.0.0.1", "10.20.30.10"):
        raise ValueError("Invalid bind host")
    if type(config["port"]) is not int or not 1024 <= config["port"] <= 65535:
        raise ValueError("Invalid port")
    for name, minimum, maximum in (("period_seconds", 0.02, 10), ("read_timeout_seconds", 0.01, 2)):
        if type(config[name]) not in (int, float) or not minimum <= config[name] <= maximum:
            raise ValueError("Invalid " + name)
    if not isinstance(config["key_file"], str) or not config["key_file"]:
        raise ValueError("Invalid key file")
    key_path = config["key_file"]
    if not os.path.isabs(key_path):
        key_path = os.path.join(os.path.dirname(os.path.abspath(path)), key_path)
    with open(key_path, "rb") as source:
        key = source.read().strip()
    if len(key) < 32:
        raise ValueError("Shared key must contain at least 32 bytes")
    return config, key


class AcquisitionWindow(object):
    def __init__(self, root, runtime, server, config_path, entrypoint, demo=False,
                 control_profile="legacy_full"):
        import tkinter as tk
        from tkinter import messagebox
        self.tk, self.messagebox = tk, messagebox
        self.root, self.runtime, self.server = root, runtime, server
        self.config_path, self.entrypoint, self.demo = config_path, entrypoint, demo
        self.general_only = control_profile == "general_only_test"
        self.extended_ht = control_profile == "extended_ht_stop"
        self.closing = False
        root.title("ELYSE Acquisition Server" + (" - DEMO / NO HARDWARE" if demo else " - Python 3.4") +
                   (" - GENERAL ONLY TEST" if self.general_only else
                    " - EXTENDED HT STOP" if self.extended_ht else ""))
        root.geometry("1000x640")
        initial_state = runtime.snapshot()
        self.status = tk.StringVar(value="{0} | NI tasks: {1} | {2}".format(
            initial_state["state"], initial_state["resource_count"], initial_state["error"]))
        tk.Label(root, textvariable=self.status, anchor="w", font=("Arial", 13)).pack(fill="x", padx=12, pady=10)
        tk.Label(root, text="Server: {0}:{1} | authenticated telemetry reads only".format(*server.server_address),
                 anchor="w").pack(fill="x", padx=12)
        self.link = tk.StringVar(value="Everest reader: not seen")
        tk.Label(root, textvariable=self.link, anchor="w").pack(fill="x", padx=12, pady=5)
        controls = tk.Frame(root)
        controls.pack(fill="x", padx=12, pady=8)
        self.init_button = tk.Button(controls, text="Initialize acquisition", command=self.initialize)
        self.init_button.pack(side="left", padx=4)
        self.deinit_button = tk.Button(controls, text="Deinitialize acquisition", command=self.deinitialize)
        self.deinit_button.pack(side="left", padx=4)
        self.general_button = tk.Button(controls, text="General Marche", command=self.general_start)
        self.general_button.pack(side="left", padx=4)
        self.general_stop_button = tk.Button(controls, text="General Arret", command=self.general_stop)
        self.general_stop_button.pack(side="left", padx=4)
        tk.Button(controls, text="Stop server", command=self.request_close).pack(side="left", padx=4)
        self.startup_button = tk.Button(controls, text="Enable Windows startup", command=self.enable_startup)
        self.startup_button.pack(side="right", padx=4)
        if demo or self.general_only:
            self.startup_button.configure(state="disabled")
        recovery_controls = tk.Frame(root)
        recovery_controls.pack(fill="x", padx=12)
        self.recovery_button = tk.Button(recovery_controls, text="Recover prior ownership", command=self.recover)
        self.recovery_button.pack(side="left", padx=4)
        self.recovery_button.configure(state="normal" if initial_state["state"] == "RECOVERY_REQUIRED" else "disabled")
        self.init_button.configure(state="normal" if initial_state["state"] == "IDLE" else "disabled")
        for button in (self.general_button, self.general_stop_button, self.deinit_button):
            button.configure(state="disabled")
        tk.Label(recovery_controls, text="Unclean prior ownership blocks initialization; no automatic replay.",
                 anchor="w").pack(side="left", padx=8)
        stop_scope = ("GENERAL ONLY TEST: Marche + two resets; Arret pulses C4[1], restoring interrupted Marche/RAZ if needed. No Chroma.\n"
                      "Other stages must already be OFF. This is NOT the full LabVIEW stop or an emergency stop.\n"
                      if self.general_only else
                      "General Arret: Focales OFF, then C4 stop pulses 8 / 17 / 6 / 4 / 1.\n"
                      "Original event 6 does NOT issue the separate HT-supply stop C4[19]. Not an emergency stop.\n")
        if self.extended_ht:
            stop_scope = ("PYTHON EXTENSION: fresh HT zero -> skip ramp; otherwise lower to8 kV without increasing command.\n"
                          "HT supply OFF -> stop counters3/4 -> fresh zero AND supply OFF -> original full General Arret.\n"
                          "Unverified feedback blocks this profile. Any HT/pulse failure retains NI and inhibits later stage shutdown.\n")
        tk.Label(root, text="Initialization applies legacy startup AO/DO and counter timing. General Marche is a separate hardware command.\n" +
                 stop_scope +
                 "Deinitialize releases tasks; blocked after Marche until Arret succeeds or cabinet is confirmed off locally.\n"
                 "AI raw volts and separate legacy-scaled values; not the full 27-bank LabVIEW schema.",
                 anchor="w", justify="left", wraplength=960).pack(fill="x", padx=12, pady=6)
        self.display = tk.Text(root, wrap="none", font=("Courier", 9))
        self.display.pack(fill="both", expand=True, padx=12, pady=10)
        root.protocol("WM_DELETE_WINDOW", self.request_close)
        root.after(200, self.refresh)

    def initialize(self):
        if not self.demo and not self.messagebox.askyesno(
                "Confirm NI startup", "LabVIEW Acquisition must be fully stopped.\n\n"
                "This will configure all 11 cards, start the recovered counters, and apply fixed legacy AO/DO startup values.\n"
                "Verify that these startup effects are permitted for the installation.\n\nInitialize now?", parent=self.root):
            return
        try:
            self.runtime.initialize(startup_confirmed=True)
        except Exception as error:
            self.messagebox.showerror("Initialization refused", str(error), parent=self.root)

    def general_start(self):
        scope = ("GENERAL ONLY TEST: verify heating, PREMA, focal supplies and HT are physically OFF.\n"
                 "Do not operate those stages during this test. Arret will stop only low-level General.\n\n"
                 if self.general_only else "")
        if not self.demo and not self.messagebox.askyesno(
                "Confirm General Marche", scope + "This energizes the low-level modulator command/safety chassis\n"
                "and pulses its reset twice (original ACQ event 5).\n\n"
                "It does not start heating, PREMA, focal supplies or HT.\n"
                "Software EPS OK is not hardware readiness.\n\nExecute General Marche now?", parent=self.root):
            return
        try:
            self.runtime.general_start(operator_confirmed=True)
        except Exception as error:
            self.messagebox.showerror("General Marche refused", str(error), parent=self.root)

    def recover(self):
        if not self.messagebox.askyesno(
                "Prior ownership recovery", "This does not initialize cards or replay a command.\n\n"
                "Has the installation been switched OFF LOCALLY and physically verified?\n"
                "A separately qualified checker must also prove the old process, native children and competing NI owners absent.\n"
                "PID absence alone is insufficient. Without that checker recovery remains blocked.", parent=self.root):
            return
        try:
            self.runtime.recover_local(electrical_off_confirmed=True)
            self.messagebox.showinfo("Ownership recovered", "Cards remain uninitialized. No command replayed.", parent=self.root)
        except Exception as error:
            self.messagebox.showerror("Recovery refused; marker preserved", str(error), parent=self.root)

    def enable_startup(self):
        try:
            if self.demo or self.general_only:
                raise RuntimeError("Windows startup is disabled for demo/General-only commissioning profiles")
            path = install_startup(self.entrypoint, self.config_path)
            self.startup_button.configure(text="Windows startup enabled", state="disabled")
            self.messagebox.showinfo("Cold startup enabled", path + "\n\nWindow/server only. Cards remain uninitialized.", parent=self.root)
        except Exception as error:
            self.messagebox.showerror("Startup not installed", str(error), parent=self.root)

    def general_stop(self):
        details = ("GENERAL ONLY TEST: restore interrupted Marche/RAZ if needed, then C4[1] False -> 150 ms -> True.\n"
                   "Only General software status fields are updated.\n"
                   "No Chroma, heating, PREMA, focal or HT stop command will be issued.\n"
                   "Those stages must already be OFF; this is not a full installation shutdown.\n\n"
                   if self.general_only else
                   "Original ACQ event 6: Focales OFF, then stop pulses for\n"
                   "C4[8], C4[17], C4[6], C4[4], C4[1], with original delays.\n\n"
                   "Stops focal klystron, Relais HT, PREMA, Chauffage and General.\n"
                   "Does NOT issue separate alimentation HT stop C4[19], cooling stop, or task cleanup.\n\n"
                   "Focal OFF also resets/configures its three Chroma supplies before output OFF.\n"
                   "Unverified Chroma mapping/driver will be reported as a partial failure;\n"
                   "the NI stop pulses will still be attempted.\n\n")
        if getattr(self, "extended_ht", False):
            details = ("PYTHON EXTENSION, not original event 6:\n"
                       "Read fresh HT. If already zero, do not lower or raise the AO command.\n"
                       "Otherwise lower to8 kV, never increasing an existing command.\n"
                       "Stop HT supply, then stop both modulator counters3/4.\n"
                       "Fresh HT zero AND supply OFF AND successful pulse stops are required\n"
                       "before the remaining Focales / Relais HT / PREMA / Chauffage / General stops.\n"
                       "Unverified feedback or any HT/pulse failure blocks that continuation.\n\n")
        if not self.demo and not self.messagebox.askyesno(
                "Confirm General Arret", details +
                "This is NOT an emergency stop or physical OFF confirmation. Execute?", parent=self.root):
            return
        try:
            self.runtime.general_stop(operator_confirmed=True)
        except Exception as error:
            self.messagebox.showerror("General Arret refused", str(error), parent=self.root)

    def confirm_local_off(self):
        state = self.runtime.snapshot()
        if not (state["general_stop_required"] or state.get("ht_supply_stop_required", False)):
            return False
        reason = ("HT supply stop remains unconfirmed. Source General Arret does not stop it directly.\n"
                  if state.get("ht_supply_stop_required", False) else
                  "General Arret has not completed successfully.\n")
        if not self.messagebox.askyesno(
                "Physical OFF confirmation required", reason +
                "Releasing NI tasks does NOT switch the installation off.\n\n"
                "Has the cabinet already been switched OFF LOCALLY and verified?\n"
                "Choose No to retain this card owner; use a qualified stop or local electrical shutdown.", parent=self.root):
            raise RuntimeError("Card ownership retained; qualified stop or verified local shutdown required")
        return True

    def deinitialize(self):
        try:
            self.runtime.deinitialize(electrical_off_confirmed=self.confirm_local_off())
        except Exception as error:
            self.messagebox.showerror("Deinitialization refused", str(error), parent=self.root)

    def request_close(self):
        if self.closing:
            return
        if self.runtime.snapshot()["state"] not in ("IDLE", "STOPPED") and not self.messagebox.askyesno(
                "Stop server", "Deinitialize/release NI tasks and stop this server?\n"
                "This is not an installation emergency stop.", parent=self.root):
            return
        try:
            self.runtime.request_shutdown(electrical_off_confirmed=self.confirm_local_off())
            self.closing = True
        except Exception as error:
            self.messagebox.showerror("Server stop refused", str(error), parent=self.root)

    def refresh(self):
        state = self.runtime.snapshot()
        self.status.set("{0} | NI tasks: {1} | {2}".format(state["state"], state["resource_count"], state["error"]))
        age = state["everest_read_age_seconds"]
        self.link.set("Everest reader: " + ("not seen" if age is None else "last signed read {0:.1f} s ago".format(age)))
        self.init_button.configure(state="normal" if state["state"] == "IDLE" and not self.closing else "disabled")
        self.recovery_button.configure(state="normal" if state["state"] == "RECOVERY_REQUIRED" and not self.closing else "disabled")
        self.general_button.configure(state="normal" if state["state"] == "RUNNING" and not self.closing else "disabled")
        can_stop = state["resource_count"] > 0 and (state["state"] in ("RUNNING", "FAULT") or
                   state["current_operation"] == "modulator.general.start")
        self.general_stop_button.configure(state="normal" if can_stop and not self.closing else "disabled")
        self.deinit_button.configure(state="disabled" if state["state"] in ("IDLE", "STOPPED", "DEINITIALIZING") else "normal")
        self.display.delete("1.0", "end")
        self.display.insert("end", json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True))
        if self.closing and state["state"] == "STOPPED" and self.runtime.join(0):
            self.server.shutdown()
            self.server.server_close()
            self.root.destroy()
            return
        if self.closing and state["state"] == "FAULT":
            self.closing = False  # Keep window/failed resources; operator can retry deinit.
        self.root.after(250, self.refresh)


def main(entrypoint, argv=None):
    import tkinter as tk
    from tkinter import messagebox
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.path.join(os.path.dirname(entrypoint), "config.acquisition.json"))
    parser.add_argument("--demo", action="store_true", help="Explicit no-hardware mode; no automatic fallback")
    args = parser.parse_args(argv)
    root = tk.Tk()
    runtime = server = thread = None
    try:
        config, key = load_configuration(args.config)
        profile = config.get("control_profile", "legacy_full")
        focal = config.get("focal_stop", {})
        ht = config.get("ht_shutdown", {})
        stage_verified = config.get("stage_controls_verified", False)
        trip_verified = config.get("cooling_trip_verified", False)
        ht_controls_verified = config.get("ht_controls_verified", False)
        focal_controls_verified = config.get("focal_controls_verified", False)
        source_flags = {name: config.get(name, False) for name in (
            "counter_controls_verified", "ht_voltage_controls_verified", "outer_stop_verified",
            "counter_timing_controls_verified", "beamline_controls_verified")}
        focal_command = (None if args.demo else
                         ChromaFocalCommand(focal.get("dll_path", DEFAULT_DLL),
                                            focal.get("resources_verified", False),
                                            focal.get("timeout_seconds", 10)))
        factory = ((lambda: DemoBackend(control_profile=profile,
                                       stage_controls_verified=stage_verified,
                                       ht_controls_verified=ht_controls_verified,
                                       focal_controls_verified=focal_controls_verified,
                                       cooling_trip_verified=trip_verified, **source_flags)) if args.demo else
                   lambda: CardBackend(read_timeout=config["read_timeout_seconds"],
                                       control_profile=profile,
                                       ht_feedback_verified=ht.get("feedback_verified", False),
                                       ht_zero_tolerance_kv=ht.get("zero_tolerance_kv", 0.0),
                                       ht_zero_timeout=ht.get("timeout_seconds", 10.0),
                                       stage_controls_verified=stage_verified,
                                       ht_controls_verified=ht_controls_verified,
                                       focal_controls_verified=focal_controls_verified,
                                       focal_command=focal_command,
                                       cooling_trip_verified=trip_verified, **source_flags))
        runtime = create_cold_runtime(factory, config["period_seconds"], args.config, demo=args.demo)
        # Binding guards against a second service window before starting a worker.
        server = RuntimeHTTPServer((config["bind_host"], config["port"]), runtime, key)
        runtime.start()  # Cold; factory is NOT called here.
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.1))
        thread.daemon = True
        thread.start()
        AcquisitionWindow(root, runtime, server, os.path.abspath(args.config), os.path.abspath(entrypoint),
                          args.demo, control_profile=profile)
    except Exception as error:
        # No event loop/buttons have run: the worker is still cold. Do not
        # strand a non-daemon idle owner after a UI/server startup failure.
        if runtime is not None:
            runtime.request_shutdown()
            runtime.join(3)
        if server is not None:
            if thread is not None and thread.is_alive():
                server.shutdown()
            server.server_close()
        messagebox.showerror("Acquisition server not started", str(error), parent=root)
        root.destroy()
        return 1
    root.mainloop()
    return 0
