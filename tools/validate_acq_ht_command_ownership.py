"""Pin every original C9 local reference and its HT command ownership.

Reads saved XML only. Direct gRef writes are not native UI/VI Server writes,
physical voltage measurements, permission checks or a complete scheduler.
"""

from __future__ import annotations

import re

from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_stop_ui_bindings import checked_trees

HT_LABEL = "00 OUT00 b01 Cmd alimentation HT"
# Local UID, direct diagram, terminal, heap type, read flag, wire peer.
C9_REFERENCES = (
    ("1074", "76558", "1269", 1894, "1", "7453"),
    ("16414", "14803", "16417", 2029, None, "39466"),
    ("25050", "24611", "25053", 2236, "1", "16726"),
    ("19627", "25990", "19630", 2282, "1", "19664"),
    ("2494", "7386", "2497", 3028, "1", "7621"),
    ("10472", "10115", "10475", 3417, None, "10466"),
    ("10410", "10115", "10413", 3425, "1", "10463"),
    ("14748", "14553", "14751", 4572, "1", "14852"),
    ("65137", "64942", "65140", 4996, "1", "65241"),
    ("55766", "41713", "55769", 7581, "1", "55803"),
    ("11041", "47573", "12311", 7708, None, "42194"),
    ("9781", "47573", "11005", 7709, "1", "42197"),
    ("538", "42212", "11581", 7726, "1", "60956"),
)
DIRECT_WRITERS = {"16414", "10472", "11041"}
LIFECYCLE_FRAMES = ("135", "188", "367", "41058", "246")


def validate_phase_ownership(bd):
    """The remote receiver and stop ramp are in different stacked phases."""
    outer = unique(bd, "sequence", "359")
    frames = outer.findall("diagramList/*")
    require(
        tuple(frame.get("uid") for frame in frames) == LIFECYCLE_FRAMES,
        "C9 lifecycle phase ordering changed",
    )
    for uid, phase in (("16414", 1), ("10472", 2), ("11041", 3)):
        node = unique(bd, "gRef", uid)
        require(node in frames[phase].iter(), "C9 writer lifecycle owner changed")
    runtime = frames[2]
    require(
        {
            (node.get("class"), node.get("uid"))
            for node in runtime.findall("zPlaneList/*")
        }
        == {("whileLoop", uid) for uid in ("47483", "59483", "20601", "203", "102")},
        "five-loop runtime phase changed",
    )
    dispatcher = unique(runtime, "whileLoop", "102")
    require(
        unique(runtime, "gRef", "10472") in dispatcher.iter(),
        "C9 remote receiver moved outside dispatcher",
    )
    stop_refs = {
        node.get("uid")
        for node in frames[3].findall(".//*[@class='gRef']")
        if node.findtext("termList/*/dco/paramIdx") == "12"
        and node.findtext("termList/*/dco/objFlags") is None
    }
    require(stop_refs == {"11041"}, "another direct C9 stop-phase writer appeared")
    return {
        "remote_receiver_phase": 2,
        "ht_ramp_phase": 3,
        "runtime_loops_must_join_before_ramp": 5,
        "remote_receiver_overlaps_outer_ramp": False,
        "indirect_writers_or_new_vi_invocations_excluded": False,
    }


def c9_type(metadata, heap):
    descriptor, flat = heap_type(metadata, heap)
    members = descriptor.findall("TypeDesc")
    require(
        descriptor.get("Type") == "Cluster"
        and descriptor.get("Label") == "C9NI6703"
        and len(members) == 10
        and all(flat[int(n.get("TypeID"))].get("Type") == "NumFloat64" for n in members)
        and flat[int(members[0].get("TypeID"))].get("Label") == HT_LABEL,
        "C9/HT typed field identity changed",
    )


def validate_trees(bd, fp, metadata):
    references = [
        node
        for node in bd.findall(".//*[@class='gRef']")
        if node.findtext("termList/*/dco/paramIdx") == "12"
    ]
    require(
        len(references) == len(C9_REFERENCES)
        and {n.get("uid") for n in references} == {r[0] for r in C9_REFERENCES},
        "complete C9 local-reference census changed",
    )
    parents = {child: parent for parent in bd.iter() for child in parent}
    writers = set()
    for uid, diagram, port, heap, flags, peer in C9_REFERENCES:
        node = unique(bd, "gRef", uid)
        terms = node.findall("termList/*")
        require(len(terms) == 1 and terms[0].get("uid") == port, "C9 terminal changed")
        dco = terms[0].find("dco")
        require(
            dco is not None
            and dco.get("class") == "gRefDCO"
            and dco.findtext("paramIdx") == "12"
            and dco.findtext("objFlags") == flags
            and dco.findtext("typeDesc") == f"TypeID({heap})",
            "C9 local direction/type/index changed",
        )
        c9_type(metadata, heap)
        direct = node
        while direct.get("class") != "diag" and direct in parents:
            direct = parents[direct]
        require(direct.get("uid") == diagram, "C9 direct owner diagram changed")
        nets = [
            {term.get("uid") for term in signal.findall("termList/*")}
            for signal in direct.findall("signalList/*")
        ]
        attached = [net for net in nets if port in net]
        require(attached == [{port, peer}], "C9 complete direct wire changed")
        if flags is None:
            writers.add(uid)
    require(writers == DIRECT_WRITERS, "C9 direct writer ownership changed")

    # Cross-check control identity separately; no loaded values are inferred.
    control = unique(fp, "fPDCO", "7032")
    display = control.find("ddo")
    require(
        control.findtext("typeDesc") == "TypeID(970)"
        and display is not None
        and display.get("class") == "stdClust"
        and display.get("uid") == "6921",
        "C9 front-panel identity changed",
    )
    c9_type(metadata, 970)
    display_ids = {n.get("uid") for n in display.iter() if n.get("uid")}
    require(
        not any(
            prop.find("ddo") is not None and prop.find("ddo").get("uid") in display_ids
            for prop in bd.findall(".//*[@class='propNode']")
        ),
        "direct property target appeared on C9 or its display descendants",
    )
    # A bank number belongs to gRef memory only, not similarly numbered iUse
    # connector slots. Other typed local indices must not alias the C9 bank.
    for ref in bd.findall(".//*[@class='gRef']"):
        type_id = re.fullmatch(
            r"TypeID\((\d+)\)", ref.findtext("termList/*/dco/typeDesc", "")
        )
        require(type_id is not None, "local type descriptor missing")
        descriptor, _ = heap_type(metadata, int(type_id[1]))
        if descriptor.get("Label") == "C9NI6703":
            require(
                ref.findtext("termList/*/dco/paramIdx") == "12",
                "another typed C9 local-bank alias appeared",
            )
    return {
        "c9_local_references": 13,
        "direct_reads": 10,
        "direct_writers": tuple(sorted(writers)),
        "saved_ht_field": 0,
        "loaded_ui_or_indirect_writers_excluded": False,
        "physical_permission_proven": False,
        "whole_acquisition_qualified": False,
    }


if __name__ == "__main__":
    trees = checked_trees()
    print(validate_trees(*trees))
    print(validate_phase_ownership(trees[0]))
