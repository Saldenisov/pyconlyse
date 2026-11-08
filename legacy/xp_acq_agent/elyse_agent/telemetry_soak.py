"""Synthetic-only soak receiver. Python 3.4, RAM only, no hardware imports.

Local ACK acknowledges the XP FIFO, not Everest. Relay removes a FIFO head
only after the existing signed Everest ACK. Never use the public fixture key
for production telemetry.
"""
from __future__ import print_function

import json
import os
import socketserver
import threading
import time

from .labview_telemetry import LabviewTelemetryStore
from .protocol import recv_message, send_message
from .supervision_wire import validate_key
from .telemetry_relay import DeadlineSocket, TelemetryRelay


SESSION = 'acq-soak-20261012'
FRAME_LIMIT = 262144


class SoakStore(object):
    def __init__(self):
        self.telemetry = LabviewTelemetryStore(SESSION, include_all_publications=True)
        self.lock = threading.RLock()
        self.started = time.monotonic()
        self.accepted = self.duplicates = self.rejected = self.sequence_gaps = 0
        self.last_error = ''

    def dispatch(self, request, peer):
        request_id = request.get('id') if isinstance(request, dict) else None
        try:
            if (type(request) is not dict or set(request) != set(('id', 'command', 'params'))
                    or not isinstance(request_id, str) or not 1 <= len(request_id) <= 128
                    or request['command'] != 'ingest_labview_telemetry'):
                raise ValueError('synthetic soak accepts telemetry ingestion only')
            packet = request['params']
            if type(packet) is not dict or packet.get('producer_kind') != 'fixture':
                raise ValueError('soak receiver rejects non-fixture producers')
            with self.lock:
                before = self.telemetry.snapshot()['publications'].get(packet.get('publication'))
                result = self.telemetry.ingest(packet, peer)
                if result['duplicate']:
                    self.duplicates += 1
                else:
                    self.accepted += 1
                    if before:
                        self.sequence_gaps += max(0, packet['sequence'] - before['sequence'] - 1)
                self.last_error = ''
            return dict(id=request_id, ok=True, result=result)
        except Exception as error:
            with self.lock:
                self.rejected += 1
                self.last_error = str(error)
            return dict(id=request_id, ok=False,
                        error=dict(code='synthetic_soak_rejected', message=str(error)))

    def snapshot(self):
        with self.lock:
            result = self.telemetry.snapshot()
            result['soak'] = dict(synthetic_only=True, uptime_seconds=time.monotonic() - self.started,
                                  accepted=self.accepted, duplicates=self.duplicates,
                                  rejected=self.rejected, sequence_gaps=self.sequence_gaps,
                                  last_error=self.last_error, storage_mode='ram_latest_plus_bounded_fifo')
            return result


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        if self.client_address[0] != '127.0.0.1':
            return
        bounded = DeadlineSocket(self.request, time.monotonic() + 2)
        try:
            request = recv_message(bounded, FRAME_LIMIT)
            reply = self.server.store.dispatch(request, '127.0.0.1:{0}'.format(self.client_address[1]))
            send_message(bounded, reply, FRAME_LIMIT)
        except Exception:
            return  # No positive ACK; sender must treat transport failure as failure.


class SoakServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, store):
        if address[0] != '127.0.0.1':
            raise ValueError('soak listener must be loopback-only')
        self.store = store
        socketserver.TCPServer.__init__(self, address, _Handler)


def run_gui(root_path):
    import tkinter as tk
    window = tk.Tk()
    window.title('ACQ SYNTHETIC SOAK - Python 3.4 - NO NI / PSP')
    window.geometry('820x650')
    status = tk.StringVar(value='Stopped. Synthetic packets only. No acquisition VI is started.')
    tk.Label(window, textvariable=status, anchor='w', wraplength=790).pack(fill='x', padx=10, pady=8)
    buttons = tk.Frame(window)
    buttons.pack(fill='x', padx=10)
    display = tk.Text(window, wrap='none')
    display.pack(fill='both', expand=True, padx=10, pady=10)
    current = dict(server=None, relay=None, thread=None, stopping=False, closing=False)

    def refresh():
        if current['server'] is not None and not current['stopping']:
            snapshot = current['server'].store.snapshot()
            snapshot['relay'] = current['relay'].status()
            display.delete('1.0', tk.END)
            display.insert(tk.END, json.dumps(snapshot, indent=2, sort_keys=True))
        if not current['closing']:
            window.after(1000, refresh)

    def start():
        if current['server'] is not None or current['stopping']:
            return
        server = relay = None
        try:
            with open(os.path.join(root_path, 'telemetry_soak_fixture.key'), 'rb') as source:
                key = validate_key(source.read().strip())
            store = SoakStore()
            relay = TelemetryRelay(store.telemetry.outbox, ('10.20.30.202', 8767), key)
            server = SoakServer(('127.0.0.1', 8766), store)
            thread = threading.Thread(target=server.serve_forever, kwargs=dict(poll_interval=0.1))
            thread.daemon = True
            thread.start()
            relay.start()
            current.update(server=server, relay=relay, thread=thread)
            status.set('SYNTHETIC ONLY: 127.0.0.1:8766 -> 10.20.30.202:8767. RAM FIFO 1000 / 16 MiB.')
        except Exception as error:
            if server is not None:
                if 'thread' in locals() and thread.is_alive():
                    server.shutdown()
                    thread.join(3)
                server.server_close()
            if relay is not None:
                relay.close()
            status.set('Not started: {0}'.format(error))

    def stop():
        if current['stopping']:
            return
        if current['server'] is None:
            if current['closing']:
                window.destroy()
            return
        current['stopping'] = True
        status.set('Stopping synthetic transport only...')

        def shutdown():
            try:
                current['server'].shutdown()
                current['server'].server_close()
                current['relay'].close()
            finally:
                current['thread'] = None

        worker = threading.Thread(target=shutdown)
        worker.daemon = True
        current['thread'] = worker
        worker.start()

        def finished():
            if current['thread'] is not None:
                window.after(100, finished)
                return
            current.update(server=None, relay=None, stopping=False)
            status.set('Stopped. Pending RAM messages discarded. No hardware owner.')
            if current['closing']:
                window.destroy()
        window.after(100, finished)

    def close():
        current['closing'] = True
        stop()

    tk.Button(buttons, text='Start SYNTHETIC receiver and relay', command=start).pack(side='left')
    tk.Button(buttons, text='Stop SYNTHETIC transport', command=stop).pack(side='left', padx=10)
    window.protocol('WM_DELETE_WINDOW', close)
    refresh()
    window.mainloop()
