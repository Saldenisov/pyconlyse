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
import datetime
import json
import uuid
import math

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from elyse_agent.isolated_backend import OPERATIONS, CACHED_ATTRIBUTES
    from elyse_agent.isolated_wire import read_frame, write_frame, encode_frame, pack_value, windows_polling_pipe
else:
    from .isolated_backend import OPERATIONS, CACHED_ATTRIBUTES
    from .isolated_wire import read_frame, write_frame, encode_frame, pack_value, windows_polling_pipe


def _attributes(backend, trace=None):
    if backend is None:
        return dict(resource_count=1)  # Failed constructor cannot certify release.
    result = {}
    for name in CACHED_ATTRIBUTES:
        if trace is not None:
            trace(dict(phase="ENTER", call="attribute:" + name))
        if hasattr(backend, name):
            result[name] = copy.deepcopy(getattr(backend, name))
        if trace is not None:
            trace(dict(phase="RETURNED", call="attribute:" + name))
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
        self.owner_thread = threading.current_thread().ident
        self.diagnostic_phase = "WAITING_FOR_INITIALIZE"
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.initialization_trace_path = os.path.join(root, "runtime",
            "initialize_{0}_{1}.jsonl".format(os.getpid(), uuid.uuid4().hex[:8]))
        self.initialization_trace_error = ""
        self.ingress_worker = None
        self.software_pending = None
        self.software_lock = threading.Lock()
        self.request_started = None
        self.initialization_status_sent_at = 0.

    def _trace_initialization(self, event):
        """Explicit startup diagnostics only; no measurements or native I/O.

        Record before and after native calls AND result serialization. An ENTER
        record alone is not proof of applied effects. Storage failures are
        visible but must never skip native cleanup or abandon a returned handle.
        """
        record = {name: event[name] for name in ("phase", "call", "card", "error", "error_code",
            "initialization_cards") if name in event}
        record.update(utc=event.get("utc", datetime.datetime.now(datetime.timezone.utc).isoformat()), pid=os.getpid())
        try:
            parent = os.path.dirname(self.initialization_trace_path)
            if not os.path.isdir(parent):
                os.makedirs(parent)
            with open(self.initialization_trace_path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except Exception as error:
            self.initialization_trace_error = type(error).__name__ + ": " + str(error)

    def _initialization_diagnostic(self):
        """Stack metadata only: never inspect locals, poll NI, or claim progress.

        A ctypes call normally releases the GIL, allowing this observer to show
        its Python call site. A native call holding the GIL can also block the
        observer; absence of notices is NOT evidence of cancellation or release.
        """
        with self.state_lock:
            request_id, phase = self.active_id, self.diagnostic_phase
        if request_id is None or phase not in ("CONSTRUCT_BACKEND", "PREPARE_DEPENDENCIES", "INITIALIZE_BACKEND"):
            return None
        frame = sys._current_frames().get(self.owner_thread)
        try:
            # Metadata only. traceback.extract_stack also reads source files
            # through linecache, which can trigger imports or block on disk.
            stack = []
            while frame is not None and len(stack) < 16:
                stack.append(dict(filename=frame.f_code.co_filename,
                                  line=frame.f_lineno, function=frame.f_code.co_name))
                frame = frame.f_back
            stack.reverse()
        finally:
            del frame
        attributes = {}
        if self.backend is not None:
            attributes = dict(initialization_cards=copy.deepcopy(getattr(self.backend, "initialization_cards", None)),
                startup_complete=getattr(self.backend, "startup_complete", None),
                resource_count=self.backend.resource_count)
        return dict(kind="progress", id=request_id, attributes=attributes, event=dict(
            kind="INITIALIZATION_DIAGNOSTIC_NOT_MEASUREMENT", operation="initialize",
            phase=phase, stack=stack, hardware_acknowledged=False, safe_to_sample=False))

    def _diagnostic_watch(self):
        while not self.disconnected.wait(1.):
            notice = self._initialization_diagnostic()
            if notice is not None:
                # Serialize admission with terminal phase transition: a late
                # diagnostic must never appear after this request's result.
                with self.state_lock:
                    if (self.active_id == notice["id"] and self.diagnostic_phase
                            in ("CONSTRUCT_BACKEND", "PREPARE_DEPENDENCIES", "INITIALIZE_BACKEND")):
                        self._emit(notice)

    def _publish_idle_initialization_status(self):
        """Report late card returns in RAM; never finish/retry startup or read NI."""
        if self.backend is None or getattr(self.backend, "startup_complete", None) is not False:
            return
        now = time.monotonic()
        if now - self.initialization_status_sent_at < .2:
            return
        report = getattr(self.backend, "initialization_cards", None)
        if type(report) is not dict:
            return
        self.initialization_status_sent_at = now
        owner = getattr(self.backend, "owner", None)
        coordinator = getattr(owner, "parallel_initialization", owner)
        publish = getattr(coordinator, "publish", None)
        if callable(publish):
            def record_boundary(event):
                if event.get("kind") == "INITIALIZATION_CALL_BOUNDARY_NOT_MEASUREMENT":
                    self._trace_initialization(event)
            publish(record_boundary)
        self._emit(dict(kind="initialization_status", attributes=dict(
            initialization_cards=report, startup_complete=False,
            resource_count=self.backend.resource_count)))

    def _emit(self, message, reliable=False):
        event = message.get("event")
        if (type(event) is dict and self.request_started is not None
                and ("sample" in event or event.get("kind") == "SOFTWARE_STATE_NOT_MEASUREMENT")):
            now = time.monotonic()
            event["observation_after_request_seconds"] = now - self.request_started
            if event.get("kind") == "SOFTWARE_STATE_NOT_MEASUREMENT":
                observed = event.pop("software_state_observed_monotonic", now)
                if type(observed) in (int, float) and math.isfinite(observed):
                    event["software_observed_after_request_seconds"] = observed - self.request_started
                    event["software_state_age_seconds"] = max(0., now - observed)
        encode_frame(message)  # Reject oversized diagnostics before enqueue.
        if (not reliable and message.get("kind") == "progress" and type(event) is dict
                and event.get("kind") == "SOFTWARE_STATE_NOT_MEASUREMENT"):
            # Software state has a separate latest-only slot. Diagnostic or
            # sample traffic must not erase the last EPS/DPS observation.
            event.setdefault("software_state_age_seconds", 0.)
            with self.software_lock:
                self.software_pending = (copy.deepcopy(message), time.monotonic())
            return True
        done = threading.Event() if reliable else None
        try:
            self.outgoing.put((message, done, time.monotonic()), timeout=1 if reliable else 0)
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
                try:
                    entry = self.outgoing.get(timeout=.02)
                except queue.Empty:
                    entry = None
                with self.software_lock:
                    pending, self.software_pending = self.software_pending, None
                if pending is not None:
                    software, created = pending
                    software["event"]["software_state_age_seconds"] += max(0., time.monotonic() - created)
                    write_frame(self.sink, software)
                if entry is None:
                    continue
                message, done, created = entry
                event = message.get("event")
                if type(event) is dict and "sample" in event:
                    event["sample_age_seconds"] += max(0., time.monotonic() - created)
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

    def _start_ingress(self):
        if self.ingress_worker is None:
            self.ingress_worker = threading.Thread(target=self._reader, name="ACQ-NI-child-ingress")
            self.ingress_worker.daemon = True
            self.ingress_worker.start()

    def _await_initialization_activation(self):
        """No card task before the parent accepts prepared modules/metadata.

        Read on this main thread; the stdin pump is still absent. Cancellation
        queued while imports ran is consumed here, not raced against Task calls.
        EOF or malformed activation fails before native initialization.
        """
        self._emit(dict(kind="initialize_ready", id=self.active_id,
                        attributes=dict(resource_count=0)), reliable=True)
        while True:
            message = read_frame(self.source)
            if type(message.get("id")) is not int or message["id"] != self.active_id:
                raise ValueError("Initialization activation request ID mismatch")
            if message.get("kind") == "cancel" and set(message) == {"kind", "id"}:
                self.cancel.set()
                continue
            if (message.get("kind") != "activate_initialize"
                    or set(message) != {"kind", "id", "cancelled"}
                    or type(message["cancelled"]) is not bool):
                raise ValueError("Exact private initialization activation required")
            if message["cancelled"]:
                self.cancel.set()
            return

    def _observe(self, event):
        if type(event) is not dict:
            return
        notice = copy.deepcopy(event)
        if notice.get("kind") in ("INITIALIZATION_CARD_STATUS_NOT_MEASUREMENT",
                                  "INITIALIZATION_CALL_BOUNDARY_NOT_MEASUREMENT"):
            self._trace_initialization(notice)
            notice.update(trace_path=self.initialization_trace_path,
                          trace_error=self.initialization_trace_error)
            self._emit(dict(kind="progress", id=self.active_id, event=notice,
                            attributes=_attributes(self.backend)))
            return  # Initialization status must never trigger input reads.
        if notice.get("kind") == "SOFTWARE_STATE_NOT_MEASUREMENT":
            self._emit(dict(kind="progress", id=self.active_id, event=notice,
                            attributes=_attributes(self.backend)))
            return  # No input reads on a software-only assignment callback.
        self._publish_software_observation()
        remaining = notice.get("remaining_seconds", 0)
        budget = self.configuration["safe_sample_budget_seconds"]
        derived = getattr(self.backend, "execution_sample_budget_seconds", None)
        sample_reader = getattr(self.backend, "read_snapshot_for_execution", None)
        if budget is not None and callable(derived) and callable(sample_reader):
            derived_budget = derived()
            if type(derived_budget) not in (int, float) or not math.isfinite(derived_budget) or derived_budget <= 0:
                budget = None
            else:
                budget = max(budget, derived_budget)
        else:
            budget = None
        if (budget is not None and notice.get("safe_to_sample") is True and type(remaining) in (int, float)
                and math.isfinite(remaining) and remaining >= budget + .05 and not self.cancel.is_set()):
            # Best effort on THIS NI main thread only. A driver overrun cannot
            # be preempted; never claim a hard deadline or pulse-width parity.
            started = time.monotonic()
            deadline = started + remaining - .05
            source_deadline = notice.get("minimum_next_action_deadline")
            if type(source_deadline) in (int, float) and math.isfinite(source_deadline):
                deadline = min(deadline, source_deadline - .05)
            try:
                sample = sample_reader(self.cancel, deadline)
                if self.cancel.is_set():
                    raise RuntimeError("Execution sample cancelled; no fresh measurement")
                if time.monotonic() > deadline:
                    raise RuntimeError("Execution sample exceeded source wait budget")
            except Exception as error:
                notice["sample_error"] = _error(error)
            else:
                notice["sample"] = sample
                notice["sample_started_monotonic"] = started
                notice["sample_completed_monotonic"] = time.monotonic()
                notice["sample_age_seconds"] = time.monotonic() - started
                if self.request_started is not None:
                    notice["sample_started_after_request_seconds"] = max(0., started - self.request_started)
                notice["sample_duration_seconds"] = notice["sample_completed_monotonic"] - started
                notice["sample_time_interpretation"] = "Child-local duration; absolute monotonic origin not shared"
            notice["sampling_policy"] = "explicit_opt_in_deadline_same_owner_not_hard_realtime"
            notice["configured_aggregate_sample_budget_seconds"] = budget
        self._emit(dict(kind="progress", id=self.active_id, event=notice,
                        attributes=_attributes(self.backend)))

    def _publish_software_observation(self):
        getter = getattr(self.backend, "get_software_state", None)
        if not callable(getter):
            return
        try:
            observed = time.monotonic()
            state = getter()  # Same owner RAM only; cold/post-close raises.
        except Exception:
            return
        self._emit(dict(kind="progress", id=self.active_id, attributes={}, event=dict(
            kind="SOFTWARE_STATE_NOT_MEASUREMENT", software_state=state,
            software_state_observed_monotonic=observed,
            source_effect="OWNER_OBSERVATION", simulated=getattr(self.backend, "_stage_simulated", False),
            safe_to_sample=False, hardware_acknowledged=False)))

    def _call(self, operation, arguments, keywords):
        if operation not in OPERATIONS or type(arguments) is not tuple or type(keywords) is not dict:
            raise ValueError("Explicit reviewed child operation required")
        counts = {"initialize": 0, "read_snapshot": 0, "general_start": 0, "general_stop": 0,
                  "execute_stage": 1, "execute_impulsion": 1, "set_ht_voltage": 1,
                  "configure_counter_timing": 1, "configure_sync_parameters": 1, "outer_controlled_stop": 0,
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
            result = method(self.cancel, **keywords)
            self._publish_software_observation()
            return result
        if operation in ("execute_stage", "execute_impulsion", "set_ht_voltage",
                         "configure_counter_timing", "configure_sync_parameters", "execute_cooling_guard"):
            result = method(arguments[0], self.cancel, **keywords)
        else:
            result = method(**keywords)
        self._publish_software_observation()
        return result

    def _retain_owner(self):
        if self.backend is None:
            return 2
        while True:
            threading.Event().wait(60)

    def run(self):
        for name, callback in (("ACQ-NI-child-egress", self._writer),
                               ("ACQ-NI-child-diagnostic", self._diagnostic_watch)):
            worker = threading.Thread(target=callback, name=name)
            worker.daemon = True
            worker.start()
        # Read the confirmed first request on this main thread. A background
        # read blocked on Windows stdin can deadlock NumPy's native loader.
        # Egress/diagnostics remain available; no NI task exists during imports.
        try:
            first = read_frame(self.source)
            if (set(first) != {"kind", "id", "operation", "arguments", "keywords", "configuration"}
                    or first.get("kind") != "call" or first.get("operation") != "initialize"
                    or type(first.get("id")) is not int or first["id"] <= 0
                    or type(first.get("arguments")) is not tuple or first["arguments"]
                    or type(first.get("keywords")) is not dict
                    or set(first["keywords"]) != {"startup_confirmed"}
                    or first["keywords"]["startup_confirmed"] is not True):
                raise ValueError("First private request must be explicitly confirmed initialize")
        except Exception:
            self.disconnected.set()
            return self._retain_owner()
        while True:
            if self.disconnected.is_set():
                # Parent disappearance is NOT an authorization to release live
                # NI tasks. Retain the child and handles for qualified recovery.
                return self._retain_owner()
            if first is not None:
                message, first = first, None
            else:
                try:
                    message = self.incoming.get(timeout=.05)
                except queue.Empty:
                    self._publish_idle_initialization_status()
                    continue
            operation, request_id = message.get("operation"), message["id"]
            with self.state_lock:
                self.active_id = request_id
                self.request_started = time.monotonic()
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
                    with self.state_lock:
                        self.diagnostic_phase = "CONSTRUCT_BACKEND"
                    self._trace_initialization(dict(phase="ENTER", call="construct_backend"))
                    self.configuration = message["configuration"]
                    self.backend = _create_backend(self.configuration)
                    self._trace_initialization(dict(phase="RETURNED", call="construct_backend"))
                    hook = getattr(self.backend, "set_execution_observer", None)
                    if hook is not None:
                        hook(self._observe)
                    with self.state_lock:
                        self.diagnostic_phase = "PREPARE_DEPENDENCIES"
                    prepare = getattr(self.backend, "prepare_isolated_dependencies", None)
                    if prepare is not None:
                        self._trace_initialization(dict(phase="ENTER", call="prepare_isolated_dependencies"))
                        prepare()
                        self._trace_initialization(dict(phase="RETURNED", call="prepare_isolated_dependencies"))
                    self._trace_initialization(dict(phase="ENTER", call="await_initialization_activation"))
                    self._await_initialization_activation()
                    self._trace_initialization(dict(phase="RETURNED", call="await_initialization_activation"))
                    # Cancellation ingress is live before task/card operations.
                    self._start_ingress()
                    with self.state_lock:
                        self.diagnostic_phase = "INITIALIZE_BACKEND"
                if operation == "initialize":
                    self._trace_initialization(dict(phase="ENTER", call="backend.initialize"))
                result = self._call(operation, message["arguments"], message["keywords"])
                if operation == "initialize":
                    self._trace_initialization(dict(phase="RETURNED", call="backend.initialize"))
            except Exception as caught:
                error = _error(caught)
            finally:
                # Even a failed import must still admit an explicit close and
                # report its result. Failure is never a reason to create tasks.
                self._start_ingress()
                with self.state_lock:
                    self.diagnostic_phase = "CALL_RETURNED"
            try:
                tracer = self._trace_initialization if operation == "initialize" else None
                attributes = _attributes(self.backend, tracer)
                if tracer is not None:
                    tracer(dict(phase="ENTER", call="encode_and_flush_initialize_result"))
                self._emit(dict(kind="result", id=request_id, ok=error is None, value=result,
                                error=error, attributes=attributes), reliable=True)
                if tracer is not None:
                    tracer(dict(phase="RETURNED", call="encode_and_flush_initialize_result"))
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
    worker = Worker(sys.stdin.buffer, sys.stdout.buffer)
    if sys.platform == "win32":
        worker.source = windows_polling_pipe(sys.stdin.buffer, worker.disconnected)
        worker._trace_initialization(dict(phase="READY", call="IPC input: PeekNamedPipe + ReadFile"))
    return worker.run()


if __name__ == "__main__":
    # Python 3.4 finalization can wait forever for daemon stdin/stdout buffer
    # locks held by the IPC threads. main() returns zero ONLY after backend
    # close proved zero resources and its reply was fully flushed. Exit this
    # already-released child directly; never terminate an active NI operation.
    os._exit(main())
