"""Separate Python 3.4 window: Initialize / Deinitialize / Stop server only."""
import argparse
import json
import os
import threading
import getpass

from .acquisition_gui import AcquisitionWindow, load_configuration
from .acquisition_backend import DemoBackend
from .acquisition_control_runtime import AcquisitionControlRuntime, control_identity
from .acquisition_recovery import OwnershipMarker
from .command_http import ControlHTTPServer
from .chroma_focal_stop import DEFAULT_DLL
from .cooling_safety import CoolingSafety
from .dual_mode_telemetry import DualModeTelemetryPublisher
from .application_view import ApplicationView, ApplicationShutdown, StartupCleanup
from .isolated_backend import IsolatedCardBackend
from .handover_recovery import LocalHandoverVerifier, HANDOVER_CONFIRMATION
from .acquisition_supervisor import FileInstanceGuard

BUTTON_LABELS = ("Initialize", "Deinitialize", "Stop server")


def application_alarm_text(state):
    """A local lifecycle error must never hide a circulation countdown."""
    alarm = state["cooling_safety"]
    messages = []
    if alarm["active"]:
        messages.append("COOLING FAULT: " + ", ".join(item["circuit"] for item in alarm["circuits"]) +
            " | countdown: {0:.0f}s | stop: {1}".format(alarm["remaining_seconds"], alarm["stop_state"]) +
            (" | AUTOMATIC STOP UNAVAILABLE" if not alarm["automatic_stop_available"] else ""))
    history = alarm.get("journal_history_warning", "")
    if history:
        messages.append("JOURNAL HISTORY (click to acknowledge): " + history)
    for error in (alarm.get("journal_storage_error", alarm["journal_error"]),
                  state.get("local_request_error"), state.get("application_view_error")):
        if error and error not in messages:
            messages.append(error)
    return " | ".join(messages)


def initialize_available(state, closing=False):
    """UI eligibility is informational; runtime repeats every ownership fence."""
    return bool(not closing and state.get("application_view_current", True)
        and not state.get("local_request_pending")
        and not state.get("telemetry_delivery", {}).get("vi_initialize_exclusion_active", False)
        and (state.get("state") == "IDLE"
             or state.get("state") == "RECOVERY_REQUIRED" and state.get("local_handover_available") is True))


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
    def __init__(self, root, runtime, server, config_path, entrypoint, demo=False, application_guard=None):
        import tkinter as tk
        from tkinter import messagebox
        self.tk, self.messagebox = tk, messagebox
        self.root, self.runtime, self.server = root, runtime, server
        self.config_path, self.entrypoint, self.demo = config_path, entrypoint, demo
        self.closing = False
        self._journal_prompted = False
        self.shutdown = ApplicationShutdown(getattr(runtime, "runtime", runtime), server, runtime,
                                             application_guard=application_guard)
        root.title("ELYSE Acquisition Control - Python 3.4" + (" - DEMO / NO HARDWARE" if demo else ""))
        root.geometry("1000x680")
        self.status, self.link, self.alarm = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for variable in (self.status, self.link):
            tk.Label(root, textvariable=variable, anchor="w").pack(fill="x", padx=12, pady=5)
        self.alarm_label = tk.Label(root, textvariable=self.alarm, fg="red", anchor="w", wraplength=960,
                                   justify="left")
        self.alarm_label.pack(fill="x", padx=12)
        self.alarm_label.bind("<Button-1>", lambda event: self.acknowledge_journal_history())
        controls = tk.Frame(root)
        controls.pack(fill="x", padx=12, pady=10)
        self.init_button = tk.Button(controls, text=BUTTON_LABELS[0], command=self.initialize)
        self.deinit_button = tk.Button(controls, text=BUTTON_LABELS[1], command=self.deinitialize)
        self.close_button = tk.Button(controls, text=BUTTON_LABELS[2], command=self.request_close)
        for button in (self.init_button, self.deinit_button, self.close_button):
            button.pack(side="left", padx=6)
        tk.Label(root, text="Stage control belongs to the Everest Tango Device Server. Opening this window does not initialize cards.\n"
                 "Deinitialize releases tasks; it is NOT electrical shutdown. Failed or unconfirmed stops retain ownership.\n"
                 "Prior ownership is reviewed through Initialize after VI stop; explicit local release/OFF confirmation required.\n"
                 "Click a journal history notice to acknowledge it without deleting history. No automatic replay/reinitialization.",
                 justify="left", anchor="w").pack(fill="x", padx=12)
        self.display = tk.Text(root, wrap="none", font=("Courier", 9))
        self.display.pack(fill="both", expand=True, padx=12, pady=10)
        root.protocol("WM_DELETE_WINDOW", self.request_close)
        root.after(200, self.refresh)

    def initialize(self):
        state = self.runtime.snapshot()
        if not initialize_available(state, self.closing):
            self.messagebox.showerror("Initialization refused",
                "Current metadata, quiet VI transport and cold card ownership are required.\n"
                "Stop LabVIEW Acquisition normally and release its NI tasks first.", parent=self.root)
            return
        if state["state"] != "RECOVERY_REQUIRED":
            return AcquisitionWindow.initialize(self)
        if not self.messagebox.askyesno("Confirm local ownership handover and NI startup",
                "This server has not created a native worker. A PRIOR ownership marker remains.\n\n"
                "Confirm ALL of the following:\n"
                "- LabVIEW Acquisition is normally STOPPED and its NI tasks are released.\n"
                "- ALL other NI clients have released their tasks. A quiet VI link is NOT proof.\n"
                "- General, Chauffage, PREMA, Focales and HT are physically OFF locally.\n\n"
                "Process metadata will check the prior parent and other Python/known NI clients.\n"
                "It does NOT inspect driver task handles or independently prove electrical OFF.\n"
                "The old marker is archived before the software barrier is removed.\n\n"
                "Then Initialize configures all 11 cards, starts legacy counters and applies fixed AO/DO startup values.\n"
                "Proceed with this local handover AND initialization?", parent=self.root):
            return
        try:
            self.runtime.initialize_after_handover(startup_confirmed=True, electrical_off_confirmed=True,
                confirmation=HANDOVER_CONFIRMATION, operator=getpass.getuser())
        except Exception as error:
            self.messagebox.showerror("Local handover refused; no automatic retry", str(error), parent=self.root)

    def acknowledge_journal_history(self):
        state = self.runtime.snapshot()
        alarm = state["cooling_safety"]
        if (self.closing or not state.get("application_view_current", True)
                or state.get("local_request_pending") or not alarm.get("journal_history_acknowledge_available")):
            return
        self._journal_prompted = True
        if not self.messagebox.askyesno("Acknowledge prior alarm journal notice",
                alarm["journal_history_warning"] + "\n\n"
                "This concerns an OLD writer, not current NI ownership.\n"
                "Acknowledgment archives this notice durably; it does NOT reconstruct missing events,\n"
                "delete history, clear cooling incidents, reset countdowns or hide current disk errors.\n"
                "A new unclean writer session will generate a NEW notice.\n\n"
                "Acknowledge the displayed historical uncertainty?", parent=self.root):
            return
        try:
            self.runtime.acknowledge_journal_history(operator=getpass.getuser(),
                reason="Local operator acknowledged prior writer uncertainty; missing events not reconstructed",
                expected_revision=alarm["journal_revision"])
        except Exception as error:
            self.messagebox.showerror("Journal acknowledgment not committed", str(error), parent=self.root)

    def refresh(self):
        state = self.runtime.snapshot()
        native = state.get("native_isolation", {})
        count = ("UNKNOWN (ownership retained)" if native.get("resource_count_interpretation")
                 == "UNKNOWN_RETAINED_OWNERSHIP_SENTINEL" else str(state["resource_count"]))
        self.status.set("{0} | NI resources: {1} | {2}".format(state["state"], count, state["error"]))
        age = state["everest_read_age_seconds"]
        delivery = state.get("telemetry_delivery", {})
        self.link.set("{0} | Everest telemetry ACK: {1} | {2} | ".format(delivery.get("source_mode", "DISABLED"), delivery.get("everest_acknowledged", 0),
                      delivery.get("publisher_error") or delivery.get("last_error", "publisher disabled")) +
                      ("command channel not seen" if age is None else "last signed read {0:.1f}s ago".format(age)) +
                      " | Commands: " + ("enabled / commissioned gates still apply" if state["control"]["enabled"] else "DISABLED"))
        self.alarm.set(application_alarm_text(state))
        metadata_current = state.get("application_view_current", True) and not state.get("local_request_pending")
        self.init_button.configure(state="normal" if initialize_available(state, self.closing) else "disabled")
        self.deinit_button.configure(state="normal" if state["resource_count"] and not self.closing
                                     and metadata_current
                                     and state["state"] not in ("DEINITIALIZING", "INITIALIZING", "EXECUTING") else "disabled")
        self.display.delete("1.0", "end")
        self.display.insert("end", json.dumps(state, sort_keys=True, indent=2))
        if self.closing and state["state"] == "STOPPED" and self.runtime.join(0):
            self.shutdown.start()
            if self.shutdown.completed:
                self.root.destroy()
                return
            if self.shutdown.error:
                self.alarm.set(self.shutdown.error)
            self.root.after(250, self.refresh)
            return
        if self.closing and state["state"] == "FAULT":
            self.closing = False
        if self.closing and state.get("local_request_error"):
            self.closing = False
        if (not self._journal_prompted and not self.closing and metadata_current
                and state["state"] in ("IDLE", "RECOVERY_REQUIRED") and not state["resource_count"]
                and state["cooling_safety"].get("journal_history_acknowledge_available")):
            self._journal_prompted = True
            self.root.after(0, self.acknowledge_journal_history)
        self.root.after(250, self.refresh)


def main(entrypoint, argv=None):
    import tkinter as tk
    from tkinter import messagebox
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.path.join(os.path.dirname(entrypoint), "config.acquisition.control.json"))
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args(argv)
    root = tk.Tk()
    runtime = server = thread = publisher = view = cooling = application_guard = None
    try:
        base, read_key, command_key, control = load_control_configuration(args.config)
        # Before opening ANY SQLite writer. The port alone is too late: a
        # second GUI must not dirty the first instance's journal on failed boot.
        application_guard = FileInstanceGuard(os.path.abspath(args.config) + ".application.lock")
        application_guard.acquire()
        flags = {name: base.get(name, False) for name in (
            "stage_controls_verified", "cooling_trip_verified", "ht_controls_verified", "focal_controls_verified",
            "counter_controls_verified", "counter_timing_controls_verified", "ht_voltage_controls_verified", "outer_stop_verified")}
        ht, focal = base.get("ht_shutdown", {}), base.get("focal_stop", {})
        profile = base.get("control_profile", "legacy_full")
        if args.demo:
            factory = lambda: DemoBackend(control_profile=profile, **flags)
        else:
            backend_options = dict(flags, read_timeout=base["read_timeout_seconds"], control_profile=profile,
                ht_feedback_verified=ht.get("feedback_verified", False), ht_zero_tolerance_kv=ht.get("zero_tolerance_kv", 0),
                ht_zero_timeout=ht.get("timeout_seconds", 10))
            focal_options = dict(dll_path=focal.get("dll_path", DEFAULT_DLL),
                resources_verified=focal.get("resources_verified", False), timeout=focal.get("timeout_seconds", 10))
            # Cold facade; the child/native backend is created only by an
            # explicitly accepted Initialize on the existing runtime owner.
            # Unqualified aggregate reads are not inserted into VI dwell times.
            factory = lambda: IsolatedCardBackend(backend_options, focal_options,
                                                   safe_sample_budget_seconds=None)
        identity = control_identity()
        handover = None if args.demo else LocalHandoverVerifier()
        guard = None if args.demo else OwnershipMarker(os.path.abspath(args.config) + ".ownership",
            identity["session_id"], identity["build_id"], quiescence_checker=handover)
        cooling = CoolingSafety()  # RAM-only until both fixed endpoints are owned.
        runtime = AcquisitionControlRuntime(factory, period=base["period_seconds"], identity=identity,
            recovery_guard=guard, handover_verifier=handover,
            remote_enabled=control["remote_control_enabled"], cooling=cooling,
            cooling_polarity_verified=control["cooling_safety"]["polarity_verified"])
        view = ApplicationView(runtime)
        server = ControlHTTPServer((base["bind_host"], base["port"]), view, read_key, command_key)
        if control["telemetry"]["enabled"]:
            publisher = DualModeTelemetryPublisher(runtime,
                (control["telemetry"]["host"], control["telemetry"]["port"]), read_key,
                period=control["telemetry"]["period_seconds"])
            runtime.telemetry_publisher = publisher
            publisher.start()
        # A leftover old bridge on 8766 or old unified server on 8772 now
        # refuses startup BEFORE touching the live alarm journal.
        if not args.demo:
            cooling.attach_owned_journal(control["cooling_safety"]["journal_file"],
                                         "xp_acquisition_control")
        runtime.start()
        view.start()
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.1))
        thread.daemon = True
        thread.start()
        ControlWindow(root, view, server, args.config, entrypoint, args.demo,
                      application_guard=application_guard)
    except Exception as error:
        # Even a bind error may follow creation of a non-daemon alarm writer.
        # Keep a visible three-button failure window until ALL joins finish.
        failure = str(error)
        for widget in root.winfo_children():
            widget.destroy()
        cleanup = StartupCleanup(runtime=runtime, server=server, view=view,
                                 publisher=publisher, cooling=cooling, server_thread=thread,
                                 application_guard=application_guard)
        root.title("ELYSE Acquisition Control - startup failed")
        error_text = tk.StringVar(value=failure)
        tk.Label(root, textvariable=error_text, wraplength=900, justify="left").pack(padx=12, pady=12)
        for label in BUTTON_LABELS[:2]:
            tk.Button(root, text=label, state="disabled").pack(side="left", padx=6)
        tk.Button(root, text=BUTTON_LABELS[2], command=cleanup.start).pack(side="left", padx=6)
        root.protocol("WM_DELETE_WINDOW", cleanup.start)
        def finish_failed_start():
            if cleanup.completed:
                root.destroy()
                return
            error_text.set(failure + "\n" + "\n".join(cleanup.errors))
            root.after(250, finish_failed_start)
        cleanup.start()
        root.after(250, finish_failed_start)
        root.mainloop()
        return 1
    root.mainloop()
    return 0
