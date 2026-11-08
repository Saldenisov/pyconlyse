"""Join two original NI6071E DSINIT/DCO tables to nine persisted parameters.

Independent raw decoding is compared with the current shared lvkit parser.
Stored values are not native control loading, task validity or returned errors.
No source VI or generated controller is executed or serialized.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from io import BytesIO

from DeviceServers.control.elyse_acq.vi_simulation.saved_ni6071e_data import (
    saved_source_ni6071e_snapshot,
)
from qualify_acq_lvkit import DEFAULT_SOURCE
from validate_acq_dfds_recovery import sha
from validate_acq_helper_source_facets import ARCHIVE
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6071e_initializer import checked_roots as initializer_roots
from validate_acq_ni6071e_read import checked_roots as reader_roots
from validate_acq_ni6071e_read import validate_read
from validate_acq_ni6220_read_error_contract import connector_map
from validate_acq_runtime_io_frame import checked_trees, heap_type
from validate_acq_saved_stop_data import DCO_ROW, DCO_TAGS


@dataclass(frozen=True)
class Parameter:
    bank: int
    slot: int
    type_id: int
    span: tuple[int, int]
    kind: str
    value: object
    flat_type: int
    control: str
    ddo: str
    heap: int
    widget: str
    label: str
    caption: str


@dataclass(frozen=True)
class Profile:
    name: str
    source_hash: str
    payload_size: int
    payload_hash: str
    record_count: int
    shift: int
    dsinit_record: int
    dsinit_hash: str
    dco_record: int
    dco_span: tuple[int, int]
    dco_hash: str
    parameters: tuple[Parameter, ...]


COUNT_LABEL = "Nb d'échantillons"
COUNT_CAPTION = '"échantillons par voie"'
ERROR_CAPTION = '"entrée d\'erreur"'
ZERO_ERROR = (False, 0, b"")
READER = Profile(
    "1_ACQ_READ_NI6071E.vi",
    "C26AEFFBFC6D48393B2424343877CBC0C0A68239431A0AE63606D5A52F207037",
    3713,
    "D0D41550A4CC9D064282788E18D35994421F992093A6223DE39285A639824E07",
    34,
    7,
    8,
    "899D292DB6D85A51875D193141BE0262E93EEC5861AE7EBD8963E3088023F3F6",
    144,
    (2883, 3415),
    "252078F7693C956BB0654EF9770B8E929C428F18C4A7050CA0A49BF3C82B2904",
    (
        Parameter(
            5,
            9,
            130,
            (2853, 2857),
            "NumInt32",
            1000,
            27,
            "761",
            "8",
            5,
            "stdNum",
            COUNT_LABEL,
            COUNT_CAPTION,
        ),
        Parameter(
            4,
            8,
            133,
            (2857, 2866),
            "Cluster",
            ZERO_ERROR,
            12,
            "1072",
            "424",
            7,
            "stdClust",
            "error in",
            ERROR_CAPTION,
        ),
        Parameter(
            3,
            0,
            138,
            (2870, 2879),
            "Cluster",
            ZERO_ERROR,
            13,
            "977",
            "288",
            12,
            "stdClust",
            "error out",
            '"error out"',
        ),
    ),
)
INITIALIZER = Profile(
    "1_ACQ_INIT_NI6071E.vi",
    "FEB881DB3A01B5402D5164C3B149195E83D8A0B089DDAEEA0D6A54D7C4E0F07C",
    5572,
    "11ACD5D93A980DB053C43B77DA60CCCFFE7D4B93109EEBA1714E2E30A612AE7D",
    57,
    10,
    11,
    "47F3B4D055020082EFDD06B9D2D2BADC44381E432E37CC75B2F5ED55819B2F2A",
    184,
    (4596, 5204),
    "3A0FDADC5E60F795AEC6AC2C0C27F4A67F9C8C178FCE6EC353C8CDB6C7013BC9",
    (
        Parameter(
            0,
            1,
            18,
            (944, 955),
            "Tag",
            b"/2/PFI0",
            45,
            "609",
            "464",
            1,
            "stdTag",
            "Trigger C2 (/2/PFI0)",
            '"Trigger C2 (/2/PFI0)"',
        ),
        Parameter(
            1,
            0,
            20,
            (955, 966),
            "Tag",
            b"/1/PFI0",
            44,
            "2050",
            "141",
            3,
            "stdTag",
            "Trigger C1 (/1/PFI0)",
            '"Trigger C1 (/1/PFI0)"',
        ),
        Parameter(
            3,
            3,
            22,
            (966, 975),
            "Cluster",
            ZERO_ERROR,
            11,
            "580",
            "451",
            10,
            "stdClust",
            "error in",
            ERROR_CAPTION,
        ),
        Parameter(
            4,
            4,
            25,
            (975, 979),
            "NumInt32",
            10,
            47,
            "266",
            "247",
            15,
            "stdNum",
            COUNT_LABEL,
            COUNT_CAPTION,
        ),
        Parameter(
            6,
            2,
            27,
            (979, 987),
            "NumFloat64",
            5000.0,
            46,
            "128",
            "23",
            20,
            "stdNum",
            "Fréq. d'éch.",
            '"Fréquence d\'échantillonnage"',
        ),
        Parameter(
            2,
            7,
            173,
            (4559, 4568),
            "Cluster",
            ZERO_ERROR,
            12,
            "1280",
            "628",
            5,
            "stdClust",
            "error out",
            '"error out"',
        ),
    ),
)
PROFILES = (READER, INITIALIZER)


def parsed_value(child, kind):
    if kind == "Cluster":
        require(
            [v.getXMLTagName() for v in child.value] == ["Boolean", "I32", "String"],
            "saved error cluster field types changed",
        )
        status, code, source = (v.value for v in child.value)
        require(status in (0, 1), "saved Boolean status changed")
        return bool(status), code, source
    return child.value


def read_source_data(profile):
    from lvkit._pylabview_dfds import _ExactReadStream
    from lvkit.extractor import _lv_rsrc, _make_read_po

    source = DEFAULT_SOURCE / profile.name
    require(
        sha(source.read_bytes()) == profile.source_hash, "original NI6071E VI changed"
    )
    po = _make_read_po(
        rsrc=str(source),
        xml="in-memory.xml",
        textcp="mac_roman",
        raw_connectors=False,
        keep_names=False,
        filebase="vi",
        list=False,
        dump=False,
        extract=True,
        create=False,
        password=None,
    )
    with source.open("rb") as stream:
        vi = _lv_rsrc.VI(po, rsrc_fh=stream, text_encoding=po.textcp)
        block = vi.get("DFDS")
        section = block.sections[block.active_section_num]
        require(
            not section.parse_failed and len(section.content) == profile.record_count,
            "NI6071E saved-data parse incomplete",
        )
        payload = block.getData().read()
        records = {r.index: r for r in section.content}
        cursor = _ExactReadStream(BytesIO(payload))
        spans = {}
        for record in section.content:
            start = cursor.tell()
            record.initWithRSRC(cursor)
            spans[record.index] = (start, cursor.tell())
        require(cursor.tell() == len(payload), "NI6071E reparse under-consumed data")
        dsinit = records[profile.dsinit_record].value[0]
        dcos = records[profile.dco_record]
        data = {
            "shift": vi.get("TM80").getMinTypeId(),
            "dsinit": tuple(v.value for v in dsinit.value),
            "dco_span": spans[profile.dco_record],
            "dcos": tuple(tuple(v.value for v in row.value) for row in dcos.value),
            "dco_tags": tuple(
                tuple(v.getXMLTagName() for v in row.value) for row in dcos.value
            ),
            "parameters": {},
        }
        for spec in profile.parameters:
            record = records[spec.type_id]
            clients = tuple(record.tdClientsWithDefltDataEnumerate())
            require(
                len(clients) == len(record.value) == 1, "saved parameter slot changed"
            )
            child = record.value[0]
            data["parameters"][spec.bank] = {
                "span": spans[spec.type_id],
                "flags": record.tm_flags,
                "client": (clients[0][0], clients[0][1]),
                "kind": child.getXMLTagName(),
                "label": child.td.label,
                "value": parsed_value(child, spec.kind),
            }
    require(
        sha(source.read_bytes()) == profile.source_hash,
        "NI6071E source changed during read",
    )
    return payload, data


def decode_saved(raw, kind):
    if kind in ("NumInt32", "NumFloat64"):
        fmt = ">i" if kind == "NumInt32" else ">d"
        require(len(raw) == struct.calcsize(fmt), "saved numeric extent changed")
        return struct.unpack(fmt, raw)[0]
    if kind == "Tag":
        require(
            len(raw) >= 4 and struct.unpack_from(">I", raw)[0] == len(raw) - 4,
            "saved tag length changed",
        )
        return raw[4:]
    require(kind == "Cluster" and len(raw) >= 9, "saved error extent changed")
    status, code, length = struct.unpack_from(">BiI", raw)
    require(
        status in (0, 1) and length == len(raw) - 9, "saved error string/status changed"
    )
    return bool(status), code, raw[9:]


def compare_source_data(profile, payload, data):
    require(
        len(payload) == profile.payload_size and sha(payload) == profile.payload_hash,
        "original NI6071E DFDS bytes changed",
    )
    require(sha(payload[:204]) == profile.dsinit_hash, "NI6071E DSINIT bytes changed")
    init = struct.unpack(">51i", payload[:204])
    require(
        data["dsinit"] == init and data["shift"] == profile.shift,
        "NI6071E DSINIT parser/raw mismatch",
    )
    start, stop = profile.dco_span
    raw = payload[start:stop]
    require(
        sha(raw) == profile.dco_hash and len(raw) == init[6] * DCO_ROW.size,
        "NI6071E DCO bytes/population changed",
    )
    rows = tuple(DCO_ROW.unpack_from(raw, i * DCO_ROW.size) for i in range(init[6]))
    require(
        data["dco_span"] == profile.dco_span
        and data["dcos"] == rows
        and data["dco_tags"] == (tuple(DCO_TAGS),) * len(rows)
        and tuple(row[0] for row in rows) == tuple(range(len(rows)))
        and profile.shift + (init[8] & 0xFFFFFF) == profile.dco_record,
        "NI6071E DCO independent decoding mismatch",
    )
    require(
        set(data["parameters"]) == {p.bank for p in profile.parameters},
        "saved NI6071E parameter population changed",
    )
    stored = {}
    for spec in profile.parameters:
        require(
            rows[spec.bank][5] == spec.slot
            and rows[spec.bank][8] == -1
            and profile.shift + (rows[spec.bank][7] & 0xFFFFFF) == spec.type_id,
            "NI6071E DCO connector/data link changed",
        )
        value = decode_saved(payload[slice(*spec.span)], spec.kind)
        require(value == spec.value, "independent saved NI6071E value changed")
        expected = {
            "span": spec.span,
            "flags": 4100 if spec.kind in ("NumInt32", "NumFloat64") else 4,
            "client": (1, spec.flat_type),
            "kind": {"NumInt32": "I32", "NumFloat64": "DBL"}.get(spec.kind, spec.kind),
            "label": spec.label.encode("latin1"),
            "value": value,
        }
        require(
            data["parameters"][spec.bank] == expected,
            "saved NI6071E typed metadata/value mismatch",
        )
        stored[spec.bank] = value
    return stored


def compare_control_identities(profile, roots):
    bd, fp, metadata = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    pane = dict(connector_map(fp))
    flags = metadata.findall("CPMp/Section/TypeDesc")
    for spec in profile.parameters:
        control = unique(fp, "fPDCO", spec.control)
        display = control.find("ddo")
        descriptor, flat = heap_type(metadata, spec.heap)
        require(
            pane[spec.slot] == spec.control
            and int(flags[spec.slot].get("Flags"), 16) >> 8 == spec.bank
            and control.findtext("typeDesc") == f"TypeID({spec.heap})"
            and display.get("uid") == spec.ddo
            and display.get("class") == spec.widget
            and display.findtext("partsList/*[@class='label']/textRec/text")
            == spec.caption
            and descriptor.get("Type") == spec.kind
            and descriptor.get("Label") == spec.label,
            "saved NI6071E front-panel/connector identity changed",
        )
        if spec.kind == "Cluster":
            require(
                [
                    (
                        flat[int(t.get("TypeID"))].get("Type"),
                        flat[int(t.get("TypeID"))].get("Label"),
                    )
                    for t in descriptor.findall("TypeDesc")
                ]
                == [("Boolean", "status"), ("NumInt32", "code"), ("String", "source")],
                "NI6071E error field order changed",
            )
        terminals = [
            n
            for n in bd.iter()
            if n.get("class") == "fPTerm"
            and n.find("dco") is not None
            and n.find("dco").get("uid") == spec.control
        ]
        require(len(terminals) == 1, "NI6071E parameter diagram terminal changed")


def checked_roots(profile):
    if profile is READER:
        return reader_roots(ARCHIVE)
    require(profile is INITIALIZER, "known original NI6071E profile required")
    return initializer_roots(ARCHIVE.parent / "1_ACQ_INIT_NI6071E_XML_shafeb8.zip")


def compare_pilot_count_wires(root, roots):
    # Complete existing helper proof, including count763 -> two DAQmx Reads.
    validate_read(roots)
    frame = unique(root, "diag", "133")
    call = unique(root, "iUse", "287")
    count = call.find("termList/*[@uid='2642']")
    require(
        call in frame.findall("zPlaneList/*")
        and call.findtext("label/textRec/text") == '"1_ACQ_READ_NI6071E.vi"'
        and count is not None
        and count.findtext("dco/paramIdx") == "9"
        and count.findtext("dco/objFlags") == "512"
        and not any(
            t.get("uid") == "2642"
            for s in frame.findall("signalList/*")
            for t in s.findall("termList/*")
        ),
        "pilot reader sample-count input is no longer unwired slot9",
    )


def validate_all():
    values = {}
    for profile in PROFILES:
        payload, data = read_source_data(profile)
        values[profile.name] = compare_source_data(profile, payload, data)
        compare_control_identities(profile, checked_roots(profile))
    snapshot = saved_source_ni6071e_snapshot()
    require(
        snapshot.reader_samples_per_channel == values[READER.name][5]
        and snapshot.initializer_clock.samples_per_channel
        == values[INITIALIZER.name][4]
        and snapshot.initializer_clock.rate_hz == values[INITIALIZER.name][6]
        and snapshot.trigger_c1.encode() == values[INITIALIZER.name][1]
        and snapshot.trigger_c2.encode() == values[INITIALIZER.name][0],
        "inert saved NI6071E snapshot differs from source",
    )
    for error in (
        snapshot.reader_error_in,
        snapshot.reader_error_out,
        snapshot.initializer_error_in,
        snapshot.initializer_public_error_out,
    ):
        require(
            (error.status, error.code, error.source.encode()) == ZERO_ERROR,
            "inert saved error snapshot differs from source",
        )
    root, _ = checked_trees(ARCHIVE.parent / "0_ACQ_ELYSE_XML_sha6fe8.zip")
    compare_pilot_count_wires(root, checked_roots(READER))
    return {
        "original_members": 2,
        "dco_rows": 15,
        "independent_dco_fields": 480,
        "saved_parameters": 9,
        "reader_samples": 1000,
        "initializer_samples": 10,
        "native_loading_proven": False,
        "unwritten_output_return_proven": False,
        "vi_executed": False,
        "hardware_executed": False,
    }


if __name__ == "__main__":
    print(validate_all())
