"""Check outer Driver Core retry predicate and status-field replacement only.

Inner protocol flags and suppress-warning behavior remain external facets.
"""

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import operations
from validate_acq_tpg300_startup import checked_roots, saved_bytes

NETS = {
    "135": (
        ("2341", "2293"),
        ("5209", "2345"),
        ("2191", "4372"),
        ("2436", "2334"),
        ("5725", "5949"),
        ("151", "970"),
        ("146", "225"),
    ),
    "191": (
        ("5235", "5205"),
        ("4368", "4398"),
        ("2463", "2431"),
        ("5945", "5975"),
        ("969", "972"),
        ("953", "200"),
        ("930", "959"),
        ("938", "956"),
        ("197", "941", "1649"),
        ("142", "944"),
        ("224", "220"),
    ),
    "155": (
        ("986", "928", "2473"),
        ("2469", "5231"),
        ("1547", "980"),
        ("2405", "2472"),
        ("5971", "2459"),
        ("1526", "983"),
        ("933", "158"),
    ),
}
OPS = {
    "135": (
        ("iUse", "2324"),
        (None, "2293"),
        (None, "2191"),
        (None, "2334"),
        (None, "5725"),
        ("whileLoop", "2067"),
        (None, "151"),
        (None, "146"),
    ),
    "191": (
        (None, "1649"),
        ("prim", "951"),
        ("prim", "936"),
        (None, "142"),
        ("sequence", "183"),
        (None, "200"),
        (None, "197"),
    ),
    "155": (("nMux", "798"), ("cpdArith", "976"), (None, "158")),
}


def validate_core(roots):
    bd, fp, meta = (roots[n] for n in ("vi_BDHb.xml", "vi_FPHb.xml", "vi.xml"))
    for uid in NETS:
        frame = unique(bd, "diag", uid)
        exact_wires(frame, NETS[uid], "TPG outer retry frame " + uid)
        operations(frame, OPS[uid], "TPG outer retry frame " + uid)
    loop = unique(bd, "whileLoop", "2067")
    require(
        loop.findtext("loopTestDCO/objFlags") == "1"
        and loop.find("loopTestDCO/termList/*").get("uid") == "200"
        and loop.find("loopIndexDCO/termList/*").get("uid") == "197"
        and len(loop.find("srDCOList")) == 0,
        "TPG retry continue/index/no-feedback-register changed",
    )
    require(
        unique(bd, "fPTerm", "142").find("dco").get("uid") == "39"
        and saved_bytes(fp, "39") == bytes.fromhex("00000003"),
        "TPG Retry control/default changed",
    )
    primitive(bd, "936", 1110, ("938", "941", "944"))
    primitive(bd, "951", 1061, ("953", "956", "959"))
    sequence = unique(bd, "sequence", "183")
    require(
        tuple(d.get("uid") for d in sequence.findall("diagramList/*"))
        == ("184", "229", "987", "155"),
        "Driver Core phase order changed",
    )
    for uid, children in (
        ("930", ("926", "927", "992", "928", "930")),
        ("5235", ("5219", "5223", "5227", "5231", "5235")),
    ):
        dco = sequence.find(f"termList/*[@uid='{uid}']/dco")
        require(
            dco.get("class") == "seqTun"
            and tuple(t.get("uid") for t in dco.findall("termList/*")) == children,
            "Driver Core final Boolean/error tunnel changed",
        )
    for uid, children in (
        ("1521", ("1522", "1523", "1525", "1526")),
        ("1542", ("1544", "1545", "1546", "1547")),
        ("688", ("2402", "2403", "2404", "2405")),
    ):
        node = unique(bd, "sLoc", uid)
        require(
            node.findtext("diagDefined") == "02"
            and tuple(t.get("uid") for t in node.findall("termList/*")) == children,
            "Driver Core phase-two local/error provenance changed",
        )
    compound = unique(bd, "cpdArith", "976")
    require(
        compound.findtext("objFlags") == "720896"
        and tuple(t.get("uid") for t in compound.findall("termList/*"))
        == ("986", "980", "983")
        and [t.findtext("dco/objFlags") for t in compound.findall("termList/*")]
        == ["131073", "262144", "262144"],
        "Driver Core non-inverted OR changed",
    )
    bundle = unique(bd, "nMux", "798")
    require(
        bundle.findtext("objFlags") == "262144"
        and tuple(t.get("uid") for t in bundle.findall("termList/*"))
        == ("2469", "2472", "2473")
        and bundle.findtext("termList/*[@uid='2473']/dco/i", "0") == "0"
        and bundle.findtext("termList/*[@uid='2473']/dco/objFlags", "0") == "0",
        "Driver Core bundle replacement of error.status changed",
    )
    descriptor, flat = heap_type(meta, 368)
    require(
        descriptor.get("Type") == "Cluster"
        and [
            flat[int(t.get("TypeID"))].get("Type")
            for t in descriptor.findall("TypeDesc")
        ]
        == ["Boolean", "NumInt32", "String"],
        "Driver Core error field order changed",
    )
    require(
        call_names(meta).get("2324") == "TPG300 suppress warning.vi",
        "Driver Core returned-error consumer changed",
    )
    return (
        "Driver Core outer retry: three diagram facets, 25 nets; "
        "Retry=3 permits four attempts if phases return"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(
        validate_core(checked_roots(parser.parse_args().archive)["TPG300-Driver Core"])
    )


if __name__ == "__main__":
    main()
