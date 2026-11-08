"""Check all52 frame0 direct graphs; retain explicit native/default boundaries.

Reads only the pinned saved root XML. Constants, scalar operations, nested
selector ranges/defaults, all direct wire fanouts and UI property connectors
are checked separately from the inert Python model. This is a source-graph
facet, not a claim that native property failures or concurrency are modeled.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from validate_acq_beamline_commands import td
from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import require
from validate_acq_modulator_start_event_guards import unique as xml_unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import operations
from validate_acq_vam_status import checked_vam

# Outer numeric arm -> (outer diagram, inner selector, inner diagrams).
BRANCHES = {
    1: (
        ("11802", "11808", ("11844", "11970", "12096", "12222", "12348")),
        ("12386", "12392", ("12428", "12554", "12680", "12806", "12932")),
        ("12970", "12976", ("13016", "13142", "13275", "13402", "13528")),
        ("13566", "13572", ("13608", "13734", "13860", "13986", "14112")),
    ),
    2: (
        ("63284", "63290", ("63318", "63444", "63570")),
        ("63608", "63614", ("63642", "63768", "63894")),
        ("63932", "63938", ("63966", "64092", "64218")),
        ("64256", "64262", ("64290", "64416", "64542")),
    ),
}
TOP = {
    1: {
        "frame": "11087",
        "case": "11557",
        "pass": ("11721", "11748", "11775"),
        "old": "11081",
        "new": "11074",
        "ref": ("11394", "11397", "1660"),
        "compare": "11244",
        "array": "11255",
        "size": "11347",
        "max": "11355",
        "loop": "11263",
        "loop_body": "11283",
        "mask": "11292",
        "loop_prims": ("11312", "11304", "11320"),
        "cast": "11400",
        "cast_literal": "11216",
        "index": "11417",
        "properties": ("11372", "11451", "11429"),
        "variant": "45758",
        "zero_cell": "11095",
        "unbundle": "11490",
        "bundle": "11517",
        "ge": "14212",
        "threshold": "11227",
        "gate": "11239",
        "flat": "14226",
        "wait_frame": "14167",
        "wait": ("14195", "14173", "14185"),
        "labels": ("14223", "14224", "14225"),
    },
    2: {
        "frame": "19057",
        "case": "63039",
        "pass": ("63203", "63230", "63257"),
        "old": "19052",
        "new": "19046",
        "ref": ("62876", "62879", "16917"),
        "compare": "62726",
        "array": "62737",
        "size": "62829",
        "max": "62837",
        "loop": "62745",
        "loop_body": "62765",
        "mask": "62774",
        "loop_prims": ("62794", "62786", "62802"),
        "cast": "62882",
        "cast_literal": "19167",
        "index": "62899",
        "properties": ("62854", "62933", "62911"),
        "variant": "45878",
        "zero_cell": "19063",
        "unbundle": "62972",
        "bundle": "62999",
        "ge": "64642",
        "threshold": "19178",
        "gate": "19190",
        "flat": "64658",
        "wait_frame": "64597",
        "wait": ("64625", "64603", "64615"),
        "labels": ("64653", "64654", "64655", "64656", "64657"),
    },
}
BUTTONS = (128, 256, 512, 1024)
DIRECT_RANGES = (
    (0, 0, 2, 0),
    (1, 1, 0, 0),
    (2, 2, 1, 0),
    (3, 6, 3, 1),
    (7, 8, 2, 1),
    (9, 10, 3, 1),
    (11, 11, 4, 0),
)
DEVIATED_RANGES = (
    (0, 3, 0, 1),
    (4, 5, 1, 1),
    (6, 6, 0, 0),
    (7, 8, 1, 1),
    (11, 11, 2, 0),
)
DIRECT_INDEX_GROUPS = ((1,), (2,), (0, 7, 8), (3, 4, 5, 6, 9, 10))
DEVIATED_INDEX_GROUPS = ((0, 1, 2, 3, 6), (4, 5, 7, 8))


class _HeapIndex:
    """Per-validation index; duplicate definitions still fail closed.

    Rebuilt for every call, including every mutated test root. No shared
    index survives between proofs or hides changed heap definitions.
    """

    def __init__(self, root):
        self.nodes = {}
        for node in root.iter():
            if node.get("class") is not None and node.get("uid") is not None:
                self.nodes.setdefault((node.get("class"), node.get("uid")), []).append(
                    node
                )


def unique(root, klass, uid):
    if not isinstance(root, _HeapIndex):
        return xml_unique(root, klass, uid)
    matches = root.nodes.get((klass, uid), ())
    require(len(matches) == 1, f"expected one {klass} UID {uid}, got {len(matches)}")
    return matches[0]


def terms(node):
    return node.findall("termList/*")


def ports(node):
    return tuple(t.get("uid") for t in terms(node))


def kinds(meta, node):
    return tuple(td(meta, t).get("Type") for t in terms(node))


def primitive(
    root, meta, uid, resource, types, flags=None, slots=None, directions=None
):
    node = unique(root, "prim", uid)
    require(
        node.findtext("primResID") == str(resource)
        and kinds(meta, node) == types
        and (flags is None or node.findtext("objFlags") == str(flags))
        and (
            slots is None
            or tuple(int(t.findtext("dco/parmIndex", "0")) for t in terms(node))
            == slots
        )
        and (
            directions is None
            or tuple(int(t.findtext("dco/objFlags", "0")) for t in terms(node))
            == directions
        ),
        f"primitive {uid} identity/type/slots/direction changed",
    )
    return ports(node)


def aliases(term, count):
    values = tuple(t.get("uid") for t in term.findall("dco/termList/*"))
    require(
        len(values) == count + 1 and values[-1] == term.get("uid"),
        "case/sequence tunnel alias count/order changed",
    )
    return values[:-1]


def selector(root, meta, uid, frames, ranges, default, field_kinds):
    node = unique(root, "select", uid)
    ts = terms(node)
    require(
        tuple(d.get("uid") for d in node.findall("diagramList/*")) == frames
        and node.findtext("SelectDefaultCase") == default
        and node.findtext("SelectNRightType") == str(len(ranges))
        and node.findtext("SelectSelLabFlags") == "10DC"
        and len(node.find("SelectStringArray")) == 0
        and kinds(meta, node) == field_kinds
        and tuple(
            tuple(
                int(x.findtext(k, "0"))
                for k in (
                    "start",
                    "end",
                    "diagramIdx",
                    "startRangeType",
                    "endRangeType",
                )
            )
            for x in node.findall("SelectRangeArray32/*")
        )
        == tuple((a, b, frame, kind, kind) for a, b, frame, kind in ranges)
        and ts[0].find("dco").get("class") == "caseSel"
        and node.find("caseSelDCO").get("uid") == ts[0].find("dco").get("uid")
        and tuple(t.get("uid") for t in node.findall("tunnelList/*"))
        == tuple(t.find("dco").get("uid") for t in ts[1:]),
        f"selector {uid} ranges/default/type/tunnel population changed",
    )
    for t in ts[1:]:
        require(t.find("dco").get("class") == "selTun", "non-case tunnel")
    return ts, [aliases(t, len(frames)) for t in ts]


def scalar_constant(frame, meta, uid):
    term = frame.find(f"nodeList/*/termList/*[@uid='{uid}']")
    require(
        term is not None and td(meta, term).get("Type") == "NumFloat64",
        "step/bound must be DBL",
    )
    raw = bytes.fromhex(constant(frame, uid))
    # Exporter includes one padding byte for the all-zero DBL literal.
    require(len(raw) == 8 or raw == bytes(9), "DBL constant encoding changed")
    return struct.unpack(">d", raw[:8])[0]


def validate_leaf(root, meta, uid, incoming, sign):
    frame = unique(root, "diag", uid)
    ps = [p for p in frame.findall("zPlaneList/*") if p.get("class") == "prim"]
    ids = {p.findtext("primResID"): p.get("uid") for p in ps}
    require(
        len(ps) == 3 and set(ids) == {"1516", str(sign), "1127"},
        "leaf must contain Select, arithmetic, In Range and Coerce",
    )
    select = primitive(
        root,
        meta,
        ids["1516"],
        1516,
        ("NumFloat64", "NumFloat64", "Boolean", "NumFloat64"),
        slots=(0, 1, 2, 3),
        directions=(1, 0, 0, 0),
    )
    arith = primitive(
        root,
        meta,
        ids[str(sign)],
        sign,
        ("NumFloat64",) * 3,
        slots=(0, 1, 2),
        directions=(1, 0, 65536),
    )
    coerce = primitive(
        root,
        meta,
        ids["1127"],
        1127,
        ("Boolean",) + ("NumFloat64",) * 4,
        slots=(0, 1, 2, 3, 4),
        directions=(1, 1, 0, 65536, 0),
    )
    require(
        unique(root, "prim", ids["1127"]).findtext("objFlags")
        in ("2097152", "2101248"),
        "coercion endpoint flags changed",
    )
    literals = [
        p.get("uid") for p in frame.findall("zPlaneList/*") if p.get("class") is None
    ]
    labels = [
        p.get("uid") for p in frame.findall("zPlaneList/*") if p.get("class") == "label"
    ]
    require(
        len(literals) == 4 and len(labels) == 3,
        "leaf constant/label population changed",
    )
    operations(
        frame,
        [("prim", p.get("uid")) for p in ps]
        + [(None, p) for p in literals]
        + [("label", p) for p in labels],
        "numeric leaf",
    )
    nets = [
        tuple(t.get("uid") for t in n.findall("termList/*"))
        for n in frame.findall("signalList/*")
    ]

    def source(destination):
        found = [
            lit
            for lit in literals
            if frozenset((lit, destination)) in {frozenset(n) for n in nets}
        ]
        require(len(found) == 1, "numeric constant wiring changed")
        return found[0]

    small, large, lower, upper = (
        source(p) for p in (select[1], select[3], coerce[2], coerce[4])
    )
    require(len({small, large, lower, upper}) == 4, "aliased step/bound constants")
    x1, consigne, output = incoming
    exact_wires(
        frame,
        (
            (small, select[1]),
            (large, select[3]),
            (x1, select[2]),
            (select[0], arith[1]),
            (consigne, arith[2]),
            (arith[0], coerce[3]),
            (lower, coerce[2]),
            (upper, coerce[4]),
            (coerce[1], output),
        ),
        "numeric leaf",
    )
    return tuple(
        scalar_constant(frame, meta, p) for p in (small, large, lower, upper)
    ), ids


def cell_schema(meta, term, count=None, boolean=False):
    desc, flat = heap_type(meta, int(term.findtext("dco/typeDesc")[7:-1]))
    require(desc.get("Type") == "Cluster", "device schema is not Cluster")
    cells = (
        [desc]
        if count is None
        else [flat[int(f.get("TypeID"))] for f in desc.findall("TypeDesc")]
    )
    if count is not None:
        require(len(cells) == count, "line device count changed")
    for cell in cells:
        children = [flat[int(f.get("TypeID"))] for f in cell.findall("TypeDesc")]
        require(
            cell.get("Type") == "Cluster"
            and len(children) == 11
            and tuple(c.get("Type") for c in children)
            == (
                ("Boolean",) * 11
                if boolean
                else ("Boolean",) * 5 + ("NumFloat64",) * 2 + ("Boolean",) * 4
            ),
            "eleven-field device schema changed",
        )
        if not boolean:
            require(
                tuple(children[i].get("Label") for i in (0, 4, 5, 6, 7, 8, 9, 10))
                == ("M/A", "X1/X10", "Consigne", "Lecture", "<<", "<", ">", ">>"),
                "device field labels/order changed",
            )


def validate_adjustment(root, meta):
    root = _HeapIndex(root)
    accepted, rules, fragments = set(), {}, []

    def prove(uid, ops, nets):
        frame = unique(root, "diag", uid)
        operations(frame, ops, uid)
        exact_wires(frame, nets, uid)
        require(uid not in accepted, "diagram checked twice")
        accepted.add(uid)

    for event, top in TOP.items():
        frames = (*top["pass"], *(r[0] for r in BRANCHES[event]))
        ct, ca = selector(
            root,
            meta,
            top["case"],
            frames,
            tuple((v, v, i, 0) for i, v in enumerate((0, 1, 16, *BUTTONS))),
            None,
            ("NumUInt32", "NumFloat64")
            + ("Boolean",) * 5
            + ("NumFloat64",) * 2
            + ("Boolean",) * 5
            + ("NumFloat64", "NumInt32"),
        )
        require(
            tuple(int(t.findtext("dco/objFlags", "0")) for t in ct[1:])
            == (2048,) * 7 + (2049,) * 7 + (2048,),
            "outer case tunnel direction changed",
        )
        for i, uid in enumerate(top["pass"]):
            prove(uid, [], tuple((ca[k][i], ca[15 - k][i]) for k in range(1, 8)))
        index_groups = DIRECT_INDEX_GROUPS if event == 1 else DEVIATED_INDEX_GROUPS
        for button, (uid, nested, leaves) in zip(BUTTONS, BRANCHES[event]):
            i = BUTTONS.index(button) + 3
            nt, na = selector(
                root,
                meta,
                nested,
                leaves,
                DIRECT_RANGES if event == 1 else DEVIATED_RANGES,
                "04" if event == 1 else "02",
                ("NumInt32", "Boolean", "NumFloat64", "NumFloat64"),
            )
            require(
                tuple(int(t.findtext("dco/objFlags", "0")) for t in nt[1:])
                == (2048, 2048, 2049),
                "nested case tunnel direction changed",
            )
            labels = [
                p.get("uid")
                for p in unique(root, "diag", uid).findall("zPlaneList/*")
                if p.get("class") == "label"
            ]
            require(len(labels) == 1, "button frame label population changed")
            prove(
                uid,
                [("select", nested), ("label", labels[0])],
                (
                    (ca[15][i], nt[0].get("uid")),
                    (ca[1][i], nt[2].get("uid")),
                    (ca[3][i], ca[12][i], nt[1].get("uid")),
                    (nt[3].get("uid"), ca[14][i]),
                )
                + tuple((ca[k][i], ca[15 - k][i]) for k in (2, 4, 5, 6, 7)),
            )
            for j, leaf in enumerate(leaves[:-1]):
                params, primitive_ids = validate_leaf(
                    root,
                    meta,
                    leaf,
                    (na[1][j], na[2][j], na[3][j]),
                    1051 if button in (128, 256) else 1050,
                )
                accepted.add(leaf)
                for index in index_groups[j]:
                    rules[event, index, button] = params
                fragments.append(
                    (event, button, index_groups[j][0], leaf, primitive_ids)
                )
            j = len(leaves) - 1
            prove(leaves[-1], [], ((na[2][j], na[3][j]),))
        validate_pipeline(root, meta, top, event, ct, prove)
    require(len(accepted) == 52, "frame0 diagram population changed")
    actual = {
        d.get("uid")
        for t in TOP.values()
        for d in unique(root, "diag", t["frame"]).iter()
        if d.get("class") == "diag"
    }
    require(actual == accepted, "unexamined frame0 descendants remain")
    net_count = sum(
        len(unique(root, "diag", uid).findall("signalList/*")) for uid in accepted
    )
    require(net_count == 424, "frame0 direct wire count changed")
    return {
        "diagram_uids": tuple(sorted(accepted, key=int)),
        "direct_nets": net_count,
        "rules": rules,
        "fragments": tuple(fragments),
        "outer_default_independently_verified": False,
    }


def validate_pipeline(root, meta, top, event, ct, prove):
    """Root graph, masked-difference For body, UI connectors and70ms flat frame."""
    compare = primitive(
        root,
        meta,
        top["compare"],
        1105,
        ("Cluster",) * 3,
        flags=65536,
        slots=(0, 1, 2),
        directions=(1, 0, 0),
    )
    node = unique(root, "prim", top["compare"])
    cell_schema(meta, terms(node)[0], 11 if event == 1 else 9, boolean=True)
    for t in terms(node)[1:]:
        cell_schema(meta, t, 11 if event == 1 else 9)
    array = primitive(
        root, meta, top["array"], 1169, ("SubArray", "Cluster"), flags=16777216
    )
    size = primitive(root, meta, top["size"], 1809, ("NumInt32", "SubArray"))
    maximum = primitive(
        root,
        meta,
        top["max"],
        1907,
        ("Array", "NumUInt32", "NumInt32", "NumUInt32", "NumInt32"),
        slots=(0, 1, 2, 3, 4),
        directions=(0, 1, 1, 1, 1),
    )
    ge = primitive(
        root, meta, top["ge"], 1103, ("Boolean", "NumUInt32", "NumUInt32"), flags=65536
    )
    frame = unique(root, "diag", top["frame"])
    require(
        constant(frame, top["threshold"]) == "00000080"
        and constant(frame, top["cast_literal"]) == "0000000000"
        and constant(frame, top["zero_cell"]) == "00" * 26,
        "frame0 threshold/ref/default-cell literals changed",
    )
    loop = unique(root, "forLoop", top["loop"])
    lt = terms(loop)
    require(
        len(lt) == 3
        and kinds(meta, loop) == ("NumInt32", "SubArray", "Array")
        and tuple(d.get("uid") for d in loop.findall("diagramList/*"))
        == (top["loop_body"],)
        and len(loop.find("srDCOList")) == len(loop.find("ConditionDCOList")) == 0
        and tuple(t.findtext("dco/TunnelType") for t in lt[1:]) == ("01", "01")
        and tuple(t.findtext("dco/objFlags") for t in lt[1:]) == ("16779264", "2049"),
        "difference For indexing/state/control changed",
    )
    la = [aliases(t, 1)[0] for t in lt[1:]]
    cl, num, mask = top["loop_prims"]
    cp = primitive(root, meta, cl, 1169, ("SubArray", "Cluster"))
    np = primitive(root, meta, num, 1815, ("NumUInt32", "SubArray"))
    mp = primitive(root, meta, mask, 1061, ("NumUInt32",) * 3)
    body = unique(root, "diag", top["loop_body"])
    require(constant(body, top["mask"]) == "00000791", "change mask no longer0x791")
    loop_index = loop.find("loopIndexDCO/termList/*").get("uid")
    prove(
        top["loop_body"],
        [
            (None, top["mask"]),
            (None, loop_index),
            ("prim", cl),
            ("prim", num),
            ("prim", mask),
        ],
        (
            (la[0], cp[1]),
            (cp[0], np[1]),
            (np[0], mp[2]),
            (top["mask"], mp[1]),
            (mp[0], la[1]),
        ),
    )
    cast = primitive(
        root,
        meta,
        top["cast"],
        8016,
        ("Refnum", "Cluster", "Refnum", "Refnum", "Cluster"),
    )
    ref = unique(root, "ctlRefConst", top["ref"][0])
    require(
        ports(ref) == (top["ref"][1],) and ref.find("ddo").get("uid") == top["ref"][2],
        "line control reference identity changed",
    )
    props = []
    for pos, uid in enumerate(top["properties"]):
        node = unique(root, "propNode", uid)
        ts = terms(node)
        require(
            len(ts) == 5
            and tuple(t.findtext("dco/objFlags", "0") for t in ts)
            == ("65536", "262145", "131072", "524289", "0" if pos == 2 else "1")
            and node.findtext("oMId") == ("09A5" if pos == 0 else "09A7")
            and ts[4].findtext("dco/propList/*/PropItemName")
            == ('"Controls[]"' if pos == 0 else '"Value"')
            and ts[4].findtext("dco/propList/*/PropItemCode")
            == ("104102914" if pos == 0 else "104013837"),
            "Controls[]/Value read-write property identity changed",
        )
        props.append(ports(node))
    index = unique(root, "aIndx", top["index"])
    require(
        kinds(meta, index) == ("Array", "Refnum", "NumInt32")
        and index.findtext("objFlags") == "524288",
        "Controls[] Index Array changed",
    )
    ip = ports(index)
    variant = primitive(
        root,
        meta,
        top["variant"],
        8003,
        ("Cluster", "Cluster", "LVVariant", "Cluster", "Cluster"),
        slots=(0, 3, 8, 9, 11),
        directions=(65536, 1, 65536, 0, 1),
    )
    cell_schema(meta, terms(unique(root, "prim", top["variant"]))[-1])
    un = unique(root, "nMux", top["unbundle"])
    bu = unique(root, "nMux", top["bundle"])
    ut, bt = terms(un), terms(bu)
    require(
        un.findtext("objFlags") == "327680"
        and len(ut) == 8
        and tuple(int(t.findtext("dco/i", "0")) for t in ut[1:])
        == (6, 1, 2, 3, 4, 0, 5)
        and all(t.findtext("dco/objFlags") == "1" for t in ut[1:])
        and bu.findtext("objFlags") == "262144"
        and len(bt) == 13
        and tuple(int(t.findtext("dco/i", "0")) for t in bt[2:])
        == (6, 1, 2, 3, 4, 0, 5, 7, 8, 9, 10)
        and all(t.findtext("dco/objFlags", "0") == "0" for t in bt[2:]),
        "selected-cell Bundle/Unbundle fields/direction changed",
    )
    cell_schema(meta, ut[0])
    cell_schema(meta, bt[0])
    for node, ts, first in ((un, ut, 1), (bu, bt, 2)):
        require(
            node.find("dcoAgg").get("uid") == ts[0].find("dco").get("uid")
            and tuple(t.get("uid") for t in node.findall("dcoList/*"))
            == tuple(t.find("dco").get("uid") for t in ts[first:]),
            "Bundle/Unbundle DCO aggregate/list order changed",
        )
    require(
        bt[0].findtext("dco/objFlags") == "1"
        and bt[1].find("dco").get("uid") == bt[0].find("dco").get("uid")
        and tuple(t.get("uid") for t in bt[0].findall("dco/termList/*"))
        == (bt[0].get("uid"), bt[1].get("uid")),
        "selected-cell Bundle aggregate alias/direction changed",
    )
    require(
        kinds(meta, un)[1:] == ("NumFloat64",) + ("Boolean",) * 5 + ("NumFloat64",)
        and tuple(td(meta, t).get("Type") for t in bt[2:])
        == ("NumFloat64",) + ("Boolean",) * 5 + ("NumFloat64",) + ("Boolean",) * 4,
        "selected-cell Bundle/Unbundle leaf types changed",
    )
    flat = unique(root, "flatSequence", top["flat"])
    seqs = flat.findall("sequenceList/*")
    require(
        len(seqs) == 1
        and tuple(d.get("uid") for d in seqs[0].findall("diagramList/*"))
        == (top["wait_frame"],),
        "70ms flat sequence order changed",
    )
    ft = terms(seqs[0])
    require(
        kinds(meta, seqs[0]) == ("NumFloat64", "NumFloat64", "Boolean")
        and tuple(t.findtext("dco/objFlags") for t in ft) == ("2048", "2049", "2049"),
        "70ms sequence tunnel types/direction changed",
    )
    fa = [aliases(t, 1)[0] for t in ft]
    wait, delay, false = top["wait"]
    wp = primitive(root, meta, wait, 1302, ("NumUInt32", "NumUInt32"))
    wait_frame = unique(root, "diag", top["wait_frame"])
    require(
        constant(wait_frame, delay) == "00000046"
        and constant(wait_frame, false) == "0000",
        "70ms wait/button reset changed",
    )
    prove(
        top["wait_frame"],
        [("prim", wait), (None, delay), (None, false)],
        ((delay, wp[1]), (false, fa[2]), (fa[0], fa[1])),
    )
    p = [t.get("uid") for t in ct]
    up, bp, fp = ports(un), ports(bu), tuple(t.get("uid") for t in ft)
    ops = [
        ("prim", top[k])
        for k in ("compare", "array", "size", "max", "cast", "variant", "ge")
    ]
    ops += [("label", uid) for uid in top["labels"]]
    ops += [(None, top[k]) for k in ("threshold", "cast_literal", "zero_cell")]
    ops += [("propNode", uid) for uid in top["properties"]]
    ops += [
        ("forLoop", top["loop"]),
        ("flatSequence", top["flat"]),
        ("select", top["case"]),
        ("ctlRefConst", top["ref"][0]),
        ("aIndx", top["index"]),
        ("nMux", top["unbundle"]),
        ("nMux", top["bundle"]),
    ]
    nets = [
        (top["new"], compare[1]),
        (top["old"], compare[2]),
        (compare[0], array[1]),
        (array[0], lt[1].get("uid"), size[1]),
        (size[0], lt[0].get("uid")),
        (lt[2].get("uid"), maximum[0]),
        (maximum[1], p[0], ge[2]),
        (maximum[2], ip[2], p[15]),
        (top["threshold"], ge[1]),
        (ge[0], top["gate"]),
        (top["ref"][1], cast[3]),
        (top["cast_literal"], cast[2]),
        (cast[0], props[0][0]),
        (props[0][4], ip[0]),
        (ip[1], props[1][0], props[2][0]),
        (props[1][4], variant[2]),
        (top["zero_cell"], variant[3], bp[1]),
        (variant[4], up[0]),
        (bp[0], props[2][4]),
        (p[14], fp[0]),
        (fp[1], bp[8]),
        (fp[2], *bp[9:]),
    ]
    # Seven retained fields arrive in reverse case input order.
    nets += [(up[i], p[8 - i]) for i in range(1, 8)]
    nets += [(p[i], bp[i - 6]) for i in range(8, 14)]
    prove(top["frame"], ops, nets)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    result = validate_adjustment(*checked_vam(parser.parse_args().root_archive))
    print(
        f"PASS: {len(result['diagram_uids'])} frame0 diagrams / "
        f"{result['direct_nets']} nets / 24 scalar chains"
    )
    print("Outer native default and property/cast failure returns remain bounded.")
