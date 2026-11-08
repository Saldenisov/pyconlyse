"""Validate saved ACQ controlled-stop phase-1 NI6602 task-stop wires.

Usage: python tools/validate_acq_controlled_stop_pulse_sync.py SOURCE_EXPORT_ZIP
Read-only: never runs a VI or accesses PSP/NI hardware.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_cooling_start_completion import checked_root, field, require, unique


TASKS = (
    # ordered frame, task field, source local, mux, property, comparison,
    # bound comparison, OR, loop, test, wait, Stop Task, Clear Errors, literals,
    # and direct terminal wires.
    (0, 3, "47925", "47933", "47845", "47826", "47867", "47878",
     "47748", "47790", "47837", "47695", "47942",
     (("47814", "00000028"), ("47802", "00000001"),
      ("47792", "01")),
     (("47928", "47935"), ("47938", "47754"),
      ("47757", "47847"), ("47859", "47834"),
      ("47792", "47831"), ("47814", "47872"),
      ("47784", "47875"), ("47828", "47883"),
      ("47869", "47886"), ("47880", "47789"),
      ("47802", "47842"), ("47758", "47698"),
      ("47750", "47731"), ("47745", "47957"))),
    (1, 4, "48208", "48214", "48128", "48108", "48150", "48161",
     "48046", "48072", "48119", "47995", "48223",
     (("48096", "00000028"), ("48084", "00000001"),
      ("48074", "01")),
     (("48211", "48216"), ("48219", "48052"),
      ("48055", "48130"), ("48142", "48116"),
      ("48074", "48113"), ("48096", "48155"),
      ("48068", "48158"), ("48110", "48166"),
      ("48152", "48169"), ("48163", "48071"),
      ("48084", "48125"), ("48056", "47998"),
      ("48048", "48031"), ("48043", "48238"))),
)


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    outer_phases = unique(root, "sequence", "51954").find("diagramList")
    require(outer_phases is not None and outer_phases[1].get("uid") == "51962",
            "controlled-stop phase 1 moved")
    sequence = unique(root, "sequence", "47655")
    require(sequence in outer_phases[1].iter(), "pulse-stop sequence moved")
    frames = sequence.find("diagramList")
    require([frame.get("uid") for frame in frames]
            == ["47671", "47989", "48537"],
            "pulse-stop frame order changed")
    signals = [
        {term.get("uid") for term in signal.findall("termList/*")}
        for signal in root.findall(".//*[@class='signal']")
    ]

    def direct(source: str, target: str) -> None:
        require(any({source, target} <= group for group in signals),
                f"direct wire {source}->{target} changed")

    for (frame_index, task_field, source_uid, mux_uid, property_uid,
         equal_uid, greater_uid, or_uid, loop_uid, test_uid, wait_uid,
         stop_uid, clear_uid, literals, wires) in TASKS:
        frame = frames[frame_index]
        nodes = [unique(root, klass, uid) for klass, uid in (
            ("gRef", source_uid), ("nMux", mux_uid),
            ("propNode", property_uid), ("prim", equal_uid),
            ("prim", greater_uid), ("cpdArith", or_uid),
            ("whileLoop", loop_uid), ("lTst", test_uid),
            ("prim", wait_uid), ("iUse", stop_uid),
            ("iUse", clear_uid))]
        require(all(node in frame.iter() for node in nodes),
                f"task {task_field} nodes moved")
        require(nodes[0].findtext("termList/*/dco/paramIdx") == "21"
                and field(nodes[1], nodes[1].findall("termList/*")[1].get("uid"))
                == task_field,
                f"task {task_field} reference source changed")
        require(nodes[2].findtext(".//PropItemCode") == "6414"
                and nodes[3].findtext("primResID") == "1102"
                and nodes[4].findtext("primResID") == "1110"
                and nodes[5].findtext("objFlags") == "720896"
                and nodes[7].findtext("objFlags") == "65537"
                and nodes[8].findtext("primResID") == "1302",
                f"task {task_field} poll predicate changed")
        require(nodes[9].findtext("label/textRec/text") == '"DAQmx Stop Task.vi"'
                and nodes[10].findtext("label/textRec/text") == '"Clear Errors.vi"',
                f"task {task_field} post-poll VI call changed")
        for literal_uid, value in literals:
            constant = frame.find(f".//*[@uid='{literal_uid}']/dco/ConstValue")
            require(constant is not None and constant.text == value,
                    f"task {task_field} literal {literal_uid} changed")
        for source, target in wires:
            direct(source, target)
    wait = unique(root, "prim", "48555")
    require(wait in frames[2].iter() and wait.findtext("primResID") == "1302",
            "post-task wait moved")
    literal = frames[2].find(".//*[@uid='48543']/dco/ConstValue")
    require(literal is not None and literal.text == "000003E8",
            "post-task wait literal changed")
    direct("48543", "48560")
    return [
        "Phase 1 polls task-reference fields 3 then 4: pulse-complete True "
        "OR loop index > 40; each loop has a 1-ms Wait",
        "Each poll is followed by DAQmx Stop Task then Clear Errors on its "
        "error wire; the ordered third frame waits 1000 ms",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: ACQ controlled-stop NI6602 pulse-sync wires")


if __name__ == "__main__":
    main()
