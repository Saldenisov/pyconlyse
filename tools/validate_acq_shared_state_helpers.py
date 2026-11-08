"""Offline audit of two native, read-only shared-state telemetry helpers.

This checks saved LabVIEW resources, not runtime data, main-VI integration,
queue ownership, timing, or delivery to Python/Everest. It executes no VI and
opens no network connection. Evidence must be re-reviewed after native edits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_runtime_io_frame import heap_type
from validate_acq_tpg300_pressure import validate_callers, validate_pressure_publication

COLLECTOR = "ACQ_SharedState_Collect_Local"
QUEUE = "ACQ_SharedState_Queue_Latest"
QUEUE_NAME = "ELYSE_ACQ_SHARED_STATE_LATEST_V1"
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
CONTROL_NAMES = tuple(
    "C10-11 NI6602" if bank == "C1011NI6602" else bank for bank in BANKS
)
SOURCE_HASHES = {
    COLLECTOR: "48A79A807A0AF4785BC2A0F5CCAFA5C4F1639AFA416F267B7C657308DF9AA59F",
    QUEUE: "4FF02F042042C2BBA37366D373453CB9CB191BD79096039A83C6EEB2AED17C8F",
}
EXPORT_HASHES = {
    COLLECTOR: {
        "vi.xml": "9AB8C44377B864F9101440B77EDEE87BF2F3913256B76323F6E8B17DD1B1E504",
        "vi_BDHb.xml": (
            "EB9D102F7152D95F2802268AC1845AB9D66884E97D03B67359804E7C16F0543F"
        ),
        "vi_FPHb.xml": (
            "B440AE266C96A5155479BF8DAED78E873CD7CF5E2EF2483A80B54564E718DA6D"
        ),
    },
    QUEUE: {
        "vi.xml": "4F6D4AD0187F1AE862EBAE88E4586E87C23DF267C5C08E6AE9EE547C0CEFE52F",
        "vi_BDHb.xml": (
            "2CEE0670F899F125307A3DC38EBA9D3944D4FAB294CF234F40C3DCED7F6FE473"
        ),
        "vi_FPHb.xml": (
            "58AC7541E25AEC34D1B1C0739CF5FA4CDDF91B330467E326E2F37C12BC7D9991"
        ),
    },
}
MAIN_FP_HASH = "000E82C66074929C7A9C7434B66629ADF6934C411AB85109E663BF0474F49E72"

COMMON_CLASSES = {
    "Image",
    "annex",
    "bDConstDCO",
    "cosm",
    "diag",
    "fPTerm",
    "label",
    "multiCosm",
    "oHExt",
    "parm",
    "prim",
    "sRN",
    "signal",
    "stdString",
    "term",
    "textHair",
}
COLLECTOR_CLASSES = COMMON_CLASSES | {
    "aBuild",
    "aBuildDCO",
    "forLoop",
    "hGrowCItem",
    "iUse",
    "iUseDCO",
    "innerLpTun",
    "invokeItem",
    "invokeNode",
    "lCnt",
    "lMax",
    "lpTun",
    "mux",
    "mxDCO",
}
QUEUE_CLASSES = COMMON_CLASSES | {"nMux", "nmxDCO", "numLabel", "stdBool", "stdNum"}
COLLECTOR_WIRES = {
    "3": (
        ("76", "63"),
        ("525", "782"),
        ("581", "558"),
        ("51", "359"),
        ("232", "60"),
        ("142", "57"),
        ("123", "145"),
    ),
    "324": (
        ("422", "577"),
        ("268", "444"),
        ("275", "462", "429"),
        ("356", "303", "426"),
        ("384", "259"),
    ),
}
QUEUE_WIRES = {
    "3": (
        ("72", "239"),
        ("692", "594"),
        ("257", "698"),
        ("666", "695"),
        ("426", "516", "663"),
        ("630", "414"),
        ("260", "417"),
        ("248", "411"),
        ("188", "54", "230"),
        ("66", "227"),
        ("160", "57"),
        ("127", "51"),
        ("92", "63"),
    ),
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def node(tree, klass, uid):
    matches = [
        n for n in tree.iter() if n.get("class") == klass and n.get("uid") == uid
    ]
    require(len(matches) == 1, f"expected one {klass}:{uid}")
    return matches[0]


class Export:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.bd = ET.parse(self.directory / "vi_BDHb.xml").getroot()
        self.fp = ET.parse(self.directory / "vi_FPHb.xml").getroot()
        self.metadata = ET.parse(self.directory / "vi.xml").getroot()
        self.calls = call_names(self.metadata)

    def shape(self, heap_id):
        td, flat = heap_type(self.metadata, heap_id)

        def walk(item, seen):
            children = []
            for ref in item.findall("TypeDesc"):
                idx = int(ref.get("TypeID"))
                require(idx not in seen, "recursive payload descriptor")
                children.append(walk(flat[idx], seen | {idx}))
            if item.get("Type") == "Array":
                return "Array", len(item.findall("Dimension")), tuple(children)
            return item.get("Type"), tuple(children)

        return walk(td, set())


def check_execution(export):
    execution = export.metadata.find("LVSR/Section/Execution")
    require(execution is not None, "saved execution metadata missing")
    for flag in (
        "BadSignal",
        "BadNode",
        "BadSubVILink",
        "BadSubVI",
        "BadCompile",
        "RunOnOpen",
    ):
        require(
            execution.get(flag) == "0", f"unsafe/broken saved execution flag: {flag}"
        )
    require(execution.get("State") == "1", "saved helper is not compiled")


def check_operations(export, expected, allowed_classes):
    classes = {n.get("class") for n in export.bd.iter() if n.get("class")}
    require(
        classes <= allowed_classes,
        "unexpected operation/class: " + str(classes - allowed_classes),
    )
    actual = [
        (n.get("class"), n.get("uid"), n.findtext("primResID"))
        for n in export.bd.iter()
        if n.get("class")
        in {"prim", "invokeNode", "iUse", "forLoop", "mux", "nMux", "aBuild"}
    ]
    require(Counter(actual) == Counter(expected), "executable operation set changed")


def check_wires(export, expected):
    diagrams = [n for n in export.bd.iter() if n.get("class") == "diag"]
    require(
        Counter(d.get("uid") for d in diagrams) == Counter(expected.keys()),
        "diagram topology changed",
    )
    for diagram in diagrams:
        signals = diagram.findall("signalList/*")
        actual = [tuple(t.get("uid") for t in w.findall("termList/*")) for w in signals]
        require(
            Counter(actual) == Counter(expected[diagram.get("uid")]),
            "wire topology changed: diagram " + diagram.get("uid"),
        )
        require(
            all(w.findtext("state") in {"1", "17", "33"} for w in signals),
            "broken/unreviewed wire state",
        )


def const_bytes(export, uid):
    return bytes.fromhex(node(export.bd, "bDConstDCO", uid).findtext("ConstValue"))


def const_string(export, uid):
    raw = const_bytes(export, uid)
    require(
        len(raw) >= 4 and int.from_bytes(raw[:4], "big") == len(raw) - 4,
        "malformed string constant",
    )
    return raw[4:].decode("ascii")


ERROR_SHAPE = ("Cluster", (("Boolean", ()), ("NumInt32", ()), ("String", ())))
RECORD_SHAPE = ("Cluster", (("String", ()), ("LVVariant", ()), ERROR_SHAPE))


def validate_collector(export):
    check_execution(export)
    check_operations(
        export,
        (
            ("iUse", "518", None),
            ("forLoop", "316", None),
            ("mux", "416", None),
            ("invokeNode", "253", None),
            ("aBuild", "136", None),
            ("prim", "43", "1539"),
        ),
        COLLECTOR_CLASSES,
    )
    require(export.calls == {"518": QUEUE + ".vi"}, "collector dependency changed")
    getter = node(export.bd, "invokeNode", "253")
    require(
        getter.findtext("methCode") == "1052"
        and getter.findtext("methName") == '"Ctrl Val.Get"'
        and getter.findtext("oMId") == "0042"
        and getter.findtext("nodeName") == '"VI"',
        "must use read-only VI Control Value:Get",
    )
    require(
        const_string(export, "230").split("\t") == list(CONTROL_NAMES),
        "27-bank whitelist/order changed",
    )
    require(const_string(export, "74") == "%s", "required name-parser format changed")
    require(
        export.shape(45) == ("Array", 1, (("String", ()),)), "name array type changed"
    )
    require(
        export.shape(26) == ("Array", 1, (RECORD_SHAPE,)), "record array type changed"
    )
    require(
        export.shape(19) == ("LVVariant", ()), "queue input must preserve variant types"
    )
    for uid in ("354", "575"):
        tunnel = node(export.bd, "lpTun", uid)
        require(tunnel.findtext("TunnelType") == "01", "auto-indexing changed")
    controls = [n for n in export.fp.iter() if n.get("class") == "fPDCO"]
    require(
        {n.get("uid") for n in controls} == {"382", "780"},
        "collector interface changed",
    )
    source = node(export.fp, "fPDCO", "382")
    require(
        source.findtext("conNum") == "5" and int(source.findtext("objFlags")) & 128,
        "source VI input must be required",
    )
    require(export.shape(6) == ("Refnum", ()), "source must be a VI reference")
    require(export.shape(1) == ERROR_SHAPE, "diagnostic error output changed")
    check_wires(export, COLLECTOR_WIRES)


def validate_queue(export):
    check_execution(export)
    check_operations(
        export,
        (
            ("prim", "222", "9130"),
            ("prim", "529", "1062"),
            ("nMux", "657", None),
            ("prim", "112", "9109"),
            ("prim", "43", "9108"),
        ),
        QUEUE_CLASSES,
    )
    require(not export.calls, "queue must not call any subVI")
    require(const_bytes(export, "90") == b"\x00\x00\x00\x01", "queue maximum must be 1")
    require(const_string(export, "125") == QUEUE_NAME, "dedicated queue name changed")
    require(const_bytes(export, "158") == b"\x00\x00", "producer must not create queue")
    require(
        const_bytes(export, "628") == b"\x00\x00",
        "producer must not force-destroy queue",
    )
    require(export.shape(8) == ("LVVariant", ()), "queue packet type changed")
    require(export.shape(15) == ("Boolean", ()), "overflow diagnostic type changed")
    require(export.shape(16) == ERROR_SHAPE, "lossy enqueue error type changed")
    overflow, _ = heap_type(export.metadata, 15)
    require(
        overflow.get("Label") == "overflow?",
        "diagnostic must describe replacement, not timeout",
    )
    flag = node(export.fp, "fPDCO", "592")
    require(flag.findtext("conNum") == "3", "replacement diagnostic connector changed")
    require(
        export.shape(1) == ("Boolean", ()), "replacement diagnostic must be Boolean"
    )
    check_wires(export, QUEUE_WIRES)


def control_catalog(main_fp):
    labels = []
    for control in main_fp.iter():
        if control.get("class") != "fPDCO":
            continue
        names = [
            p.findtext("textRec/text", "").strip('"')
            for p in control.findall("ddo/partsList/*")
            if p.get("class") == "label" and p.findtext("partID") == "16"
        ]
        labels.extend(names)
    counts = Counter(labels)
    require(
        all(counts[name] == 1 for name in CONTROL_NAMES),
        "bank control absent or ambiguous in original main VI",
    )


def validate_pressure_inclusion(collector, main_bd):
    """Join collector whitelist to the existing pressure wires, not a new poll.

    The caller receives a separately hash-checked main BD. This proves source
    inclusion only: no sensor Status, units, freshness, or delivery is inferred.
    """
    validate_collector(collector)
    validate_callers(main_bd)
    validate_pressure_publication(main_bd)
    return {
        "bank": "VAM-A",
        "zero_based_fields": [10, 11, 20],
        "pressure_local_banks": [53, 54, 60],
        "sensor_arguments": [0, 0, 3],
        "sensor_status_included": False,
        "new_instrument_poll": False,
        "units_verified_here": False,
        "transport_delivery_verified": False,
    }


def validate(collector, queue, library, main_fp):
    validate_collector(collector)
    validate_queue(queue)
    variables = [
        n.get("Name") for n in library.iter("Item") if n.get("Type") == "Variable"
    ]
    require(
        Counter(variables) == Counter(BANKS), "shared-variable library catalog differs"
    )
    control_catalog(main_fp)
    return {
        "scope": "static saved helper audit only",
        "bank_count": 27,
        "banks": list(BANKS),
        "control_to_bank_alias": {"C10-11 NI6602": "C1011NI6602"},
        "source_semantics": (
            "sequential local ACQ control values, not atomic PSP values"
        ),
        "record": ["control_name", "native_variant_value", "individual_read_error"],
        "queue": {
            "name": QUEUE_NAME,
            "max_elements": 1,
            "enqueue_primitive": 9130,
            "policy": "discard old, admit new",
            "create_if_missing": False,
            "force_destroy": False,
            "owner_implemented_here": False,
            "consumer_implemented_here": False,
        },
        "proposed_timeout_frame": 4,
        "main_timeout_integrated": False,
        "telemetry_complete": False,
        "native_vi_executed": False,
        "hardware_access": False,
        "psp_access_in_helpers": False,
        "network_access_in_helpers": False,
        "limitations": [
            "Main integration is not assessed by this helper-only audit.",
            "Queue owner and asynchronous consumer are required; producer reports "
            "an error if queue is absent.",
            "27-bank parser/getter has not been executed or timed; exact runtime "
            "parsing remains untested.",
            "VI Server reads can involve UI-thread scheduling; network isolation "
            "is not a timing guarantee.",
            "Other ACQ loops may update local values between bank reads; "
            "snapshot is not atomic.",
            "Local post-Timeout EPS can precede its publication by another loop; "
            "PSP equality is not guaranteed.",
            "No capture timestamp or sequence number is added by these helpers yet.",
            "Python parsing, forwarding and Everest delivery for this new "
            "aggregate are not implemented here.",
            "The old initialization hooks/synthetic receiver are separate "
            "and are not upgraded by this audit.",
            "Stored queue metadata retains PropTypesIssues=1 despite zero "
            "native error-list entries; runtime not verified.",
            "C12NI1409 is a String bank, not camera pixels; output values "
            "are software state, not measured AO voltage.",
        ],
    }


def audit(root, library_path, main_fp_path):
    root = Path(root)
    for name in (COLLECTOR, QUEUE):
        require(
            digest(root / (name + ".vi")) == SOURCE_HASHES[name],
            "unreviewed native source: " + name,
        )
        for filename, expected in EXPORT_HASHES[name].items():
            require(
                digest(root / "export" / name / filename) == expected,
                "unreviewed export: " + name + "/" + filename,
            )
    require(
        digest(main_fp_path) == MAIN_FP_HASH, "unreviewed original main front panel"
    )
    report = validate(
        Export(root / "export" / COLLECTOR),
        Export(root / "export" / QUEUE),
        ET.parse(library_path).getroot(),
        ET.parse(main_fp_path).getroot(),
    )
    report["source_sha256"] = SOURCE_HASHES
    report["export_sha256"] = EXPORT_HASHES
    report["original_main_fp_sha256"] = MAIN_FP_HASH
    report["library_sha256"] = digest(library_path)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--main-fp", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit(args.root, args.library, args.main_fp)
    serialized = json.dumps(report, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
    print(serialized, end="")


if __name__ == "__main__":
    main()
