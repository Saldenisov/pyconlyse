"""Validate saved ACQ runtime-stop/TCP-error and outer-stop ingress wires.

Usage: python tools/validate_acq_stop_ingress.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, require, unique


LOCAL_CENSUS = {
    "30": {"47557", "60120", "43027", "21059", "1756", "50011",
           "1888", "85095", "12978"},
    "45": {"358", "43040", "50019", "68231", "7387"},
    "46": {"45441", "43367", "115330", "18163"},
    "47": {"118957", "43536"},
}


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def direct(source: str, target: str) -> None:
        require(any({source, target} <= group for group in signals),
                f"direct wire {source}->{target} changed")

    for index, expected in LOCAL_CENSUS.items():
        actual = {node.get("uid") for node in root.findall(".//*[@class='gRef']")
                  if node.findtext("termList/*/dco/paramIdx") == index}
        require(actual == expected, f"local param {index} reference census changed")

    for (selector_uid, source_node_uid, source_class, source_term,
         select_term, true_frame_uid, literal_uid, value, stop_uid,
         stop_term, tcp_uid, tcp_term) in (
        ("28682", "24576", "sharedVariableDynamicWrite", "24593",
         "40177", "42989", "43005", "01", "43027", "43033",
         "43040", "43045"),
        ("40346", "7486", "sharedVariableDynamicWrite", "7511",
         "47171", "50030", "49997", "01", "50011", "50014",
         "50019", "50022"),
        ("40205", "22840", "sharedVariableDynamicRead", "22851",
         "40253", "40224", "44039", "0000", "85095", "85111",
         "68231", "68238"),
    ):
        selector = unique(root, "select", selector_uid)
        source = unique(root, source_class, source_node_uid)
        require(source_term in {term.get("uid") for term in source.findall("termList/*")},
                f"PSP source {source_node_uid} terminal changed")
        direct(source_term, select_term)
        require([(entry.findtext("start"), entry.findtext("diagramIdx"))
                 for entry in selector.findall("SelectRangeArray32/*")]
                == [("0", "0"), ("1", "1")],
                f"PSP error selector {selector_uid} polarity changed")
        false_arm, true_arm = selector.find("diagramList")
        require(true_arm.get("uid") == true_frame_uid
                and len(false_arm.find("zPlaneList")) == 0,
                f"PSP error arm {selector_uid} changed")
        literal = true_arm.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
        stop = unique(root, "gRef", stop_uid)
        tcp = unique(root, "gRef", tcp_uid)
        require(literal is not None and literal.text == value
                and stop in true_arm.iter() and tcp in true_arm.iter()
                and stop.findtext("termList/*/dco/paramIdx") == "30"
                and tcp.findtext("termList/*/dco/paramIdx") == "45",
                f"PSP error assignment in {selector_uid} changed")
        direct(literal_uid, stop_term)
        direct(literal_uid, tcp_term)

    for loop_uid, reader_uid, source_term, test_uid, test_term in (
        ("47483", "47557", "47561", "47497", "47496"),
        ("59483", "60120", "60127", "59503", "59505"),
        ("20601", "21059", "21066", "20619", "20621"),
        ("203", "1756", "1806", "221", "223"),
        ("102", "1888", "7921", "120", "122"),
    ):
        loop = unique(root, "whileLoop", loop_uid)
        reader = unique(root, "gRef", reader_uid)
        test = unique(root, "lTst", test_uid)
        require(reader in loop.iter() and test in loop.iter()
                and reader.findtext("termList/*/dco/paramIdx") == "30"
                and test.findtext("objFlags") == "65537",
                f"runtime-stop loop {loop_uid} source or polarity changed")
        direct(source_term, test_term)
    general_reader = unique(root, "gRef", "118957")
    general_writer = unique(root, "gRef", "43536")
    require(general_reader.find("termList/*").findtext("objFlags") == "4096"
            and general_writer.find("termList/*").findtext("objFlags") == "36864",
            "Arrêt général read/write direction changed")
    return [
        "Two PSP-write error True arms assign stop=True and TCP ED=True; "
        "the checked PSP-read error True arm assigns both False",
        "All five runtime While exits read stop with Stop-if-True polarity; "
        "Arrêt général has no root local True writer in the saved diagram",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ stop ingress and local-writer census")


if __name__ == "__main__":
    main()
