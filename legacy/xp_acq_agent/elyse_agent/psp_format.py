from __future__ import division

import copy
import csv
import io
import os


PSP_FORMAT = "psp_supervision_scalar_v1"
PSP_PAYLOAD_FORMAT = "channel:value:source_timestamp"


SOURCE_BINDINGS = {
    ("C1NI6071E", "AI"): ("analog_inputs", "C1_NI6071E_AI"),
    ("C2NI6071E", "AI"): ("analog_inputs", "C2_NI6071E_AI"),
    ("C3_IN_DIO96", "DI"): ("digital_inputs", "C3_DIO96_DI"),
    ("C4_IN_DIO96", "DI"): ("digital_inputs", "C4_DIO96_DI"),
    ("C5_IN_DIO96", "DI"): ("digital_inputs", "C5_DIO96_DI"),
    ("C3_OUT_DIO96", "DO"): ("digital_outputs", "C3_DIO96_DO"),
    ("C4_OUT_DIO96", "DO"): ("digital_outputs", "C4_DIO96_DO"),
    ("C5_OUT_DIO96", "DO"): ("digital_outputs", "C5_DIO96_DO"),
    ("C6NI6703", "AO"): ("analog_outputs_volts", "C6_NI6703_AO"),
    ("C7NI6703", "AO"): ("analog_outputs_volts", "C7_NI6703_AO"),
    ("C8NI6703", "AO"): ("analog_outputs_volts", "C8_NI6703_AO"),
    ("C9NI6703", "AO"): ("analog_outputs_volts", "C9_NI6703_AO"),
}


def _default_channel_map_path():
    package_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(package_dir), "data", "channel_map.csv")


def _raw_channel_name(row):
    return "{0:02d} {1} {2} {3}".format(
        int(row["index"]),
        row["logical_code"].strip(),
        row["connector_pin"].strip(),
        row["description"].strip(),
    )


def _wire_value(value):
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def _format_wire_value(value):
    if value == int(value):
        return str(int(value))
    return "{0:.12g}".format(value)


class PspSupervisionEncoder(object):
    """Encode one simulator image as the scalar stream consumed by DS_PSP."""

    def __init__(self, channel_map_path=None):
        self.channel_map_path = channel_map_path or _default_channel_map_path()
        self._channels = self._load_channels()

    def _load_channels(self):
        channels = []
        with io.open(self.channel_map_path, "r", encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                status = str(row.get("status") or "").strip()
                if status == "LEGACY_OR_UNRESOLVED_C11_FIELDS":
                    continue
                group = str(row.get("group") or "").strip()
                direction = str(row.get("direction") or "").strip()
                index = int(row["index"])
                binding = SOURCE_BINDINGS.get((group, direction))
                if binding is None and not (
                    group == "C10-11 NI6602" and direction == "CO"
                ):
                    continue
                channels.append(
                    {
                        "raw_name": _raw_channel_name(row),
                        "group": group,
                        "direction": direction,
                        "index": index,
                        "logical_code": str(row.get("logical_code") or ""),
                        "connector_pin": str(row.get("connector_pin") or ""),
                        "description": str(row.get("description") or ""),
                        "status": status,
                        "source_section": binding[0] if binding else "counter_outputs",
                        "source_task": binding[1] if binding else "C10_NI6602_CO",
                    }
                )
        return channels

    def catalog(self):
        return {
            "format": PSP_FORMAT,
            "payload_format": PSP_PAYLOAD_FORMAT,
            "channel_count": len(self._channels),
            "channels": copy.deepcopy(self._channels),
            "excluded_unresolved_c11_fields": 16,
        }

    def encode(self, snapshot, source_timestamp):
        timestamp_text = "{0:.6f}".format(float(source_timestamp))
        data = {}
        payloads = []
        for channel in self._channels:
            value = self._read_value(snapshot, channel)
            data[channel["raw_name"]] = value
            payloads.append(
                "{0}:{1}:{2}".format(
                    channel["raw_name"], _format_wire_value(value), timestamp_text
                )
            )
        return {
            "format": PSP_FORMAT,
            "payload_format": PSP_PAYLOAD_FORMAT,
            "source_timestamp": float(source_timestamp),
            "timestamp_utc": snapshot["timestamp_utc"],
            "sequence": snapshot["sequence"],
            "scenario": snapshot["scenario"],
            "channel_count": len(self._channels),
            "messages_in_batch": len(payloads),
            "data": data,
            "payloads": payloads,
            "outputs_simulated": True,
            "hardware_writes": False,
        }

    @staticmethod
    def _read_value(snapshot, channel):
        if channel["source_section"] == "counter_outputs":
            logical_index = channel["index"]
            counter = snapshot["counter_outputs"][logical_index // 2]
            field = "delay_seconds" if logical_index % 2 == 0 else "width_seconds"
            return float(counter[field]) * 1000000.0
        values = snapshot[channel["source_section"]][channel["source_task"]]
        return _wire_value(values[channel["index"]])
