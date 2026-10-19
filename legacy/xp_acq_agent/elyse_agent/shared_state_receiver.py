"""Loopback XML ingress and signed latest-snapshot relay. Python 3.4 stdlib.

Starting this receiver cannot start Acquisition, discover hardware or publish
PSP variables. The GUI has no hardware/control command routes.
"""

from __future__ import print_function

import json
import os
import socketserver
import struct
import threading
import time

from .protocol import recv_exact, send_message
from .shared_state import MAX_XML_BYTES, SharedStateStore
from .supervision_wire import validate_key
from .telemetry_relay import DeadlineSocket, TelemetryRelay


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        if self.client_address[0] != "127.0.0.1":
            return
        bounded = DeadlineSocket(self.request, time.monotonic() + 2)
        try:
            size = struct.unpack("!I", recv_exact(bounded, 4))[0]
            if not 1 <= size <= MAX_XML_BYTES:
                raise ValueError("invalid snapshot XML frame length")
            result = self.server.store.ingest(
                recv_exact(bounded, size), self.client_address[0]
            )
            reply = dict(id="shared-state", ok=True, result=result)
        except Exception as error:
            with self.server.store.lock:
                self.server.store.rejected += 1
                self.server.store.last_error = str(error)
            reply = dict(
                id="shared-state",
                ok=False,
                error=dict(code="snapshot_rejected", message=str(error)),
            )
        try:
            send_message(bounded, reply, MAX_XML_BYTES)
        except Exception:
            pass  # No positive delivery claim when local ACK is not delivered.


class SharedStateServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = False

    def __init__(self, address, store):
        if address[0] != "127.0.0.1":
            raise ValueError("shared-state ingress must be IPv4 loopback")
        self.store = store
        socketserver.TCPServer.__init__(self, address, _Handler)


def load_configuration(root):
    with open(os.path.join(root, "config.shared-state.json"), "r") as source:
        config = json.load(source)
    if (
        type(config) is not dict
        or set(config)
        != set(
            (
                "key_file",
                "everest_host",
                "everest_port",
                "producer_kind",
                "xml_encoding",
            )
        )
        or config["everest_host"] != "10.20.30.202"
        or type(config["everest_port"]) is not int
        or config["everest_port"] != 8767
        or config["producer_kind"] not in ("fixture", "copied_acquisition")
        or config["xml_encoding"] not in ("utf-8", "cp1252")
        or not isinstance(config["key_file"], str)
        or not config["key_file"]
    ):
        raise ValueError("invalid shared-state receiver configuration")
    key_file = config["key_file"]
    if not os.path.isabs(key_file):
        key_file = os.path.join(root, key_file)
    with open(key_file, "rb") as source:
        key = validate_key(source.read().strip())
    return config, key


def run_gui(root):
    import tkinter as tk

    window = tk.Tk()
    window.title("ACQ SHARED STATE - Python 3.4 - TELEMETRY ONLY / NO NI / PSP")
    window.geometry("900x630")
    status = tk.StringVar(value="Stopped. Does not start or stop Acquisition.")
    tk.Label(window, textvariable=status, wraplength=870, anchor="w").pack(
        fill="x", padx=10, pady=8
    )
    buttons = tk.Frame(window)
    buttons.pack(fill="x", padx=10)
    display = tk.Text(window, wrap="none")
    display.pack(fill="both", expand=True, padx=10, pady=10)
    current = dict(
        server=None, relay=None, thread=None, stopping=False, closing=False, error=""
    )

    def refresh():
        if current["server"] is not None and not current["stopping"]:
            snapshot = current["server"].store.snapshot()
            snapshot["relay"] = current["relay"].status()
            display.delete("1.0", tk.END)
            display.insert(tk.END, json.dumps(snapshot, indent=2, sort_keys=True))
        if not current["closing"]:
            window.after(500, refresh)

    def start():
        if current["server"] is not None or current["stopping"]:
            return
        server = relay = thread = None
        try:
            config, key = load_configuration(root)
            store = SharedStateStore(
                config["producer_kind"], xml_encoding=config["xml_encoding"]
            )
            relay = TelemetryRelay(
                store.outbox, (config["everest_host"], config["everest_port"]), key
            )
            server = SharedStateServer(("127.0.0.1", 8766), store)
            thread = threading.Thread(
                target=server.serve_forever, kwargs=dict(poll_interval=0.1)
            )
            thread.daemon = True
            thread.start()
            relay.start()
            current.update(server=server, relay=relay, thread=thread, error="")
            status.set(
                "27-bank XML snapshots: 127.0.0.1:8766 -> 10.20.30.202:8767. "
                "Latest pending plus one in-flight snapshot; RAM only. Producer: "
                + config["producer_kind"]
            )
        except Exception as error:
            if server is not None:
                if thread is not None and thread.is_alive():
                    server.shutdown()
                    thread.join(3)
                server.server_close()
            if relay is not None:
                relay.close()
            status.set("Not started: " + str(error))

    def stop():
        if current["stopping"]:
            return
        if current["server"] is None:
            if current["closing"]:
                window.destroy()
            return
        current["stopping"] = True
        status.set("Stopping telemetry bridge only; Acquisition is untouched.")

        def shutdown():
            try:
                current["server"].shutdown()
                current["server"].server_close()
                current["relay"].close()
            except Exception as error:
                current["error"] = str(error)

        worker = threading.Thread(target=shutdown)
        worker.daemon = True
        current["thread"] = worker
        worker.start()

        def finished():
            if current["thread"].is_alive():
                window.after(100, finished)
                return
            current.update(server=None, relay=None, thread=None, stopping=False)
            status.set("Stopped. Pending RAM snapshots discarded. " + current["error"])
            if current["closing"]:
                window.destroy()

        window.after(100, finished)

    def close():
        current["closing"] = True
        stop()

    tk.Button(buttons, text="Start telemetry bridge", command=start).pack(side="left")
    tk.Button(buttons, text="Stop telemetry bridge", command=stop).pack(
        side="left", padx=10
    )
    window.protocol("WM_DELETE_WINDOW", close)
    refresh()
    window.mainloop()
