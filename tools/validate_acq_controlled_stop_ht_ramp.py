"""Validate the saved ACQ outer-frame-3 controlled-stop HT command ramp.

Usage: python tools/validate_acq_controlled_stop_ht_ramp.py SOURCE_EXPORT_ZIP
Static and read-only: no VI, PSP, or NI task is accessed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


WIRES = (
    ("7927", "43512"),   # TCP ED local -> outer Case
    ("118967", "53005"), # Arrêt général local -> inner Case
    ("11581", "60956"),  # current C9 command cluster -> field-0 read
    ("60959", "44766"),  # current field -> Less? x
    ("46097", "44763"),  # 6.6 -> Less? y
    ("44760", "47590"),  # comparison -> False/True selector
    ("51598", "42224"),  # selector result -> While Stop-if-True
    ("43717", "51591"),  # False arm keeps loop running
    ("50686", "51595"),  # True arm exits loop
    ("52299", "40575"),  # False-arm current field -> Subtract x
    ("53615", "40571"),  # 0.1 -> Subtract y
    ("40566", "42198"),  # decremented field -> C9 bundle field 0
    ("11005", "42197"),  # old C9 cluster -> bundle base
    ("42194", "12311"),  # updated C9 cluster -> local writer
    ("46134", "46126"),  # 500 ms -> Wait
    ("51420", "206183"), # separate 6.0 -> local param 50
    ("60959", "47551"),  # current field -> local param 48
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    outer = unique(root, "sequence", "359")
    frame = outer.find("diagramList")[3]
    require(frame.get("uid") == "41058", "outer controlled-stop frame moved")
    tcp_case = unique(root, "select", "43488")
    require(tcp_case in frame.iter(), "TCP ED selector moved")
    require(unique(root, "gRef", "7387").findtext("termList/*/dco/paramIdx") == "45"
            and [(entry.findtext("start"), entry.findtext("diagramIdx"))
                 for entry in tcp_case.findall("SelectRangeArray32/*")]
            == [("0", "0"), ("1", "1")],
            "TCP ED source or Case polarity changed")
    tcp_false, tcp_true = tcp_case.find("diagramList")
    require(tcp_false.get("uid") == "43496"
            and tcp_true.get("uid") == "43502"
            and len(tcp_false.find("zPlaneList")) == 0,
            "TCP ED outer Case arms changed")
    general_case = unique(root, "select", "52981")
    require(general_case in tcp_true.iter(), "Arrêt général Case moved")
    require(unique(root, "gRef", "118957").findtext("termList/*/dco/paramIdx") == "47"
            and [(entry.findtext("start"), entry.findtext("diagramIdx"))
                 for entry in general_case.findall("SelectRangeArray32/*")]
            == [("0", "0"), ("1", "1")],
            "Arrêt général source or Case polarity changed")
    _, general_true = general_case.find("diagramList")
    require(general_true.get("uid") == "52995", "general-stop True arm moved")
    phases = unique(root, "sequence", "51954")
    require(phases in general_true.iter()
            and len(phases.find("diagramList")) == 7,
            "seven controlled-stop phases changed")
    ramp_phase = phases.find("diagramList")[0]
    require(ramp_phase.get("uid") == "60323", "HT ramp phase moved")
    ramp = unique(root, "whileLoop", "18613")
    require(ramp in ramp_phase.iter(), "HT ramp While loop moved")
    selector = unique(root, "select", "47558")
    require(selector in ramp.iter()
            and [(entry.findtext("start"), entry.findtext("diagramIdx"))
                 for entry in selector.findall("SelectRangeArray32/*")]
            == [("0", "0"), ("1", "1")],
            "HT comparison Case polarity changed")
    false_arm, true_arm = selector.find("diagramList")
    require(false_arm.get("uid") == "47573"
            and true_arm.get("uid") == "47580"
            and not any(node.get("class") == "gRef" for node in true_arm.iter()),
            "HT ramp False/True arms changed")
    test = unique(root, "lTst", "42222")
    require(test in ramp.iter() and test.findtext("objFlags") == "65537",
            "HT ramp While exit polarity changed")
    require(unique(root, "prim", "44754").findtext("primResID") == "1111"
            and unique(root, "prim", "583").findtext("primResID") == "1051"
            and unique(root, "prim", "46117").findtext("primResID") == "1302",
            "Less/Subtract/Wait primitives changed")
    require(field(unique(root, "nMux", "41650"), "60959") == 0
            and field(unique(root, "nMux", "42188"), "42198") == 0,
            "C9 command field changed")
    for uid, index in (("538", "12"), ("9781", "12"),
                       ("11041", "12"), ("42204", "48"),
                       ("206173", "50")):
        node = unique(root, "gRef", uid)
        require(node in ramp.iter()
                and node.findtext("termList/*/dco/paramIdx") == index,
                f"HT ramp local reference {uid} changed")
    literals = {
        "46097": "401A666666666666",  # DBL 6.6
        "53615": "3FB999999999999A",  # DBL 0.1
        "46134": "000001F4",           # U32 500 ms
        "43717": "0000",               # False
        "50686": "01",                 # True
        "51420": "4018000000000000",  # DBL 6.0, separate local
    }
    for uid, expected in literals.items():
        matches = ramp.findall(f".//*[@uid='{uid}']/dco/ConstValue")
        require(len(matches) == 1 and matches[0].text == expected,
                f"HT ramp literal {uid} changed")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]
    for source, target in WIRES:
        require(any({source, target} <= group for group in signals),
                f"HT ramp wire {source}->{target} changed")
    return [
        "Outer controlled-stop phase 0 compares local C9[0] command < 6.6; "
        "the True arm exits without another C9 write",
        "False arm subtracts 0.1 from C9[0], writes the rebuilt local C9 "
        "cluster, and waits 500 ms; no separate iteration-limit wire",
        "Loop body also assigns 6.0 to local param 50 and mirrors the current "
        "C9[0] value to local param 48; their business labels remain unverified",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ controlled-stop HT ramp raw wires")


if __name__ == "__main__":
    main()
