"""Private headless NI child entrypoint; launched only by confirmed initialize.

The main thread alone constructs/calls CardBackend. Pipe reader and writer
threads perform no NI calls. Cancellation is cooperative; process death,
timeout or parent disappearance are never translated into physical OFF.
"""
import copy
import importlib
import os
import queue
import sys
import threading
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from elyse_agent.isolated_backend import OPERATIONS, CACHED_ATTRIBUTES
    from elyse_agent.isolated_wire import read_frame, write_frame, encode_frame, pack_value
else:
    from .isolated_backend import OPERATIONS, CACHED_ATTRIBUTES
    from .isolated_wire import read_frame, write_frame, encode_frame, pack_value


def _attributes(backend):
    if backend is None:
        return dict(resource_count=1)  # Failed constructor cannot certify release.
    result = {}
    for name in CACHED_ATTRIBUTES:
        if hasattr(backend, name):
            result[name] = copy.deepcopy(getattr(backend, name))
    return result


def _error(error):
    result = dict(type=type(error).__name__, message=str(error)[:4096])
    for name in ("report", "result", "failures", "error_code", "code"):
        if hasattr(error, name):
            value = getattr(error, name)
            try:
                pack_value(value)
            except Exception:
                result[name + "_unavailable_type"] = type(value).__name__
            else:
                result[name] = copy.deepcopy(value)
    return result


def _create_backend(configuration):
    if type(configuration) is not dict or set(configuration) != {
            "factory", "backend_options", "focal_options", "safe_sample_budget_seconds"}:
        raise ValueError("Exact private child configuration required")
    options, focal = configuration["backend_options"], configuration["focal_options"]
    if type(options) is not dict or type(focal) is not dict:
        raise ValueError("Inert backend/focal option dictionaries required")
    name = configuration["factory"]
    if name is None:
        if __package__ in (None, ""):
            from elyse_agent.acquisition_backend import CardBackend
            from elyse_agent.chroma_focal_command import ChromaFocalCommand
        else:
            from .acquisition_backend import CardBackend
            from .chroma_focal_command import ChromaFocalCommand
        return CardBackend(focal_command=ChromaFocalCommand(**focal), **options)
    # Trusted constructor seam for driver-free offline tests only. No public
    # operation can select/import a factory or submit executable code.
    if type(name) is not str or name.count(":") != 1:
        raise ValueError("Invalid trusted local factory name")
    module_name, attribute = name.split(":")
    if not attribute.isidentifier() or not all(part.isidentifier() for part in module_name.split(".")):
        raise ValueError("Importable top-level local factory required")
    factory = getattr(importlib.import_module(module_name), attribute)
    return factory(**options)


class Worker(object):
    def __init__(self, source, sink):
        self.source, self.sink = source, sink
        self.incoming = queue.Queue(maxsize=1)
        self.outgoing = queue.Queue(maxsize=2)
        self.cancel, self.disconnected = threading.Event(), threading.Event()
        self.state_lock = threading.Lock()
        self.active_id = self.cancelled_id = None
        self.backend, self.configuration = None, None

    def _emit(self, message, reliable=False):
        encode_frame(message)  # Reject oversized diagnostics before enqueue.
        done = threading.Event() if reliable else None
        try:
            self.outgoing.put((message, done), timeout=1 if reliable else 0)
        except queue.Full:
            if reliable:
                raise RuntimeError("Bounded child result pipe queue exhausted")
            return False  # Progress is latest/best-effort, never stalls NI.
        if reliable:
            deadline = time.monotonic() + 3
            while not done.wait(.02):
                if self.disconnected.is_set() or time.monotonic() >= deadline:
                    raise RuntimeError("Child result pipe write not confirmed")
        return True

    def _writer(self):
        try:
            while True:
                message, done = self.outgoing.get()
                write_frame(self.sink, message)
                if done is not None:
                    done.set()
        except Exception:
            self.disconnected.set()
            self.cancel.set()

    def _reader(self):
        try:
            while True:
                message = read_frame(self.source)
                request_id = message.get("id")
                if type(request_id) is not int or request_id <= 0:
                    raise ValueError("Positive child request ID required")
                if message.get("kind") == "cancel" and set(message) == {"kind", "id"}:
                    with self.state_lock:
                        self.cancelled_id = request_id
                        if self.active_id == request_id:
                            self.cancel.set()
                elif message.get("kind") == "call":
                    self.incoming.put_nowait(message)
                else:
                    raise ValueError("Unknown private child message")
        except Exception:
            self.disconnected.set()
            self.cancel.set()

    def _observe(self, event):
        if type(event) is not dict:
            return
        notice = copy.deepcopy(event)
        remaining = notice.get("remaining_seconds", 0)
        budget = self.configuration["safe_sample_budget_seconds"]
        if (budget is not None and notice.get("safe_to_sample") is True and type(remaining) in (int, float)
                and remaining >= budget + .05 and not self.cancel.is_set()):
            # Best effort on THIS NI main thread only. A driver overrun cannot
            # be preempted; never claim a hard deadline or pulse-width parity.
            started = time.monotonic()
            try:
                sample = self.backend.read_snapshot(self.cancel)
            except Exception as error:
                notice["sample_error"] = _error(error)
            else:
                notice["sample"] = sample
                notice["sample_started_monotonic"] = started
                notice["sample_completed_monotonic"] = time.monotonic()
                notice["sample_age_seconds"] = time.monotonic() - started
                notice["sample_duration_seconds"] = notice["sample_completed_monotonic"] - started
                notice["sample_time_interpretation"] = "Child-local duration; absolute monotonic origin not shared"
            notice["sampling_policy"] = "best_effort_same_owner_not_hard_realtime"
        self._emit(dict(kind="progress", id=self.active_id, event=notice,
                        attributes=_attributes(self.backend)))

    def _call(self, operation, arguments, keywords):
        if operation not in OPERATIONS or type(arguments) is not tuple or type(keywords) is not dict:
            raise ValueError("Explicit reviewed child operation required")
        counts = {"initialize": 0, "read_snapshot": 0, "general_start": 0, "general_stop": 0,
                  "execute_stage": 1, "execute_impulsion": 1, "set_ht_voltage": 1,
                  "configure_counter_timing": 1, "outer_controlled_stop": 0,
                  "execute_cooling_guard": 1, "close": 0}
        allowed_keywords = ({"startup_confirmed"} if operation == "initialize" else
                            {"operator_confirmed", "new_value"} if operation in ("execute_stage", "execute_impulsion") else
                            set() if operation in ("read_snapshot", "execute_cooling_guard", "close") else
                            {"operator_confirmed"})
        if len(arguments) != counts[operation] or set(keywords) - allowed_keywords:
            raise ValueError("Private child argument contract rejected")
        if self.backend is None:
            raise RuntimeError("No constructed child backend; release cannot be certified")
        method = getattr(self.backend, operation)
        if operation in ("initialize", "read_snapshot", "general_start"):
            return method(self.cancel, **keywords)
        if operation in ("execute_stage", "execute_impulsion", "set_ht_voltage",
                         "configure_counter_timing", "execute_cooling_guard"):
            return method(arguments[0], self.cancel, **keywords)
        return method(**keywords)

    def _retain_owner(self):
        if self.backend is None:
            return 2
        while True:
            threading.Event().wait(60)

    def run(self):
        for name, callback in (("ACQ-NI-child-ingress", self._reader), ("ACQ-NI-child-egress", self._writer)):
            worker = threading.Thread(target=callback, name=name)
            worker.daemon = True
            worker.start()
        while True:
            if self.disconnected.is_set():
                # Parent disappearance is NOT an authorization to release live
                # NI tasks. Retain the child and handles for qualified recovery.
                return self._retain_owner()
            try:
                message = self.incoming.get(timeout=.05)
            except queue.Empty:
                continue
            operation, request_id = message.get("operation"), message["id"]
            with self.state_lock:
                self.active_id = request_id
                self.cancel.clear()
                if self.cancelled_id == request_id:
                    self.cancel.set()
            result, error = None, None
            try:
                required = {"kind", "id", "operation", "arguments", "keywords"}
                if operation == "initialize":
                    required.add("configuration")
                if set(message) != required:
                    raise ValueError("Exact private request envelope required")
                if operation == "initialize":
                    if self.configuration is not None:
                        raise RuntimeError("A retained child backend cannot be replaced")
                    self.configuration = message["configuration"]
                    self.backend = _create_backend(self.configuration)
                    hook = getattr(self.backend, "set_execution_observer", None)
                    if hook is not None:
                        hook(self._observe)
                result = self._call(operation, message["arguments"], message["keywords"])
            except Exception as caught:
                error = _error(caught)
            try:
                attributes = _attributes(self.backend)
                self._emit(dict(kind="result", id=request_id, ok=error is None, value=result,
                                error=error, attributes=attributes), reliable=True)
            except Exception:
                # A failed/blocked pipe must not unwind the process and let
                # interpreter teardown silently release an existing NI owner.
                self.disconnected.set()
                self.cancel.set()
                return self._retain_owner()
            if operation == "close" and error is None and attributes.get("resource_count") == 0:
                return 0
            with self.state_lock:
                self.active_id = None


def main():
    # stdout is reserved exclusively for framed IPC. This executable does not
    # load NI, open a socket or create a backend until its initialize message.
    return Worker(sys.stdin.buffer, sys.stdout.buffer).run()


if __name__ == "__main__":
    # Python 3.4 finalization can wait forever for daemon stdin/stdout buffer
    # locks held by the IPC threads. main() returns zero ONLY after backend
    # close proved zero resources and its reply was fully flushed. Exit this
    # already-released child directly; never terminate an active NI operation.
    os._exit(main())
