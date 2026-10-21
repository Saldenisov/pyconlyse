"""Read-only 27-bank snapshots, LabVIEW XML and latest-only relay, Python 3.4.

The timestamp is XP receipt time, not a hardware sample timestamp. The VI reads
local controls sequentially, so a snapshot is not an atomic hardware sample.
No driver, PSP, Tango, database or file storage is imported here.
"""

from __future__ import division

import copy
import datetime
import json
import math
import re
import threading
import time
import uuid
import xml.etree.ElementTree as ET

from .labview_telemetry import validate_packet

SNAPSHOT_PUBLICATION = "ACQ_SHARED_STATE"
BANKS = (
    "C1NI6071E",
    "C2NI6071E",
    "C3_IN_DIO96",
    "C3_OUT_DIO96",
    "C4_IN_DIO96",
    "C4_OUT_DIO96",
    "C5_IN_DIO96",
    "C5_OUT_DIO96",
    "C6NI6703",
    "C7NI6703",
    "C8NI6703",
    "C9NI6703",
    "C1011NI6602",
    "DPS",
    "DPC",
    "EPS",
    "EPC",
    "C12NI1409",
    "VDM-A",
    "VDM-S",
    "VDD",
    "VAM-A",
    "VAM-S",
    "VAD",
    "VTA",
    "VTS",
    "VTL",
)
MAX_XML_BYTES = 262144
METADATA_TAGS = frozenset(("Name", "NumElts", "Dimsize"))
INTEGER_TYPES = dict(
    (prefix + str(bits), (bits, prefix == "I"))
    for prefix in ("I", "U")
    for bits in (8, 16, 32, 64)
)


def _tag(node):
    if "}" in node.tag:
        namespace, name = node.tag[1:].split("}", 1)
        if namespace not in ("http://www.ni.com/labview", "http://www.ni.com/LVData"):
            raise ValueError("unknown LabVIEW XML namespace")
        return name
    return node.tag


def _text(node, name):
    matches = [child for child in node if _tag(child) == name]
    if len(matches) != 1 or len(matches[0]):
        raise ValueError("missing, duplicate or nested XML field: " + name)
    return matches[0].text or ""


def _integer(text, bits, signed):
    if not re.match(r"^-?[0-9]+$", text):
        raise ValueError("invalid integer XML value")
    value = int(text)
    low, high = (
        (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1) if signed else (0, 2**bits - 1)
    )
    if not low <= value <= high:
        raise ValueError("integer XML value outside declared type")
    return value


def _decode(node, depth=0):
    if depth > 12 or node.attrib:
        raise ValueError("unsupported XML depth or attributes")
    kind = _tag(node)
    name = _text(node, "Name")
    if len(name) > 4096:
        raise ValueError("XML name exceeds limit")
    descriptor = dict(type=kind, name=name)
    children = list(node)
    if kind == "LvVariant":
        values = [child for child in children if _tag(child) != "Name"]
        if len(values) > 1:
            raise ValueError("variant attributes/multiple values are not supported")
        if not values:
            descriptor["contained_type"] = None
            return None, descriptor
        value, datatype = _decode(values[0], depth + 1)
        descriptor["contained_type"] = datatype
        return value, descriptor
    if kind in ("Cluster", "Array"):
        values = [child for child in children if _tag(child) not in METADATA_TAGS]
        if kind == "Cluster":
            count = _integer(_text(node, "NumElts"), 32, False)
            if count != len(values) or any(
                _tag(child) == "Dimsize" for child in children
            ):
                raise ValueError("cluster element count mismatch")
        else:
            dimensions = [
                _integer(child.text or "", 32, False)
                for child in children
                if _tag(child) == "Dimsize"
            ]
            if len(dimensions) != 1 or any(
                _tag(child) == "NumElts" for child in children
            ):
                raise ValueError("only one-dimensional snapshot arrays are supported")
            count = dimensions[0]
            descriptor["dimensions"] = dimensions
            # NI XML can include one datatype prototype for an empty array.
            if count == 0 and len(values) == 1:
                _, datatype = _decode(values[0], depth + 1)
                descriptor["element_type"] = datatype
                return [], descriptor
            if count != len(values):
                raise ValueError("array dimension/element count mismatch")
        decoded = [_decode(child, depth + 1) for child in values]
        descriptor["fields" if kind == "Cluster" else "elements"] = [
            item[1] for item in decoded
        ]
        return [item[0] for item in decoded], descriptor
    if kind not in INTEGER_TYPES and kind not in (
        "DBL",
        "SGL",
        "Boolean",
        "String",
        "EB",
        "EW",
        "EL",
    ):
        raise ValueError("unsupported LabVIEW XML type: " + kind)
    permitted = (
        {"Name", "Val", "Choice"} if kind in ("EB", "EW", "EL") else {"Name", "Val"}
    )
    if any(_tag(child) not in permitted for child in children):
        raise ValueError("unexpected scalar XML field")
    text = _text(node, "Val")
    if kind in INTEGER_TYPES:
        return _integer(text, *INTEGER_TYPES[kind]), descriptor
    if kind in ("EB", "EW", "EL"):
        descriptor["choices"] = [
            child.text or "" for child in children if _tag(child) == "Choice"
        ]
        value = _integer(text, {"EB": 8, "EW": 16, "EL": 32}[kind], False)
        if not 0 <= value < len(descriptor["choices"]):
            raise ValueError("enum XML value outside choices")
        return value, descriptor
    if kind == "Boolean":
        if text not in ("0", "1", "false", "true"):
            raise ValueError("invalid Boolean XML value")
        return text in ("1", "true"), descriptor
    if kind == "String":
        if len(text) > 4096:
            raise ValueError("XML string exceeds limit")
        return text, descriptor
    value = float(text)
    if not math.isfinite(value):
        # Preserve unavailable/nonfinite values explicitly, never replace with zero.
        return dict(
            nonfinite="NaN" if math.isnan(value) else ("+Inf" if value > 0 else "-Inf")
        ), descriptor
    return value, descriptor


def decode_snapshot_xml(raw, xml_encoding="utf-8"):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_XML_BYTES:
        raise ValueError("snapshot XML byte limit exceeded")
    if xml_encoding not in ("utf-8", "cp1252"):
        raise ValueError("unsupported snapshot wire encoding")
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("XML DTD/entities are forbidden")
    try:
        # LabVIEW 2012 on French Windows emits native ANSI strings. Decode
        # only the explicitly configured wire encoding, never guess/fallback
        # or replace invalid bytes. JSON relaying remains UTF-8.
        root = ET.fromstring(raw.decode(xml_encoding, "strict"))
    except (UnicodeDecodeError, ET.ParseError) as error:
        raise ValueError("invalid LabVIEW XML: " + str(error))
    if sum(1 for _ in root.iter()) > 16384:
        raise ValueError("XML node limit exceeded")
    if _tag(root) != "LvVariant":
        raise ValueError("snapshot must be an outer LabVIEW variant")
    values, datatype = _decode(root)
    contained = datatype.get("contained_type")
    if not contained or contained["type"] != "Array" or len(values) != len(BANKS):
        raise ValueError("snapshot must contain exactly 27 bank records")
    records = []
    for value, shape in zip(values, contained["elements"]):
        fields = shape.get("fields", [])
        if (
            shape["type"] != "Cluster"
            or len(value) != 3
            or [f["type"] for f in fields] != ["String", "LvVariant", "Cluster"]
        ):
            raise ValueError("invalid bank record type")
        bank, data, error = value
        bank = "C1011NI6602" if bank == "C10-11 NI6602" else bank
        if bank not in BANKS:
            raise ValueError("unknown shared-state bank")
        if len(error) != 3 or [f["type"] for f in fields[2].get("fields", [])] != [
            "Boolean",
            "I32",
            "String",
        ]:
            raise ValueError("invalid bank-read error cluster")
        records.append(
            dict(
                publication=bank,
                data=data,
                lv_type=fields[1],
                error=dict(status=error[0], code=error[1], source=error[2]),
            )
        )
    if tuple(record["publication"] for record in records) != BANKS:
        raise ValueError("duplicate, reordered or missing shared-state banks")
    return records


def validate_snapshot_packet(packet):
    encoded = validate_packet(packet, (SNAPSHOT_PUBLICATION,), structural_limit=32768)
    payload = packet["data"]
    if type(payload) is not dict or set(payload) != set(
        ("snapshot_version", "capture_kind", "timestamp_origin", "banks")
    ):
        raise ValueError("invalid shared snapshot data")
    if (
        type(payload["snapshot_version"]) is not int
        or payload["snapshot_version"] != 1
        or payload["capture_kind"] != "sequential_local_controls"
        or payload["timestamp_origin"] != "xp_receipt_not_card_sample"
        or type(payload["banks"]) is not list
        or len(payload["banks"]) != len(BANKS)
    ):
        raise ValueError("invalid shared snapshot metadata")
    for record, bank in zip(payload["banks"], BANKS):
        if (
            type(record) is not dict
            or set(record) != set(("publication", "data", "lv_type", "error"))
            or record["publication"] != bank
        ):
            raise ValueError("invalid shared snapshot bank order/schema")
        error = record["error"]
        if (
            type(record["lv_type"]) is not dict
            or record["lv_type"].get("type") != "LvVariant"
            or type(error) is not dict
            or set(error) != set(("status", "code", "source"))
            or type(error["status"]) is not bool
            or type(error["code"]) is not int
            or not -(2**31) <= error["code"] < 2**31
            or not isinstance(error["source"], str)
        ):
            raise ValueError("invalid shared snapshot datatype/read error")
    return encoded


def expand_snapshot(packet):
    validate_snapshot_packet(packet)
    result = {}
    for record in packet["data"]["banks"]:
        item = dict(packet)
        item.update(
            publication=record["publication"],
            data=copy.deepcopy(record["data"]),
            lv_type=copy.deepcopy(record["lv_type"]),
            error=copy.deepcopy(record["error"]),
            timestamp_origin="xp_receipt_not_card_sample",
            capture_kind="sequential_local_controls",
        )
        result[item["publication"]] = item
    return result


class LatestSnapshotOutbox(object):
    """One pending latest snapshot plus one immutable in-flight retry.

    Relay IDs are assigned on peek, not ingestion, so replacing pending
    snapshots cannot create a gap in the existing signed ACK protocol.
    """

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._latest = self._inflight = None
        self._next_id = 1
        self.relay_id = uuid.uuid4().hex
        self.changed = threading.Event()
        self.delivered = self.replaced = 0

    def enqueue(self, encoded, received_utc):
        if len(encoded.encode("utf-8")) > MAX_XML_BYTES:
            raise ValueError("encoded snapshot exceeds limit")
        with self._lock:
            if self._latest is not None:
                self.replaced += 1
            self._latest = (encoded, received_utc, self._clock())
            self.changed.set()

    def peek(self):
        with self._lock:
            if self._inflight is None:
                if self._latest is None:
                    self.changed.clear()
                    return None
                self._inflight = (self._next_id,) + self._latest
                self._latest = None
            sequence, encoded, received_utc, received_at = self._inflight
            return dict(
                schema_version=1,
                relay_id=self.relay_id,
                message_id=sequence,
                received_utc_on_xp=received_utc,
                age_seconds_on_xp=max(0.0, self._clock() - received_at),
                packet=json.loads(encoded),
                hardware_writes=False,
            )

    def acknowledge(self, relay_id, message_id):
        with self._lock:
            if (
                relay_id != self.relay_id
                or self._inflight is None
                or message_id != self._inflight[0]
            ):
                raise ValueError("ACK does not match in-flight snapshot")
            self._inflight = None
            self._next_id += 1
            self.delivered += 1
            if self._latest is None:
                self.changed.clear()

    def status(self):
        with self._lock:
            return dict(
                capacity=2,
                pending=int(self._latest is not None) + int(self._inflight is not None),
                pending_latest=int(self._latest is not None),
                inflight=int(self._inflight is not None),
                replaced_pending=self.replaced,
                everest_acknowledged=self.delivered,
                overflow_policy="replace_pending_latest_preserve_inflight",
                durable=False,
                relay_id=self.relay_id,
            )


class SharedStateStore(object):
    def __init__(
        self, producer_kind="copied_acquisition", clock=None, xml_encoding="utf-8"
    ):
        if producer_kind not in ("fixture", "copied_acquisition"):
            raise ValueError("invalid snapshot producer kind")
        if xml_encoding not in ("utf-8", "cp1252"):
            raise ValueError("unsupported snapshot wire encoding")
        self.producer_kind = producer_kind
        self.xml_encoding = xml_encoding
        self.xml_diagnostics = {}
        self.session_id = uuid.uuid4().hex
        self.clock = clock or time.monotonic
        self.outbox = LatestSnapshotOutbox(clock=self.clock)
        self.lock = threading.RLock()
        self._latest = None
        self._received_at = None
        self.accepted = self.rejected = 0
        self.last_error = ""

    def ingest(self, raw, peer):
        if peer != "127.0.0.1":
            raise ValueError("snapshot ingestion requires IPv4 loopback")
        if type(raw) is bytes:
            try:
                raw.decode("utf-8", "strict")
                utf8_valid = True
            except UnicodeDecodeError:
                utf8_valid = False
            with self.lock:
                # Structural diagnostics only; no values or XML history.
                self.xml_diagnostics = dict(
                    bytes=len(raw),
                    nonascii_bytes=sum(byte >= 128 for byte in raw),
                    utf8_valid=utf8_valid,
                )
        records = decode_snapshot_xml(raw, self.xml_encoding)
        with self.lock:
            packet = dict(
                session_id=self.session_id,
                publication=SNAPSHOT_PUBLICATION,
                sequence=self.accepted,
                source_seconds_1904=time.time() + 2082844800,
                producer_kind=self.producer_kind,
                data=dict(
                    snapshot_version=1,
                    capture_kind="sequential_local_controls",
                    timestamp_origin="xp_receipt_not_card_sample",
                    banks=records,
                ),
                error=dict(status=False, code=0, source=""),
            )
            encoded = validate_snapshot_packet(packet)
            received_utc = datetime.datetime.utcnow().isoformat() + "Z"
            self.outbox.enqueue(encoded, received_utc)
            self._latest = copy.deepcopy(packet)
            self._received_at = self.clock()
            self.accepted += 1
            self.last_error = ""
            return dict(
                accepted=True,
                bank_count=len(BANKS),
                sequence=packet["sequence"],
                hardware_writes=False,
                acknowledged_on="xp_ram_not_everest",
            )

    def snapshot(self):
        with self.lock:
            age = (
                None
                if self._received_at is None
                else max(0.0, self.clock() - self._received_at)
            )
            return dict(
                session_id=self.session_id,
                accepted=self.accepted,
                rejected=self.rejected,
                last_error=self.last_error,
                xml_encoding=self.xml_encoding,
                xml_diagnostics=dict(self.xml_diagnostics),
                latest_age_seconds=age,
                stale=age is None or age >= 2,
                bank_count=0
                if self._latest is None
                else len(self._latest["data"]["banks"]),
                storage_mode="latest_snapshot_plus_one_inflight_ram",
                hardware_writes=False,
                physical_measurements_verified=False,
                atomic_across_publications=False,
                outbox=self.outbox.status(),
            )
