"""Read-only validation of bounded NI6602 selector/error evidence.

Only pinned local files, ZIP members and XML are read. No VI, vendor module,
native library, transport, process or device is loaded or invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile

DEFAULT_EVIDENCE = (
    Path(__file__).resolve().parents[1]
    / "legacy/xp_acq_agent/data/counter_selector_error_evidence.json"
)
ROOT_ARCHIVE_SHA256 = "6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527"
HELPER_ARCHIVE_SHA256 = (
    "645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F"
)
HELPER_MEMBER = "1_ACQ_WRITE_NI6602.vi/vi_BDHb.xml"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(root, kind, uid):
    nodes = [
        node
        for node in root.iter()
        if node.get("class") == kind and node.get("uid") == uid
    ]
    require(len(nodes) == 1, "Expected one %s UID %s" % (kind, uid))
    return nodes[0]


def signals(root):
    return {
        node.get("uid"): tuple(term.get("uid") for term in node.findall("termList/*"))
        for node in root.iter()
        if node.get("class") == "signal"
    }


def exact_net(nets, terminals):
    matches = [
        uid for uid, connected in nets.items() if set(connected) == set(terminals)
    ]
    require(
        len(matches) == 1, "Expected one exact net for terminals %s" % list(terminals)
    )


def connected_slots(node, nets):
    wired = {terminal for net in nets.values() for terminal in net}
    return sorted(
        int(term.findtext("dco/paramIdx", "0"))
        for term in node.findall("termList/*")
        if term.get("uid") in wired
    )


def validate(evidence_path):
    evidence = json.loads(Path(evidence_path).read_text(encoding="utf-8"))
    require(evidence["schema_version"] == 1, "Evidence schema changed")
    pins = evidence["source_pins"]
    require(
        pins["acquisition_xml_archive"]["sha256"] == ROOT_ARCHIVE_SHA256,
        "Root archive identity changed",
    )
    require(
        pins["helper_xml_archive"]["sha256"] == HELPER_ARCHIVE_SHA256,
        "Helper archive identity changed",
    )
    require(
        pins["helper_xml_archive"]["diagram_member"] == HELPER_MEMBER,
        "Helper XML member changed",
    )
    checked_artifacts = set()
    checked_members = set()

    def checked_file(path, expected):
        require(
            type(expected) is str and re.fullmatch(r"[0-9A-F]{64}", expected),
            "Expected uppercase SHA-256 pin",
        )
        payload = Path(path).read_bytes()
        require(
            hashlib.sha256(payload).hexdigest().upper() == expected,
            "Artifact SHA-256 mismatch: %s" % path,
        )
        checked_artifacts.add((str(path), expected))
        return payload

    def checked_member(pin, member_key, digest_key):
        with ZipFile(pin["path"]) as archive:
            member = pin[member_key]
            require(
                archive.namelist().count(member) == 1,
                "Missing/duplicate archive member: %s" % member,
            )
            payload = archive.read(member)
        require(
            hashlib.sha256(payload).hexdigest().upper() == pin[digest_key],
            "Archive member SHA-256 mismatch: %s" % member,
        )
        checked_members.add((pin["path"], member))
        return ET.fromstring(payload)

    for name, pin in pins.items():
        path = pin.get("path", pin.get("extracted_vi_path"))
        require(path is not None, "Missing local artifact path: %s" % name)
        checked_file(path, pin["sha256"])
    local_handler = pins["inspected_local_simple_handler"]
    for prefix in ("diagram", "metadata"):
        checked_file(local_handler[prefix + "_path"], local_handler[prefix + "_sha256"])

    root = checked_member(
        pins["acquisition_xml_archive"], "diagram_member", "diagram_sha256"
    )
    metadata = checked_member(
        pins["acquisition_xml_archive"], "metadata_member", "metadata_sha256"
    )
    helper = checked_member(
        pins["helper_xml_archive"], "diagram_member", "diagram_sha256"
    )
    selector = evidence["selector_arithmetic"]
    resolution = selector["type_resolution"]
    heap = metadata.find("DTHP/Section/TypeDescSlice")
    require(heap is not None, "Missing heap type slice")
    shift = int(heap.get("IndexShift"))
    require(shift == resolution["dthp_index_shift"] == 6033, "Heap type shift changed")
    top = {}
    for node in metadata.findall("VCTP/Section/TopLevel/TypeDesc"):
        index = int(node.get("Index"))
        require(index not in top, "Duplicate consolidated type")
        top[index] = int(node.get("FlatTypeID"))
    flat = metadata.findall("VCTP/Section/TypeDesc")
    types = resolution["terminal_types"]
    require(
        len(types) == 15 and len({row["terminal_uid"] for row in types}) == 15,
        "Expected fifteen distinct selector terminal types",
    )
    for row in types:
        terminal = unique(root, "term", row["terminal_uid"])
        require(
            terminal.findtext("dco/typeDesc") == "TypeID(%d)" % row["heap_type_id"],
            "Terminal heap type changed: %s" % row["terminal_uid"],
        )
        require(
            1 <= row["heap_type_id"] <= int(heap.get("Count")),
            "Heap type outside slice",
        )
        consolidated = shift + row["heap_type_id"] - 1
        require(
            consolidated == row["consolidated_type_id"], "Consolidated type changed"
        )
        require(top[consolidated] == row["flat_type_id"], "Flat type mapping changed")
        require(
            flat[top[consolidated]].get("Type") == row["representation"],
            "Terminal numeric representation changed",
        )
    root_nets = signals(root)
    wires = selector["wires"]
    require(
        len(wires) == 11 and len({row["signal_uid"] for row in wires}) == 11,
        "Expected eleven distinct selector nets",
    )
    for row in wires:
        require(
            root_nets[row["signal_uid"]] == tuple(row["terminal_uids"]),
            "Selector wire changed: %s" % row["signal_uid"],
        )
    for key in ("divisor_constant", "multiplier_constant"):
        constant = selector[key]
        node = unique(root, "term", constant["terminal_uid"])
        require(
            node.findtext("dco/ConstValue") == constant["dbl_hex"] == "4000000000000000"
            and constant["value"] == 2.0,
            "Counter arithmetic constant changed",
        )
    for uid, resource in (
        ("15887", "1058"),
        ("26175", "1056"),
        ("22328", "1052"),
        ("22884", "1057"),
    ):
        require(
            unique(root, "prim", uid).findtext("primResID") == resource,
            "Selector primitive changed: %s" % uid,
        )
    cases = selector["representative_cases"]
    require(len(cases) == 12, "Expected twelve selector examples")
    for row in cases:
        n = row["selector"]
        require(type(n) is float and math.isfinite(n), "Finite DBL example required")
        guard = 0.0 < n < 17.0
        q = math.floor((n - 1.0) / 2.0) if guard else None
        require(
            row["source_guard"] is guard
            and row["counter"] == q
            and row["delay_index"] == (2 * q if guard else None)
            and row["width_index"] == (2 * q + 1 if guard else None)
            and row["task_in_bounds"] is (guard and 0 <= q < 8),
            "Selector example mismatch: %r" % n,
        )

    helper_nets = signals(helper)
    helper_pairs = (
        ("2758", "3135"),
        ("3138", "3204"),
        ("13028", "184"),
        ("180", "3210"),
        ("3207", "3146"),
        ("3143", "2983"),
        ("3213", "3134"),
        ("3131", "3016"),
    )
    for pair in helper_pairs:
        exact_net(helper_nets, pair)
    helper_flow = evidence["native_helper_error_flow"]
    downstream = helper_flow["downstream_terminal_routes"]
    require(len(downstream) == 6, "Expected six downstream helper routes")
    for route in downstream:
        exact_net(helper_nets, (route["from_terminal"], route["to_terminal"]))
    for outer, inner in (
        ("3135", "3138"),
        ("184", "180"),
        ("3143", "3146"),
        ("3131", "3134"),
    ):
        tunnel = unique(helper, "term", outer).find("dco")
        require(
            tunnel is not None and tunnel.get("class") == "lpTun",
            "Ordinary loop tunnel replaced",
        )
        require(
            {term.get("uid") for term in tunnel.findall("termList/*")}
            == {outer, inner},
            "Loop tunnel terminal pair changed",
        )
    clear = unique(helper, "iUse", "309")
    require(
        connected_slots(clear, helper_nets) == [0, 4],
        "Clear Errors connector wiring changed",
    )
    require(
        helper_flow["clear_errors"]["specific_error_code_input_wired"] is False,
        "Clear Errors code input must remain unwired",
    )

    caller = evidence["caller_error_handler_and_continuation"]
    require(
        root_nets[caller["error_wire_uid"]]
        == (
            caller["helper_error_output_terminal"],
            caller["handler_error_input_terminal"],
        ),
        "Caller handler error wire changed",
    )
    handler = unique(root, "iUse", caller["handler_call_uid"])
    require(
        connected_slots(handler, root_nets) == [9],
        "Caller handler has an unexpected wired connector",
    )
    mode = unique(root, "term", caller["handler_dialog_mode_input_terminal"])
    require(
        mode.findtext("dco/paramIdx") == "8", "Caller dialog mode connector changed"
    )
    sequence = unique(root, "sequence", selector["true_sequence_uid"])
    require(
        [node.get("uid") for node in sequence.findall("diagramList/*")]
        == caller["ordered_frame_uids_after_normal_return"],
        "Caller sequence frames changed",
    )

    proof_pin = pins["prior_local_handler_source_proof"]
    proof = json.loads(Path(proof_pin["path"]).read_text(encoding="utf-8"))
    observations = proof["observations"]
    require(
        observations["Simple_dialog_default"] == 1
        and observations["General_to_CORE_mode_remap"]
        == [[0, 0], [1, 1], [2, 2], [3, 4], [4, 5]],
        "Pinned local handler proof has different mode semantics",
    )
    require(
        proof["source_pins"]["simple"]["sha256"] == local_handler["sha256"],
        "Local handler proof identifies another binary",
    )
    front_pins = [
        row
        for row in proof["source_pins"]["simple"]["xml"]
        if row["path"].endswith("_FPHb.xml")
    ]
    require(len(front_pins) == 1, "Missing/ambiguous local handler front-panel pin")
    front = ET.fromstring(checked_file(front_pins[0]["path"], front_pins[0]["sha256"]))
    controls = [
        node
        for node in front.iter()
        if node.get("class") == "fPDCO" and node.findtext("conNum") == "8"
    ]
    require(len(controls) == 1, "Local handler dialog control changed")
    default = controls[0].findtext("DefaultData", "")
    require(
        re.findall(r"#x([0-9A-Fa-f]{2});", default) == ["00", "01"],
        "Local handler saved mode is not one",
    )
    xp_profile = caller["deployed_xp_labview_2012_profile"]
    invalid_index = selector["out_of_range_boundary"]
    require(
        xp_profile["binary_identity_qualified"] is False
        and invalid_index["native_default_task_qualified"] is False,
        "Unqualified native boundaries must remain explicit",
    )
    return {
        "status": "PASS",
        "evidence_path": str(Path(evidence_path).resolve()),
        "pinned_artifacts_checked": len(checked_artifacts),
        "archive_members_checked": len(checked_members),
        "selector_terminal_types_checked": len(types),
        "selector_wire_nets_checked": len(wires),
        "selector_examples_checked": len(cases),
        "helper_error_wire_nets_checked": len(helper_pairs) + len(downstream),
        "ordinary_loop_tunnels_checked": 4,
        "caller_wired_slots": [9],
        "local_2020_saved_dialog_mode": 1,
        "native_execution_performed": False,
        "hardware_access_performed": False,
        "output_files_written": False,
        "limits": evidence["limitations"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", nargs="?", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args(argv)
    try:
        result = validate(args.evidence)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        ET.ParseError,
        BadZipFile,
    ) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
