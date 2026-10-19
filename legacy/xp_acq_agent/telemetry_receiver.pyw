"""Manual, loopback-only launcher for the copied LabVIEW telemetry receiver.

Python 3.4 standard library. No hardware backend, discovery or PSP access.
Opening this file does not start a listener; Start requires an operator click.
"""
from __future__ import print_function

import json
import os
import threading

from elyse_agent.config import load_config
from main import build_agent
from elyse_agent.telemetry_runtime import load_relay


def create_receiver():
    root_path = os.path.dirname(os.path.abspath(__file__))
    config = load_config(os.path.join(root_path, "config.labview-telemetry.json"))
    # Do not let a changed config silently open network or hardware access.
    config = dict(config, bind_host="127.0.0.1", command_port=8766,
                  allow_input_task_creation=False, allow_hardware_writes=False)
    return build_agent(config, telemetry_options=dict(session_id="acq-copy-20261012",
                                                      include_all_publications=True))


def main():
    import tkinter as tk
    window = tk.Tk()
    window.title("ACQ telemetry receiver - loopback only - NO NI / PSP")
    window.geometry("760x580")
    status = tk.StringVar(value="Stopped. Original Acquisition is not modified.")
    tk.Label(window, textvariable=status, anchor="w", wraplength=730).pack(fill="x", padx=10, pady=8)
    buttons = tk.Frame(window)
    buttons.pack(fill="x", padx=10)
    display = tk.Text(window, wrap="none")
    display.pack(fill="both", expand=True, padx=10, pady=10)
    current = {"server": None, "thread": None, "relay": None,
               "stopping": False, "closing": False, "shutdown_error": ""}

    def refresh():
        server = current["server"]
        if server is not None and not current["stopping"]:
            snapshot = server.router.labview_telemetry.snapshot()
            if current['relay'] is not None:
                snapshot['relay'] = current['relay'].status()
            display.delete("1.0", tk.END)
            display.insert(tk.END, json.dumps(snapshot, indent=2, sort_keys=True))
        if not current["closing"]:
            window.after(500, refresh)

    def start():
        if current["server"] is not None or current["stopping"]:
            return
        try:
            server, audit = create_receiver()
            try:
                relay = load_relay(os.path.dirname(os.path.abspath(__file__)),
                                   server.router.labview_telemetry.outbox)
            except Exception:
                server.server_close()
                raise
        except Exception as error:
            status.set("Not started: {0}".format(error))
            return
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1})
        thread.daemon = True
        try:
            thread.start()
            if relay is not None:
                relay.start()
        except Exception as error:
            if thread.is_alive():
                server.shutdown()
                thread.join(3)
            server.server_close()
            if relay is not None:
                relay.close()
            status.set("Not started: {0}".format(error))
            return
        current.update(server=server, relay=relay, thread=thread, shutdown_error="")
        status.set("Receiving on 127.0.0.1:8766; FIFO 1000 / 16 MiB (RAM). Everest relay {0}.".format(
            'enabled' if relay is not None else 'disabled'))

    def finish_stop():
        if current["thread"] is not None and current["thread"].is_alive():
            window.after(100, finish_stop)
            return
        error = current['shutdown_error']
        pending = current['server'].router.labview_telemetry.outbox.status()['pending']
        current.update(server=None, thread=None, relay=None, stopping=False)
        status.set("Stopped. {0} pending RAM messages discarded; no hardware owner. {1}".format(
            pending, error))
        if current["closing"]:
            window.destroy()

    def stop():
        if current["stopping"]:
            return
        server = current["server"]
        if server is None:
            if current["closing"]:
                window.destroy()
            return
        current["stopping"] = True
        status.set("Stopping telemetry listener only...")

        def shutdown():
            try:
                try:
                    server.shutdown()
                finally:
                    try:
                        server.server_close()
                    finally:
                        if current['relay'] is not None:
                            current['relay'].close()
            except Exception as error:
                current['shutdown_error'] = "Shutdown error: {0}".format(error)

        shutdown_thread = threading.Thread(target=shutdown)
        shutdown_thread.daemon = True
        current["thread"] = shutdown_thread
        shutdown_thread.start()
        window.after(100, finish_stop)

    def close():
        current["closing"] = True
        stop()

    tk.Button(buttons, text="Start telemetry receiver", command=start).pack(side="left")
    tk.Button(buttons, text="Stop receiver", command=stop).pack(side="left", padx=10)
    window.protocol("WM_DELETE_WINDOW", close)
    refresh()
    window.mainloop()


if __name__ == "__main__":
    main()
