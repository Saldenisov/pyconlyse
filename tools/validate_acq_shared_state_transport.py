"""Hash-pinned, offline audit of the native latest-only telemetry consumer.

Executes no VI, opens no network connection and makes no delivery/timing claim.
The empty queue is selected by NOT Dequeue.timed_out, not error_out: a native
100 ms Dequeue timeout returns a default element without an error.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from validate_acq_shared_state_helpers import (
    COMMON_CLASSES,
    Export,
    check_execution,
    check_wires,
    const_bytes,
    const_string,
    digest,
    node,
    require,
)

NAME = "ACQ_SharedState_Transport"
NATIVE = Path("C:/dev/ELYSE-ACQ-telemetry/2026-10-14/transport_timeout_guard_20261014")
SOURCE_HASH = "873D1484E7368077F823100570EFCC9B8E6B51051B43125FAF1B05D46930BC5A"
EXPORT_HASHES = {
    "vi.xml": "809C649FE22E6A390BA7F58062C924B2330D6A83CE1B8BBBD3575577165EA920",
    "vi_BDHb.xml": "29479908B1E3CB8BF2EA9CE7FBF422502281D6CD9E533A4F38A4D023BAAA5197",
    "vi_FPHb.xml": "BF210D0A5CC57763E0A0ED13D3FFA85C26B3A94EA994F40B6F94861AB33F1AC0",
}
PRIMITIVES = {
    "1342": "9109",  # Release Queue, outside While
    "1072": "9108",  # Obtain Queue, owner outside While
    "1832": "1064",  # NOT timed_out
    "551": "1127",  # ACK header range check
    "492": "1166",  # ACK header -> I32
    "459": "1716",  # Read ACK body
    "310": "1164",  # I32 length -> four big-endian bytes
    "254": "1502",  # XML byte length
    "221": "1716",  # Read four-byte ACK header
    "105": "1713",  # TCP Close
    "75": "1714",  # TCP Write
    "43": "1715",  # TCP Open
    "1410": "1062",  # Stop OR owner failure
    "1251": "8400",  # Flatten Variant to XML
    "62": "9113",  # Dequeue Element
}
WIRES = {
    "3": (
        ("1363", "1626"),
        ("1386", "1348"),
        ("1095", "1333"),
        ("1089", "1207"),
        ("1062", "1077"),
        ("1125", "1080"),
        ("1113", "1074"),
        ("1101", "1086"),
    ),
    "297": (
        ("1838", "1704"),
        ("1182", "1841"),  # timed_out -> NOT -> selector
        ("1412", "311"),
        ("1403", "1415"),
        ("446", "1418"),
        ("1330", "1173", "1400"),
        ("1176", "1382"),
        ("1185", "1794"),
        ("1257", "1781"),
        ("1179", "1260"),
        ("1230", "1170"),
        ("1204", "1167"),
        ("1769", "930"),
    ),
    "1688": (),  # False: no packet, no TCP operation
    "1694": (
        ("1793", "60"),
        ("1780", "263", "363"),
        ("557", "1768"),
        ("111", "864"),
        ("468", "760"),
        ("701", "63", "93", "242", "480"),
        ("465", "117"),
        ("471", "123"),
        ("560", "483"),
        ("635", "563"),
        ("600", "569"),
        ("504", "566"),
        ("227", "477"),
        ("233", "486"),
        ("230", "498"),
        ("440", "245", "501"),
        ("81", "239"),
        ("87", "248"),
        ("357", "96"),
        ("322", "360"),
        ("260", "334"),
        ("51", "90"),
        ("54", "99"),
        ("178", "66"),
        ("143", "69"),
    ),
}


def validate(export):
    check_execution(export)
    require(not export.calls, "consumer must not call subVIs")
    allowed = COMMON_CLASSES | {
        "SelectorRange",
        "caseSel",
        "concat",
        "concatDCO",
        "lCnt",
        "lTst",
        "lpTun",
        "nMux",
        "nmxDCO",
        "numLabel",
        "selLabel",
        "selTun",
        "select",
        "stdBool",
        "stdNum",
        "whileLoop",
    }
    classes = {item.get("class") for item in export.bd.iter() if item.get("class")}
    require(
        classes <= allowed, "unexpected executable class: " + str(classes - allowed)
    )
    primitives = [
        (item.get("uid"), item.findtext("primResID"))
        for item in export.bd.iter()
        if item.get("class") == "prim"
    ]
    require(Counter(primitives) == Counter(PRIMITIVES.items()), "primitive set changed")
    for klass, uid in (
        ("whileLoop", "286"),
        ("select", "1680"),
        ("nMux", "1394"),
        ("concat", "351"),
    ):
        require(
            [item.get("uid") for item in export.bd.iter() if item.get("class") == klass]
            == [uid],
            "control structure changed: " + klass,
        )
    check_wires(export, WIRES)
    selector = node(export.bd, "select", "1680")
    ranges = [
        (r.findtext("start"), r.findtext("end"), r.findtext("diagramIdx"))
        for r in selector.findall("SelectRangeArray32/*")
    ]
    require(ranges == [("0", "0", "0"), ("1", "1", "1")], "case polarity changed")
    empty = node(export.bd, "diag", "1688")
    require(
        [item.get("class") for item in empty.findall("nodeList/*")] == ["sRN"],
        "empty queue case must contain no executable operation",
    )
    require(
        node(export.bd, "selTun", "1765").findtext("objFlags") == "3147777",
        "idle ACK-length output default changed",
    )
    for uid, value in {
        "1099": "00000001",
        "1123": "01",
        "1228": "00000064",
        "699": "000003E8",
        "176": "223E",
        "438": "00000004",
        "598": "00010000",
        "633": "00000001",
    }.items():
        require(
            const_bytes(export, uid).hex().upper() == value, "constant changed: " + uid
        )
    require(const_string(export, "141") == "127.0.0.1", "TCP must be loopback only")
    require(
        const_string(export, "1111") == "ELYSE_ACQ_SHARED_STATE_LATEST_V1",
        "dedicated queue name changed",
    )
    for uid in ("1077", "1179", "1260"):
        type_id = node(export.bd, "term", uid).findtext("dco/typeDesc")
        require(export.shape(int(type_id[7:-1])) == ("LVVariant", ()), "variant lost")
    type_id = node(export.bd, "term", "1182").findtext("dco/typeDesc")
    require(
        export.shape(int(type_id[7:-1])) == ("Boolean", ()), "timed_out must be Boolean"
    )
    return {
        "static_native_audit_passed": True,
        "queue_capacity": 1,
        "dequeue_timeout_ms": 100,
        "tcp_timeout_ms_each_operation": 1000,
        "empty_queue_tcp_operations": 0,
        "queue_cleanup_outside_while": True,
        "hardware_access": False,
        "native_runtime_verified_by_this_audit": False,
        "ack_json_validation": False,
        "limitations": [
            "ACK JSON remains raw; header validity is not an acceptance/delivery proof",
            "Network time is isolated from main VI but bounds are per operation",
            "A dequeued sample lost before XP acceptance is not retried by this VI",
            "Static audit does not verify live cards, main integration or timing",
        ],
    }


def audit(native=NATIVE):
    native = Path(native)
    require(digest(native / (NAME + ".vi")) == SOURCE_HASH, "native VI hash changed")
    directory = native / "export" / NAME
    for filename, expected in EXPORT_HASHES.items():
        require(digest(directory / filename) == expected, "saved export hash changed")
    return validate(Export(directory))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, default=NATIVE)
    args = parser.parse_args()
    print(json.dumps(audit(args.native), indent=2))
