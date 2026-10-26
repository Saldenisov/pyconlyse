"""Private per-card SuperVision services for retained child processes; Python3.4."""
import importlib
import threading
import time

from .supervision_cards import SupervisionCounterCard
from .supervision_imaq import SupervisionVideoCard, source_video_configuration


SYNC_TASKS = tuple("SUPCOUNT{0}".format(i) for i in range(8))
VIDEO_TASKS = ("img0.interface", "img0.session")


def _trusted_factory(name):
    if type(name) is not str or name.count(":") != 1:
        raise ValueError("Trusted local test factory name required")
    module, attribute = name.split(":")
    if not attribute.isidentifier() or not all(p.isidentifier() for p in module.split(".")):
        raise ValueError("Importable local test factory required")
    return getattr(importlib.import_module(module), attribute)()


class _Service(object):
    def __init__(self, device, trusted_factory=None):
        self.device, self.trusted_factory = device, trusted_factory
        self.adapter, self.observer = None, None
        self.admitted = False

    @property
    def resource_count(self):
        return 0 if self.adapter is None else self.adapter.resource_count

    def set_execution_observer(self, observer):
        self.observer = observer

    def prepare_isolated_dependencies(self):
        if self.adapter is None:
            self.adapter = (_trusted_factory(self.trusted_factory) if self.trusted_factory is not None
                            else self._make_adapter())
        setter = getattr(self.adapter, "set_execution_observer", None)
        if setter is not None:
            setter(self.observer)
        self.adapter.prepare_isolated_dependencies()

    def close(self):
        if self.adapter is not None:
            self.adapter.close()
        self.admitted = False

    def _require_initialize(self, cancel, startup_confirmed):
        if startup_confirmed is not True or self.admitted or cancel.is_set():
            raise ValueError("One explicit local initialization confirmation required")
        if self.adapter is None:
            self.prepare_isolated_dependencies()
        self.admitted = True  # A failed call is not an invitation to replay.


class SupervisionSyncService(_Service):
    def __init__(self, device="sync", trusted_factory=None):
        if device != "sync":
            raise ValueError("SuperVision synchronization service identity must be sync")
        _Service.__init__(self, device, trusted_factory)

    def _make_adapter(self):
        return SupervisionCounterCard()

    def initialize(self, cancel, startup_confirmed=False):
        self._require_initialize(cancel, startup_confirmed)
        self.adapter.initialize(operator_confirmed=True, resources_released_confirmed=True,
                                observer=self.observer)
        return dict(device=self.device, tasks=list(SYNC_TASKS), started_counters=list(range(8)),
                    hardware_acknowledged=False)

    def read_snapshot(self, cancel):
        if not self.admitted or self.adapter is None or cancel.is_set():
            raise RuntimeError("Current SuperVision counter owner required")
        started = time.monotonic()
        value = self.adapter.snapshot()
        return dict(device=self.device, banks={}, counter_memory=value["synchronization"],
            sample_elapsed_seconds=time.monotonic() - started,
            interpretation="Retained counter software memory, not physical pulse readback")

    def card_call(self, request, cancel):
        if (type(request) is not dict or set(request) != {"action", "arguments"}
                or request["action"] != "configure_timing" or type(request["arguments"]) not in (tuple, list)
                or len(request["arguments"]) != 3 or not self.admitted or cancel.is_set()):
            raise ValueError("Only the private typed synchronization operation is accepted")
        value = self.adapter.configure_timing(*request["arguments"], operator_confirmed=True)
        return dict(value=value, driver_report=None)


class SupervisionVideoService(_Service):
    def __init__(self, device="video", configuration=None, timeout_ms=500, trusted_factory=None):
        if device != "video":
            raise ValueError("SuperVision video service identity must be video")
        _Service.__init__(self, device, trusted_factory)
        self.configuration = dict(source_video_configuration() if configuration is None else configuration)
        self.timeout_ms = timeout_ms

    def _make_adapter(self):
        return SupervisionVideoCard(timeout_ms=self.timeout_ms)

    def initialize(self, cancel, startup_confirmed=False):
        self._require_initialize(cancel, startup_confirmed)
        self.adapter.initialize(self.configuration, operator_confirmed=True,
                                resources_released_confirmed=True)
        return dict(device=self.device, tasks=list(VIDEO_TASKS), started_counters=[],
                    hardware_acknowledged=False)

    def read_snapshot(self, cancel):
        if not self.admitted or self.adapter is None or cancel.is_set():
            raise RuntimeError("Current SuperVision NI1409 owner required")
        started = time.monotonic()
        value = self.adapter.read_frame()
        return dict(device=self.device, banks={}, video_frame=value,
                    sample_elapsed_seconds=time.monotonic() - started)

    def card_call(self, request, cancel):
        raise ValueError("NI1409 accepts no remote acquisition-control mutations")
