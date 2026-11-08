"""Trace saved Acquisition NI6071E initialization fallback, without execution.

Usage: python tools/validate_acq_initialization_ai_fallback.py SOURCE_EXPORT_ZIP
Proves root call order/arguments, not DAQmx effects or a successful retry.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

from validate_acq_cooling_start_completion import checked_root, require, unique
from validate_acq_controlled_stop_wait_tunnels import direct


def error_case(root, uid, ports, arms):
    case = unique(root, "select", uid)
    require([(item.findtext("start"), item.findtext("diagramIdx"))
             for item in case.findall("SelectRangeArray32/*")]
            == [("0", "0"), ("1", "1")], "error Case mapping changed")
    diagrams = case.find("diagramList")
    require(diagrams is not None and len(diagrams) == 2
            and [diagram.get("uid") for diagram in diagrams] == list(arms),
            "error Case diagram order changed")
    terms = case.findall("termList/*")
    require(len(terms) == 2, "error Case external ports changed")
    for term, (external, kind, internal) in zip(terms, ports):
        dco = term.find("dco")
        require(term.get("uid") == external and dco.get("class") == kind
                and [port.get("uid") for port in dco.findall("termList/*")]
                == [*internal, external], "error Case frame-port mapping changed")
    require(len(diagrams[0].find("zPlaneList")) == 0,
            "no-error arm is no longer empty")
    direct(diagrams[0], ports[0][2][0], ports[1][2][0])
    return case, diagrams[1]


def call(root, frame, uid, label, terminal_slots):
    node = unique(root, "iUse", uid)
    require(node in frame.findall("zPlaneList/*")
            and node.findtext("label/textRec/text") == f'"{label}"',
            f"fallback call {uid} changed or moved")
    for term_uid, slot in terminal_slots:
        term = node.find(f"termList/*[@uid='{term_uid}']")
        require(term is not None and (term.findtext("dco/paramIdx") or "0") == slot,
                f"fallback call {uid} connector slot changed")


def validate_tree(root: ET.Element) -> list[str]:
    sequence = unique(root, "sequence", "201")
    frame = sequence.find("diagramList")[2]
    require(frame.get("uid") == "133", "AI test initialization frame moved")
    require({node.get("uid") for node in frame.findall("zPlaneList/*")}
            == {"45", "1675", "319", "287", "2389", "2105"},
            "AI test frame gained/removed selector logic")
    call(root, frame, "287", "1_ACQ_READ_NI6071E.vi", (("1309", "0"),))
    direct(frame, "1309", "2107")
    gate, failure = error_case(root, "2105", (
        ("2107", "caseSel", ("2110", "2111")),
        ("2112", "selTun", ("2115", "2116")),
    ), ("2119", "2128"))
    require(gate in frame.findall("zPlaneList/*"), "AI read error gate moved")
    require({node.get("uid") for node in failure.findall("zPlaneList/*")}
            == {"8364", "8343", "7931", "4034", "2390", "2402",
                "2415", "2428", "2310", "2302", "2239", "1198", "2134"},
            "fallback arm operations changed")
    call(root, failure, "2134", "Clear Errors.vi",
         (("2149", "4"), ("2137", "0")))
    call(root, failure, "4034", "DAQmx Clear Task.vi",
         (("4041", "0"), ("4160", "11"), ("4247", "15")))
    call(root, failure, "7931", "DAQmx Clear Task.vi",
         (("7971", "0"), ("8009", "11"), ("8021", "15")))
    call(root, failure, "1198", "1_ACQ_INIT_NI6071E.vi", (
        ("1201", "0"), ("1205", "1"), ("1209", "2"), ("1212", "3"),
        ("1229", "4"), ("1232", "5"), ("1235", "6"), ("1238", "7"),
    ))
    for source, target in (("2111", "2149"), ("2137", "4160"),
                           ("4247", "8009"), ("8021", "1212"),
                           ("1238", "2241"), ("2246", "2116")):
        direct(failure, source, target)

    for uid, slot, term_uid, peer in (
        ("8364", "23", "8367", "4041"),
        ("8343", "24", "8351", "7971"),
        ("2310", "23", "2313", "1232"),
        ("2302", "24", "2305", "1235"),
    ):
        reference = unique(root, "gRef", uid)
        require(reference in failure.findall("zPlaneList/*")
                and reference.findtext(f"termList/*[@uid='{term_uid}']/dco/paramIdx") == slot,
                "fallback task-reference bank changed")
        direct(failure, term_uid, peer)

    expected_literals = {
        "2390": ("0000000A", "1229"),
        "2402": ("000000102F312F32304D487A54696D6562617365", "1201"),
        "2415": ("000000102F322F32304D487A54696D6562617365", "1205"),
        "2428": ("40B3880000000000", "1209"),
    }
    literal_source = unique(root, "sRN", "2132")
    require(literal_source in failure.findall("nodeList/*"),
            "fallback constant definitions moved")
    for uid, (value, destination) in expected_literals.items():
        term = literal_source.find(f"termList/*[@uid='{uid}']")
        require(term is not None and term.find("dco").get("class") == "bDConstDCO"
                and term.findtext("dco/ConstValue") == value,
                f"fallback literal {uid} changed")
        direct(failure, uid, destination)
    require(struct.unpack(">d", bytes.fromhex(expected_literals["2428"][0]))[0] == 5000,
            "fallback sample-rate literal decode changed")

    last_gate, last_failure = error_case(root, "2239", (
        ("2241", "caseSel", ("2244", "2245")),
        ("2246", "selTun", ("2249", "2250")),
    ), ("2253", "2262"))
    require(last_gate in failure.findall("zPlaneList/*")
            and len(last_failure.find("zPlaneList")) == 1,
            "fallback initializer error arm changed")
    call(root, last_failure, "2268", "Clear Errors.vi",
         (("2283", "4"), ("2271", "0")))
    direct(last_failure, "2245", "2283")
    direct(last_failure, "2271", "2250")

    local = unique(root, "sLoc", "306")
    require(local in sequence.findall("seqLocDCOList/*")
            and local.findtext("diagDefined") == "02"
            and [term.get("uid") for term in local.findall("termList/*")]
            == ["20372", "1319", "1320", "1371", "21528", "7590"],
            "fallback result sequence-local mapping changed")
    direct(frame, "2112", "1320")
    return [
        "NI6071E READ error output 1309 directly selects Case 2105; "
        "-200284 is a comment, not an equality guard in this frame",
        "Error arm: Clear Errors -> Clear Task(C1 bank 23) -> "
        "Clear Task(C2 bank 24) -> NI6071E INIT -> error gate",
        "Fallback initializer gets trigger inputs /1/20MHzTimebase and "
        "/2/20MHzTimebase, 5000 Hz, 10 samples; outputs replace banks 23/24",
        "Final error arm only clears the initializer error; output goes "
        "to sequence local 306. No second test read or retry loop exists "
        "inside this root frame; success and subVI internals are not proved",
    ]


def validate(path: Path) -> list[str]:
    return validate_tree(checked_root(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    for line in validate(parser.parse_args().source_export_zip):
        print(line)
    print("PASS: ACQ NI6071E initialization fallback root wires")


if __name__ == "__main__":
    main()
