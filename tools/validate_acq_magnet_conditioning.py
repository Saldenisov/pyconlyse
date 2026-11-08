"""Pin all four event16 magnet-conditioning For graphs, without device I/O."""

from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations

FIELDS = (0, 1, 3, 4, 6, 7, 8, 9)
PARENT_LABELS = {
    "44981": ("45090", "45089"),
    "41847": ("42040", "42039"),
    "39014": ("39183", "39207"),
    "42572": ("42793", "42817"),
}
INDEX_PORTS = {"48496": "48505", "41875": "41881", "39041": "39047", "42635": "42663"}
# Parent/loop/body; N literal/value; seed literal/raw; math node/resource/ports;
# wait node/ports/literal; step literal; reader/port, writer/port;
# bundle/ports; body label. For connectors are N, right SR, left SR.
RAMPS = (
    (
        "44981",
        "48488",
        "48496",
        ("33138", 160),
        ("33111", "000000000000000000"),
        ("34286", 1050, ("34292", "34295", "34298")),
        ("43281", ("48510", "48513"), "48521"),
        "41125",
        ("45081", "45084"),
        ("45039", "45042"),
        (
            "45045",
            (
                "45047",
                "45050",
                "45051",
                "45054",
                "45058",
                "45062",
                "45068",
                "45071",
                "45074",
                "45077",
            ),
        ),
        "48533",
    ),
    (
        "41847",
        "41858",
        "41875",
        ("42016", 320),
        ("42027", "4030000000000000"),
        ("35956", 1051, ("36080", "36191", "36403")),
        ("41978", ("41980", "41986"), "41896"),
        "41884",
        ("41948", "41951"),
        ("41909", "41912"),
        (
            "41917",
            (
                "41919",
                "41922",
                "41923",
                "41926",
                "41929",
                "41932",
                "41935",
                "41938",
                "41941",
                "41944",
            ),
        ),
        "41989",
    ),
    (
        "39014",
        "39024",
        "39041",
        ("39184", 320),
        ("39195", "C030000000000000"),
        ("39709", 1050, ("41200", "41203", "41206")),
        ("39136", ("39138", "39141"), "39065"),
        "39050",
        ("39117", "39120"),
        ("39078", "39081"),
        (
            "39086",
            (
                "39088",
                "39091",
                "39092",
                "39095",
                "39098",
                "39101",
                "39104",
                "39107",
                "39110",
                "39113",
            ),
        ),
        "39156",
    ),
    (
        "42572",
        "42600",
        "42635",
        ("42794", 160),
        ("42805", "4030000000000000"),
        ("31772", 1051, ("31780", "31783", "31786")),
        ("42748", ("42750", "42753"), "42678"),
        "42666",
        ("42729", "42732"),
        ("42690", "42693"),
        (
            "42698",
            (
                "42700",
                "42703",
                "42704",
                "42707",
                "42710",
                "42713",
                "42716",
                "42719",
                "42722",
                "42725",
            ),
        ),
        "42767",
    ),
)


def validate_ramp(root, metadata, frame):
    matches = [row for row in RAMPS if row[0] == frame.get("uid")]
    require(len(matches) == 1, "unqualified conditioning frame")
    _, loop_uid, body_uid, n, seed, math, wait, step, reader, writer, mux, label = (
        matches[0]
    )
    loop = unique(root, "forLoop", loop_uid)
    require(loop in frame.findall("zPlaneList/*"), "conditioning For moved")
    body = loop.find("diagramList/*")
    require(
        body.get("uid") == body_uid
        and len(loop.find("diagramList")) == 1
        and len(loop.find("ConditionDCOList")) == 0
        and len(loop.find("tunnelList")) == 0
        and loop.findtext("ParForIndexDistribution") == "00"
        and loop.findtext("ParForNumStaticWorkers") == "00",
        "For iteration/parallel/tunnel behavior changed",
    )
    ports = loop.findall("termList/*")
    require(
        len(ports) == 3
        and [t.find("dco").get("class") for t in ports] == ["lMax", "rSR", "lSR"],
        "conditioning For connector classes changed",
    )
    maximum, right, left = [p.get("uid") for p in ports]
    inside = []
    for port in ports:
        pair = [t.get("uid") for t in port.findall("dco/termList/*")]
        require(
            len(pair) == 2 and pair[1] == port.get("uid"),
            "For connector pairing changed",
        )
        inside.append(pair[0])
    right_dco, left_dco = ports[1].find("dco"), ports[2].find("dco")
    require(
        right_dco.findtext("objFlags") == "1"
        and [s.get("uid") for s in loop.findall("srDCOList/*")]
        == [right_dco.get("uid")]
        and [s.get("uid") for s in right_dco.findall("lsrDCOList/*")]
        == [left_dco.get("uid")]
        and left_dco.find("rsrDCO").get("uid") == right_dco.get("uid"),
        "initialized one-value shift-register recurrence changed",
    )
    operations(
        frame,
        [("forLoop", loop_uid), (None, n[0]), (None, seed[0])]
        + [("label", uid) for uid in PARENT_LABELS[frame.get("uid")]],
        "ramp parent",
    )
    exact_wires(frame, ((n[0], maximum), (seed[0], left)), "ramp parent")
    require(
        constant(frame, n[0]) == n[1].to_bytes(4, "big", signed=True).hex().upper()
        and constant(frame, seed[0]) == seed[1],
        "ramp N/seed literal changed",
    )
    operations(
        body,
        [
            ("prim", math[0]),
            ("prim", wait[0]),
            ("gRef", reader[0]),
            ("gRef", writer[0]),
            ("nMux", mux[0]),
            ("label", label),
            (None, step),
            (None, wait[2]),
            (None, INDEX_PORTS[body_uid]),
        ],
        "ramp body",
    )
    index_term = body.find(f"nodeList/*/termList/*[@uid='{INDEX_PORTS[body_uid]}']/dco")
    require(
        index_term.get("uid") == loop.find("loopIndexDCO").get("uid")
        and loop.find("loopIndexDCO").get("class") == "lCnt",
        "unused For index changed",
    )
    require(
        constant(body, step) == "3FB999999999999A"
        and constant(body, wait[2]) == "00000064",
        "ramp step/wait changed",
    )
    for uid, resource, expected in (math, (wait[0], 1302, wait[1])):
        primitive = unique(root, "prim", uid)
        require(
            primitive.findtext("primResID") == str(resource)
            and tuple(t.get("uid") for t in primitive.findall("termList/*"))
            == expected,
            "ramp primitive/ports changed",
        )
    local(root, reader[0], reader[1], 10)
    local(root, writer[0], writer[1], 10, True)
    bundle = unique(root, "nMux", mux[0])
    terms = bundle.findall("termList/*")
    require(
        tuple(t.get("uid") for t in terms) == mux[1]
        and tuple(int(t.findtext("dco/i", "0")) for t in terms[2:]) == FIELDS,
        "ramp C7 output field set changed",
    )
    exact_wires(
        body,
        (
            (step, math[2][1]),
            (wait[2], wait[1][1]),
            (math[2][0], inside[1], *mux[1][2:]),
            (inside[2], math[2][2]),
            (reader[1], mux[1][1]),
            (mux[1][0], writer[1]),
        ),
        "ramp body",
    )

    def kind(term):
        return heap_type(metadata, int(term.findtext("dco/typeDesc")[7:-1]))[0]

    literal_terms = {
        t.get("uid"): t
        for f in (frame, body)
        for t in f.findall("nodeList/*/termList/*")
    }
    require(
        kind(literal_terms[n[0]]).get("Type") == "NumInt32"
        and kind(literal_terms[wait[2]]).get("Type") == "NumUInt32"
        and all(
            kind(literal_terms[p]).get("Type") == "NumFloat64" for p in (seed[0], step)
        )
        and kind(ports[0]).get("Type") == "NumInt32"
        and all(kind(p).get("Type") == "NumFloat64" for p in ports[1:]),
        "ramp scalar types changed",
    )
    for uid in (reader[0], writer[0]):
        desc = kind(unique(root, "gRef", uid).find("termList/*"))
        flat = metadata.find("VCTP/Section").findall("TypeDesc")
        require(
            desc.get("Type") == "Cluster"
            and desc.get("Label") == "C7NI6703"
            and len(desc.findall("TypeDesc")) == 10
            and all(
                flat[int(c.get("TypeID"))].get("Type") == "NumFloat64"
                for c in desc.findall("TypeDesc")
            ),
            "ramp C7 bank shape changed",
        )
    require(
        all(
            kind(t).get("Type") == "NumFloat64"
            for t in terms[2:] + unique(root, "prim", math[0]).findall("termList/*")
        ),
        "ramp math/field types changed",
    )
    seed_value = {
        "000000000000000000": 0.0,
        "4030000000000000": 16.0,
        "C030000000000000": -16.0,
    }[seed[1]]
    return (
        "conditioning_ramp",
        body_uid,
        10,
        FIELDS,
        n[1],
        seed_value,
        0.1 if math[1] == 1050 else -0.1,
        100,
    )
