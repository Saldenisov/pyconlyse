"""Pin seven saved measurement controls and their whole-root local ownership.

Stored array dimension zero is not four DBL zeros. Source fixtures do not
establish live loading, native Mean(empty), conversion padding or restart.
No source VI, generated controller, transport or instrument executes.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from io import BytesIO

from DeviceServers.control.elyse_acq.vi_simulation.saved_measurement_data import (
    saved_source_measurement_snapshot,
)
from validate_acq_dfds_recovery import recovered_source, sha
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_saved_stop_data import compare_control_table, read_control_table
from validate_acq_stop_ui_bindings import checked_trees


@dataclass(frozen=True)
class SavedControl:
    type_id: int
    offset: int
    format: str
    control: str
    ddo: str
    widget: str
    heap_type: int
    label: str
    kind: str
    client_type: int
    descriptor: str
    child_descriptor: str


CONTROLS = {
    59: SavedControl(
        3345,
        41202,
        ">I",
        "100281",
        "44443",
        "indArr",
        358,
        "C1_NI6259_0:3,7,9",
        "Array",
        857,
        "000e00500004058b035903590359",
        "001e40400001ffffffff003a1143315f4e49363235395f303a332c372c39",
    ),
    62: SavedControl(
        3351,
        41218,
        ">i",
        "62058",
        "57884",
        "stdNum",
        7,
        "B6220",
        "NumInt32",
        939,
        "000e00500004058b03ab03ab03ab",
        "000b400300054236323230",
    ),
    63: SavedControl(
        3279,
        39009,
        ">H",
        "276502",
        "276473",
        "stdKnob",
        279,
        "Voies:",
        "NumUInt16",
        1215,
        "000e00500004058b04bf04bf04bf",
        "000d40060006566f6965733a00",
    ),
    65: SavedControl(
        3355,
        41230,
        ">I",
        "80694",
        "80662",
        "indArr",
        394,
        "C1_NI6259_4:7",
        "Array",
        1328,
        "000e00500004058b053005300530",
        "001a40400001ffffffff003a0d43315f4e49363235395f343a37",
    ),
    66: SavedControl(
        3357,
        41234,
        ">I",
        "148174",
        "148142",
        "indArr",
        390,
        "C1_NI6259_4:7 Max",
        "Array",
        933,
        "000e00500004058b03a503a503a5",
        "001e40400001ffffffff003a1143315f4e49363235395f343a37204d6178",
    ),
    67: SavedControl(
        3359,
        41238,
        ">I",
        "185695",
        "185663",
        "indArr",
        386,
        "C1_NI6259_4:7 Min",
        "Array",
        945,
        "000e00500004058b03b103b103b1",
        "001e40400001ffffffff003a1143315f4e49363235395f343a37204d696e",
    ),
    68: SavedControl(
        3361,
        41242,
        ">I",
        "52015",
        "52000",
        "stdNum",
        384,
        "Iteration WCM",
        "NumUInt32",
        946,
        "000e00500004058b03b203b203b2",
        "00134007000d497465726174696f6e2057434d",
    ),
}
LOCALS = {
    59: (("48802", "48805", "48574", "0"), ("18306", "55194", "45859", "1")),
    62: (("196772", "196782", "47487", "0"), ("46908", "46911", "46898", "1")),
    63: (("48822", "48825", "48574", "1"),),
    65: (
        ("50544", "50572", "45510", "0"),
        ("47026", "47036", "206856", "0"),
        ("48168", "48174", "47080", "5"),
    ),
    66: (
        ("101607", "101610", "100569", "0"),
        ("202970", "202980", "81868", "0"),
        ("47013", "47017", "46898", "1"),
    ),
    67: (("202320", "202330", "206856", "0"), ("47100", "62369", "46898", "1")),
    68: (
        ("100549", "100552", "100537", "0"),
        ("100543", "100546", "100537", "1"),
        ("101615", "101618", "100569", "0"),
        ("100508", "100515", "45510", "1"),
        ("86041", "86048", "81862", "0"),
        ("85375", "85391", "81862", "1"),
        ("91670", "91677", "81868", "0"),
        ("74934", "74944", "206856", "1"),
    ),
}
FOUR_ZERO_BYTES_SHA256 = (
    "DF3F619804A92FDB4057192DC43DD748EA778ADC52BC498CE80524C014B81119"
)
TWO_ZERO_BYTES_SHA256 = (
    "96A296D224F285C67BEE93C30F8A309157F0DAA35DC5B87E410B78630A09CFC7"
)
DBL_ELEMENT_DESCRIPTOR = "000b400a00046d65616e00"


def read_source_data():
    from lvkit._pylabview_dfds import _ExactReadStream

    with recovered_source() as (vi, section, payload):
        records = {record.index: record for record in section.content}
        result = read_control_table(vi, records)
        result["controls"] = {}
        # Reparse the already linked data in memory to measure actual consumed
        # intervals. No serializer or expected-size calculation establishes them.
        stream = _ExactReadStream(BytesIO(payload))
        spans = {}
        for record in section.content:
            start = stream.tell()
            record.initWithRSRC(stream)
            spans[record.index] = (start, stream.tell())
        require(
            stream.tell() == len(payload), "measurement reparse under-consumed DFDS"
        )
        element = vi.get("VCTP").getFlatType(58)
        element.parseData()
        result["element_descriptor"] = element.raw_data.hex()
        result["element_type"] = int(element.fullType())
        for bank, spec in CONTROLS.items():
            record = records[spec.type_id]
            clients = tuple(record.tdClientsWithDefltDataEnumerate())
            require(
                len(record.value) == len(clients) == 1, "saved control slot changed"
            )
            child = record.value[0]
            result["controls"][bank] = {
                "type_id": record.index,
                "span": spans[record.index],
                "flags": record.tm_flags,
                "client_index": clients[0][0],
                "client_type": clients[0][1],
                "tag": child.getXMLTagName(),
                "value": tuple(child.value) if spec.kind == "Array" else child.value,
                "dimensions": tuple(getattr(child, "dimensions", ())),
                "label_bytes": child.td.label,
                "descriptor": record.td.raw_data.hex(),
                "child_descriptor": child.td.raw_data.hex(),
            }
    return payload, result


def compare_source_data(payload, data):
    rows = compare_control_table(payload, data)
    require(
        data["element_descriptor"] == DBL_ELEMENT_DESCRIPTOR
        and data["element_type"] == 10,
        "saved measurement element is not the original DBL descriptor",
    )
    require(set(data["controls"]) == set(CONTROLS), "saved control population changed")
    fixture = saved_source_measurement_snapshot()
    stored = {}
    for bank, spec in CONTROLS.items():
        size = struct.calcsize(spec.format)
        raw = payload[spec.offset : spec.offset + size]
        digest = TWO_ZERO_BYTES_SHA256 if size == 2 else FOUR_ZERO_BYTES_SHA256
        require(sha(raw) == digest, "original measurement data bytes changed")
        decoded = struct.unpack(spec.format, raw)[0]
        array = spec.kind == "Array"
        value = () if array else decoded
        require(decoded == 0, "saved measurement scalar/dimension changed")
        require(
            rows[bank][8] == -1 and 25 + (rows[bank][7] & 0xFFFFFF) == spec.type_id,
            "measurement DCO data reference changed",
        )
        require(
            data["controls"][bank]
            == {
                "type_id": spec.type_id,
                "span": (spec.offset, spec.offset + size),
                "flags": 4 if array else 4100,
                "client_index": 1,
                "client_type": spec.client_type,
                "tag": {"NumInt32": "I32", "NumUInt16": "U16", "NumUInt32": "U32"}.get(
                    spec.kind, "Array"
                ),
                "value": value,
                "dimensions": (decoded,) if array else (),
                "label_bytes": spec.label.encode("latin1"),
                "descriptor": spec.descriptor,
                "child_descriptor": spec.child_descriptor,
            },
            "saved measurement typed metadata/value mismatch",
        )
        require(
            getattr(fixture, f"bank{bank}") == value, "source fixture value differs"
        )
        stored[bank] = value
    return stored


def compare_control_identities(bd, fp, metadata):
    parents = {child: parent for parent in bd.iter() for child in parent}
    for bank, spec in CONTROLS.items():
        control = unique(fp, "fPDCO", spec.control)
        display = control.find("ddo")
        descriptor, flat = heap_type(metadata, spec.heap_type)
        require(
            control.findtext("typeDesc") == f"TypeID({spec.heap_type})"
            and display is not None
            and display.get("uid") == spec.ddo
            and display.get("class") == spec.widget
            and display.findtext("partsList/*[@class='label']/textRec/text")
            == '"' + spec.label + '"'
            and descriptor.get("Type") == spec.kind
            and descriptor.get("Label") == spec.label,
            "measurement front-panel identity changed",
        )
        if spec.kind == "Array":
            require(
                len(descriptor.findall("Dimension")) == 1
                and descriptor.find("TypeDesc").get("TypeID") == "58"
                and flat[58].get("Type") == "NumFloat64",
                "measurement front-panel array representation changed",
            )
        actual = []
        for node in bd.findall(".//*[@class='gRef']"):
            if node.findtext("termList/*/dco/paramIdx") != str(bank):
                continue
            terms = node.findall("termList/*")
            require(len(terms) == 1, "measurement local terminal population changed")
            terminal = terms[0]
            owner = parents[node]
            while owner.get("class") != "diag":
                owner = parents[owner]
            actual.append(
                (
                    node.get("uid"),
                    terminal.get("uid"),
                    owner.get("uid"),
                    terminal.findtext("dco/objFlags", "0"),
                )
            )
            typed, local_flat = heap_type(
                metadata, int(terminal.findtext("dco/typeDesc")[7:-1])
            )
            require(
                typed.get("Type") == spec.kind and typed.get("Label") == spec.label,
                "measurement local type/label changed",
            )
            if spec.kind == "Array":
                require(
                    len(typed.findall("Dimension"))
                    == len(typed.findall("TypeDesc"))
                    == 1
                    and local_flat[int(typed.find("TypeDesc").get("TypeID"))].get(
                        "Type"
                    )
                    == "NumFloat64",
                    "measurement local array element changed",
                )
        require(
            len(actual) == len(LOCALS[bank]) and set(actual) == set(LOCALS[bank]),
            "whole-root measurement local ownership changed",
        )


def validate_all():
    payload, data = read_source_data()
    stored = compare_source_data(payload, data)
    compare_control_identities(*checked_trees())
    return {
        "saved_controls": len(stored),
        "independent_saved_bytes": 26,
        "root_local_references": sum(len(sites) for sites in LOCALS.values()),
        "stored": stored,
        "loaded_controls_proven": False,
        "mean_empty_return_proven": False,
        "short_cluster_padding_proven": False,
        "implicit_initialization_reset_added": False,
        "vi_executed": False,
        "hardware_executed": False,
    }


if __name__ == "__main__":
    print(validate_all())
