"""Join original DCO indices with persisted Boolean data, not live defaults."""

from __future__ import annotations

import struct

from DeviceServers.control.elyse_acq.vi_simulation.saved_stop_data import (
    saved_source_stop_snapshot,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import STOP_FIELDS
from validate_acq_dfds_recovery import recovered_source, sha
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_stop_ui_bindings import checked_trees

DSINIT_SHA256 = "81BE850DD2F3A39EC4D1CA9A1E4E4C19899973DD63ECF72EBEA74EC0105CD45B"
DCO_SLICE = (
    49079,
    54323,
    "6FBA7E6C07F987BFE62230046D5D257D8D0839C1967DC3F3756C336DCBEF262C",
)
DCO_ROW = struct.Struct(">hHBBBbiiiiiBBBBiiiiiBBBBBBBBi4s4s4s")
DCO_TAGS = (
    "I16 U16 U8 U8 U8 I8 I32 I32 I32 I32 I32 U8 U8 U8 U8 "
    "I32 I32 I32 I32 I32 U8 U8 U8 U8 U8 U8 U8 U8 I32 Block Block Block"
).split()
# bank: persisted TypeID, byte offset, FP control, DDO, heap type, exact label.
STOP_DATA = {
    30: (3219, 36659, "1732", "1627", 21, "stop"),
    45: (3327, 41153, "44213", "11783", 15, "TCP ED"),
    46: (3254, 38492, "45855", "45845", 339, "stop urgence"),
    47: (3257, 38493, "40749", "40722", 19, "Arrêt général"),
}


def read_control_table(vi, records):
    """Read the shared DSINIT/DCO association without inferring live values."""
    dsinit = records[26].value[0]
    require(
        dsinit.td.raw_data.hex() == "000a0064000000330073",
        "original DSINIT descriptor changed",
    )
    dcos = records[4707]
    require(
        dcos.td.raw_data.hex() == "000a006400000045060e",
        "original DCO repeated-block descriptor changed",
    )
    return {
        "index_shift": vi.get("TM80").getMinTypeId(),
        "dsinit": tuple(item.value for item in dsinit.value),
        "dcos": tuple(tuple(item.value for item in row.value) for row in dcos.value),
        "dco_tags": tuple(
            tuple(item.getXMLTagName() for item in row.value) for row in dcos.value
        ),
    }


def read_source_data():
    with recovered_source() as (vi, section, payload):
        records = {item.index: item for item in section.content}
        result = read_control_table(vi, records)
        result["stops"] = {}
        for bank, (tid, _, _, _, _, _) in STOP_DATA.items():
            record = records[tid]
            clients = tuple(record.tdClientsWithDefltDataEnumerate())
            require(len(clients) == len(record.value) == 1, "stored stop slot changed")
            child = record.value[0]
            result["stops"][bank] = {
                "type_id": tid,
                "flags": record.tm_flags,
                "client_index": clients[0][0],
                "tag": child.getXMLTagName(),
                "value": child.value,
                "label_bytes": child.td.label,
            }
    return payload, result


def compare_control_table(payload, data):
    raw_init = payload[:204]
    require(sha(raw_init) == DSINIT_SHA256, "original DSINIT bytes changed")
    init = struct.unpack(">51i", raw_init)
    require(data["dsinit"] == init, "DSINIT parser/raw mismatch")
    require(
        data["index_shift"] == 25 and init[6] == 69 and init[8] == 4682,
        "DCO population/type-map reference changed",
    )
    require(data["index_shift"] + (init[8] & 0xFFFFFF) == 4707, "DCO link changed")
    start, stop, digest = DCO_SLICE
    raw = payload[start:stop]
    require(sha(raw) == digest, "original DCO bytes changed")
    require(DCO_ROW.size == 76 and len(raw) == 69 * 76, "DCO extent changed")
    rows = tuple(DCO_ROW.unpack_from(raw, index * 76) for index in range(69))
    require(
        data["dcos"] == rows
        and data["dco_tags"] == (tuple(DCO_TAGS),) * 69
        and tuple(row[0] for row in rows) == tuple(range(69)),
        "DCO independent field/population mismatch",
    )
    return rows


def compare_source_data(payload, data):
    rows = compare_control_table(payload, data)
    require(set(data["stops"]) == set(STOP_DATA), "stored stop population changed")
    snapshot = saved_source_stop_snapshot()
    for bank, (tid, offset, _, _, _, label) in STOP_DATA.items():
        row = rows[bank]
        require(
            row[8] == -1 and 25 + (row[7] & 0xFFFFFF) == tid,
            "DCO stop-data reference changed",
        )
        require(payload[offset : offset + 1] == b"\x00", "stored stop byte changed")
        require(
            data["stops"][bank]
            == {
                "type_id": tid,
                "flags": 4100,
                "client_index": 1,
                "tag": "Boolean",
                "value": 0,
                "label_bytes": label.encode("latin1"),
            },
            "stored stop typed metadata/value mismatch",
        )
        require(
            getattr(snapshot, STOP_FIELDS[bank]) is False,
            "inert source snapshot differs from persisted data",
        )
    return {bank: False for bank in STOP_DATA}


def compare_control_identities(bd, fp, metadata):
    for bank, (_, _, control, ddo, heap, label) in STOP_DATA.items():
        node = unique(fp, "fPDCO", control)
        display = node.find("ddo")
        descriptor, _ = heap_type(metadata, heap)
        require(
            node.findtext("typeDesc") == f"TypeID({heap})"
            and display is not None
            and display.get("uid") == ddo
            and display.get("class") == "stdBool"
            and display.findtext("partsList/*[@class='label']/textRec/text")
            == '"' + label + '"'
            and descriptor.get("Type") == "Boolean"
            and descriptor.get("Label") == label,
            "stored stop/front-panel typed identity mismatch",
        )
        locals_ = []
        for local in bd.findall(".//*[@class='gRef']"):
            terminal = local.find("termList/*/dco")
            if terminal is None or terminal.findtext("paramIdx") != str(bank):
                continue
            value = terminal.findtext("typeDesc")
            typed, _ = heap_type(metadata, int(value[7:-1]))
            require(
                typed.get("Type") == "Boolean" and typed.get("Label") == label,
                "stop-local index/label mismatch",
            )
            locals_.append(local)
        require(
            len(locals_) == {30: 9, 45: 5, 46: 4, 47: 2}[bank],
            "stop-local census changed",
        )


def validate_all():
    payload, data = read_source_data()
    stored = compare_source_data(payload, data)
    compare_control_identities(*checked_trees())
    return {
        "dco_rows": 69,
        "independent_dco_fields": 69 * 32,
        "stored_stop_values": stored,
        "loaded_control_values_proven": False,
        "implicit_restart_reset_added": False,
        "vi_executed": False,
        "hardware_executed": False,
    }


if __name__ == "__main__":
    print(validate_all())
