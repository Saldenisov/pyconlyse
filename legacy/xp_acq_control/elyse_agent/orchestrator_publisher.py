"""Owner-scoped publisher; software memory versus physical inputs stay distinct.

Same bounded authenticated transport and VI/local-owner exclusion as r15.
Independent per-card input ages survive a different card's blocked command.
Import performs no I/O. Python 3.4.
"""
import copy
import csv
import io
import json
import math
import os
import time

from .dual_mode_telemetry import DualModeTelemetryPublisher
from .federation_wire import owner_frame, OWNED_BANKS
from .standard_banks import INPUTS, schemas
from .shared_state import LatestSnapshotOutbox
from .telemetry_relay import TelemetryRelay


def _age(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value < 2


def _record(name, data, age):
    return dict(publication=name, data=copy.deepcopy(list(data) if isinstance(data, tuple) else data),
                lv_type=copy.deepcopy(schemas()[name]),
                error=dict(status=False, code=0, source=""), source_age_seconds=age)


def _calibration():
    result = {}
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "calibration_map.csv")
    with io.open(path, "r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row["group"] in ("C1NI6071E", "C2NI6071E"):
                result[(row["group"], int(row["index"]))] = (float(row["scale"]), float(row["offset"]))
    if len(result) != 128:
        raise ValueError("Complete pinned analog calibration required")
    return result


def independent_input_records(projection, calibration):
    result = {}
    state = projection.get("card_processes") or {}
    transport = state.get("transport_age_seconds", 0.)
    if not _age(transport) or projection.get("telemetry_view_current") is False:
        return result
    for name, (native_name, kind, device, count, field, value_type) in INPUTS.items():
        card = state.get("cards", {}).get(str(device), {})
        native = card.get("native", {})
        age = card.get("sample_age_seconds")
        if (card.get("input_current") is not True or card.get("state") != "READY"
                or native.get("ownership_uncertain") is not False or card.get("unresolved_request")
                or not _age(age) or not _age(age + transport)):
            continue
        sample = card.get("sample") or {}
        bank = sample.get("banks", {}).get(native_name, {})
        values = bank.get("values")
        if (sample.get("device") != device or bank.get("device") != device or bank.get("kind") != kind
                or not isinstance(values, (tuple, list)) or len(values) != count):
            continue
        if value_type == "Boolean":
            if any(type(v) is not bool for v in values):
                continue
            scaled = values
        else:
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
                continue
            scaled = [v * calibration[(name, i)][0] + calibration[(name, i)][1]
                      for i, v in enumerate(values)]
        result[name] = _record(name, scaled, age + transport)
    return result


class OwnerTelemetryPublisher(DualModeTelemetryPublisher):
    def __init__(self, runtime, address, key, period=.2, role="acquisition", **options):
        if role not in OWNED_BANKS:
            raise ValueError("Fixed local orchestrator role required")
        self.role, self.calibration = role, _calibration() if role == "acquisition" else {}
        self.last_video_sent = None
        DualModeTelemetryPublisher.__init__(self, runtime, address, key, period,
                                           packet_transform=self._transform, **options)
        # Legacy XML remains capped at256KiB. Only this typed owner protocol
        # admits the larger bounded raw-frame payload, before any thread starts.
        self.outbox = LatestSnapshotOutbox(clock=self.clock, max_encoded_bytes=900 * 1024)
        self.relay = TelemetryRelay(self.outbox, address, key)

    def _transform(self, packet, age, projection):
        projection, records, counterpart = projection or {}, {}, None
        bridge = packet["producer_kind"] == "copied_acquisition"
        for record in packet["data"]["banks"]:
            name = record["publication"]
            if name in OWNED_BANKS[self.role]:
                records[name] = dict(copy.deepcopy(record), source_age_seconds=age)
            if bridge and name == "C1011NI6602" and record.get("error", {}).get("status") is False:
                values = record.get("data")
                if isinstance(values, list) and len(values) == 33:
                    start = 0 if self.role == "acquisition" else 16
                    counterpart = dict(values=values[start:start + 16], source_age_seconds=age,
                        source="observed_labview_control_memory", selector=values[32],
                        pending_selector=values[32] != -1)
        mode = "LABVIEW_BRIDGE" if bridge else "PYTHON_NATIVE"
        if not bridge:
            if self.role == "acquisition":
                records.update(independent_input_records(projection, self.calibration))
            if projection.get("telemetry_view_current") is not False:
                counterpart = copy.deepcopy(projection.get("_publisher_counter_part"))
            if not projection.get("resource_count"):
                mode = "UNAVAILABLE"
        video = None
        if self.role == "supervision" and not bridge:
            now = self.clock()
            if (projection.get("telemetry_view_current") is not False
                    and (self.last_video_sent is None or now - self.last_video_sent >= 1.)):
                video = copy.deepcopy(projection.get("_publisher_video_frame"))
                if video is not None:
                    video = dict(video)
                    video.pop("age_seconds", None)
                    video.pop("owner_session_id", None)
                    self.last_video_sent = now
        frame = owner_frame(self.role, packet["session_id"], packet["sequence"], records,
                            source_mode=mode, counter_part=counterpart, video_frame=video)
        return json.dumps(frame, allow_nan=False, separators=(",", ":"))

    def status(self):
        return dict(DualModeTelemetryPublisher.status(self), owner=self.role,
                    telemetry_wire="federated_owner", raw_video_period_seconds=1.)
