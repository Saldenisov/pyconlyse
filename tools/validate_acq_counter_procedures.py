"""Complete pulse start/stop graphs; standard DAQmx calls remain boundaries."""

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations

COUNTER_FRAMES = ("45203", "40802", "49141")
START_NETS = (
    ("52879", "54914"),
    ("54926", "20510"),
    ("46319", "52891"),
    ("51935", "54881"),
    ("49188", "46274"),
    ("50008", "49185"),
    ("45220", "45257"),
)
STOP_ROWS = (
    # Frame / task field / local node,port / unbundle,ports / loop,body / stop / clear.
    (
        "40802",
        3,
        ("40905", "40926"),
        ("40949", ("40951", "40954")),
        ("2682", "2745"),
        "2546",
        "39385",
    ),
    (
        "49141",
        4,
        ("49379", "49382"),
        ("49387", ("49389", "49392")),
        ("49217", "49233"),
        "49161",
        "41727",
    ),
)
STOP_NETS = {
    "40802": (
        ("2664", "39426"),
        ("40954", "2700"),
        ("40926", "40951"),
        ("2690", "2635"),
        ("2717", "2560"),
        ("40808", "40821"),
    ),
    "49141": (
        ("49214", "41746"),
        ("49392", "49223"),
        ("49382", "49389"),
        ("49219", "49202"),
        ("49227", "49164"),
    ),
}
POLL_NETS = {
    "2745": (
        ("3014", "8483"),
        ("2889", "8479"),
        ("8474", "2772"),
        ("2846", "8389"),
        ("2763", "8467"),
        ("2954", "2726"),
        ("2972", "2699"),
        ("2981", "2907"),
        ("2711", "2945"),
        ("2810", "2933"),
        ("2781", "2898"),
    ),
    "49233": (
        ("49323", "49340"),
        ("49282", "49337"),
        ("49334", "49242"),
        ("49268", "49326"),
        ("49239", "49329"),
        ("49304", "49230"),
        ("49310", "49222"),
        ("49313", "49288"),
        ("49226", "49301"),
        ("49256", "49296"),
        ("49245", "49285"),
    ),
}
# OR, Greater, Equal, Wait, Done property, constants(True,1ms,40), index and test ports.
POLL_ROWS = {
    "2745": (
        "8471",
        ("8474", "8479", "8483"),
        ("3006", ("3014", "8389", "8467")),
        ("2882", ("2889", "2898", "2907")),
        ("2916", ("2924", "2933")),
        ("2942", ("2945", "2954", "2963", "2972", "2981")),
        ("2781", "2810", "2846"),
        "2763",
        "2772",
    ),
    "49233": (
        "49332",
        ("49334", "49337", "49340"),
        ("49321", ("49323", "49326", "49329")),
        ("49280", ("49282", "49285", "49288")),
        ("49291", ("49293", "49296")),
        ("49299", ("49301", "49304", "49307", "49310", "49313")),
        ("49245", "49256", "49268"),
        "49239",
        "49242",
    ),
}

# Separate saved graphs in the outer seven-phase controlled stop. These are
# not event24 aliases: the first frame also writes the ETAPES marker.
CONTROLLED_STOP_ROWS = (
    (
        "47671",
        3,
        ("47925", "47928"),
        ("47933", ("47935", "47938")),
        ("47748", "47770"),
        "47695",
        "47942",
    ),
    (
        "47989",
        4,
        ("48208", "48211"),
        ("48214", ("48216", "48219")),
        ("48046", "48062"),
        "47995",
        "48223",
    ),
)
CONTROLLED_STOP_NETS = {
    "47671": (
        ("53457", "53447"),
        ("47745", "47957"),
        ("47938", "47754"),
        ("47928", "47935"),
        ("47750", "47731"),
        ("47758", "47698"),
    ),
    "47989": (
        ("48043", "48238"),
        ("48219", "48052"),
        ("48211", "48216"),
        ("48048", "48031"),
        ("48056", "47998"),
    ),
}
CONTROLLED_POLL_ROWS = {
    "47770": (
        "47878",
        ("47880", "47883", "47886"),
        ("47867", ("47869", "47872", "47875")),
        ("47826", ("47828", "47831", "47834")),
        ("47837", ("47839", "47842")),
        ("47845", ("47847", "47850", "47853", "47856", "47859")),
        ("47792", "47802", "47814"),
        "47784",
        "47789",
    ),
    "48062": (
        "48161",
        ("48163", "48166", "48169"),
        ("48150", ("48152", "48155", "48158")),
        ("48108", ("48110", "48113", "48116")),
        ("48119", ("48122", "48125")),
        ("48128", ("48130", "48133", "48136", "48139", "48142")),
        ("48074", "48084", "48096"),
        "48068",
        "48071",
    ),
}
CONTROLLED_POLL_NETS = {
    "47770": (
        ("47869", "47886"),
        ("47828", "47883"),
        ("47880", "47789"),
        ("47814", "47872"),
        ("47784", "47875"),
        ("47850", "47763"),
        ("47856", "47753"),
        ("47859", "47834"),
        ("47757", "47847"),
        ("47802", "47842"),
        ("47792", "47831"),
    ),
    "48062": (
        ("48152", "48169"),
        ("48110", "48166"),
        ("48163", "48071"),
        ("48096", "48155"),
        ("48068", "48158"),
        ("48133", "48059"),
        ("48139", "48051"),
        ("48142", "48116"),
        ("48055", "48130"),
        ("48084", "48125"),
        ("48074", "48113"),
    ),
}


def _kind(metadata, term):
    return heap_type(metadata, int(term.findtext("dco/typeDesc")[7:-1]))[0]


def _call(root, names, uid, name, count, active):
    node = unique(root, "iUse", uid)
    terms = node.findall("termList/*")
    require(
        names.get(uid) == name
        and len(terms) == count
        and [int(t.findtext("dco/paramIdx", "0")) for t in terms] == list(range(count)),
        "counter call identity/connector changed",
    )
    for slot, flags in active.items():
        require(
            terms[slot].findtext("dco/objFlags", "0") == flags,
            "counter call active direction changed",
        )


def _task_unbundle(root, metadata, reference, mux, fields):
    local(root, reference[0], reference[1], 21)
    desc = _kind(metadata, unique(root, "gRef", reference[0]).find("termList/*"))
    flat = metadata.find("VCTP/Section").findall("TypeDesc")
    members = [flat[int(c.get("TypeID"))] for c in desc.findall("TypeDesc")]
    require(
        desc.get("Type") == "Cluster"
        and desc.get("Label") == "ID_NI6602_DAQmx"
        and len(members) == 8
        and all(
            c.get("Type") == "Refnum"
            and c.get("Ident") == "Task"
            and c.get("TypeName") == "NIDAQ"
            and c.get("Label") == f"ID_NI6602_out{i}"
            for i, c in enumerate(members)
        ),
        "counter task bank type/field identity changed",
    )
    node = unique(root, "nMux", mux[0])
    terms = node.findall("termList/*")
    require(
        node.findtext("objFlags") == "327680"
        and tuple(t.get("uid") for t in terms) == mux[1]
        and tuple(int(t.findtext("dco/i", "0")) for t in terms[1:]) == fields,
        "counter unbundle/task indices changed",
    )
    require(
        all(
            _kind(metadata, t).get("Type") == "Refnum"
            and _kind(metadata, t).get("Ident") == "Task"
            for t in terms[1:]
        ),
        "counter selected field type changed",
    )


def _action(root, metadata, frame, ref, port, literal):
    local(root, ref, port, 35, True)
    term = unique(root, "gRef", ref).find("termList/*")
    require(
        _kind(metadata, term).get("Type") == "Boolean"
        and constant(frame, literal) == "01",
        "counter ACTION changed",
    )


def validate_counter_frame(root, metadata, frame, *, controlled_stop=False):
    uid = frame.get("uid")
    rows = CONTROLLED_STOP_ROWS if controlled_stop else STOP_ROWS
    qualified = tuple(row[0] for row in rows) if controlled_stop else COUNTER_FRAMES
    require(uid in qualified, "counter frame not qualified")
    names = call_names(metadata)
    if uid == "45203":
        operations(
            frame,
            [
                ("iUse", "2548"),
                ("iUse", "52872"),
                ("iUse", "54874"),
                ("iUse", "46267"),
                ("nMux", "49179"),
                ("gRef", "50001"),
                ("gRef", "45254"),
                ("label", "45262"),
                ("label", "45263"),
                (None, "45220"),
            ],
            "pulse start",
        )
        exact_wires(frame, START_NETS, "pulse start")
        _task_unbundle(
            root,
            metadata,
            ("50001", "50008"),
            ("49179", ("49185", "49188", "51935")),
            (3, 4),
        )
        for call in ("46267", "54874"):
            _call(
                root,
                names,
                call,
                "DAQmx Start Task.vi",
                16,
                {0: "128", 11: "512", 15: "513"},
            )
        for call in ("2548", "52872"):
            _call(root, names, call, "Clear Errors.vi", 8, {0: "513", 4: "512"})
        _action(root, metadata, frame, "45254", "45257", "45220")
        return (("counter_start_clear_chain", 21, (3, 4)), ("write", 35, ((-1, True),)))

    row = next(row for row in rows if row[0] == uid)
    _, task_index, reference, mux, loop_info, stop, clear = row
    ops = [
        ("iUse", stop),
        ("iUse", clear),
        ("nMux", mux[0]),
        ("gRef", reference[0]),
        ("whileLoop", loop_info[0]),
    ]
    if controlled_stop:
        labels = ("47969", "47970") if task_index == 3 else ("48250", "48251")
        ops.extend(("label", label) for label in labels)
        if task_index == 3:
            ops.extend((("gRef", "52774"), (None, "53457")))
            local(root, "52774", "53447", 50, True)
            require(
                _kind(metadata, unique(root, "gRef", "52774").find("termList/*")).get(
                    "Type"
                )
                == "NumFloat64"
                and constant(frame, "53457") == "4014000000000000",
                "controlled-stop marker5 changed",
            )
    elif uid == "40802":
        ops.extend(
            [("label", "41142"), ("label", "41143"), ("gRef", "40818"), (None, "40808")]
        )
        _action(root, metadata, frame, "40818", "40821", "40808")
    else:
        ops.extend([("label", "49429"), ("label", "49440")])
    operations(frame, ops, "pulse stop")
    stop_nets = CONTROLLED_STOP_NETS if controlled_stop else STOP_NETS
    exact_wires(frame, stop_nets[uid], "pulse stop")
    _task_unbundle(root, metadata, reference, mux, (task_index,))
    _call(root, names, stop, "DAQmx Stop Task.vi", 16, {0: "128", 11: "512", 15: "513"})
    _call(root, names, clear, "Clear Errors.vi", 8, {0: "513", 4: "512"})
    loop = unique(root, "whileLoop", loop_info[0])
    body = loop.find("diagramList/*")
    require(
        len(loop.find("diagramList")) == 1
        and body.get("uid") == loop_info[1]
        and len(loop.find("srDCOList")) == 0
        and len(loop.find("tunnelList")) == 3,
        "pulse poll body/tunnel/SR changed",
    )
    for term, flags in zip(loop.findall("termList/*"), ("2049", "2048", "2049")):
        dco = term.find("dco")
        require(
            dco.get("class") == "lpTun"
            and dco.findtext("objFlags") == flags
            and len(dco.find("termList")) == 2
            and dco.find("termList")[1].get("uid") == term.get("uid"),
            "ordinary poll tunnel changed",
        )
    poll_rows = CONTROLLED_POLL_ROWS if controlled_stop else POLL_ROWS
    compound, cp, greater, equal, wait, prop, literals, index, test = poll_rows[
        body.get("uid")
    ]
    operations(
        body,
        [
            ("cpdArith", compound),
            ("prim", greater[0]),
            ("prim", equal[0]),
            ("prim", wait[0]),
            ("propNode", prop[0]),
        ]
        + [(None, p) for p in (*literals, index, test)],
        "pulse poll body",
    )
    poll_nets = CONTROLLED_POLL_NETS if controlled_stop else POLL_NETS
    exact_wires(body, poll_nets[body.get("uid")], "pulse poll body")
    cpd = unique(root, "cpdArith", compound)
    require(
        cpd.findtext("objFlags") == ("720896" if controlled_stop else "724992")
        and tuple(t.get("uid") for t in cpd.findall("termList/*")) == cp
        and [t.findtext("dco/objFlags") for t in cpd.findall("termList/*")]
        == ["131073", "262144", "262144"],
        "non-inverted OR changed",
    )
    for spec, resource in ((greater, 1110), (equal, 1102), (wait, 1302)):
        node = unique(root, "prim", spec[0])
        require(
            node.findtext("primResID") == str(resource)
            and tuple(t.get("uid") for t in node.findall("termList/*")) == spec[1],
            "poll primitive/connector changed",
        )
    require(
        [constant(body, p) for p in literals] == ["01", "00000001", "00000028"],
        "poll True/1ms/40 literals changed",
    )
    property_node = unique(root, "propNode", prop[0])
    require(
        property_node.findtext("oMId") == "1790"
        and [c.text for c in property_node.findall(".//PropItemCode")] == ["6414"]
        and tuple(t.get("uid") for t in property_node.findall("termList/*")) == prop[1]
        and [t.findtext("dco/objFlags") for t in property_node.findall("termList/*")]
        == ["65536", "262145", "131072", "524289", "1"],
        "DAQmx Done read changed",
    )
    for placeholder, tag, klass, flags in (
        (index, "loopIndexDCO", "lCnt", None),
        (test, "loopTestDCO", "lTst", "65537"),
    ):
        dco = body.find(f"nodeList/*/termList/*[@uid='{placeholder}']/dco")
        saved = loop.find(tag)
        require(
            dco.get("uid") == saved.get("uid")
            and saved.get("class") == klass
            and (flags is None or saved.findtext("objFlags") == flags),
            "poll index or Stop-if-True changed",
        )
    # Pin the tunnel pairs against the exact query/Stop wires, not merely their count.
    if controlled_stop:
        expected_pairs = (
            (("47753", "47750"), ("47757", "47754"), ("47763", "47758"))
            if task_index == 3
            else (("48051", "48048"), ("48055", "48052"), ("48059", "48056"))
        )
    else:
        expected_pairs = (
            (("2699", "2690"), ("2711", "2700"), ("2726", "2717"))
            if task_index == 3
            else (("49222", "49219"), ("49226", "49223"), ("49230", "49227"))
        )
    require(
        tuple(
            tuple(t.get("uid") for t in p.findall("dco/termList/*"))
            for p in loop.findall("termList/*")
        )
        == expected_pairs,
        "poll tunnel pairs changed",
    )
    literal_terms = {t.get("uid"): t for t in body.findall("nodeList/*/termList/*")}
    require(
        [_kind(metadata, literal_terms[p]).get("Type") for p in literals]
        == ["Boolean", "NumUInt32", "NumInt32"],
        "poll literal types changed",
    )
    for spec, kinds in (
        (greater, ("Boolean", "NumInt32", "NumInt32")),
        (equal, ("Boolean", "Boolean", "Boolean")),
    ):
        require(
            tuple(
                _kind(metadata, t).get("Type")
                for t in unique(root, "prim", spec[0]).findall("termList/*")
            )
            == kinds,
            "poll comparison types changed",
        )
    require(
        all(
            _kind(metadata, t).get("Type") == "Boolean"
            for t in cpd.findall("termList/*")
        )
        and _kind(metadata, property_node.findall("termList/*")[-1]).get("Type")
        == "Boolean"
        and heap_type(metadata, int(loop.findtext("loopIndexDCO/typeDesc")[7:-1]))[
            0
        ].get("Type")
        == "NumInt32",
        "poll Boolean or iteration type changed",
    )
    effects = [("counter_poll_stop_clear", 21, task_index, loop_info[1], 40, 1)]
    if controlled_stop and task_index == 3:
        effects.append(("write", 50, ((-1, 5.0),)))
    if uid == "40802":
        effects.append(("write", 35, ((-1, True),)))
    return tuple(sorted(effects, key=repr))
