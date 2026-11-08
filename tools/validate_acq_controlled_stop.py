"""Complete direct graphs of the original seven-phase outer stop, offline.

Calls to standard DAQmx/Done/Error primitives remain injected boundaries.
This proof does not cover the sibling I/O loop or the outer TCP selector.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from DeviceServers.control.elyse_acq.vi_simulation.controlled_stop import (
    CONTROLLED_STOP,
)
from validate_acq_counter_procedures import validate_counter_frame
from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_linear_procedures import decode_frame
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations
from validate_acq_vam_status import checked_vam

SCALARS = {
    35: ("Boolean", "ACTION"),
    46: ("Boolean", "stop urgence"),
    47: ("Boolean", "Arrêt général"),
    50: ("NumFloat64", "ETAPES:"),
}
WRAPPERS = {
    "51962": ("47655", ("47671", "47989", "48537"), "52572"),
    "43360": ("49098", ("49114", "49284", "49853"), "44402"),
    "129793": ("128434", ("128452", "128743", "128773", "129221"), "129956"),
    "1722": (
        "42397",
        (
            "42424",
            "42549",
            "42712",
            "42763",
            "42895",
            "43136",
            "43197",
            "43264",
            "43315",
            "43345",
            "43418",
            "43468",
            "43520",
            "43589",
            "43933",
        ),
        "40565",
    ),
    "52159": (
        "54275",
        ("54293", "54391", "54440", "54470", "54530", "54590", "58827", "54731"),
        "52936",
    ),
}
RAMP_NETS = {
    "42212": (
        ("51420", "206183"),
        ("60959", "44766", "52307", "47551"),
        ("51598", "42224"),
        ("44760", "47590"),
        ("46097", "44763"),
        ("11581", "60956"),
    ),
    "47573": (
        ("46134", "46126"),
        ("43717", "51591"),
        ("40566", "42198"),
        ("42194", "12311"),
        ("11005", "42197"),
        ("53615", "40571"),
        ("52299", "40575"),
    ),
    "47580": (("50686", "51595"),),
}


def _kind(metadata, term):
    return heap_type(metadata, int(term.findtext("dco/typeDesc")[7:-1]))[0]


def validate_ramp(root, metadata):
    phase = unique(root, "diag", "60323")
    operations(phase, [("whileLoop", "18613")], "HT ramp wrapper")
    exact_wires(phase, (), "HT ramp wrapper")
    loop = unique(root, "whileLoop", "18613")
    require(
        [d.get("uid") for d in loop.findall("diagramList/*")] == ["42212"]
        and not loop.findall("termList/*")
        and not loop.findall("srDCOList/*")
        and not loop.findall("tunnelList/*"),
        "HT loop boundary changed",
    )
    body = unique(root, "diag", "42212")
    operations(
        body,
        [
            (None, "51420"),
            ("gRef", "206173"),
            ("label", "41331"),
            ("gRef", "42204"),
            ("select", "47558"),
            (None, "46097"),
            ("prim", "44754"),
            ("nMux", "41650"),
            ("gRef", "538"),
            (None, "42224"),
            (None, "42221"),
        ],
        "HT loop body",
    )
    false = unique(root, "diag", "47573")
    true = unique(root, "diag", "47580")
    operations(
        false,
        [
            ("label", "41430"),
            (None, "46134"),
            ("prim", "46117"),
            (None, "43717"),
            ("nMux", "42188"),
            ("gRef", "11041"),
            ("gRef", "9781"),
            (None, "53615"),
            ("prim", "583"),
        ],
        "HT decrement arm",
    )
    operations(true, [("label", "41493"), (None, "50686")], "HT exit arm")
    for frame in (body, false, true):
        exact_wires(frame, RAMP_NETS[frame.get("uid")], "HT ramp")
    selector = unique(root, "select", "47558")
    require(
        [d.get("uid") for d in selector.findall("diagramList/*")] == ["47573", "47580"]
        and [
            (d.findtext("start"), d.findtext("diagramIdx"))
            for d in selector.findall("SelectRangeArray32/*")
        ]
        == [("0", "0"), ("1", "1")],
        "HT Boolean arms changed",
    )
    require(
        tuple(
            (t.get("uid"), tuple(p.get("uid") for p in t.findall("dco/termList/*")))
            for t in selector.findall("termList/*")
        )
        == (
            ("47590", ("47588", "47589", "47590")),
            ("51598", ("51591", "51595", "51598")),
            ("52307", ("52299", "52303", "52307")),
        ),
        "HT selector tunnel aliases changed",
    )
    for port, tag, klass, flags in (
        ("42224", "loopTestDCO", "lTst", "65537"),
        ("42221", "loopIndexDCO", "lCnt", None),
    ):
        dco = body.find(f"nodeList/*/termList/*[@uid='{port}']/dco")
        saved = loop.find(tag)
        require(
            saved.get("class") == klass
            and dco.get("uid") == saved.get("uid")
            and (flags is None or saved.findtext("objFlags") == flags),
            "HT index or Stop-if-True changed",
        )
    for uid, ports, resource, kinds in (
        (
            "44754",
            ("44760", "44763", "44766"),
            "1111",
            ("Boolean", "NumFloat64", "NumFloat64"),
        ),
        ("583", ("40566", "40571", "40575"), "1051", ("NumFloat64",) * 3),
        ("46117", ("46123", "46126"), "1302", ("NumUInt32",) * 2),
    ):
        node = unique(root, "prim", uid)
        require(
            node.findtext("primResID") == resource
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports
            and tuple(
                _kind(metadata, t).get("Type") for t in node.findall("termList/*")
            )
            == kinds,
            "HT typed primitive changed",
        )
    for uid, port, index, write, label in (
        ("538", "11581", 12, False, "C9NI6703"),
        ("9781", "11005", 12, False, "C9NI6703"),
        ("11041", "12311", 12, True, "C9NI6703"),
        ("42204", "47551", 48, True, "Cmd alimentation HT:"),
        ("206173", "206183", 50, True, "ETAPES:"),
    ):
        local(root, uid, port, index, write)
        desc = _kind(metadata, unique(root, "gRef", uid).find("termList/*"))
        require(desc.get("Label") == label, "HT local label changed")
        if index == 12:
            flat = metadata.find("VCTP/Section").findall("TypeDesc")
            require(
                desc.get("Type") == "Cluster"
                and len(desc.findall("TypeDesc")) == 10
                and all(
                    flat[int(c.get("TypeID"))].get("Type") == "NumFloat64"
                    for c in desc.findall("TypeDesc")
                ),
                "C9 DBL bank changed",
            )
        else:
            require(desc.get("Type") == "NumFloat64", "HT scalar type changed")
    for uid, flags, ports in (
        ("41650", "327680", ("60956", "60959")),
        ("42188", "262144", ("42194", "42197", "42198")),
    ):
        mux = unique(root, "nMux", uid)
        require(
            mux.findtext("objFlags") == flags
            and tuple(t.get("uid") for t in mux.findall("termList/*")) == ports
            and int(mux.findall("termList/*")[-1].findtext("dco/i", "0")) == 0,
            "HT bundle/unbundle field changed",
        )
    for frame, port, raw, kind in (
        (body, "51420", "4018000000000000", "NumFloat64"),
        (body, "46097", "401A666666666666", "NumFloat64"),
        (false, "53615", "3FB999999999999A", "NumFloat64"),
        (false, "46134", "000001F4", "NumUInt32"),
        (false, "43717", "0000", "Boolean"),
        (true, "50686", "01", "Boolean"),
    ):
        term = frame.find(f"nodeList/*/termList/*[@uid='{port}']")
        require(
            constant(frame, port) == raw and _kind(metadata, term).get("Type") == kind,
            "HT typed literal changed",
        )
    return (("ht_ramp", "18613", "42212"),)


def decode_stop(root, metadata):
    names = call_names(metadata)
    sequence = unique(root, "sequence", "51954")
    require(
        not sequence.findall("termList/*") and not sequence.findall("tunnelList/*"),
        "outer stop sequence now has a boundary wire",
    )
    require(
        tuple(f.get("uid") for f in sequence.findall("diagramList/*"))
        == tuple(p[0] for p in CONTROLLED_STOP),
        "seven-phase ordering changed",
    )
    results = []
    for frame in sequence.findall("diagramList/*"):
        uid = frame.get("uid")
        if uid == "60323":
            effects = validate_ramp(root, metadata)
        elif uid in WRAPPERS:
            nested_uid, child_uids, label = WRAPPERS[uid]
            expected_ops = [("sequence", nested_uid), ("label", label)]
            expected_nets = ()
            scalar_effects = ()
            if uid == "51962":
                expected_ops.extend(((None, "47677"), ("gRef", "47687")))
                expected_nets = (("47677", "47690"),)
                local(root, "47687", "47690", 35, True)
                require(constant(frame, "47677") == "01", "stop ACTION changed")
                scalar_effects = (("write", 35, ((-1, True),)),)
            elif uid in ("1722", "52159"):
                literal, port = (
                    ("47276", "42403") if uid == "1722" else ("52924", "54281")
                )
                expected_ops.append((None, literal))
                expected_nets = ((literal, port),)
                require(constant(frame, literal) == "00000096", "stop duration changed")
            operations(frame, expected_ops, "controlled-stop wrapper")
            exact_wires(frame, expected_nets, "controlled-stop wrapper")
            nested = unique(root, "sequence", nested_uid)
            children = nested.findall("diagramList/*")
            require(
                tuple(c.get("uid") for c in children) == child_uids,
                "stop nested frame order changed",
            )
            externals = nested.findall("termList/*")
            internal = externals[0].findall("dco/termList/*") if externals else []
            if uid in ("1722", "52159"):
                require(
                    len(externals) == 1 and len(internal) == len(children) + 1,
                    "stop duration tunnel changed",
                )
            else:
                require(
                    not externals and not nested.findall("tunnelList/*"),
                    "unexpected stop sequence boundary wire",
                )
            decoded = []
            for i, child in enumerate(children):
                if child.get("uid") in ("47671", "47989"):
                    row = validate_counter_frame(
                        root, metadata, child, controlled_stop=True
                    )
                else:
                    row = decode_frame(
                        root,
                        metadata,
                        child,
                        internal[i].get("uid") if internal else None,
                        150 if internal else None,
                        names,
                        scalar_types=SCALARS,
                        dbl_values=(0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
                    )
                decoded.append((child.get("uid"), row))
            effects = tuple(
                sorted((*scalar_effects, ("subsequence", tuple(decoded))), key=repr)
            )
        else:
            effects = decode_frame(
                root, metadata, frame, None, None, names, scalar_types=SCALARS
            )
        results.append((uid, effects))
    return tuple(results)


def validate_stop(root, metadata):
    # Complete alias definitions/parent duration literals are an independent facet.
    from validate_acq_controlled_stop_wait_tunnels import validate_tree

    validate_tree(root)
    result = decode_stop(root, metadata)
    require(result == CONTROLLED_STOP, "independently reviewed outer stop plan differs")
    diagrams = unique(root, "sequence", "51954").findall(".//*[@class='diag']")
    return {
        "diagrams": len(diagrams),
        "nets": sum(len(d.findall("signalList/*")) for d in diagrams),
        "diagram_uids": tuple(d.get("uid") for d in diagrams),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    root, metadata = checked_vam(args.source_export_zip)
    proof = validate_stop(root, metadata)
    print(
        f"PASS: {proof['diagrams']} controlled-stop direct graphs; {proof['nets']} nets"
    )
    print("No hardware, sleep, PSP, VI execution or full Acquisition closure")


if __name__ == "__main__":
    main()
