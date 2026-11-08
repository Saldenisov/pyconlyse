"""Check recovered numeric selector records against original ACQ heap labels.

This checks two saved representations, not native runtime defaults. The root
has no tdOffset links for these cases; matching content is not a direct table
identity proof. No generated code, VI, transport or instrument executes.
"""

from __future__ import annotations

import hashlib
import struct
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass

from qualify_acq_lvkit import DEFAULT_SOURCE
from validate_acq_helper_source_facets import ARCHIVE
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_vam_status import checked_vam

ROOT_SHA256 = "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF"
DFDS_SHA256 = "33C3D8AF2CE159F83C547013E8339964DF4E26520F6917A211CBEA83D78C03D5"
ROOT_ARCHIVE = ARCHIVE.parent / "0_ACQ_ELYSE_XML_sha6fe8.zip"
# Historical misaligned interval: this is NOT the corrected TypeID 3057.
HISTORICAL_MISALIGNED_SLICE = (
    27348,
    56852,
    "38EB0C46CCEE574B985AB8409449C34D28DFCD5625BDD59049DC533115C765A9",
)
TAIL_REPEAT_SLICE = (
    27348,
    35328,
    "2674C849753CBE5C2EAA6C8135471F498593813D17E18747D51902A68F19852B",
)
TAIL_TABLE_SLICE = (
    35328,
    35376,
    "2979B45A45B351C794BA3FAD5D9961780CCE5E2C765A91E37130E7C8574C07DE",
)


@dataclass(frozen=True)
class NumericTable:
    displayed: int
    rows: tuple[tuple[int, int, int, int, int], ...]


# Byte offsets are in the decompressed, hash-pinned original DFDS payload.
# Offsets/lengths plus independent struct decoding avoid self-validation by
# lvkit's case-table parser or its positional correlation fallback.
SLICES = {
    2938: (
        8420,
        8468,
        "0E2040E5CE2B1F4116CE9E3FC9009ED14C1C158567EE8574EB1986E1E5E9E2F0",
    ),
    2939: (
        8468,
        8528,
        "ED0F54C8ADFE4BDE84C0E77D341D3BE195340EE03A3B1BBF81925B52A4DF5363",
    ),
    2987: (
        8900,
        9008,
        "1CD476B68C76C84E1B720126CC31A93C93F3B5DB32945331F469724DD3E27D80",
    ),
    2994: (
        9380,
        9488,
        "29AC71F6F63277F19D942F1D1D13DB0302173B085F7B58328FA359E51ACE8611",
    ),
    3005: (
        9716,
        10040,
        "8FDF3D6A4657C4F4DB4C33FA13F6A418B55CE83B33A0EBAAEFD56BB321516D35",
    ),
}
EXPECTED = {
    2938: NumericTable(0, ((0, 0, 0, 0, 0), (3, 3, 0, 0, 1))),
    2939: NumericTable(1, ((0, 0, 0, 0, 0), (1, 1, 0, 0, 1), (3, 3, 0, 0, 2))),
    2987: NumericTable(
        4,
        (
            (0, 0, 0, 0, 2),
            (1, 1, 0, 0, 0),
            (2, 2, 0, 0, 1),
            (3, 6, 1, 1, 3),
            (7, 8, 1, 1, 2),
            (9, 10, 1, 1, 3),
            (11, 11, 0, 0, 4),
        ),
    ),
    2994: NumericTable(
        0,
        tuple(
            (value, value, 0, 0, index)
            for index, value in enumerate((0, 1, 16, 128, 256, 512, 1024))
        ),
    ),
    3005: NumericTable(0, tuple((index, index, 0, 0, index) for index in range(25))),
}
MATCHES = {
    2938: (("81854", 2, None),),
    2939: (("100523", 3, "01"),),
    2987: tuple((uid, 5, "04") for uid in ("11808", "12392", "12976", "13572")),
    2994: (("11557", 7, None), ("63039", 7, None)),
    3005: (("8105", 25, None),),
}


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def decode_table(raw):
    require(len(raw) >= 24, "numeric table truncated")
    displayed, declared, length = struct.unpack_from(">iii", raw)
    require(0 < declared == length <= 100, "numeric range count changed")
    require(len(raw) == 24 + 12 * length, "numeric table extent changed")
    rows = tuple(struct.unpack_from(">iiBBh", raw, 12 + 12 * i) for i in range(length))
    require(raw[-12:] == bytes(12), "numeric table strings/footer changed")
    require(
        all(
            start <= end and a in (0, 1) and b in (0, 1) and index >= 0
            for start, end, a, b, index in rows
        ),
        "unsupported numeric range encoding",
    )
    return NumericTable(displayed, rows)


def raw_tables(payload):
    require(
        len(payload) == 56852 and sha(payload) == DFDS_SHA256,
        "original DFDS bytes changed",
    )
    result = {}
    for tid, (start, stop, digest) in SLICES.items():
        raw = payload[start:stop]
        require(sha(raw) == digest, "numeric table bytes changed")
        result[tid] = decode_table(raw)
        require(result[tid] == EXPECTED[tid], "numeric table value changed")
    return result


def compare_heap(root, tables):
    cases = frames = 0
    for tid, matches in MATCHES.items():
        for uid, count, default in matches:
            node = unique(root, "select", uid)
            array = node.find("SelectRangeArray32")
            require(
                array is not None
                and array.get("elements") == str(len(tables[tid].rows)),
                "heap range population changed",
            )
            rows = tuple(
                tuple(
                    int(item.findtext(field))
                    for field in (
                        "start",
                        "end",
                        "startRangeType",
                        "endRangeType",
                        "diagramIdx",
                    )
                )
                for item in array
            )
            require(rows == tables[tid].rows, "DFDS/heap numeric selector mismatch")
            diagrams = node.findall("diagramList/*")
            require(
                len(diagrams) == count and all(row[-1] < count for row in rows),
                "heap numeric frame population changed",
            )
            require(
                node.findtext("SelectDefaultCase") == default,
                "saved default metadata changed",
            )
            require(
                node.find("tdOffset") is None, "table provenance assumptions changed"
            )
            cases += 1
            frames += count
    return cases, frames


@contextmanager
def recovered_source(source=DEFAULT_SOURCE / "0_ACQ_ELYSE.vi"):
    # In-memory resource reading only. Do not export/write/save the source VI.
    require(sha(source.read_bytes()) == ROOT_SHA256, "original Acquisition VI changed")
    from lvkit.extractor import _lv_rsrc, _make_read_po

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
            not section.parse_failed and len(section.content) == 829,
            "shared lvkit did not fully decode root DFDS",
        )
        payload = block.getData().read()
        require(
            len(payload) == 56852 and sha(payload) == DFDS_SHA256,
            "original DFDS bytes changed",
        )
        yield vi, section, payload
    require(sha(source.read_bytes()) == ROOT_SHA256, "source changed during read")


def read_recovered_source(source=DEFAULT_SOURCE / "0_ACQ_ELYSE.vi", extra_type_ids=()):
    with recovered_source(source) as (_, section, payload):
        records = {record.index: record for record in section.content}
        xml = ET.Element("Recovery")
        for tid in (*SLICES, *extra_type_ids):
            record = records[tid]
            elem = ET.SubElement(xml, "DataFill", TypeID=str(tid))
            value = ET.SubElement(elem, record.getXMLTagName())
            record.exportXML(value, "in-memory")  # in memory; no binary sidecars
    return payload, xml


def compare_converter(xml, tables):
    from lvkit.parser.nodes.case import parse_selector_tables

    # Extra records can be inspected separately; only the independently
    # qualified record population belongs to this five-table comparison.
    selected = ET.Element("QualifiedRecords")
    selected.extend(item for item in xml if int(item.get("TypeID", "-1")) in tables)
    actual = {table.type_id: table for table in parse_selector_tables(selected)}
    require(set(actual) == set(tables), "numeric converter table population changed")
    for tid, expected in tables.items():
        table = actual[tid]
        require(
            table.displayed_frame == expected.displayed
            and not table.strings
            and tuple(table.ranges)
            == tuple((a, b, index) for a, b, _, _, index in expected.rows),
            "shared converter numeric table mismatch",
        )


def check_tail_alignment(payload, xml):
    # Formerly unparsed descriptor 1359 initialized numRepeats to zero.
    # Its 1995 real I32 entries were misread as the following case table;
    # the permissive reader then fabricated values after reaching EOF.
    start, stop, digest = HISTORICAL_MISALIGNED_SLICE
    raw = payload[start:stop]
    require(sha(raw) == digest, "historical misaligned byte interval changed")
    require(
        struct.unpack_from(">iii", raw) == (0, 1, 2),
        "historical misaligned header changed",
    )
    start, stop, digest = TAIL_REPEAT_SLICE
    repeated = payload[start:stop]
    require(sha(repeated) == digest, "original repeated-block bytes changed")
    require(len(repeated) == 1995 * 4, "original repeated-block extent changed")
    record = xml.find("DataFill[@TypeID='3056']/RepeatedBlock")
    require(record is not None, "corrected repeated-block export missing")
    require(
        len(record) == 1995
        and all(item.tag == "I32" for item in record)
        and tuple(int(item.text) for item in record)
        == struct.unpack(">1995i", repeated),
        "lazy repeated-block data mismatch",
    )
    start, stop, digest = TAIL_TABLE_SLICE
    raw = payload[start:stop]
    require(sha(raw) == digest, "corrected original tail table bytes changed")
    expected = decode_table(raw)
    cluster = xml.find("DataFill[@TypeID='3057']/Cluster")
    require(cluster is not None, "corrected tail table export missing")
    require(
        cluster[1].text == "2"
        and cluster[2].findtext("dim") == "2"
        and len(cluster[2].findall("Cluster")) == 2
        and cluster[3].findtext("dim") == "0",
        "corrected tail table shape changed",
    )
    from lvkit.parser.nodes.case import parse_selector_tables

    require(
        any(
            table.type_id == 3057
            and table.displayed_frame == expected.displayed
            and not table.strings
            and tuple(table.ranges)
            == tuple((a, b, index) for a, b, _, _, index in expected.rows)
            for table in parse_selector_tables(xml)
        ),
        "corrected original tail table mismatch",
    )


def validate_all():
    payload, xml = read_recovered_source(extra_type_ids=(3056, 3057))
    tables = raw_tables(payload)
    root, _ = checked_vam(ROOT_ARCHIVE)
    cases, frames = compare_heap(root, tables)
    compare_converter(xml, tables)
    check_tail_alignment(payload, xml)
    return {
        "dfds_bytes": len(payload),
        "decoded_records": 829,
        "independent_numeric_tables": len(tables),
        "matching_cases": cases,
        "matching_frames": frames,
        "tail_repeat_values_checked": 1995,
        "permissive_eof_reads_used": False,
        "all_dfds_records_semantically_qualified": False,
        "direct_table_links_proven": False,
        "omitted_default_case_proven": False,
        "loaded_control_defaults_proven": False,
        "vi_executed": False,
        "hardware_executed": False,
        "whole_acquisition_qualified": False,
    }


if __name__ == "__main__":
    print(validate_all())
