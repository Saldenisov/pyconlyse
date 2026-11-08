"""Pin the complete direct NI6220 runtime graphs, not driver execution.

Missing True-counter default metadata remains unresolved. This validator
checks absence; it deliberately does not infer default from displayed dIdx.
"""

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6602_writer import primitive
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations
from validate_acq_vam_status import checked_vam

NETS = {
    "47487": (
        ("44983", "47134"),
        ("47493", "196782"),
        ("48198", "45004"),
        ("44973", "48160"),
        ("48186", "45010"),
        ("47528", "47924"),
        ("47561", "47496"),
    ),
    "47080": (
        ("48174", "135593", "62733"),
        ("56008", "138217"),
        ("58092", "56011"),
        ("135596", "56014"),
        ("90236", "136898", "208163"),
        ("138214", "206866"),
        ("136901", "138220"),
        ("52284", "90239"),
        ("53076", "90879"),
        ("53085", "90884"),
        ("53091", "90887"),
        ("62519", "53094"),
        ("61838", "53088"),
        ("61184", "53081"),
        ("47133", "52281"),
        ("53790", "52287"),
    ),
    "45510": (("208155", "50572", "100530"), ("100515", "100525")),
    "206856": (("208159", "47036", "91012"), ("74944", "81878"), ("62724", "202330")),
    "104729": (),
    "100537": (("100557", "100552"), ("100546", "100560")),
    "100569": (("100575", "101618"), ("100534", "101610")),
    "81862": (("86713", "86048"), ("85391", "86716")),
    "81868": (("92946", "91677"), ("91009", "202980")),
    "48574": (
        ("49037", "48805", "48812"),
        ("48815", "48792"),
        ("49026", "49057"),
        ("49005", "49053"),
        ("48984", "49049"),
        ("48963", "49046"),
        ("48942", "49043"),
        ("48849", "49040"),
        ("49062", "48936", "48837", "48978", "48999", "49020", "48957"),
        ("48923", "49017"),
        ("48917", "48996"),
        ("48911", "48975"),
        ("48905", "48954"),
        ("48897", "48933"),
        ("48887", "48833"),
        ("49074", "48926"),
        ("49086", "48920"),
        ("49099", "48914"),
        ("49111", "48908"),
        ("49133", "48902"),
        ("48581", "48884"),
        ("49157", "48892"),
        ("48825", "48818"),
    ),
    "68780": (("72031", "74865"), ("71369", "72028")),
    "68786": (),
    "74849": (),
    "74855": (),
}
OPS = {
    "47487": [
        ("commentNode", "68772"),
        ("sequence", "15804"),
        ("gRef", "196772"),
        ("iUse", "44966"),
        ("gRef", "48193"),
        ("gRef", "48181"),
        ("iUse", "48083"),
        (None, "47528"),
        ("prim", "47918"),
        ("gRef", "47557"),
        (None, "47496"),
        (None, "47493"),
    ],
    "47080": [
        (None, "58092"),
        ("prim", "18880"),
        ("select", "45497"),
        ("prim", "136891"),
        ("polyIUse", "136243"),
        ("polyIUse", "135586"),
        ("aBuild", "15699"),
        (None, "62519"),
        (None, "61838"),
        (None, "61184"),
        (None, "53790"),
        ("aIndx", "52275"),
        ("gRef", "48168"),
    ],
    "45510": [("select", "100523"), ("gRef", "100508"), ("gRef", "50544")],
    "206856": [
        ("select", "81854"),
        ("gRef", "74934"),
        ("gRef", "202320"),
        ("gRef", "47026"),
    ],
    "104729": [],
    "100537": [("prim", "100555"), ("gRef", "100549"), ("gRef", "100543")],
    "100569": [(None, "100575"), ("gRef", "101615"), ("gRef", "101607")],
    "81862": [("prim", "86707"), ("gRef", "86041"), ("gRef", "85375")],
    "81868": [(None, "92946"), ("gRef", "91670"), ("gRef", "202970")],
    "48574": [
        ("aBuild", "49035"),
        (None, "49062"),
        ("iUse", "49014"),
        ("iUse", "48993"),
        ("iUse", "48972"),
        ("iUse", "48951"),
        ("iUse", "48930"),
        (None, "49074"),
        (None, "49086"),
        (None, "49099"),
        (None, "49111"),
        (None, "49133"),
        (None, "49157"),
        ("aIndx", "48881"),
        ("iUse", "48830"),
        ("gRef", "48822"),
        ("aIndx", "48810"),
        (None, "48792"),
        ("gRef", "48802"),
    ],
    "68780": [
        (None, "86412"),
        ("select", "74832"),
        ("nMux", "15006"),
        ("gRef", "71359"),
    ],
    "68786": [],
    "74849": [],
    "74855": [],
}
LOCALS = (
    ("196772", "196782", 62, True),
    ("48193", "48198", 57, False),
    ("48181", "48186", 56, False),
    ("47557", "47561", 30, False),
    ("100508", "100515", 68, False),
    ("50544", "50572", 65, True),
    ("100549", "100552", 68, True),
    ("100543", "100546", 68, False),
    ("101615", "101618", 68, True),
    ("101607", "101610", 66, True),
    ("74934", "74944", 68, False),
    ("202320", "202330", 67, True),
    ("47026", "47036", 65, True),
    ("86041", "86048", 68, True),
    ("85375", "85391", 68, False),
    ("91670", "91677", 68, True),
    ("202970", "202980", 66, True),
    ("48822", "48825", 63, False),
    ("48802", "48805", 59, True),
    ("71359", "71369", 39, False),
)
POINT_CALLS = (
    ("48830", ("48833", "48837", "48840", "48849", "48854", "48878")),
    ("48930", ("48933", "48936", "48939", "48942", "48945", "48948")),
    ("48951", ("48954", "48957", "48960", "48963", "48966", "48969")),
    ("48972", ("48975", "48978", "48981", "48984", "48987", "48990")),
    ("48993", ("48996", "48999", "49002", "49005", "49008", "49011")),
    ("49014", ("49017", "49020", "49023", "49026", "49029", "49032")),
)


def selector(root, uid, diagrams, values, default):
    node = unique(root, "select", uid)
    require(
        tuple(d.get("uid") for d in node.findall("diagramList/*")) == diagrams,
        "NI6220 case frame order changed",
    )
    require(
        tuple(
            (
                x.findtext("start"),
                x.findtext("end"),
                x.findtext("startRangeType"),
                x.findtext("endRangeType"),
                x.findtext("diagramIdx"),
            )
            for x in node.findall("SelectRangeArray32/*")
        )
        == tuple((str(v), str(v), "0", "0", str(i)) for i, v in enumerate(values)),
        "NI6220 case selector ranges changed",
    )
    require(
        node.findtext("SelectDefaultCase") == default,
        "NI6220 saved default-case metadata changed",
    )
    return node


def port_order(node, ports):
    require(
        tuple(t.get("uid") for t in node.findall("termList/*")) == ports,
        "NI6220 aggregate/call terminal ordering changed",
    )


def tunnel(node, port, kind, flags, children):
    dco = node.find(f"termList/*[@uid='{port}']/dco")
    require(
        dco is not None
        and dco.get("class") == kind
        and dco.findtext("objFlags", "0") == flags
        and tuple(t.get("uid") for t in dco.findall("termList/*")) == children,
        "NI6220 structure input/branch tunnel changed",
    )


def validate_runtime(root, meta):
    for uid, nets in NETS.items():
        frame = unique(root, "diag", uid)
        operations(frame, OPS[uid], "NI6220 runtime " + uid)
        exact_wires(frame, nets, "NI6220 runtime " + uid)
    sequence = unique(root, "sequence", "15804")
    require(
        [d.get("uid") for d in sequence.findall("diagramList/*")] == ["47080", "48574"],
        "NI6220 runtime sequence order changed",
    )
    tunnel(sequence, "47134", "seqTun", "2048", ("47133", "48581", "47134"))
    loop = unique(root, "whileLoop", "47483")
    require(
        loop.find("diagramList/*").get("uid") == "47487"
        and loop.find("loopIndexDCO/termList/*").get("uid") == "47493"
        and loop.find("loopTestDCO/termList/*").get("uid") == "47496"
        and loop.findtext("loopTestDCO/objFlags") == "65537",
        "NI6220 loop count/Stop-if-True binding changed",
    )
    primitive(root, "47918", 1302, ("47921", "47924"))
    primitive(root, "18880", 1050, ("56008", "56011", "56014"))
    primitive(root, "136891", 1110, ("138214", "138217", "138220"))
    primitive(root, "100555", 1057, ("100557", "100560"))
    primitive(root, "86707", 1057, ("86713", "86716"))
    for uid, port, bank, write in LOCALS:
        local(root, uid, port, bank, write)
    special = unique(root, "gRef", "48168")
    require(
        special.findtext("termList/*/dco/paramIdx") == "65"
        and special.findtext("termList/*/dco/objFlags") == "5"
        and special.find("termList/*").get("uid") == "48174",
        "NI6220 flagged prior-array local changed",
    )
    descriptor = unique(root, "gRef", "100508").findtext("termList/*/dco/typeDesc")
    value, _ = heap_type(meta, int(descriptor[7:-1]))
    require(value.get("Type") == "NumUInt32", "NI6220 counter is not U32")
    for cls, uid, port, expected in (
        ("prim", "100555", "100557", "NumUInt32"),
        ("prim", "100555", "100560", "NumUInt32"),
        ("prim", "86707", "86713", "NumUInt32"),
        ("prim", "86707", "86716", "NumUInt32"),
        ("gRef", "48822", "48825", "NumUInt16"),
    ):
        descriptor = unique(root, cls, uid).findtext(
            f"termList/*[@uid='{port}']/dco/typeDesc"
        )
        value, _ = heap_type(meta, int(descriptor[7:-1]))
        require(
            value.get("Type") == expected,
            "NI6220 increment/index representation changed",
        )
    for frame, port, literal in (
        ("47487", "47528", "0000000F"),
        ("47080", "58092", "3F9EB851EB851EB8"),
        ("47080", "53790", "00000004"),
        ("47080", "61184", "00000005"),
        ("47080", "61838", "00000006"),
        ("47080", "62519", "00000007"),
        ("48574", "49157", "0000000000"),
        ("48574", "49133", "00000001"),
        ("48574", "49111", "00000002"),
        ("48574", "49099", "00000003"),
        ("48574", "49086", "00000008"),
        ("48574", "49074", "00000009"),
        ("48574", "49062", "00000014"),
        ("100569", "100575", "0000000000"),
        ("81868", "92946", "0000000000"),
    ):
        require(
            constant(unique(root, "diag", frame), port) == literal,
            "NI6220 index/threshold/window/reset literal changed",
        )
    branch = selector(root, "45497", ("45510", "206856"), (0, 1), None)
    tunnel(branch, "206866", "caseSel", "0", ("206864", "206865", "206866"))
    tunnel(branch, "208163", "selTun", "2048", ("208155", "208159", "208163"))
    tunnel(branch, "62733", "selTun", "2048", ("62720", "62724", "62733"))
    counter_false = selector(
        root, "100523", ("104729", "100537", "100569"), (0, 1, 3), "01"
    )
    counter_true = selector(root, "81854", ("81862", "81868"), (0, 3), None)
    for node, ports in (
        (
            counter_false,
            (
                ("100525", "caseSel", "0", ("104739", "100528", "100529", "100525")),
                ("100530", "selTun", "2048", ("104736", "100533", "100534", "100530")),
            ),
        ),
        (
            counter_true,
            (
                ("81878", "caseSel", "0", ("81876", "81877", "81878")),
                ("91012", "selTun", "2048", ("91005", "91009", "91012")),
            ),
        ),
    ):
        for args in ports:
            tunnel(node, *args)
    comment = unique(root, "commentNode", "68772")
    require(
        comment.findtext("activeDiag") == "01"
        and comment.findtext("defaultDiag") == "01"
        and comment.findtext("commentMode") == "True"
        and [d.get("uid") for d in comment.findall("diagramList/*")]
        == ["68780", "68786"]
        and len(comment.find("tunnelList")) == 0,
        "NI6220 Diagram Disable saved active arm changed",
    )
    selector(root, "74832", ("74849", "74855"), (0, 4981000), None)
    inactive_extract = unique(root, "nMux", "15006")
    port_order(inactive_extract, ("72028", "72031"))
    require(
        inactive_extract.findtext("termList/*[@uid='72031']/dco/i") == "3",
        "NI6220 inactive bank39 field extraction changed",
    )
    names = call_names(meta)
    for cls, uid, qualified, ports in (
        (
            "iUse",
            "44966",
            "1_ACQ_READ_NI6220.vi",
            (
                "44973",
                "44976",
                "44979",
                "44983",
                "44989",
                "44992",
                "44995",
                "44998",
                "45001",
                "45004",
                "45007",
                "45010",
            ),
        ),
        (
            "iUse",
            "48083",
            "Simple Error Handler.vi",
            (
                "48094",
                "48100",
                "48109",
                "48118",
                "48124",
                "48132",
                "48141",
                "48147",
                "48151",
                "48160",
            ),
        ),
        (
            "polyIUse",
            "135586",
            "NI_AALBase.lvlib:Mean (DBL).vi",
            ("135593", "135596", "135599"),
        ),
        (
            "polyIUse",
            "136243",
            "NI_AALBase.lvlib:Mean (DBL).vi",
            ("136898", "136901", "136904"),
        ),
        *(
            ("iUse", uid, "NI_PtbyPt.lvlib:Mean PtByPt.vi", ports)
            for uid, ports in POINT_CALLS
        ),
    ):
        node = unique(root, cls, uid)
        require(names.get(uid) == qualified, "NI6220 qualified callee identity changed")
        port_order(node, ports)
        for i, port in enumerate(ports):
            public_term(node, port, i)
    for cls, uid, ports in (
        ("aBuild", "15699", ("90236", "90239", "90879", "90884", "90887")),
        (
            "aBuild",
            "49035",
            ("49037", "49040", "49043", "49046", "49049", "49053", "49057"),
        ),
        (
            "aIndx",
            "52275",
            (
                "52281",
                "52284",
                "52287",
                "53076",
                "53081",
                "53085",
                "53088",
                "53091",
                "53094",
            ),
        ),
        (
            "aIndx",
            "48881",
            (
                "48884",
                "48887",
                "48892",
                "48897",
                "48902",
                "48905",
                "48908",
                "48911",
                "48914",
                "48917",
                "48920",
                "48923",
                "48926",
            ),
        ),
        ("aIndx", "48810", ("48812", "48815", "48818")),
    ):
        node = unique(root, cls, uid)
        port_order(node, ports)
        terms = node.findall("termList/*")
        require(
            node.find("dcoAgg").get("uid")
            == terms[0 if cls == "aBuild" else 1].find("dco").get("uid"),
            "NI6220 aggregate first-element/output mapping changed",
        )
        require(
            tuple(t.get("uid") for t in node.findall("dcoList/*"))
            == tuple(
                t.find("dco").get("uid") for t in terms[1 if cls == "aBuild" else 2 :]
            ),
            "NI6220 aggregate element/index list changed",
        )
        if cls == "aIndx":
            require(
                node.find("srcDCO").get("uid") == terms[0].find("dco").get("uid"),
                "NI6220 Index Array aggregate input changed",
            )
    require(
        unique(root, "fPTerm", "48792").find("dco").get("uid") == "48790",
        "NI6220 selected scalar indicator changed",
    )
    return (
        "PASS: NI6220 runtime 14 diagrams / 61 direct nets; "
        "True counter unspecified-default dispatch remains open"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    args = parser.parse_args()
    print(validate_runtime(*checked_vam(args.root_archive)))


if __name__ == "__main__":
    main()
