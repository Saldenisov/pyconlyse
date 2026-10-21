"""Independent receive-only Everest recorder. Never opens NI, PSP or XP.

The receiver exposes latest state, not a lossless journal. Every distinct
observed receipt is archived; missed receiver receipts and source-sequence
gaps are reported separately. Numeric JSON tokens are preserved losslessly in
compressed byte datasets, including integers beyond IEEE-754 exact range.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time
import uuid

import h5py
import numpy as np

DEVICE = "tango://10.20.30.202:10000/elyse/acquisition/telemetry"
BANKS = tuple("C1NI6071E C2NI6071E C3_IN_DIO96 C3_OUT_DIO96 C4_IN_DIO96 C4_OUT_DIO96 "
              "C5_IN_DIO96 C5_OUT_DIO96 C6NI6703 C7NI6703 C8NI6703 C9NI6703 C1011NI6602 "
              "DPS DPC EPS EPC C12NI1409 VDM-A VDM-S VDD VAM-A VAM-S VAD VTA VTS VTL".split())
INDEX = np.dtype([("observed_ns", "<u8"), ("monotonic_ns", "<u8"),
                  ("offset", "<u8"), ("length", "<u4"),
                  ("receiver_count", "<u8"), ("kind", "S24")])
DISCRETE_BANKS = frozenset("EPS DPS DPC EPC C3_IN_DIO96 C3_OUT_DIO96 "
                           "C4_IN_DIO96 C4_OUT_DIO96 C5_IN_DIO96 C5_OUT_DIO96".split())


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"), sort_keys=True).encode("utf-8")


class Archive:
    """Exclusive writer; monitor JSON, not the live HDF5 file on Windows.

    Windows HDF5 readers can deny writes even with swmr=True. The SWMR
    format is retained for recovery; live readers are not supported here.
    """
    def __init__(self, path):
        self.file = h5py.File(path, "x", libver="latest")
        self.file.attrs.update(schema_version=1, created_utc=utc_now(), source=DEVICE,
                               capture="observed_latest_receipts_not_lossless_ingress",
                               hardware_commands=False, compression="gzip9 lossless",
                               physical_measurements_verified=False,
                               atomic_across_banks=False,
                               live_hdf5_readers_supported=False,
                               clock_alignment="receiver/recorder UTC; XP clock unqualified",
                               recorder_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        self.payload = self.file.create_dataset(
            "payload_utf8", (0,), maxshape=(None,), dtype="u1", chunks=(262144,),
            compression="gzip", compression_opts=9, shuffle=True, fletcher32=True)
        self.index = self.file.create_dataset(
            "index", (0,), maxshape=(None,), dtype=INDEX, chunks=(256,),
            compression="gzip", compression_opts=9, shuffle=True, fletcher32=True)
        self.committed = self.file.create_dataset("committed_rows", data=np.uint64(0))
        self.file.flush()
        self.file.swmr_mode = True
        self.uncompressed_bytes = 0
        self.last_committed_rows = 0
        self.write_retries = 0
        self.last_write_error = ""

    def append(self, kind, value, receiver_count=0):
        raw = encoded(value)
        offset, row = len(self.payload), len(self.index)
        self.payload.resize((offset + len(raw),))
        self.payload[offset:] = np.frombuffer(raw, dtype="u1")
        self.index.resize((row + 1,))
        self.index[row] = (time.time_ns(), time.monotonic_ns(), offset, len(raw),
                           receiver_count, kind.encode("ascii"))
        self.uncompressed_bytes += len(raw)

    def _flush_once(self):
        self.payload.flush()
        self.index.flush()
        self.committed[()] = len(self.index)
        self.committed.flush()
        self.file.flush()

    def flush(self, max_wait_seconds=3.0):
        deadline = time.monotonic() + max_wait_seconds
        while True:
            try:
                self._flush_once()
                self.last_committed_rows = len(self.index)
                return
            except Exception as error:
                self.last_write_error = type(error).__name__ + ": " + str(error)[:2048]
                permission_denied = (isinstance(error, PermissionError)
                                     or "Permission denied" in str(error))
                if not permission_denied or time.monotonic() >= deadline:
                    raise
                self.write_retries += 1
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))

    def close(self, flush=True):
        try:
            if flush:
                self.flush()
        finally:
            self.file.close()


def flatten(value, path=""):
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from flatten(item, path + "/" + str(index))
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from flatten(item, path + "/" + key)
    else:
        yield path, value


class Observations:
    def __init__(self):
        self.previous_identity = None
        self.receiver_session = None
        self.receiver_count = None
        self.source_identity = None
        self.source_sequence = None
        self.missed_receiver_receipts = 0
        self.source_sequence_gaps = 0
        self.receiver_changes = 0
        self.frames = 0
        self.producer_source = None
        self.producer_changes = 0
        self.bank_hashes = {}
        self.bank_changes = Counter()
        self.field_values = {}
        self.field_changes = Counter()
        self.numeric = {}
        self.discrete_values = {}
        self.recent_discrete_changes = deque(maxlen=128)

    def accept(self, snapshot):
        if (type(snapshot) is not dict or snapshot.get("source") not in ("copied_labview_telemetry", "python_daqmx_acquisition")
                or snapshot.get("hardware_writes") is not False
                or snapshot.get("storage_mode") != "ram_latest"
                or type(snapshot.get("publications")) is not dict
                or set(snapshot["publications"]) - set(BANKS)):
            raise ValueError("Unexpected read-only telemetry receiver contract")
        producer = snapshot["source"]
        if producer == "python_daqmx_acquisition" and (
                set(snapshot["publications"]) != set(BANKS) or any(
                    bank.get("producer_kind") != "python_acquisition"
                    or bank.get("lv_type", {}).get("type") != "LvVariant"
                    for bank in snapshot["publications"].values())):
            raise ValueError("Complete, explicitly attributed Python 27-bank envelope required")
        session, count = snapshot["receiver_session"], snapshot["received_this_process"]
        if type(count) is not int or count < 0:
            raise ValueError("Invalid receiver count")
        identity = (session, count, producer)
        if identity == self.previous_identity:
            return False, []
        events = []
        if self.receiver_session is not None:
            if session != self.receiver_session:
                self.receiver_changes += 1
                events.append(dict(event="receiver_session_changed", before=self.receiver_session,
                                   after=session))
            elif count < self.receiver_count:
                raise ValueError("Receiver count regressed without session change")
            elif count > self.receiver_count + 1:
                missing = count - self.receiver_count - 1
                self.missed_receiver_receipts += missing
                events.append(dict(event="receiver_receipts_not_observed", count=missing,
                                   previous=self.receiver_count, current=count))
        if self.producer_source is not None and producer != self.producer_source:
            events.append(dict(event="telemetry_producer_changed", before=self.producer_source, after=producer,
                               summary_statistics_reset=True))
            self.producer_changes += 1
            self.source_identity = self.source_sequence = None
            self.bank_hashes.clear(); self.bank_changes.clear()
            self.field_values.clear(); self.field_changes.clear(); self.numeric.clear()
            self.discrete_values.clear(); self.recent_discrete_changes.clear()
        self.producer_source = producer
        banks = snapshot["publications"]
        if banks:
            source = next(iter(banks.values()))
            source_identity = (source["session_id"], source["relay_id"])
            sequence = source["sequence"]
            if self.source_identity == source_identity and self.source_sequence is not None:
                self.source_sequence_gaps += max(0, sequence - self.source_sequence - 1)
            self.source_identity, self.source_sequence = source_identity, sequence
        for name, bank in banks.items():
            digest = hashlib.sha256(encoded(dict(data=bank["data"], error=bank["error"]))).digest()
            if name in self.bank_hashes and digest != self.bank_hashes[name]:
                self.bank_changes[name] += 1
            self.bank_hashes[name] = digest
            if name in DISCRETE_BANKS:
                self.discrete_values[name] = json.loads(encoded(bank["data"]))
            valid = not bank["stale"] and not bank["error"]["status"] and bank["error"]["code"] == 0
            for suffix, value in flatten(bank["data"]):
                field = name + suffix
                # Type distinguishes False from 0; the authoritative archive
                # retains all original values even when quality is bad.
                tag = (type(value).__name__, value)
                if field in self.field_values and self.field_values[field] != tag:
                    self.field_changes[field] += 1
                    if name in DISCRETE_BANKS:
                        self.recent_discrete_changes.append(dict(
                            observed_utc=utc_now(), field=field,
                            before=self.field_values[field][1], after=value,
                            receiver_session=session, receiver_count=count,
                            bank_stale=bank["stale"], bank_error=bank["error"]))
                self.field_values[field] = tag
                if valid and type(value) in (int, float) and math.isfinite(value):
                    state = self.numeric.setdefault(field, [0, value, value, 0.0, 0.0])
                    state[0] += 1
                    state[1], state[2] = min(state[1], value), max(state[2], value)
                    delta = value - state[3]
                    state[3] += delta / state[0]
                    state[4] += delta * (value - state[3])
        self.previous_identity, self.receiver_session, self.receiver_count = identity, session, count
        self.frames += 1
        return True, events

    def summary(self):
        return dict(recorded_snapshots=self.frames,
                    telemetry_source=self.producer_source, telemetry_source_changes=self.producer_changes,
                    missed_receiver_receipts=self.missed_receiver_receipts,
                    source_sequence_gaps=self.source_sequence_gaps,
                    receiver_session_changes=self.receiver_changes,
                    receiver_session=self.receiver_session, receiver_count=self.receiver_count,
                    bank_value_changes=dict(self.bank_changes),
                    discrete_values=self.discrete_values,
                    recent_discrete_changes=list(self.recent_discrete_changes),
                    most_changed_fields=self.field_changes.most_common(25),
                    numeric_statistics={key: dict(n=s[0], minimum=s[1], maximum=s[2],
                        mean=s[3], variance=s[4] / (s[0] - 1) if s[0] > 1 else 0.0)
                        for key, s in self.numeric.items()})


class TangoReader:
    def __init__(self):
        import tango
        self.proxy = tango.DeviceProxy(DEVICE)
        self.proxy.set_timeout_millis(1500)

    def read(self):
        attributes = self.proxy.read_attributes(["State", "telemetry_json"])
        if any(item.has_failed for item in attributes):
            raise RuntimeError("Receiver attributes failed")
        return str(attributes[0].value), json.loads(attributes[1].value)


def atomic_status(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(encoded(value))
    os.replace(temporary, path)


def run(folder, period=0.05, max_seconds=None):
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    archive_path, status_path = folder / "telemetry.h5", folder / "status.json"
    archive, observations = Archive(archive_path), Observations()
    started = last_flush = last_read = time.monotonic()
    start_utc, recorder_id = utc_now(), uuid.uuid4().hex
    reads = read_errors = stale_reads = storage_errors = 0
    state, last_error, last_quality = "RUNNING", "", None
    last_success = None
    last_bank_count = 0
    max_bank_age = 0.0
    reader = None
    archive.append("recorder_start", dict(utc=start_utc, recorder_id=recorder_id,
                   period=period, source=DEVICE, guarantee="observed_latest_only",
                   stop_file=str(folder / "stop.request")))

    def report():
        value = observations.summary()
        value.update(state=state, recorder_id=recorder_id, pid=os.getpid(),
                     started_utc=start_utc, updated_utc=utc_now(), file=str(archive_path),
                     reads=reads, read_errors=read_errors, stale_reads=stale_reads,
                     last_error=last_error, last_success_utc=last_success,
                     last_quality=last_quality, banks=last_bank_count,
                     phase="baseline_until_operator_time_marker",
                     max_observed_bank_age_seconds=max_bank_age,
                     recorded_uncompressed_bytes=archive.uncompressed_bytes,
                     file_bytes=archive_path.stat().st_size,
                     committed_rows=archive.last_committed_rows,
                     storage_errors=storage_errors, write_retries=archive.write_retries,
                     last_write_error=archive.last_write_error,
                     live_hdf5_readers_supported=False,
                     hardware_commands_sent=False, capture_is_lossless_ingress=False)
        atomic_status(status_path, value)

    try:
        report()
        while not (folder / "stop.request").exists():
            tick = time.monotonic()
            if max_seconds is not None and tick - started >= max_seconds:
                break
            if tick - last_read > 3:
                archive.append("observation_gap", dict(utc=utc_now(), seconds=tick-last_read))
            last_read = tick
            try:
                if reader is None:
                    reader = TangoReader()
                server_state, snapshot = reader.read()
                reads += 1
                banks = snapshot["publications"]
                last_bank_count = len(banks)
                ages = [b["age_seconds"] for b in banks.values()]
                max_bank_age = max([max_bank_age] + ages)
                bad = [name for name, b in banks.items() if b["stale"]
                       or b["error"]["status"] or b["error"]["code"] != 0]
                quality = ("FRESH" if server_state == "ON" and set(banks) == set(BANKS) and not bad
                           else "UNHEALTHY")
                stale_reads += int(quality != "FRESH")
                changed, events = observations.accept(snapshot)
            except Exception as error:
                read_errors += 1
                message = type(error).__name__ + ": " + str(error)[:2048]
                if message != last_error:
                    archive.append("read_error", dict(utc=utc_now(), message=message))
                last_error, last_quality, reader = message, "READ_ERROR", None
            else:
                # Storage failures must not be misreported as Tango read errors.
                if changed:
                    archive.append("snapshot", dict(observed_utc=utc_now(), state=server_state,
                                   quality=quality, snapshot=snapshot), snapshot["received_this_process"])
                for event in events:
                    archive.append("gap_or_session", dict(utc=utc_now(), **event))
                if quality != last_quality:
                    archive.append("quality", dict(utc=utc_now(), before=last_quality,
                                   after=quality, bad_banks=bad))
                last_quality, last_success, last_error = quality, utc_now(), ""
            if time.monotonic() - last_flush >= 1:
                if shutil.disk_usage(folder).free < 5 * 1024**3:
                    raise OSError("Recorder stopped: less than 5 GiB free on recording volume")
                archive.flush()
                report()
                last_flush = time.monotonic()
            time.sleep(max(0, (1 if last_error else period) - (time.monotonic() - tick)))
        state = "STOPPED"
    except KeyboardInterrupt:
        state = "STOPPED"
    except Exception as error:
        state, last_error = "FAILED", type(error).__name__ + ": " + str(error)[:2048]
        storage_errors += 1
    finally:
        try:
            if state != "FAILED":
                archive.append("recorder_stop", dict(utc=utc_now(), state=state, error=last_error))
                archive.flush()
        except Exception as error:
            state, last_error = "FAILED", type(error).__name__ + ": " + str(error)[:2048]
            storage_errors += 1
        finally:
            try:
                archive.close(flush=False)
            except Exception as error:
                if state != "FAILED":
                    last_error = type(error).__name__ + ": " + str(error)[:2048]
                state = "FAILED"
                storage_errors += 1
            finally:
                # A broken archive must not leave an apparently RUNNING status.
                report()
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--period", type=float, default=0.05)
    parser.add_argument("--max-seconds", type=float)
    args = parser.parse_args()
    if not math.isfinite(args.period) or not 0.02 <= args.period <= 10:
        parser.error("period must be finite and 0.02..10 seconds")
    raise SystemExit(1 if run(args.output, args.period, args.max_seconds) == "FAILED" else 0)
