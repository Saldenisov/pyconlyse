"""Everest-only, read-only comparison during LOCAL hardware button trials.

No NI initialization/commands, PSP writes, files or telemetry history. One
previous sample and the latest comparison remain in RAM. CLI prints diagnostic
counts/channel identities, not measured value arrays. It does not authorize a
trial or establish cooling/interlock readiness.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time

from DeviceServers.control.elyse_acq.runtime_client import read_runtime
from tools.acq_runtime_telemetry_check import load_input_labels


BANKS = (
    ("C1_NI6071E_AI", "C1NI6071E", "analog_input", 64),
    ("C2_NI6071E_AI", "C2NI6071E", "analog_input", 64),
    ("C11_NI6220_AI", None, "analog_input", 16),
    ("C3_DIO96_DI", "C3_IN_DIO96", "digital_input", 56),
    ("C4_DIO96_DI", "C4_IN_DIO96", "digital_input", 64),
    ("C5_DIO96_DI", "C5_IN_DIO96", "digital_input", 56),
)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def input_values(snapshot, max_age, transit_seconds):
    """Reject stale/demo/partial data rather than inventing zero/off inputs."""
    latest = snapshot.get("latest") or {}
    if (snapshot.get("state") != "RUNNING" or snapshot.get("stale") is not False
            or snapshot.get("error") or snapshot.get("resource_count") != 21
            or snapshot.get("current_operation") is not None
            or snapshot.get("storage_mode") != "ram_latest"
            or snapshot.get("auto_initialize") is not False
            or snapshot.get("remote_initialization_enabled") is not False
            or snapshot.get("remote_setpoints_enabled") is not False
            or not finite(snapshot.get("age_seconds"))
            or not 0 <= snapshot["age_seconds"] + transit_seconds <= max_age
            or type(snapshot.get("sequence")) is not int or snapshot["sequence"] < 1
            or latest.get("source") != "python_daqmx_acquisition"
            or latest.get("simulated") is not False):
        raise ValueError("No fresh, complete, real-card input sample available")
    values = {}
    for bank, _group, kind, count in BANKS:
        record = latest.get("banks", {}).get(bank, {})
        vector = record.get("values")
        if record.get("kind") != kind or type(vector) is not list or len(vector) != count:
            raise ValueError("Invalid bank shape: " + bank)
        if kind == "analog_input" and record.get("unit") != "V":
            raise ValueError("Expected raw volts: " + bank)
        for index, value in enumerate(vector):
            if (kind == "digital_input" and type(value) is not bool) or (
                    kind == "analog_input" and not finite(value)):
                raise ValueError("Invalid scalar: {0}[{1}]".format(bank, index))
            values[(bank, index)] = value
    return values


class InputObserver:
    def __init__(self, labels=None, analog_step_volts=.01, max_age=2):
        if not finite(analog_step_volts) or analog_step_volts <= 0 or not finite(max_age) or max_age <= 0:
            raise ValueError("Positive finite thresholds required")
        self.labels = load_input_labels() if labels is None else labels
        self.analog_step_volts, self.max_age = analog_step_volts, max_age
        self.previous = self.previous_sequence = self.previous_interval = None
        self.latest_result = None

    def gap(self, reason):
        self.previous = self.previous_sequence = self.previous_interval = None
        self.latest_result = dict(state="NOT_READY", reason=str(reason), changes=[],
                                  storage_mode="ram_previous_and_latest_comparison")
        return self.latest_result

    def observe(self, snapshot, request_started, request_finished):
        if (not finite(request_started) or not finite(request_finished)
                or request_finished < request_started):
            return self.gap("Invalid local request time interval")
        try:
            values = input_values(snapshot, self.max_age, request_finished - request_started)
        except (ValueError, TypeError, AttributeError) as error:
            return self.gap(error)
        sequence = snapshot["sequence"]
        interval = [request_started, request_finished]
        base = dict(sequence=sequence, changes=[], analog_step_volts=self.analog_step_volts,
                    response_interval_monotonic_s=interval, values_checked=len(values),
                    physical_edge_times_known=False, within_snapshot_order_known=False,
                    output_readback_available=False, storage_mode="ram_previous_and_latest_comparison")
        if self.previous is None or sequence < self.previous_sequence:
            base.update(state="BASELINE", baseline_reason="first_valid_or_after_gap" if self.previous is None else "sequence_rollback")
        elif sequence == self.previous_sequence:
            # A repeated publication is not an independent measurement.
            if values != self.previous:
                return self.gap("Input values changed without a new source sequence")
            base.update(state="DUPLICATE")
            self.latest_result = base
            return base
        else:
            changes = []
            for bank, group, kind, count in BANKS:
                for index in range(count):
                    old, new = self.previous[(bank, index)], values[(bank, index)]
                    changed = old != new if kind == "digital_input" else abs(new - old) >= self.analog_step_volts
                    if changed:
                        label = self.labels[(group, index)] if group is not None else "/11/ai{0} (raw volts; purpose unverified)".format(index)
                        changes.append(dict(bank=bank, index=index, kind=kind, label=label,
                                            before=old, after=new, unit="bool" if kind == "digital_input" else "V"))
            base.update(state="CHANGES" if changes else "UNCHANGED", changes=changes,
                        previous_sequence=self.previous_sequence,
                        previous_response_interval_monotonic_s=self.previous_interval,
                        source_snapshots_skipped=sequence - self.previous_sequence - 1,
                        observed_response_gap_seconds=request_finished - self.previous_interval[1])
        self.previous, self.previous_sequence, self.previous_interval = values, sequence, interval
        self.latest_result = base
        return base


def diagnostic_summary(result):
    """Do not dump input values/history into terminal logs."""
    return {key: value for key, value in result.items() if key != "changes"} | {
        "changed_inputs": [{key: row[key] for key in ("bank", "index", "kind", "label")}
                           for row in result["changes"]],
        "changed_digital_count": sum(row["kind"] == "digital_input" for row in result["changes"]),
        "changed_analog_count": sum(row["kind"] == "analog_input" for row in result["changes"]),
        "raw_values_printed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--readiness", action="store_true", help="One authenticated read; no initialization")
    parser.add_argument("--seconds", type=float, default=10, help="Bounded observation; 1..600 seconds")
    parser.add_argument("--poll-seconds", type=float, default=.1, help="Client poll; does not speed up NI sampling")
    args = parser.parse_args(argv)
    if not args.live or not 1 <= args.seconds <= 600 or not .05 <= args.poll_seconds <= 2:
        parser.error("--live and bounded duration/poll interval required")
    import tango
    key_path = tango.Database().get_device_property("elyse/acquisition/telemetry", ["key_file"])["key_file"]
    if len(key_path) != 1:
        raise ValueError("Expected one existing telemetry key file")
    key, observer = Path(key_path[0]).read_bytes().strip(), InputObserver()
    deadline = time.monotonic() + args.seconds
    last_not_ready = None
    while True:
        started = time.monotonic()
        try:
            snapshot = read_runtime(key, timeout=2)
            result = observer.observe(snapshot, started, time.monotonic())
        except Exception as error:
            result = observer.gap(type(error).__name__ + ": " + str(error))
        repeated_not_ready = result["state"] == "NOT_READY" and result.get("reason") == last_not_ready
        if args.readiness or (result["state"] not in ("DUPLICATE", "UNCHANGED") and not repeated_not_ready):
            print(json.dumps(diagnostic_summary(result), ensure_ascii=True), flush=True)
        last_not_ready = result.get("reason") if result["state"] == "NOT_READY" else None
        if args.readiness or time.monotonic() >= deadline:
            return 0 if result["state"] != "NOT_READY" else 2
        time.sleep(min(args.poll_seconds, max(0, deadline - time.monotonic())))


if __name__ == "__main__":
    raise SystemExit(main())
