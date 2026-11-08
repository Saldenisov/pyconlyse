"""Prove all runtime frame 2..5 direct DIO/AI-to-line field-copy wires."""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_final_cleanup import exact_wires
from validate_acq_modulator_start_event_guards import checked_root, require, unique
from validate_acq_ni6602_writer import operations

# Frame index, diagram, source mux/local, target mux/read local/write local,
# source fields, destination fields, aggregate/input/local port identities.
ROWS = (
    (
        2,
        "2010",
        "25618",
        "25612",
        "25539",
        "25533",
        "25606",
        (
            31,
            32,
            28,
            29,
            35,
            36,
            37,
            38,
            39,
            40,
            41,
            42,
            12,
            13,
            14,
            15,
            43,
            44,
            45,
            46,
        ),
        (
            2,
            4,
            14,
            16,
            38,
            40,
            50,
            52,
            62,
            64,
            74,
            76,
            86,
            88,
            98,
            100,
            110,
            112,
            122,
            124,
        ),
        ("25615", "25620", "25536", "25544", "25541", "25609"),
        18,
        28,
        "25684",
    ),
    (
        3,
        "8695",
        "21381",
        "21375",
        "21308",
        "21301",
        "21369",
        (24, 25, 26, 27, 20, 21, 47, 38, 39, 48, 33, 34, 51, 52, 53, 54, 18, 19),
        (2, 4, 14, 16, 38, 40, 50, 52, 62, 64, 74, 76, 86, 88, 98, 100, 26, 28),
        ("21378", "21383", "21304", "21313", "21310", "21372"),
        18,
        33,
        "21441",
    ),
    (
        4,
        "1283",
        "10713",
        "10707",
        "10752",
        "10792",
        "10798",
        (28, 20, 38, 29, 22, 30, 23, 16, 24, 31, 32),
        (7, 19, 31, 43, 55, 67, 79, 91, 103, 115, 127),
        ("10710", "10715", "10795", "10757", "10754", "10801"),
        19,
        28,
        None,
    ),
    (
        5,
        "18156",
        "24699",
        "24692",
        "24766",
        "24800",
        "24806",
        (19, 27, 25, 18, 40, 33, 21, 34, 34),
        (7, 19, 31, 43, 55, 67, 79, 91, 103),
        ("24695", "24701", "24803", "24771", "24768", "24809"),
        19,
        33,
        None,
    ),
)


def validate_tree(root):
    sequence = unique(root, "sequence", "1244")
    frames = sequence.findall("diagramList/*")
    require(
        [f.get("uid") for f in frames]
        == ["7386", "7392", "2010", "8695", "1283", "18156", "1619"],
        "runtime seven-frame sequence order changed",
    )
    for (
        index,
        diagram,
        source_mux_uid,
        source_local_uid,
        target_mux_uid,
        target_read_uid,
        target_write_uid,
        source_fields,
        target_fields,
        ports,
        source_index,
        target_index,
        label_uid,
    ) in ROWS:
        frame = frames[index]
        expected = [
            ("nMux", source_mux_uid),
            ("gRef", source_local_uid),
            ("nMux", target_mux_uid),
            ("gRef", target_read_uid),
            ("gRef", target_write_uid),
        ]
        if label_uid:
            expected.append(("label", label_uid))
        operations(frame, expected, "runtime line readback " + diagram)
        source_mux = unique(root, "nMux", source_mux_uid)
        target_mux = unique(root, "nMux", target_mux_uid)
        source_terms = source_mux.findall("termList/*")
        target_terms = target_mux.findall("termList/*")
        require(
            len(source_terms) == len(source_fields) + 1
            and len(target_terms) == len(target_fields) + 2
            and tuple(int(t.findtext("dco/i", "0")) for t in source_terms[1:])
            == source_fields
            and tuple(int(t.findtext("dco/i", "0")) for t in target_terms[2:])
            == target_fields,
            "runtime line readback field identity/order changed",
        )
        require(
            source_terms[0].findtext("dco/objFlags", "0") == "0"
            and all(t.findtext("dco/objFlags") == "1" for t in source_terms[1:])
            and target_terms[0].findtext("dco/objFlags") == "1"
            and all(t.findtext("dco/objFlags", "0") == "0" for t in target_terms[1:]),
            "runtime line readback bundle/unbundle direction changed",
        )
        for uid, local_index, is_write, port in (
            (source_local_uid, source_index, False, ports[0]),
            (target_read_uid, target_index, False, ports[2]),
            (target_write_uid, target_index, True, ports[5]),
        ):
            alias = unique(root, "gRef", uid)
            require(
                alias.findtext("termList/*/dco/paramIdx") == str(local_index)
                and alias.find("termList/*").get("uid") == port
                and alias.findtext("termList/*/dco/objFlags", "0")
                == ("0" if is_write else "1"),
                "runtime line readback local identity/direction changed",
            )
        require(
            (
                source_terms[0].get("uid"),
                target_terms[1].get("uid"),
                target_terms[0].get("uid"),
            )
            == (ports[1], ports[3], ports[4]),
            "runtime line readback aggregate identities changed",
        )
        nets = [tuple(ports[i : i + 2]) for i in (0, 2, 4)]
        nets.extend(
            (src.get("uid"), dst.get("uid"))
            for src, dst in zip(source_terms[1:], target_terms[2:])
        )
        exact_wires(frame, nets, "runtime line readback " + diagram)
    return (
        "Runtime frames 2/3: 20/18 C3 DI fields -> direct/deviated line state; "
        "frames 4/5: 11/9 C1 AI fields -> line readback. "
        "Deviated targets 91 and 103 BOTH use C1[34]; no inversion or gate. "
        "Separate local read-modify-write frames, not an atomic cycle."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_tree(checked_root(args.root_archive)))


if __name__ == "__main__":
    main()
