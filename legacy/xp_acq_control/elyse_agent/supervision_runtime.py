"""Independent two-card SuperVision host orchestration. Python3.4, cold import.

One lifecycle/command owner queues work; each card endpoint retains its own
native process and independent input polling. GUI/HTTP read RAM snapshots.
No owner is replaced after a crash/timeout, and no NI ownership is inferred
from a quiet VI, absent PID, metadata heartbeat or a physical-OFF attestation.
"""
import copy
import datetime
import math
import threading
import time

from .card_process_owner import CardProcessEndpoint
from .supervision_service import SupervisionSyncService, SupervisionVideoService, SYNC_TASKS, VIDEO_TASKS
from .supervision_imaq import source_video_configuration
from .command_broker import CommandBroker
from .command_protocol import OPERATIONS
from .acquisition_counter_timing import validate_remote_timing
from .acquisition_recovery import RecoveryRequired
from .runtime_identity import valid_hex


def new_supervision_identity():
    # Canonical package closure includes both host roles and the shared private
    # process, observation, HTTP and federation code. Boot sessions stay unique.
    from .acquisition_control_runtime import control_identity
    return control_identity()


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (ValueError, OverflowError):
        return False


def _video_metadata(value):
    if not isinstance(value, dict):
        return None
    return dict((key, copy.deepcopy(item)) for key, item in value.items() if key != "data")


def _status_metadata(value):
    result = copy.deepcopy(value)
    sample = result.get("sample")
    if isinstance(sample, dict) and "video_frame" in sample:
        sample["video_frame"] = _video_metadata(sample["video_frame"])
    return result


class SupervisionRuntime(object):
    server_variant = "supervision_control_vnext"
    host_role = "supervision"

    def __init__(self, identity=None, recovery_guard=None, remote_enabled=False,
                 counter_timing_controls_verified=False, video_configuration=None,
                 period=.2, read_timeout=.5, endpoint_factory=None,
                 trusted_service_options=None, clock=None, vi_passive_shadow=False):
        if type(counter_timing_controls_verified) is not bool or type(remote_enabled) is not bool:
            raise ValueError("Exact SuperVision commissioning and remote flags required")
        if type(vi_passive_shadow) is not bool:
            raise ValueError("Exact Boolean vi_passive_shadow policy required")
        self._vi_passive_shadow = vi_passive_shadow  # Pinned for this process lifetime.
        if not _finite(period) or not .02 <= period <= 10 or not _finite(read_timeout) or not .01 <= read_timeout <= 2:
            raise ValueError("Bounded SuperVision poll/read periods required")
        identity = dict(new_supervision_identity() if identity is None else identity)
        if not valid_hex(identity.get("session_id"), 32) or not valid_hex(identity.get("build_id"), 64):
            raise ValueError("Exact runtime source identity required")
        self._identity, self._recovery_guard = identity, recovery_guard
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._wake, self._done = threading.Event(), threading.Event()
        self._thread = None
        self._owners = {}
        self._state, self._error = "IDLE", ""
        self._pending = self._operation = None
        self._state_revision, self._sequence = 0, 0
        self._shutdown_requested = False
        self._everest_seen = None
        self._startup_complete = False
        self._observation_token = None
        self._observation_utc = None
        self._last_command_result = None
        self._counter_sample_min_sequence = None
        self._period, self._read_timeout = period, read_timeout
        self._endpoint_factory = endpoint_factory or CardProcessEndpoint
        self._service_options = copy.deepcopy(trusted_service_options or {})
        self._video_configuration = dict(source_video_configuration() if video_configuration is None else video_configuration)
        self.counter_timing_controls_verified = counter_timing_controls_verified
        self.broker = CommandBroker(self, enabled=remote_enabled and not self.vi_passive_shadow, clock=self._clock)

    @property
    def vi_passive_shadow(self):
        return self._vi_passive_shadow

    def _require_native_permitted(self):
        if self.vi_passive_shadow:
            raise RuntimeError("VI_PASSIVE_SHADOW: native initialization and commands are disabled")

    def _recovery(self):
        if self._recovery_guard is None:
            return dict(required=False, reason="NO_PERSISTENT_GUARD_TEST_MODE", protection_active=False)
        return self._recovery_guard.snapshot()

    def start(self):
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("SuperVision lifecycle owner cannot be started twice")
            self._thread = threading.Thread(target=self._run, name="SUPERVISION-local-orchestrator")
            self._thread.daemon = False
            self._thread.start()

    def note_everest_read(self):
        with self._lock:
            self._everest_seen = self._clock()

    def initialize(self, startup_confirmed=False):
        self._require_native_permitted()  # No telemetry-silence/recovery exception.
        if startup_confirmed is not True:
            raise ValueError("Local SuperVision synchronization/video initialization confirmation required")
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                raise RuntimeError("Start the cold local orchestrator before Initialize")
            if self._state != "IDLE" or self._owners or self._pending or self._shutdown_requested:
                raise RuntimeError("Initialize requires a cold IDLE SuperVision host")
            publisher = getattr(self, "telemetry_publisher", None)
            if publisher is not None and hasattr(publisher, "assert_initialize_allowed"):
                publisher.assert_initialize_allowed()
            recovery = self._recovery()
            if recovery.get("required"):
                self._state, self._error = "RECOVERY_REQUIRED", recovery.get("reason", "Owner recovery required")
                self._state_revision += 1
                raise RecoveryRequired(self._error)
            if self._recovery_guard is not None:
                self._recovery_guard.acquire()
            self._pending, self._operation = ("initialize", None), "initialize"
            self._state, self._error = "INITIALIZING", ""
            self._state_revision += 1
            if publisher is not None and hasattr(publisher, "note_native_transition"):
                publisher.note_native_transition()
            self._wake.set()

    def _close_request(self, shutdown, electrical_off_confirmed):
        with self._lock:
            if not self._owners and self._state == "STOPPED":
                return True
            if not self._owners and self._thread is None:
                self._state = "STOPPED" if shutdown else "IDLE"
                self._done.set()
                return True
            if self._pending is not None or self._operation is not None:
                raise RuntimeError("Lifecycle/command already active; no concurrent cleanup")
            if self._owners and electrical_off_confirmed is not True:
                raise ValueError("Explicit local OFF/stop-synchronization confirmation required")
            self._shutdown_requested = shutdown
            self._pending, self._operation = ("close", None), "close"
            self._state = "STOPPING" if shutdown else "DEINITIALIZING"
            self._state_revision += 1
            self.broker.interrupt_queued()
            self._wake.set()

    def deinitialize(self, electrical_off_confirmed=False):
        return self._close_request(False, electrical_off_confirmed)

    def request_shutdown(self, electrical_off_confirmed=False):
        return self._close_request(True, electrical_off_confirmed)

    def fenced_local_request(self, session_id, expected_revision, callback):
        with self._lock:
            if (session_id != self._identity["session_id"] or type(expected_revision) is not int
                    or expected_revision != self._state_revision or not callable(callback)):
                raise RuntimeError("Runtime session/revision fence rejected")
            if self._shutdown_requested or self._pending is not None:
                raise RuntimeError("Local lifecycle pending")
            return callback()

    def _statuses(self):
        with self._lock:
            owners = dict(self._owners)
        return {name: endpoint.status() for name, endpoint in owners.items()}

    def _sync_permit(self, statuses):
        if self.vi_passive_shadow:
            return False
        sync = statuses.get("sync", {})
        memory = (sync.get("sample") or {}).get("counter_memory") or {}
        return bool(sync.get("state") == "READY" and sync.get("input_current") is True
                    and not sync.get("error") and not memory.get("uncertain_counters")
                    and sync.get("native", {}).get("ownership_uncertain") is False
                    and sync.get("native", {}).get("resource_count") == 8
                    and not sync.get("unresolved_request")
                    and isinstance(sync.get("native", {}).get("worker_generation"), str)
                    and sync["native"]["worker_generation"]
                    and tuple(sync.get("tasks", ())) == SYNC_TASKS)

    def _capabilities(self, statuses):
        result = {name: dict(enabled=False, reason="NOT_OWNED_BY_SUPERVISION") for name in OPERATIONS}
        if self.vi_passive_shadow:
            return {name: dict(enabled=False, reason="VI_PASSIVE_SHADOW") for name in OPERATIONS}
        reason = ""
        if not self.broker.enabled:
            reason = "REMOTE_CONTROL_DISABLED"
        elif not self.counter_timing_controls_verified:
            reason = "SUPERVISION_TIMING_NOT_COMMISSIONED"
        elif self._recovery().get("required"):
            reason = "LOCAL_OWNERSHIP_RECOVERY_REQUIRED"
        elif self._state not in ("RUNNING", "FAULT") or self._pending is not None or self._operation is not None:
            reason = "SUPERVISION_OWNER_BUSY_OR_NOT_RUNNING"
        elif not self._sync_permit(statuses):
            reason = "FRESH_KNOWN_SUPERVISION_SYNC_OWNER_REQUIRED"
        result["counter_timing.set"] = dict(enabled=not reason, reason=reason)
        return result

    def dispatch_remote(self, operation, value):
        self._require_native_permitted()
        if operation != "counter_timing.set":
            raise RuntimeError("Operation is not owned by SuperVision")
        request = validate_remote_timing(value)
        with self._lock:
            capability = self._capabilities(self._statuses())[operation]
            if capability["enabled"] is not True:
                raise RuntimeError(capability["reason"])
            sync = self._owners["sync"].status()
            sample = sync.get("sample") or {}
            running = sample.get("counter_memory", {}).get("running_counters", [])
            if request["counter"] not in running:
                raise RuntimeError("SuperVision timing requires an already running retained counter")
            self._pending = ("timing", dict(request))
            self._counter_sample_min_sequence = sync.get("sample_sequence")
            self._operation, self._state = operation, "EXECUTING"
            self._state_revision += 1
            self._wake.set()
            return True

    def _initialize_cards(self):
        self._require_native_permitted()  # Also fence an incorrectly queued private action.
        specs = (("sync", SupervisionSyncService, SYNC_TASKS, tuple(range(8))),
                 ("video", SupervisionVideoService, VIDEO_TASKS, ()))
        endpoints_started, failures = [], []
        for name, service, tasks, counter_starts in specs:
            options = dict(device=name)
            if name == "video":
                options.update(configuration=self._video_configuration,
                               timeout_ms=int(self._read_timeout * 1000))
            options.update(self._service_options.get(name, {}))
            stream = getattr(self, "telemetry_publisher", None)
            native_video = bool(name == "video" and stream is not None
                                and getattr(stream, "independent_native_video", False))
            endpoint = self._endpoint_factory(device=name, service_factory=service,
                service_options=options, expected_tasks=tasks, expected_started_counters=counter_starts,
                period=self._period, read_timeout=self._read_timeout,
                sample_sink=self._native_video_sample if native_video else None,
                continuous_input=native_video)
            with self._lock:
                self._owners[name] = endpoint  # Retain before any process-start effect.
            try:
                endpoint.start()
            except Exception as error:
                # A local spawn failure on one board must not prevent the
                # other board's own independent diagnostic/initialization.
                failures.append(name + ": " + str(error))
            else:
                endpoints_started.append(endpoint)
        deadline = self._clock() + 40
        for endpoint in endpoints_started:
            if not endpoint.ready.wait(max(0., deadline - self._clock())):
                failures.append("SuperVision card initialization deadline; owner retained")
        statuses = self._statuses()
        if failures or any(item.get("state") != "READY" or item.get("native", {}).get("ownership_uncertain") is not False
               for item in statuses.values()):
            raise RuntimeError("SuperVision card initialization failed; all owners retained: " + "; ".join(failures))
        self._startup_complete = True

    def _native_video_sample(self, endpoint, sample, started):
        """Stage each returned camera sample, rather than polling latest at 1Hz.

        Called only by this card's dispatcher. Ownership/lifecycle are fenced
        before a bounded RAM append; no NI, pixel decode, network or disk work.
        Lock contention/full queues are explicit endpoint sink rejections.
        """
        native = endpoint.client.isolation_snapshot()
        frame = sample.get("video_frame")
        generation = native.get("worker_generation")
        if (not isinstance(frame, dict) or native.get("ownership_uncertain") is not False
                or not valid_hex(generation, 32) or not self._lock.acquire(False)):
            return False
        try:
            if (self.vi_passive_shadow or self._owners.get("video") is not endpoint
                    or self._shutdown_requested
                    or self._state not in ("INITIALIZING", "RUNNING", "EXECUTING", "FAULT")
                    or self._operation == "close"):
                return False
            publisher = getattr(self, "telemetry_publisher", None)
            if publisher is None or not publisher.independent_native_video:
                return False
            value = dict(frame, capture_session_id=generation,
                         source_age_seconds=max(0., time.monotonic() - started))
            return publisher.offer_native_video(value)
        finally:
            self._lock.release()

    def _close_cards(self):
        owners = dict(self._owners)
        if self.vi_passive_shadow and owners:
            raise RuntimeError("VI_PASSIVE_SHADOW: unexpected native ownership; no card cleanup calls admitted")
        failures, threads = [], []
        lock = threading.Lock()
        def close(name, endpoint):
            try:
                endpoint.close()
            except Exception as error:
                with lock:
                    failures.append(name + ": " + str(error))
        for name, endpoint in owners.items():
            worker = threading.Thread(target=close, args=(name, endpoint), name="SUP-close-" + name)
            worker.daemon = True
            threads.append(worker)
            worker.start()
        deadline = self._clock() + 30
        for worker in threads:
            worker.join(max(0., deadline - self._clock()))
        if failures or any(worker.is_alive() for worker in threads):
            raise RuntimeError("SuperVision cleanup not confirmed: " + "; ".join(failures))
        for name, endpoint in owners.items():
            if endpoint.status().get("native", {}).get("cleanup_confirmed") is not True:
                raise RuntimeError("Card cleanup/join unconfirmed; ownership marker retained")
        if self._recovery_guard is not None and not self.vi_passive_shadow:
            self._recovery_guard.release_after_cleanup(resources_quiescent=True)
        with self._lock:
            self._owners = {}
            self._startup_complete = False
            self._observation_token, self._observation_utc = None, None

    def _run(self):
        try:
            while True:
                with self._lock:
                    pending, self._pending = self._pending, None
                if pending is None:
                    self._wake.wait(.05)
                    self._wake.clear()
                    continue
                action, value = pending
                token, error = None, None
                try:
                    if action == "initialize":
                        self._initialize_cards()
                    elif action == "close":
                        self._close_cards()
                    elif action == "timing":
                        self._require_native_permitted()
                        token = self.broker.begin("counter_timing.set")
                        if not self._sync_permit(self._statuses()):
                            raise RuntimeError("SuperVision counter ownership changed before dispatch")
                        self._last_command_result = self._owners["sync"].call("configure_timing",
                            (value["counter"], value["delay_us"], value["width_us"]))
                    else:
                        raise RuntimeError("Unknown local SuperVision action")
                except Exception as caught:
                    error = caught
                self.broker.finish(token, error)
                with self._lock:
                    self._operation = None
                    if error is not None:
                        self._state, self._error = "FAULT", type(error).__name__ + ": " + str(error)
                        self._shutdown_requested = False
                    elif action == "close":
                        self._state, self._error = ("STOPPED" if self._shutdown_requested else "IDLE"), ""
                    else:
                        self._state, self._error = "RUNNING", ""
                    self._state_revision += 1
                    finished = self._state == "STOPPED"
                if finished:
                    return
        finally:
            self._done.set()

    @property
    def card_processes(self):
        return dict(mode="per_card", source="supervision", cards={
            name: _status_metadata(value) for name, value in self._statuses().items()},
            hardware_acknowledged=False, automatic_restart=False)

    def video_frame_snapshot(self):
        if self.vi_passive_shadow:
            return None  # Original-VI images arrive through its passive ingress.
        # Independent video may stay current during a synchronization command
        # or an unrelated synchronization fault. Lifecycle transitions never
        # reuse an old owner/sample as a new camera observation.
        started = self._clock()
        if not self._lock.acquire(False):
            return None
        try:
            endpoint = self._owners.get("video")
            if self._state not in ("INITIALIZING", "RUNNING", "EXECUTING", "FAULT") or self._shutdown_requested:
                return None
        finally:
            self._lock.release()
        if endpoint is None:
            return None
        value = endpoint.input_snapshot()
        sample = value.get("sample") or {}
        frame = sample.get("video_frame")
        if (value.get("current") is not True or not isinstance(frame, dict)
                or not _finite(value.get("age_seconds")) or not 0 <= value["age_seconds"] < 2
                or not valid_hex(value.get("card_generation"), 32)):
            return None
        result = copy.deepcopy(frame)
        result.update(source_age_seconds=value["age_seconds"],
                      capture_session_id=value["card_generation"])
        from .federation_wire import validate_video_frame
        try:
            validate_video_frame(result)
        except (ValueError, TypeError):
            return None
        native = endpoint.status()
        if (native.get("state") != "READY" or native.get("input_current") is not True
                or native.get("unresolved_request")
                or native.get("native", {}).get("ownership_uncertain") is not False
                or native.get("native", {}).get("worker_generation") != value["card_generation"]):
            return None
        if not self._lock.acquire(False):
            return None
        try:
            if (self._owners.get("video") is not endpoint or self._shutdown_requested
                    or self._state not in ("INITIALIZING", "RUNNING", "EXECUTING", "FAULT")):
                return None
        finally:
            self._lock.release()
        age = value["age_seconds"] + max(0., self._clock() - started)
        if not age < 2:
            return None
        result.update(age_seconds=age, source_age_seconds=age,
            capture_session_id=value.get("card_generation"),
            owner_session_id=self._identity["session_id"])
        return result

    def unavailable_video_snapshot(self, reason="VIDEO_NOT_CURRENT"):
        return dict(self._identity, schema_version=1, owner="supervision",
            server_variant=self.server_variant, host_role=self.host_role,
            state_revision=self._state_revision, available=False, stale=True,
            age_seconds=None, frame=None, reason=reason,
            hardware_writes=False, execution_allowed=False,
            remote_initialization_enabled=False, auto_initialize=False)

    def video_snapshot(self):
        """Separate bounded raw image API; only current per-card RAM is read."""
        revision = self._state_revision
        frame = self.video_frame_snapshot()
        if frame is None:
            return self.unavailable_video_snapshot()
        result = dict(frame)
        age = result.pop("age_seconds")
        result.pop("owner_session_id")
        if not self._lock.acquire(False):
            return self.unavailable_video_snapshot("VIDEO_CONTEXT_BUSY")
        try:
            if revision != self._state_revision or self._shutdown_requested:
                return self.unavailable_video_snapshot("VIDEO_CONTEXT_CHANGED")
            value = dict(self.unavailable_video_snapshot(), available=True, stale=False,
                age_seconds=age, source_mode="PYTHON_NATIVE", frame=result)
        finally:
            self._lock.release()
        value.update((key, copy.deepcopy(result[key])) for key in (
            "source", "capture_session_id", "sequence", "width", "height", "pixel_type",
            "encoding", "channel", "processing", "observed_utc", "hardware_acknowledged"))
        return value

    def counter_memory_part(self):
        """Current retained-command half for federation; no physical readback."""
        if self.vi_passive_shadow:
            return None
        statuses = self._statuses()
        sync = statuses.get("sync", {})
        with self._lock:
            minimum = self._counter_sample_min_sequence
            if (self._operation == "counter_timing.set" or self._pending is not None
                    or self._state not in ("RUNNING", "FAULT")
                    or not self._sync_permit(statuses)
                    or minimum is not None and sync.get("sample_sequence", -1) <= minimum):
                return None
        native = sync.get("native", {})
        if native.get("worker_state") != "IDLE_OWNED" or native.get("active_request_id") is not None:
            return None
        memory = (sync.get("sample") or {}).get("counter_memory") or {}
        values, age = memory.get("timing_pairs_us"), sync.get("sample_age_seconds")
        if (not isinstance(values, (list, tuple)) or len(values) != 16
                or any(not _finite(item) for item in values) or not _finite(age) or not 0 <= age < 2):
            return None
        return dict(values=list(values), source_age_seconds=age,
            source="last_successful_counter_command_memory", selector=-1, pending_selector=False)

    def snapshot(self, include_publisher=True):
        statuses = self._statuses()
        now = self._clock()
        metadata = {name: _status_metadata(value) for name, value in statuses.items()}
        with self._lock:
            recovery = self._recovery()
            if recovery.get("required") and self._state == "IDLE" and not self._owners:
                self._state, self._error = "RECOVERY_REQUIRED", recovery.get("reason", "Recovery required")
                self._state_revision += 1
            if self._state == "RUNNING" and any(
                    row.get("state") != "READY" or row.get("native", {}).get("ownership_uncertain") is not False
                    for row in statuses.values()):
                self._state, self._error = "FAULT", "A SuperVision card owner is unavailable; other owners retained"
                self._state_revision += 1
            token = tuple((name, row.get("sample_sequence")) for name, row in sorted(statuses.items()))
            if token and token != self._observation_token:
                self._sequence += 1
                self._observation_token = token
                self._observation_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            ages = [row.get("sample_age_seconds") for row in statuses.values()]
            age = max(ages) if ages and all(_finite(x) for x in ages) else None
            current = bool(len(statuses) == 2 and all(row.get("input_current") is True for row in statuses.values())
                           and age is not None and age < 2)
            all_ready = bool(len(statuses) == 2 and self._startup_complete and all(
                row.get("state") == "READY" and not row.get("error") and not row.get("unresolved_request")
                and row.get("input_current") is True
                and row.get("native", {}).get("ownership_uncertain") is False
                and row.get("native", {}).get("resource_count") == (8 if name == "sync" else 2)
                for name, row in statuses.items()))
            sync = statuses.get("sync", {})
            counter = copy.deepcopy((sync.get("sample") or {}).get("counter_memory"))
            video = (statuses.get("video", {}).get("sample") or {}).get("video_frame")
            latest = None if not statuses else dict(source="python_supervision_card_processes", simulated=False,
                received_utc=self._observation_utc, banks={}, counter_memory=counter,
                counter_memory_current=sync.get("input_current") is True,
                counter_memory_age_seconds=sync.get("sample_age_seconds"),
                video_frame=_video_metadata(video),
                video_frame_age_seconds=statuses.get("video", {}).get("sample_age_seconds"))
            resource_count = sum(row.get("native", {}).get("resource_count", 0) for row in statuses.values())
            result = dict(self._identity, server_variant="supervision_control_vnext", host_role="supervision",
                vi_passive_shadow=self.vi_passive_shadow,
                owner_mode="VI_PASSIVE_SHADOW" if self.vi_passive_shadow else "NATIVE_CAPABLE",
                native_initialization_allowed=not self.vi_passive_shadow,
                source_host="10.20.30.2", control_policy_version=2, state=self._state,
                state_revision=self._state_revision, current_operation=self._operation,
                pending_operation=None if self._pending is None else self._pending[0], error=self._error,
                sequence=self._sequence, latest=latest, age_seconds=age, stale=not current,
                measurement_current=current, startup_complete=self._startup_complete,
                resource_count=resource_count, card_processes=dict(mode="per_card", source="supervision", cards=metadata),
                card_health=dict(all_required_ready=all_ready, required_cards=["sync", "video"],
                                 faulted_cards=[name for name, row in statuses.items()
                                     if row.get("state") != "READY" or row.get("error") or row.get("input_error")
                                     or row.get("native", {}).get("ownership_uncertain") is not False],
                                 independently_current={name: row.get("input_current") is True for name, row in statuses.items()}),
                native_isolation=dict(mode="per_card", worker_state="MULTIPLE_CARD_OWNERS",
                    ownership_uncertain=any(row.get("native", {}).get("ownership_uncertain") is not False
                                            for row in statuses.values()), resource_count=resource_count,
                    hardware_off_confirmed=False, automatic_restart=False),
                recovery=recovery, remote_initialization_enabled=False, auto_initialize=False,
                remote_setpoints_enabled=self.broker.enabled, shutdown_requested=self._shutdown_requested,
                everest_read_age_seconds=None if self._everest_seen is None else max(0, now - self._everest_seen),
                stage_execution=dict(remote_commands_enabled=self.broker.enabled,
                                     counter_timing_commissioned=self.counter_timing_controls_verified),
                counter_timing_state=counter or {}, video_frame=_video_metadata(video),
                last_command_result=copy.deepcopy(self._last_command_result),
                physical_measurements_verified=False, hardware_writes=False,
                hardware_writes_interpretation="This RAM snapshot read writes no hardware; Initialize and admitted commands can mutate local boards",
                build_id_interpretation="Explicit SuperVision source closure, not configuration/firmware/environment attestation",
                output_interpretation="Source pulse software memory; no physical timing acknowledgement",
                telemetry_view_current=True,
                telemetry_bridge_mode=(not self._owners and self._state in ("IDLE", "RECOVERY_REQUIRED")
                    and self._pending is None and self._operation is None and not self._shutdown_requested),
                cooling_safety=dict(active=False, circuits=[], stop_state="NONE", remaining_seconds=None,
                    automatic_stop_available=False, journal_error="", authority="NOT_OWNED_BY_SUPERVISION"))
            result["control"] = self.broker.snapshot(issue_lease=False)
            if self.vi_passive_shadow:
                result["control"].update(enabled=False, lease=None)
                result["remote_setpoints_enabled"] = False
                result["stage_execution"]["remote_commands_enabled"] = False
            result["control"]["capabilities"] = self._capabilities(statuses)
            publisher = getattr(self, "telemetry_publisher", None)
        # Never nest the runtime lock with publisher status/admission locks.
        # The telemetry projection itself excludes this recursive status path.
        result["telemetry_delivery"] = (publisher.status() if publisher is not None and include_publisher
                                        else dict(enabled=False) if publisher is None else dict(projection_only=True))
        return result

    def try_telemetry_snapshot(self):
        """RAM-only, non-waiting local admission projection; no NI/card reads."""
        if not self._lock.acquire(False):
            return None
        try:
            return self.snapshot(include_publisher=False)
        finally:
            self._lock.release()

    def join(self, timeout=None):
        worker = self._thread
        if worker is None:
            return self._state == "STOPPED"
        worker.join(timeout)
        return not worker.is_alive()
