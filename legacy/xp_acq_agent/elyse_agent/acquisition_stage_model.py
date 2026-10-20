"""Python 3.4, non-actuating stage model; import performs no I/O.

This module provides static catalog reads and pure frame projections, not
actuation. The separate acquisition_stage_execution adapter consumes its pinned
plans for commissioned CardBackend callbacks. These model methods themselves
accept no hardware callback or convert an EPS OK flag to a safety permit.
Frame effects are unordered; callers supply each local-read snapshot.
"""
import copy
import hashlib
import io
import json
import os


BANK_SHAPES = {15: 32, 17: 40, 36: 29, 44: 77}
SOURCE_ARCHIVE_SHA256 = "6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527"
CATALOG_SHA256 = "a9d821e7519ea50f6b35593e58c78129ec7d8a7bfedcc06098e247bef011a0b0"
EVENTS = {
    "cooling.start": (3, 0), "cooling.stop": (4, 1),
    "general.start": (5, 2), "general.stop": (6, 3),
    "chauffage.stop": (7, 5), "prema.stop": (8, 7),
    "relays_ht.stop": (9, 9), "focales.stop": (10, 11),
    "modulator.reset": (11, 12), "chauffage.start": (12, 4),
    "prema.start": (13, 6), "relays_ht.start": (14, 8),
    "focales.start": (15, 10), "alimentation_ht.start": (20, 15),
    "alimentation_ht.stop": (21, 17), "alimentation_ht.reset": (22, 16),
}


def _snapshot(snapshots, bank):
    values = tuple(snapshots[bank])
    if len(values) != BANK_SHAPES[bank] or any(type(v) is not bool for v in values):
        raise ValueError("Explicit Boolean local snapshot required for bank " + str(bank))
    return values


class StageModel(object):
    def __init__(self, catalog):
        self._catalog = copy.deepcopy(catalog)
        if (catalog.get("schema_version") != 1 or catalog.get("hardware_enabled") is not False
                or catalog.get("source_archive_sha256") != SOURCE_ARCHIVE_SHA256
                or catalog.get("source_frame_effects_unordered") is not True
                or set(catalog.get("procedures", {})) != set(EVENTS)):
            raise ValueError("Unqualified stage catalog")
        self._frames = {}
        for name, procedure in self._catalog["procedures"].items():
            if (procedure.get("event"), procedure.get("dps_request_field")) != EVENTS[name]:
                raise ValueError("Stage event/DPS identity changed")
            self._validate_frames(procedure["frames"])

    def _validate_frames(self, frames):
        if not isinstance(frames, list) or not frames:
            raise ValueError("Nonempty ordered source frames required")
        for uid, effects in frames:
            if not isinstance(uid, str) or not uid.isdigit() or uid in self._frames:
                raise ValueError("Unique source frame UID required")
            self._frames[uid] = effects
            for effect in effects:
                kind = effect[0]
                if kind == "write":
                    _, bank, fields = effect
                    if bank not in (15, 17, 35, 36, 44) or not fields:
                        raise ValueError("Unsupported local write")
                    seen = set()
                    for index, value in fields:
                        if (type(index) is not int or type(value) is not bool or index in seen
                                or (bank == 35 and (index != -1 or value is not True))
                                or (bank != 35 and not 0 <= index < BANK_SHAPES[bank])):
                            raise ValueError("Invalid local field/type")
                        seen.add(index)
                elif kind == "wait":
                    if len(effect) != 2 or type(effect[1]) is not int or not 0 < effect[1] <= 29000:
                        raise ValueError("Invalid source wait")
                elif kind == "subsequence":
                    self._validate_frames(effect[1])
                elif kind in ("call_clear_error", "call_handle_error"):
                    if len(effect) != 2 or effect[1] not in ("1_Focales ON.vi", "1_Focales OFF.vi"):
                        raise ValueError("Unqualified helper boundary")
                elif kind == "publish":
                    for name, bank in effect[1]:
                        if (name, bank) not in (("DPS", 36), ("EPS", 44), ("C4_OUT_DIO96", 15)):
                            raise ValueError("Unqualified publication intent")
                else:
                    raise ValueError("Unqualified source effect")

    def plan(self, operation, new_value=True):
        if operation not in EVENTS or type(new_value) is not bool:
            raise ValueError("Qualified operation and explicit Boolean NewVal required")
        return copy.deepcopy(self._catalog["procedures"][operation]["frames"]) if new_value else []

    def project_frame(self, uid, snapshots):
        """One frame, explicit read snapshots; no automatic next-frame execution.

        A helper is a boundary, NOT assumed successful. A publish is intent,
        NOT PSP delivery. Same-frame publication reads are independent of
        same-frame writes; they use the supplied snapshot, not a merge.
        """
        if uid not in self._frames:
            raise ValueError("Unqualified source frame")
        result = dict(source_uid=uid, local_writes=[], publication_intents=[],
                      wait_requests_ms=[], nested_frame_uids=[], helper_boundaries=[],
                      hardware_enabled=False, hardware_acknowledged=False,
                      frame_effects_ordered=False)
        for effect in self._frames[uid]:
            kind = effect[0]
            if kind == "write":
                _, bank, changes = effect
                values = True if bank == 35 else list(_snapshot(snapshots, bank))
                if bank != 35:
                    for index, value in changes:
                        values[index] = value
                result["local_writes"].append((bank, values))
            elif kind == "publish":
                result["publication_intents"].append([
                    (name, bank, list(_snapshot(snapshots, bank))) for name, bank in effect[1]])
            elif kind == "wait":
                result["wait_requests_ms"].append(effect[1])
            elif kind == "subsequence":
                result["nested_frame_uids"].append([frame[0] for frame in effect[1]])
            else:
                result["helper_boundaries"].append(dict(
                    helper=effect[1], error_policy=kind, completion="UNSUPPLIED"))
        return result

    def admission(self, operation):
        """Explicit separation: known procedure is not live-control qualification."""
        if operation not in EVENTS:
            raise ValueError("Unqualified operation")
        return dict(operation=operation, event=EVENTS[operation][0],
                    source_frames_modeled=True, live_control_enabled=False,
                    physical_cooling_permit="UNQUALIFIED",
                    physical_stage_feedback="UNQUALIFIED",
                    hardware_shutdown_qualified=False,
                    reason="Static stage model cannot authorize outputs")


def load_model():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "modulator_stage_catalog.json")
    with io.open(path, "rb") as source:
        raw = source.read()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError("Source-qualified stage catalog identity changed")
    return StageModel(json.loads(raw.decode("utf-8")))


def cooling_flow_trip(c4_in, c3_in):
    """Saved raw Boolean predicate, NOT a klystron heating-flow permit."""
    c4, c3 = tuple(c4_in), tuple(c3_in)
    if len(c4) != 64 or len(c3) != 56 or any(type(v) is not bool for v in c4 + c3):
        raise ValueError("Explicit complete raw C4/C3 Boolean inputs required")
    return (c4[19] or c4[38]) and (not c3[0] or not c3[6])
