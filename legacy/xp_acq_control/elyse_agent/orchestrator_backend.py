"""Main-orchestrator business logic; one directly owned process per NI card.

Construction and metadata are cold. This process never imports the NI Python
driver, loads an NI DLL, or owns a native card task: CardBackend's per-card
factory delegates those calls to its eleven direct children. Business calls
run on the existing runtime thread, independently of the card input dispatchers.
Chroma retains its existing separately owned native helper processes.

The logical generation belongs to this facade, not to an aggregate worker.
Component generations separately fence samples and source ordering. No whole
backend restart, lost-owner replacement, or command replay is exposed here.
Python 3.4 compatible; status never performs a process/pipe/native query.
"""
import copy
from functools import wraps
import os
import threading
import time
import uuid

from .acquisition_backend import CardBackend
from .chroma_focal_command import ChromaFocalCommand


_READS = frozenset(("read_snapshot", "read_snapshot_for_execution"))


def _tracked(method):
    @wraps(method)
    def call(self, *arguments, **keywords):
        name = method.__name__
        self._enter_operation(name)
        try:
            return method(self, *arguments, **keywords)
        finally:
            self._leave_operation(name)
    return call


class PerCardOrchestratorBackend(CardBackend):
    """CardBackend-compatible facade whose direct children retain NI ownership."""
    def __init__(self, focal_options=None, **options):
        mode = options.pop("native_isolation_mode", "per_card")
        if mode != "per_card":
            raise ValueError("Main-orchestrator facade requires per_card isolation")
        if focal_options is not None:
            if type(focal_options) is not dict or "focal_command" in options:
                raise ValueError("One explicit Chroma helper configuration required")
            options["focal_command"] = ChromaFocalCommand(**dict(focal_options))
        self._orchestrator_lock = threading.RLock()
        self._orchestrator_generation = uuid.uuid4().hex
        self._orchestrator_pid = os.getpid()
        self._orchestrator_serial = 0
        self._orchestrator_request = None
        self._orchestrator_thread = None
        self._orchestrator_stack = []
        self._orchestrator_observer = None
        self._orchestrator_observer_error = ""
        self._orchestrator_closed = False
        CardBackend.__init__(self, native_isolation_mode="per_card", **options)

    def _enter_operation(self, name):
        ident = threading.current_thread().ident
        with self._orchestrator_lock:
            if self._orchestrator_stack and ident != self._orchestrator_thread:
                raise RuntimeError("Business calls require the existing orchestrator owner thread")
            if not self._orchestrator_stack:
                self._orchestrator_thread = ident
                self._orchestrator_serial += 1
                self._orchestrator_request = self._orchestrator_serial
            self._orchestrator_stack.append(name)

    def _leave_operation(self, name):
        with self._orchestrator_lock:
            if (not self._orchestrator_stack or self._orchestrator_stack[-1] != name
                    or self._orchestrator_thread != threading.current_thread().ident):
                raise RuntimeError("Orchestrator operation context changed unexpectedly")
            self._orchestrator_stack.pop()
            if not self._orchestrator_stack:
                self._orchestrator_thread = self._orchestrator_request = None

    def _components(self):
        owner = self.owner
        status = None if owner is None else owner.snapshot()
        components, uncertain = {}, False
        if status is not None:
            dispatchers = tuple(owner.dispatchers.items())
            for device, dispatcher in dispatchers:
                card = status["cards"].get(str(device), {})
                native = card.get("native", {})
                # Thread liveness is local RAM only; never poll a child here.
                joined = not dispatcher.thread.is_alive()
                closed = (card.get("state") == "CLOSED_JOINED"
                          and native.get("cleanup_confirmed") is True and joined)
                bad = (native.get("ownership_uncertain") is not False
                       or card.get("unresolved_request") is not False
                       or (card.get("state") == "CLOSED_JOINED" and not closed)
                       or (dispatcher.finished.is_set() and not closed))
                uncertain = uncertain or bad
                components[str(device)] = dict(device=device, state=card.get("state"),
                    worker_generation=native.get("worker_generation"),
                    worker_pid=native.get("worker_pid"), worker_state=native.get("worker_state"),
                    resource_count=native.get("resource_count", 0),
                    cleanup_confirmed=closed, dispatcher_joined=joined,
                    ownership_uncertain=bool(bad),
                    unresolved_request=card.get("unresolved_request"),
                    input_error=card.get("input_error", ""))
        return owner, status, components, bool(uncertain)

    @property
    def resource_count(self):
        # Include retained serial helper handles. A successful NI close cannot
        # make an unresolved native helper disappear from lifecycle admission.
        helpers, count, uncertain = self._focal_ownership()
        count += CardBackend.resource_count.fget(self)
        if count:
            return count
        owner, status, components, uncertain = self._components()
        return 1 if uncertain else 0

    def _focal_ownership(self):
        try:
            helpers = self.focal_command.snapshot()
            count = helpers.get("pending_worker_count")
            if type(count) is not int or count < 0:
                raise ValueError("Invalid retained Chroma helper count")
            return helpers, count, False
        except Exception as error:
            return dict(error=type(error).__name__ + ": " + str(error),
                        pending_worker_count=None), 1, True

    def isolation_snapshot(self):
        """RAM-only lifecycle proof; input quality is reported independently."""
        with self._orchestrator_lock:
            stack = tuple(self._orchestrator_stack)
            request = self._orchestrator_request
            generation, pid = self._orchestrator_generation, self._orchestrator_pid
            observer_error = self._orchestrator_observer_error
            closed = self._orchestrator_closed
        owner, status, components, uncertain = self._components()
        helpers, pending_helpers, helper_uncertain = self._focal_ownership()
        uncertain = uncertain or helper_uncertain
        # During a call these are explicitly owned executing helpers; after a
        # return, retained/unjoined helpers require reconciliation, not replay.
        commands = any(name not in _READS for name in stack)
        if pending_helpers and not commands:
            uncertain = True
        count = self.resource_count
        cleanup = bool(closed and count == 0 and not uncertain
                       and all(v["cleanup_confirmed"] for v in components.values()))
        if stack:
            state = "EXECUTING_READ_SNAPSHOT" if stack[-1] in _READS else "EXECUTING_OP"
        elif uncertain:
            state = "OWNERSHIP_UNCERTAIN"
        elif count:
            state = "IDLE_OWNED"
        elif cleanup:
            state = "CLOSED_JOINED"
        else:
            state = "COLD"
        return dict(mode="per_card", worker_generation=generation, worker_pid=pid,
            worker_state=state, active_request_id=request, commands_in_flight=bool(commands),
            active_operation=stack[-1] if stack else None,
            ownership_uncertain=bool(uncertain), cleanup_confirmed=cleanup,
            resource_count=max(1, count) if uncertain and not count else count,
            resource_count_interpretation="DIRECT_CARD_OWNERS_PLUS_RETAINED_NATIVE_HELPERS",
            component_generations=([] if status is None else copy.deepcopy(status["generation_vector"])),
            component_states=components, focal_helpers=copy.deepcopy(helpers),
            progress_observer_error=observer_error, automatic_restart=False,
            hardware_off_confirmed=False, main_process_owns_ni_tasks=False)

    def set_execution_observer(self, observer, interval_seconds=.2):
        if observer is not None and not callable(observer):
            raise TypeError("Local progress observer must be callable")
        with self._orchestrator_lock:
            self._orchestrator_observer = observer
        # Preserve the existing source scheduler and its original qualified
        # dwell spans. This adapter adds identity, never a new aggregate read.
        CardBackend.set_execution_observer(self, self._observe, interval_seconds)

    def _observe(self, event):
        if type(event) is not dict:
            return
        with self._orchestrator_lock:
            observer = self._orchestrator_observer
            request = self._orchestrator_request
        if observer is None:
            return
        value = copy.deepcopy(event)
        value.update(worker_generation=self._orchestrator_generation,
                     worker_pid=self._orchestrator_pid, active_request_id=request)
        if value.get("kind") == "SOFTWARE_STATE_NOT_MEASUREMENT":
            observed = value.get("software_state_observed_monotonic")
            if type(observed) in (int, float):
                value["software_state_age_seconds"] = max(0., time.monotonic() - observed)
        try:
            observer(value)
        except Exception as error:
            with self._orchestrator_lock:
                self._orchestrator_observer_error = type(error).__name__ + ": " + str(error)
            raise

    @_tracked
    def initialize(self, *arguments, **keywords):
        self._orchestrator_closed = False
        result = CardBackend.initialize(self, *arguments, **keywords)
        return result

    @_tracked
    def read_snapshot(self, *arguments, **keywords):
        return CardBackend.read_snapshot(self, *arguments, **keywords)

    @_tracked
    def read_snapshot_for_execution(self, *arguments, **keywords):
        return CardBackend.read_snapshot_for_execution(self, *arguments, **keywords)

    @_tracked
    def general_start(self, *arguments, **keywords):
        return CardBackend.general_start(self, *arguments, **keywords)

    @_tracked
    def general_stop(self, *arguments, **keywords):
        return CardBackend.general_stop(self, *arguments, **keywords)

    @_tracked
    def execute_stage(self, *arguments, **keywords):
        return CardBackend.execute_stage(self, *arguments, **keywords)

    @_tracked
    def execute_beamline(self, *arguments, **keywords):
        return CardBackend.execute_beamline(self, *arguments, **keywords)

    @_tracked
    def execute_impulsion(self, *arguments, **keywords):
        return CardBackend.execute_impulsion(self, *arguments, **keywords)

    @_tracked
    def set_ht_voltage(self, *arguments, **keywords):
        return CardBackend.set_ht_voltage(self, *arguments, **keywords)

    @_tracked
    def configure_counter_timing(self, *arguments, **keywords):
        return CardBackend.configure_counter_timing(self, *arguments, **keywords)

    @_tracked
    def configure_sync_parameters(self, *arguments, **keywords):
        return CardBackend.configure_sync_parameters(self, *arguments, **keywords)

    @_tracked
    def outer_controlled_stop(self, *arguments, **keywords):
        return CardBackend.outer_controlled_stop(self, *arguments, **keywords)

    @_tracked
    def execute_cooling_guard(self, *arguments, **keywords):
        return CardBackend.execute_cooling_guard(self, *arguments, **keywords)

    @_tracked
    def record_procedure_request(self, *arguments, **keywords):
        return CardBackend.record_procedure_request(self, *arguments, **keywords)

    @_tracked
    def close(self):
        result = CardBackend.close(self)
        self._orchestrator_closed = True
        return result
