"""Prove all setpoint copies into nested direct/deviated display clusters."""

import argparse
from pathlib import Path

from validate_acq_final_cleanup import exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations
from validate_acq_vam_status import checked_vam

NETS = (
    ("23950", "23990"),
    ("23947", "23987"),
    ("23944", "23984"),
    ("23941", "23981"),
    ("23938", "23978"),
    ("24014", "23975"),
    ("24011", "23972"),
    ("24008", "23969"),
    ("24005", "23966"),
    ("23962", "24021"),
    ("23997", "24002"),
    ("23957", "23965"),
    ("23929", "23935"),
    ("10643", "10598"),
    ("10552", "10595"),
    ("10549", "10592"),
    ("10546", "10589"),
    ("10543", "10586"),
    ("10628", "10583"),
    ("10625", "10580"),
    ("10622", "10577"),
    ("10619", "10574"),
    ("10616", "10571"),
    ("10613", "10568"),
    ("10564", "10650"),
    ("10635", "10640"),
    ("10605", "10610"),
    ("10559", "10567"),
    ("10535", "10540"),
)
LOCALS = (
    ("24018", "24021", 33, True),
    ("23994", "23997", 9, False),
    ("23954", "23957", 33, False),
    ("23926", "23929", 10, False),
    ("10647", "10650", 28, True),
    ("10632", "10635", 11, False),
    ("10602", "10605", 9, False),
    ("10556", "10559", 28, False),
    ("10532", "10535", 10, False),
)
MUXES = (
    ("24000", "327680", ("24002", "24005", "24008", "24011", "24014"), (0, 6, 7, 9, 8)),
    (
        "23933",
        "327680",
        ("23935", "23938", "23941", "23944", "23947", "23950"),
        (0, 9, 6, 7, 3, 4),
    ),
    ("10638", "327680", ("10640", "10643"), (0, 5)),
    (
        "10608",
        "327680",
        ("10610", "10613", "10616", "10619", "10622", "10625", "10628"),
        (0, 0, 1, 2, 3, 4, 5),
    ),
    ("10538", "327680", ("10540", "10543", "10546", "10549", "10552"), (0, 8, 5, 0, 1)),
    (
        "23960",
        "262144",
        (
            "23962",
            "23965",
            "23966",
            "23969",
            "23972",
            "23975",
            "23978",
            "23981",
            "23984",
            "23987",
            "23990",
        ),
        (0, 0, 54, 66, 102, 90, 78, 6, 18, 30, 42),
    ),
    (
        "10562",
        "262144",
        (
            "10564",
            "10567",
            "10568",
            "10571",
            "10574",
            "10577",
            "10580",
            "10583",
            "10586",
            "10589",
            "10592",
            "10595",
            "10598",
        ),
        (0, 0, 42, 54, 66, 78, 114, 126, 6, 18, 90, 102, 30),
    ),
)


def validate_display(root, meta):
    frame = unique(root, "diag", "10526")
    exact_wires(frame, NETS, "Timeout setpoint displays")
    operations(
        frame,
        [("gRef", uid) for uid, *_ in LOCALS] + [("nMux", uid) for uid, *_ in MUXES],
        "Timeout setpoint displays",
    )
    for args in LOCALS:
        local(root, *args)
    for uid, flags, ports, indices in MUXES:
        node = unique(root, "nMux", uid)
        terms = node.findall("termList/*")
        require(
            node.findtext("objFlags") == flags
            and tuple(t.get("uid") for t in terms) == ports
            and tuple(int(t.findtext("dco/i", "0")) for t in terms) == indices,
            "Timeout nested setpoint field/port mapping changed",
        )
        require(
            node.find("dcoAgg").get("uid") == terms[0].find("dco").get("uid")
            and tuple(t.get("uid") for t in node.findall("dcoList/*"))
            == tuple(
                t.find("dco").get("uid") for t in terms[1 if flags == "327680" else 2 :]
            ),
            "Timeout nested field DCO ordering changed",
        )
    # Bundle By Name indices count the nested cluster and each of its leaves.
    # Each device has one container plus eleven fields: stride12, Consigne index6.
    for uid, size in (("23954", 9), ("10556", 11)):
        desc = unique(root, "gRef", uid).findtext("termList/*/dco/typeDesc")
        aggregate, flat = heap_type(meta, int(desc[7:-1]))
        require(
            aggregate.get("Type") == "Cluster"
            and len(aggregate.findall("TypeDesc")) == size,
            "Timeout display top-level nested cluster count changed",
        )
        for child in aggregate.findall("TypeDesc"):
            cell = flat[int(child.get("TypeID"))]
            fields = [flat[int(t.get("TypeID"))] for t in cell.findall("TypeDesc")]
            require(
                cell.get("Type") == "Cluster"
                and len(fields) == 11
                and [f.get("Type") for f in fields]
                == ["Boolean"] * 5 + ["NumFloat64"] * 2 + ["Boolean"] * 4
                and fields[5].get("Label") == "Consigne",
                "Timeout device cell structure/Consigne field changed",
            )
    return (
        "PASS: Timeout setpoint display 1 diagram / 29 direct nets / "
        "20 nested Consigne copies"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_display(*checked_vam(args.root_archive)))


if __name__ == "__main__":
    main()
