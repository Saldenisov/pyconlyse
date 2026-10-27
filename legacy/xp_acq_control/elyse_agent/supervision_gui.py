"""Three-button cold SuperVision host application; Python3.4."""
import argparse
import json
import math
import os
import threading

from .supervision_runtime import SupervisionRuntime, new_supervision_identity
from .supervision_imaq import source_video_configuration
from .supervision_cards import validate_initial_sync_values_us
from .acquisition_recovery import OwnershipMarker
from .acquisition_supervisor import FileInstanceGuard
from .command_http import ControlHTTPServer
from .application_view import ApplicationView, ApplicationShutdown, StartupCleanup


BUTTON_LABELS = ("Initialize", "Deinitialize", "Stop server")
CONFIGURATION_FIELDS = frozenset(("schema_version", "bind_host", "port", "read_key_file",
    "command_key_file", "remote_control_enabled", "counter_timing_controls_verified",
    "period_seconds", "read_timeout_seconds", "video", "telemetry"))


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (ValueError, OverflowError):
        return False


def default_supervision_configuration():
    return dict(schema_version=1, bind_host="10.20.30.2", port=8772,
        read_key_file="acquisition.key", command_key_file="acquisition.command.key",
        remote_control_enabled=False, counter_timing_controls_verified=False,
        vi_passive_shadow=False,
        period_seconds=.2, read_timeout_seconds=.5, video=source_video_configuration(),
        telemetry=dict(enabled=False, wire="federated_owner", host="10.20.30.202", port=8767,
                       period_seconds=.2))


def validate_supervision_configuration(value):
    if (type(value) is not dict or not CONFIGURATION_FIELDS <= set(value)
            or set(value) - CONFIGURATION_FIELDS - {"initial_sync_values_us", "vi_passive_shadow"} or value.get("schema_version") != 1):
        raise ValueError("Exact versioned SuperVision host configuration required")
    if type(value.get("vi_passive_shadow", False)) is not bool:
        raise ValueError("Exact Boolean vi_passive_shadow policy required")
    if "initial_sync_values_us" in value:
        if value["initial_sync_values_us"] is None:
            raise ValueError("Omit initial_sync_values_us or supply the full16-value local profile")
        validate_initial_sync_values_us(value["initial_sync_values_us"])
    if value["bind_host"] != "10.20.30.2" or type(value["port"]) is not int or value["port"] != 8772:
        raise ValueError("SuperVision serves only 10.20.30.2:8772")
    for name in ("remote_control_enabled", "counter_timing_controls_verified"):
        if type(value[name]) is not bool:
            raise ValueError("Exact Boolean configuration flag required: " + name)
    for name, low, high in (("period_seconds", .02, 10), ("read_timeout_seconds", .01, 2)):
        if not _finite(value[name]) or not low <= value[name] <= high:
            raise ValueError("Bounded SuperVision timing required: " + name)
    for name in ("read_key_file", "command_key_file"):
        item = value[name]
        if (type(item) is not str or not item or item in (".", "..")
                or os.path.basename(item) != item or "/" in item or "\\" in item or ":" in item
                or "\x00" in item):
            raise ValueError("Installation-local key basename required")
    video = value["video"]
    if (type(video) is not dict or set(video) != {"channel", "white_ref_volt", "black_ref_volt"}
            or type(video["channel"]) is not int or not 0 <= video["channel"] <= 3
            or any(not _finite(video[k]) for k in ("white_ref_volt", "black_ref_volt"))
            or not 0 <= video["white_ref_volt"] <= 1.3 or not 0 <= video["black_ref_volt"] <= 1):
        raise ValueError("Source-qualified NI1409 channel/reference configuration required")
    telemetry = value["telemetry"]
    if (type(telemetry) is not dict or set(telemetry) != {"enabled", "wire", "host", "port", "period_seconds"}
            or type(telemetry["enabled"]) is not bool
            or telemetry["wire"] not in ("legacy_27", "federated_owner")
            or telemetry["host"] != "10.20.30.202" or type(telemetry["port"]) is not int or telemetry["port"] != 8767
            or not _finite(telemetry["period_seconds"]) or not .05 <= telemetry["period_seconds"] <= 10):
        raise ValueError("Explicit fixed Everest telemetry configuration required")
    if telemetry["enabled"] and telemetry["wire"] != "federated_owner":
        raise ValueError("SuperVision cannot emit its local source into the old 27-bank receiver")
    return value


def load_supervision_configuration(path):
    with open(path, "r", encoding="utf-8") as stream:
        value = validate_supervision_configuration(json.load(stream))
    folder = os.path.dirname(os.path.abspath(path))
    keys = []
    for name in ("read_key_file", "command_key_file"):
        with open(os.path.join(folder, value[name]), "rb") as stream:
            key = stream.read(4097).strip()
        if not 32 <= len(key) <= 4096:
            raise ValueError("Bounded authentication key of at least 32 bytes required")
        keys.append(key)
    if keys[0] == keys[1]:
        raise ValueError("Read and command authentication keys must be distinct")
    return value, keys[0], keys[1]


class SupervisionWindow(object):
    def __init__(self, root, view, runtime, shutdown):
        import tkinter as tk
        from tkinter import messagebox
        self.root, self.view, self.runtime, self.shutdown = root, view, runtime, shutdown
        self.messagebox = messagebox
        self.closing = False
        root.title("ELYSE SuperVision Orchestrator - Python 3.4")
        root.geometry("1000x680")
        self.status, self.link = tk.StringVar(), tk.StringVar()
        for variable in (self.status, self.link):
            tk.Label(root, textvariable=variable, anchor="w", justify="left", wraplength=970).pack(fill="x", padx=12, pady=5)
        row = tk.Frame(root)
        row.pack(fill="x", padx=12, pady=10)
        self.buttons = []
        for text, callback in zip(BUTTON_LABELS, (self.initialize, self.deinitialize, self.request_close)):
            button = tk.Button(row, text=text, command=callback)
            button.pack(side="left", padx=6)
            self.buttons.append(button)
        tk.Label(root, anchor="w", justify="left", text=
            "This cold host owns only SuperVision Dev1 NI6602 and img0 NI1409 after explicit Initialize.\n"
            "Initialize starts all eight source synchronization tasks and raw camera capture.\n"
            "LabVIEW must first release these boards. A quiet network does not prove release.\n"
            "Deinitialize stops local synchronization/camera tasks; it does not shut down the accelerator.\n"
            "Retained or uncertain workers are never automatically restarted.").pack(fill="x", padx=12)
        self.display = tk.Text(root, wrap="none", font=("Courier", 9))
        self.display.pack(fill="both", expand=True, padx=12, pady=10)
        root.protocol("WM_DELETE_WINDOW", self.request_close)
        root.after(200, self.refresh)

    def initialize(self):
        value = self.view.snapshot()
        if self.runtime.vi_passive_shadow or value.get("vi_passive_shadow") is True:
            return
        if value.get("state") != "IDLE" or value.get("recovery", {}).get("required"):
            return
        if not self.messagebox.askyesno("Initialize SuperVision boards", 
            "Confirm SuperVision VI and all other local NI clients have normally stopped and released Dev1/img0.\n\n"
            "The experiment is OFF and initialization of the eight synchronization outputs and camera is now authorized.\n"
            "This changes hardware timing and begins raw frame capture. Initialize both local boards?", parent=self.root):
            return
        try:
            self.view.initialize(startup_confirmed=True)
        except Exception as error:
            self.messagebox.showerror("Initialization not accepted", str(error), parent=self.root)

    def deinitialize(self):
        if not self.messagebox.askyesno("Stop local synchronization and camera", 
            "Confirm the experiment is OFF and the local synchronization outputs can be stopped.\n"
            "Release the two boards normally? This does not send General/HT commands.", parent=self.root):
            return
        try:
            self.view.deinitialize(electrical_off_confirmed=True)
        except Exception as error:
            self.messagebox.showerror("Deinitialization not accepted", str(error), parent=self.root)

    def request_close(self):
        if self.closing:
            return
        value = self.view.snapshot()
        confirmed = not value.get("resource_count") and value.get("state") in ("IDLE", "RECOVERY_REQUIRED", "STOPPED")
        if not confirmed:
            confirmed = self.messagebox.askyesno("Stop SuperVision host", 
                "Confirm the experiment is OFF and local synchronization/camera tasks may be stopped and released.\n"
                "No other computer or accelerator stage will be stopped by this action.", parent=self.root)
        if confirmed:
            self.closing = True
            try:
                self.view.request_shutdown(electrical_off_confirmed=True)
            except Exception as error:
                self.closing = False
                self.messagebox.showerror("Shutdown not accepted", str(error), parent=self.root)

    def refresh(self):
        value = self.view.snapshot()
        self.status.set("{0} | {1} | local NI resources: {2} | {3}".format(
            value.get("state"), value.get("owner_mode", "UNKNOWN"), value.get("resource_count"), value.get("error", "")))
        delivery = value.get("telemetry_delivery", {})
        self.link.set("Everest telemetry: {0} | ACK: {1} | {2}".format(
            "enabled" if delivery.get("enabled") else "DISABLED (requires federated Device Server)",
            delivery.get("everest_acknowledged", 0), delivery.get("last_error", "")))
        current = value.get("application_view_current") and not value.get("local_request_pending") and not self.closing
        self.buttons[0].configure(state="normal" if not self.runtime.vi_passive_shadow
                                  and value.get("vi_passive_shadow") is not True
                                  and current and value.get("state") == "IDLE"
                                  and value.get("recovery", {}).get("required") is False else "disabled")
        self.buttons[1].configure(state="normal" if current and value.get("resource_count")
            and value.get("state") in ("RUNNING", "FAULT") else "disabled")
        self.display.delete("1.0", "end")
        self.display.insert("end", json.dumps(value, sort_keys=True, indent=2))
        if self.closing and value.get("state") == "STOPPED" and self.runtime.join(0):
            self.shutdown.start()
            if self.shutdown.completed:
                self.root.destroy()
                return
            if self.shutdown.error:
                self.link.set(self.shutdown.error)
        if self.closing and (value.get("state") == "FAULT" or value.get("local_request_error")):
            self.closing = False
        self.root.after(250, self.refresh)


def main(entrypoint, argv=None, publisher_factory=None):
    import tkinter as tk
    from tkinter import messagebox
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.path.join(os.path.dirname(entrypoint), "config.supervision.control.json"))
    options = parser.parse_args(argv)
    root = tk.Tk()
    runtime = server = view = publisher = guard = server_thread = None
    try:
        config, read_key, command_key = load_supervision_configuration(options.config)
        guard = FileInstanceGuard(os.path.abspath(options.config) + ".application.lock")
        guard.acquire()
        identity = new_supervision_identity()
        marker = OwnershipMarker(os.path.abspath(options.config) + ".ownership",
                                 identity["session_id"], identity["build_id"])
        runtime = SupervisionRuntime(identity=identity, recovery_guard=marker,
            vi_passive_shadow=config.get("vi_passive_shadow", False),
            remote_enabled=config["remote_control_enabled"],
            counter_timing_controls_verified=config["counter_timing_controls_verified"],
            video_configuration=config["video"], period=config["period_seconds"],
            read_timeout=config["read_timeout_seconds"],
            trusted_service_options={"sync": {"initial_sync_values_us": config["initial_sync_values_us"]}}
                if "initial_sync_values_us" in config else None)
        view = ApplicationView(runtime)
        server = ControlHTTPServer((config["bind_host"], config["port"]), view, read_key,
                                   command_key if config["remote_control_enabled"] else None)
        telemetry = config["telemetry"]
        if telemetry["enabled"]:
            if publisher_factory is None:
                from .supervision_vi_telemetry import SupervisionTelemetryPublisher
                publisher_factory = SupervisionTelemetryPublisher
            publisher = publisher_factory(runtime, (telemetry["host"], telemetry["port"]), read_key,
                period=telemetry["period_seconds"], role="supervision")
            runtime.telemetry_publisher = publisher
        runtime.start()
        view.start()
        view.capture_once()
        server_thread = threading.Thread(target=server.serve_forever, name="SUPERVISION-authenticated-HTTP")
        server_thread.daemon = True
        server_thread.start()
        if publisher is not None:
            publisher.start()
        shutdown = ApplicationShutdown(runtime, server, view, guard)
        SupervisionWindow(root, view, runtime, shutdown)
    except Exception as error:
        messagebox.showerror("SuperVision host not started", str(error), parent=root)
        cleanup = StartupCleanup(runtime=runtime, server=server, view=view,
            publisher=publisher, server_thread=server_thread, application_guard=guard)
        cleanup.start()
        root.destroy()
        return
    root.mainloop()
