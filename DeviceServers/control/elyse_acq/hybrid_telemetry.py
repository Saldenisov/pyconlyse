"""Explicit migration: unchanged Acquisition 27 banks plus read-only Sup data.

Both authenticated streams enter the same existing DS listener. The sidecar
never supplies or replaces a public bank, never becomes an Acquisition source,
and never grants command authority. Default and full-federation modes differ.
"""
import copy
import json
from pathlib import Path
import time

from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkStore
from DeviceServers.control.elyse_acq.federated_telemetry import FederatedTelemetryStore
from legacy.xp_acq_control.elyse_agent.federation_wire import PUBLICATION
from legacy.xp_acq_agent.elyse_agent.supervision_wire import validate_key


MIGRATION_MODE = "acquisition_legacy_supervision_read_only"


def load_migration_configuration(path, acquisition_key):
    path = Path(path).resolve()
    raw = path.read_bytes()
    if not 0 < len(raw) <= 16384:
        raise ValueError("Bounded local SuperVision migration configuration required")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("Duplicate migration configuration field")
            value[key] = item
        return value
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    if (type(value) is not dict or set(value) != {"schema_version", "migration_mode", "supervision"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["migration_mode"] != MIGRATION_MODE):
        raise ValueError("Explicit read-only SuperVision migration mode required")
    item = value["supervision"]
    if (type(item) is not dict or set(item) != {"host", "port", "read_key_file"}
            or item["host"] != "10.20.30.2" or type(item["port"]) is not int or item["port"] != 8772
            or type(item["read_key_file"]) is not str or not item["read_key_file"]):
        raise ValueError("Fixed SuperVision host/port and explicit local read key required")
    key_name = item["read_key_file"]
    if key_name in (".", "..") or any(char in key_name for char in ("/", "\\", ":", "\x00")):
        raise ValueError("Installation-local read-key basename required")
    key = validate_key((path.parent / item["read_key_file"]).read_bytes().strip())
    if key == validate_key(acquisition_key):
        raise ValueError("Acquisition and SuperVision telemetry keys must differ")
    return dict(host=item["host"], port=item["port"], read_key=key, enabled=False)


class HybridTelemetryStore:
    def __init__(self, acquisition_key, supervision_key, clock=time.monotonic,
                 permitted_producer_kind=None, cooling=None, archive=None):
        acquisition_key, supervision_key = validate_key(acquisition_key), validate_key(supervision_key)
        if acquisition_key == supervision_key:
            raise ValueError("Migration owner keys must differ")
        self.legacy = TelemetrySinkStore(acquisition_key, clock=clock,
            permitted_producer_kind=permitted_producer_kind, cooling=cooling, archive=archive)
        # This Acq key slot satisfies the fixed two-owner validator; the router
        # below rejects ALL Acq owner frames. No foreign-key bank fallback exists.
        self.supervision = FederatedTelemetryStore(dict(acquisition=acquisition_key,
            supervision=supervision_key), clock=clock, archive=archive)
        self.closed = False

    def accept(self, request):
        if self.closed:
            raise RuntimeError("Hybrid telemetry store is closed")
        body = request.get("body") if type(request) is dict else None
        packet = body.get("packet") if type(body) is dict else None
        if type(packet) is dict and packet.get("publication") == PUBLICATION:
            if packet.get("owner") != "supervision":
                raise ValueError("Migration accepts only SuperVision owner frames; Acquisition keeps its selected 27-bank wire")
            return self.supervision.accept(request)
        return self.legacy.accept(request)

    def snapshot(self):
        value = self.legacy.snapshot()
        sidecar = self.supervision.snapshot()
        value.update(migration_mode=MIGRATION_MODE, public_bank_authority="selected_acquisition_legacy_stream",
            supervision_owner=copy.deepcopy(sidecar["owners"]["supervision"]),
            video_metadata=copy.deepcopy(sidecar["video_metadata"]),
            migration_received_total=value["received_this_process"] + sidecar["received_this_process"],
            sidecar_read_only=True, atomic_across_sources=False)
        return value

    def video_snapshot(self):
        value = self.supervision.video_snapshot()
        value.update(migration_mode=MIGRATION_MODE, sidecar_read_only=True)
        return value

    def owner_current(self, owner, session_id=None, native=False):
        return owner == "supervision" and self.supervision.owner_current(owner, session_id, native)

    def close(self):
        self.closed = True
        failures = []
        for store in (self.legacy, self.supervision):
            try:
                store.close()
            except Exception as error:
                failures.append(str(error))
        if failures:
            raise RuntimeError("Hybrid telemetry cleanup unfinished: " + "; ".join(failures))
