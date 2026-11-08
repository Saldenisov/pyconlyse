"""Prove runtime publication, disabled comparison and I/O-loop control wires."""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import checked_root, require, unique
from validate_acq_ni6602_writer import primitive

# Node, local node/index/port, URI constant port/name; writer ports are in
# saved order: URL, URL out, error in, error out, data.
PUBLICATIONS = (
    (
        "2182",
        "24753",
        19,
        "24756",
        "24705",
        "C1NI6071E",
        ("2325", "2342", "2351", "2368", "2377"),
    ),
    (
        "7854",
        "24821",
        20,
        "24824",
        "24723",
        "C2NI6071E",
        ("7862", "7865", "7868", "7871", "7874"),
    ),
    (
        "18665",
        "18634",
        44,
        "18639",
        "18802",
        "EPS",
        ("18667", "18671", "18674", "18677", "18680"),
    ),
    (
        "18683",
        "18645",
        38,
        "18648",
        "18760",
        "EPC",
        ("18685", "18688", "18691", "18694", "18697"),
    ),
    (
        "18703",
        "18657",
        2,
        "18660",
        "18736",
        "VTA",
        ("18710", "18716", "18723", "18727", "18731"),
    ),
    (
        "2052",
        "24985",
        18,
        "24988",
        "24931",
        "C3_IN_DIO96",
        ("2229", "2237", "2321", "2446", "2492"),
    ),
    (
        "4245",
        "25024",
        16,
        "25027",
        "24949",
        "C4_IN_DIO96",
        ("4257", "4261", "4265", "4268", "4271"),
    ),
    (
        "7486",
        "25063",
        14,
        "25066",
        "24967",
        "C5_IN_DIO96",
        ("7502", "7505", "7508", "7511", "7514"),
    ),
)
URI_PREFIX = "ni.var.psp://10.20.30.2/SUPERVISION/"


def operations(frame, expected, label):
    actual = [(n.get("class"), n.get("uid")) for n in frame.findall("zPlaneList/*")]
    require(
        len(actual) == len(expected) and set(actual) == set(expected),
        label + " operations changed",
    )


def case(root, uid, false_uid, true_uid):
    selector = unique(root, "select", uid)
    require(
        [
            (x.findtext("start"), x.findtext("diagramIdx"))
            for x in selector.findall("SelectRangeArray32/*")
        ]
        == [("0", "0"), ("1", "1")]
        and [d.get("uid") for d in selector.findall("diagramList/*")]
        == [false_uid, true_uid]
        and len(selector.find("tunnelList")) == 0,
        "runtime Boolean case polarity/arms/tunnels changed",
    )
    false, true = selector.find("diagramList")
    operations(false, [], "runtime empty False arm")
    exact_wires(false, (), "runtime empty False arm")
    return true


def local(root, uid, port, index, write=False):
    node = unique(root, "gRef", uid)
    term = node.find("termList/*")
    require(
        len(node.find("termList")) == 1
        and term.get("uid") == port
        and term.findtext("dco/paramIdx") == str(index)
        and term.findtext("dco/objFlags", "0") == ("0" if write else "1"),
        "runtime local identity/direction changed",
    )


def validate_tree(root):
    frame = unique(root, "diag", "7392")
    ops = [("select", "40346")]
    ops.extend(("label", uid) for uid in ("11738", "18734", "42096"))
    nets = []
    for index, (uid, alias, field, port, const, name, terms) in enumerate(PUBLICATIONS):
        ops.extend(
            (("sharedVariableDynamicWrite", uid), ("gRef", alias), (None, const))
        )
        node = unique(root, "sharedVariableDynamicWrite", uid)
        actual = node.findall("termList/*")
        require(
            [t.get("uid") for t in actual] == list(terms)
            and [t.findtext("dco/terminal_ID", "") for t in actual]
            == ["0B", "03", "08", "", "0A"]
            and [t.findtext("dco/objFlags") for t in actual]
            == ["128", "513", "512", "513", "128"],
            "runtime PSP writer ports/directions changed",
        )
        local(root, alias, port, field)
        payload = bytes.fromhex(constant(frame, const))
        expected_uri = (URI_PREFIX + name).encode("ascii")
        require(
            payload == len(expected_uri).to_bytes(4, "big") + expected_uri,
            "runtime PSP destination literal changed",
        )
        nets.extend(((const, terms[0]), (port, terms[4])))
        if index:
            nets.append((PUBLICATIONS[index - 1][6][3], terms[2]))
    nets.append(("7511", "47171"))
    operations(frame, ops, "runtime publication")
    exact_wires(frame, nets, "runtime publication")

    true = case(root, "40346", "49991", "50030")
    operations(
        true,
        [("gRef", "50011"), ("gRef", "50019"), (None, "49997")],
        "runtime PSP error True arm",
    )
    require(constant(true, "49997") == "01", "runtime PSP error assignment changed")
    local(root, "50011", "50014", 30, True)
    local(root, "50019", "50022", 45, True)
    exact_wires(true, (("49997", "50014", "50022"),), "runtime PSP error True arm")

    frame = unique(root, "diag", "1619")
    operations(
        frame,
        [(None, "8741"), ("select", "8602"), ("label", "25790")],
        "runtime comparison frame",
    )
    require(constant(frame, "8741") == "0000", "runtime comparison not saved False")
    exact_wires(frame, (("8741", "8629"),), "runtime comparison frame")
    true = case(root, "8602", "8613", "8619")
    operations(
        true,
        [
            (None, "30597"),
            ("gRef", "15300"),
            ("gRef", "15051"),
            ("iUse", "14648"),
            ("gRef", "25784"),
            ("iUse", "25772"),
            ("gRef", "25766"),
            ("gRef", "25760"),
        ],
        "inactive runtime comparison True arm",
    )
    for uid, port, index, write in (
        ("15300", "15307", 33, True),
        ("15051", "15059", 33, False),
        ("25784", "25787", 29, False),
        ("25766", "25769", 28, False),
        ("25760", "25763", 28, True),
    ):
        local(root, uid, port, index, write)
    for uid, name, terms in (
        ("25772", "VDirecte", ("25775", "25778", "25781")),
        ("14648", "VD", ("14675", "14684", "14693")),
    ):
        node = unique(root, "iUse", uid)
        require(
            name in node.findtext("label/textRec/text", ""),
            "inactive runtime comparison helper changed",
        )
        for slot, term in enumerate(terms):
            public_term(node, term, slot)
    exact_wires(
        true,
        (
            ("15059", "14684"),
            ("14675", "15307"),
            ("25787", "25781", "14693"),
            ("25769", "25778"),
            ("25775", "25763"),
        ),
        "inactive runtime comparison True arm",
    )

    loop = unique(root, "whileLoop", "203")
    require(
        [d.get("uid") for d in loop.findall("diagramList/*")] == ["211"]
        and len(loop.find("srDCOList")) == 0
        and len(loop.find("tunnelList")) == 0
        and loop.findtext("loopTestDCO/objFlags") == "65537",
        "runtime I/O loop topology/Stop-if-True changed",
    )
    body = unique(root, "diag", "211")
    operations(
        body,
        [
            ("prim", "24889"),
            (None, "24741"),
            ("gRef", "1756"),
            ("gRef", "1395"),
            ("sequence", "1244"),
            (None, "223"),
            (None, "220"),
        ],
        "runtime I/O loop body",
    )
    primitive(body, "24889", 1302, ("24891", "24894"))
    require(constant(body, "24741") == "00000050", "runtime wait literal changed")
    local(root, "1756", "1806", 30)
    local(root, "1395", "11002", 32, True)
    exact_wires(
        body,
        (("24741", "24894"), ("1806", "223"), ("220", "11002")),
        "runtime I/O loop body",
    )
    return (
        "8 ordered PSP requests C1/C2/EPS/EPC/VTA/C3/C4/C5; final returned "
        "error True assigns stop/TCP ED True. Comparison frame saved False, "
        "inactive two-helper True arm retained. Wait=80 ms, stop sampled "
        "independently of sequence; no atomic cycle or emergency latency guarantee."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_tree(checked_root(args.root_archive)))


if __name__ == "__main__":
    main()
