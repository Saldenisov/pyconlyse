"""Complete frame 227 and eight error arms; offline, no driver execution.

The existing gate proof supplies selector/tunnel mappings. This adds exact
net sets, connected and unwired connector slots, typed arguments and task
destinations. Returned task validity and standard Clear Errors behavior
remain external boundaries.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from validate_acq_final_cleanup import constant, exact_wires, public_term
from validate_acq_initialization_ai_fallback import (
    validate_tree as validate_fallback_gates,
)
from validate_acq_initialization_error_gates import GATES, validate_tree
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_psp_discovery import validate_tree as validate_discovery_wires
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import local, operations
from validate_acq_vam_status import checked_vam

NETS = (
    ("254", "439"),
    ("1317", "271"),
    ("1314", "274"),
    ("1303", "433"),
    ("442", "1692"),
    ("445", "1668"),
    ("562", "1131"),
    ("625", "557"),
    ("628", "335"),
    ("1510", "517"),
    ("1220", "637"),
    ("448", "1505"),
    ("374", "436"),
    ("505", "1215"),
    ("508", "1360"),
    ("598", "1266"),
    ("601", "1156"),
)
CALL_PORTS = (
    ("593", ("598", "601", "604", "607", "610", "613", "616", "619")),
    ("262", ("271", "274", "433", "436", "439", "442", "445", "448")),
    ("500", ("505", "508", "511", "514", "517", "520", "523", "526")),
    ("620", ("625", "628", "631", "634", "637", "640", "643", "646")),
)
TASK_BANKS = (
    ("1053", "1156", 21, "ID_NI6602_DAQmx", 8),
    ("431", "1692", 23, "C1_NI6071E", 1),
    ("419", "1668", 24, "C2_NI6071E", 1),
    ("1170", "1360", 22, "ID Cx_DIO", 6),
    ("325", "335", 25, "ID 4xNI6703", 4),
)
LITERALS = (
    ("254", "NumInt32", "0000000A"),
    ("1303", "NumFloat64", "40B3880000000000"),
    ("1317", "Tag", "000000072F312F50464930"),
    ("1314", "Tag", "000000072F322F50464930"),
)
DIAGRAM_UIDS = ("227", "1256", "1250", "1517", "1526", "1227", "1410", "1609", "1837")
FALLBACK_NETS = {
    "133": (
        ("1309", "2107", "25688"),
        ("2112", "1320"),
        ("1195", "2639"),
        ("1678", "2648"),
        ("1664", "2645"),
    ),
    "2119": (("2110", "2115"),),
    "2128": (
        ("8351", "7971"),
        ("8367", "4041"),
        ("8021", "1212"),
        ("4247", "8009"),
        ("2137", "4160"),
        ("2246", "2116"),
        ("1238", "2241"),
        ("1235", "2305"),
        ("1232", "2313"),
        ("2428", "1209"),
        ("2415", "1205"),
        ("2402", "1201"),
        ("2390", "1229"),
        ("2111", "2149"),
    ),
    "2253": (("2244", "2249"),),
    "2262": (("2271", "2250"), ("2245", "2283")),
}
FALLBACK_CALLS = (
    (
        "287",
        "1_ACQ_READ_NI6071E.vi",
        (
            "1309",
            "1400",
            "1452",
            "2624",
            "2627",
            "2630",
            "2633",
            "2636",
            "2639",
            "2642",
            "2645",
            "2648",
        ),
        {0: "513", 2: "513", 3: "513", 8: "512", 9: "512", 10: "512", 11: "512"},
    ),
    (
        "1198",
        "1_ACQ_INIT_NI6071E.vi",
        ("1201", "1205", "1209", "1212", "1229", "1232", "1235", "1238"),
        {i: "512" if i < 5 else "513" for i in range(8)},
    ),
    (
        "2134",
        "Clear Errors.vi",
        ("2137", "2140", "2143", "2146", "2149", "2152", "2155", "2158"),
        {0: "513", 4: "512"},
    ),
    (
        "2268",
        "Clear Errors.vi",
        ("2271", "2274", "2277", "2280", "2283", "2286", "2289", "2292"),
        {0: "513", 4: "512"},
    ),
    (
        "4034",
        "DAQmx Clear Task.vi",
        (
            "4041",
            "4044",
            "4048",
            "4076",
            "4079",
            "4082",
            "4087",
            "4097",
            "4103",
            "4151",
            "4157",
            "4160",
            "4164",
            "4169",
            "4243",
            "4247",
        ),
        {0: "128", 11: "512", 15: "513"},
    ),
    (
        "7931",
        "DAQmx Clear Task.vi",
        (
            "7971",
            "7974",
            "7978",
            "7982",
            "7986",
            "7990",
            "7993",
            "7996",
            "7999",
            "8003",
            "8006",
            "8009",
            "8012",
            "8015",
            "8018",
            "8021",
        ),
        {0: "128", 11: "512", 15: "513"},
    ),
)
PARENT_NETS = {
    "188": (),
    "20362": (),
    "17607": (("21713", "21511"),),
    "17949": (("18773", "9276"), ("9191", "21049")),
    "7580": (("25691", "28003"),),
}


def desc(metadata, term):
    value = term.findtext("dco/typeDesc")
    require(value and value.startswith("TypeID("), "caller terminal type absent")
    return heap_type(metadata, int(value[7:-1]))[0]


def error_type(metadata, term):
    node = desc(metadata, term)
    require(
        node.get("Type") == "Cluster"
        and [child.get("TypeID") for child in node.findall("TypeDesc")]
        == ["0", "1", "2"],
        "caller error cluster changed",
    )
    # Error fields use saved flat-table types, not caller-local heap indices.
    types = metadata.findall("VCTP/Section/TypeDesc")
    require(
        [types[int(i)].get("Type") for i in (0, 1, 2)]
        == ["Boolean", "NumInt32", "String"],
        "error field types changed",
    )


def check_call(metadata, node, ports, connected, names, expected_name):
    require(
        names.get(node.get("uid")) == expected_name,
        "initializer qualified call changed",
    )
    terms = node.findall("termList/*")
    require(
        tuple(t.get("uid") for t in terms) == ports,
        "initializer connector population changed",
    )
    for slot, term in enumerate(terms):
        public_term(node, term.get("uid"), slot)
        direction = term.findtext("dco/objFlags")
        expected = connected.get(slot)
        require(direction == expected, "initializer connector direction changed")
        if slot not in connected:
            require(
                desc(metadata, term).get("Type") == "Void",
                "unused initializer connector acquired a type",
            )


def validate_caller(root, metadata):
    validate_tree(root)
    frame = unique(root, "diag", "227")
    exact_wires(frame, NETS, "complete initializer caller")
    names = call_names(metadata)
    for uid, ports in CALL_PORTS:
        node = unique(root, "iUse", uid)
        if uid == "262":
            connected = {i: "512" if i < 5 else "513" for i in range(8)}
        else:
            connected = {0: "513", 1: "513", 4: "512"}
        check_call(
            metadata,
            node,
            ports,
            connected,
            names,
            next(row[1] for row in GATES if row[0] == uid),
        )
        for slot in (3, 7) if uid == "262" else (0, 4):
            error_type(metadata, node.findall("termList/*")[slot])
    # First initializer's error input 610 has no net; no readiness predicate.
    literal_terms = {
        t.get("uid"): t
        for t in frame.findall("nodeList/*/termList/*")
        if t.find("dco/ConstValue") is not None
    }
    require(
        set(literal_terms) == {row[0] for row in LITERALS},
        "initializer literal population changed",
    )
    for uid, typ, raw in LITERALS:
        require(
            constant(frame, uid) == raw
            and desc(metadata, literal_terms[uid]).get("Type") == typ,
            "initializer typed literal changed",
        )
        if typ == "Tag":
            require(
                desc(metadata, literal_terms[uid]).get("TagType") == "DAQmxTerminal",
                "trigger terminal tag kind changed",
            )
    for left, right in NETS:
        terms = {t.get("uid"): t for t in frame.findall("zPlaneList/*/termList/*")}
        terms.update(literal_terms)
        if left in terms and right in terms:

            def signature(term):
                node = desc(metadata, term)
                return (
                    {
                        key: value
                        for key, value in node.attrib.items()
                        if key != "Label"
                    },
                    [child.attrib for child in node],
                )

            require(
                signature(terms[left]) == signature(terms[right]),
                "initializer connected types disagree",
            )
    for uid, port, index, label, size in TASK_BANKS:
        local(root, uid, port, index, True)
        node = desc(metadata, unique(root, "gRef", uid).find("termList/*"))
        require(node.get("Label") == label, "initializer task bank label changed")
        fields = node.findall("TypeDesc") if size > 1 else [node]
        require(len(fields) == size, "initializer task bank cardinality changed")
        types = metadata.findall("VCTP/Section/TypeDesc")
        for field in fields:
            task = types[int(field.get("TypeID"))] if size > 1 else field
            require(
                task.get("Type") == "Refnum"
                and task.get("Ident") == "Task"
                and task.get("TypeName") == "NIDAQ",
                "initializer task reference type changed",
            )
    for row in GATES:
        (
            _,
            _,
            _,
            _,
            _,
            _,
            pass_uid,
            pass_input,
            pass_output,
            fail_uid,
            fail_input,
            fail_output,
            clear_uid,
            clear_input,
            clear_output,
        ) = row
        exact_wires(
            unique(root, "diag", pass_uid),
            ((pass_input, pass_output),),
            "complete initializer pass arm",
        )
        exact_wires(
            unique(root, "diag", fail_uid),
            ((fail_input, clear_input), (clear_output, fail_output)),
            "complete initializer clear arm",
        )
        clear = unique(root, "iUse", clear_uid)
        ports = tuple(str(int(clear_output) + 3 * i) for i in range(8))
        check_call(
            metadata, clear, ports, {0: "513", 4: "512"}, names, "Clear Errors.vi"
        )
        error_type(metadata, clear.findall("termList/*")[0])
        error_type(metadata, clear.findall("termList/*")[4])
        gate = unique(root, "select", row[3])
        for term in gate.findall("termList/*"):
            error_type(metadata, term)
    return (
        "Nine complete direct graphs; 29 nets; fixed 5000-Hz/10-sample "
        "PFI0 arguments; first error-in unwired; task writes outside error gates"
    )


def validate_fallback(root, metadata):
    validate_fallback_gates(root)
    for uid, nets in FALLBACK_NETS.items():
        exact_wires(unique(root, "diag", uid), nets, "complete AI fallback")
        require(
            {
                t.get("uid")
                for t in unique(root, "diag", uid).findall("nodeList/*/termList/*")
                if t.find("dco/ConstValue") is not None
            }
            == ({"2390", "2402", "2415", "2428"} if uid == "2128" else set()),
            "fallback literal population changed",
        )
    names = call_names(metadata)
    for uid, name, ports, directions in FALLBACK_CALLS:
        check_call(metadata, unique(root, "iUse", uid), ports, directions, names, name)
    for uid, port, index, write in (
        ("1675", "1678", 23, False),
        ("319", "1664", 24, False),
        ("8364", "8367", 23, False),
        ("8343", "8351", 24, False),
        ("2310", "2313", 23, True),
        ("2302", "2305", 24, True),
    ):
        local(root, uid, port, index, write)
    reader = unique(root, "iUse", "287")
    for port in ("1309", "2639"):
        error_type(metadata, reader.find(f"termList/*[@uid='{port}']"))
    require(
        desc(metadata, reader.find("termList/*[@uid='2642']")).get("Type")
        == "NumInt32",
        "AI test unwired sample-count type changed",
    )
    for uid, typ in (
        ("2390", "NumInt32"),
        ("2428", "NumFloat64"),
        ("2402", "Tag"),
        ("2415", "Tag"),
    ):
        term = unique(root, "diag", "2128").find(f"nodeList/*/termList/*[@uid='{uid}']")
        require(
            desc(metadata, term).get("Type") == typ, "fallback literal type changed"
        )
        if typ == "Tag":
            require(
                desc(metadata, term).get("TagType") == "DAQmxTerminal",
                "fallback terminal tag kind changed",
            )
    return (
        "Five complete fallback graphs; 23 nets; any read error.status "
        "triggers one clear/reinitialize path; raw error retained separately; "
        "test-read sample count unwired"
    )


def validate_parents(root, metadata):
    expected_ops = {
        "188": (("sequence", "201"), ("label", "195")),
        "20362": (("flatSequence", "17558"),),
        "17607": ((None, "21713"), ("prim", "21219")),
        "17949": ((None, "18773"), ("iUse", "9061"), ("iUse", "21015")),
        "7580": (("sequence", "24603"),),
    }
    for uid, nets in PARENT_NETS.items():
        frame = unique(root, "diag", uid)
        operations(frame, expected_ops[uid], "initialization parent")
        exact_wires(frame, nets, "initialization parent")
    initialization = unique(root, "sequence", "201")
    require(
        len(initialization.findall("termList/*")) == 0
        and [d.get("uid") for d in initialization.findall("diagramList/*")]
        == ["20362", "227", "133", "1356", "21518", "7580"],
        "initialization parent frame order changed",
    )
    flat = unique(root, "flatSequence", "17558")
    require(
        not flat.findall("termList/*")
        and [
            d.get("uid")
            for c in flat.findall("sequenceList/*")
            for d in c.findall("diagramList/*")
        ]
        == ["17607", "17949"],
        "clock synchronization flat-cell order changed",
    )
    wait = unique(root, "prim", "21219")
    require(
        wait.findtext("primResID") == "1302"
        and wait.findtext("primIndex") == "160"
        and [t.get("uid") for t in wait.findall("termList/*")] == ["21508", "21511"]
        and constant(unique(root, "diag", "17607"), "21713") == "000000C8",
        "startup 200-ms Wait changed",
    )
    command = constant(unique(root, "diag", "17949"), "18773")
    require(
        command == "0000001D6E65742074696D65205C5C31302E32302E33302E32202F736574202F79",
        "saved System Exec command changed",
    )
    names = call_names(metadata)
    for uid, name, ports, flags in (
        (
            "9061",
            "System Exec.vi",
            (
                "9191",
                "9244",
                "9247",
                "9250",
                "9253",
                "9256",
                "9259",
                "9262",
                "9265",
                "9269",
                "9273",
                "9276",
            ),
            (
                "513",
                "513",
                "513",
                "513",
                None,
                None,
                "512",
                "512",
                "512",
                "512",
                "512",
                "128",
            ),
        ),
        (
            "21015",
            "Simple Error Handler.vi",
            (
                "21022",
                "21025",
                "21028",
                "21031",
                "21034",
                "21037",
                "21040",
                "21043",
                "21046",
                "21049",
            ),
            ("513", "513", None, None, None, "513", "513", "513", "512", "512"),
        ),
    ):
        node = unique(root, "iUse", uid)
        require(
            names.get(uid) == name
            and tuple(t.get("uid") for t in node.findall("termList/*")) == ports,
            "clock synchronization call identity/ports changed",
        )
        for slot, (port, flag) in enumerate(zip(ports, flags)):
            public_term(node, port, slot)
            require(
                node.findtext(f"termList/*[@uid='{port}']/dco/objFlags") == flag,
                "clock synchronization call directions changed",
            )
    error_type(metadata, unique(root, "iUse", "9061").find("termList/*[@uid='9191']"))
    error_type(metadata, unique(root, "iUse", "21015").find("termList/*[@uid='21049']"))
    sequence = unique(root, "sequence", "24603")
    require(
        [d.get("uid") for d in sequence.findall("diagramList/*")]
        == ["14803", "24611", "25990", "33052", "17881"],
        "final startup child order changed",
    )
    require(
        [t.get("uid") for t in sequence.findall("termList/*")] == ["28003"]
        and sequence.find("termList/*/dco").get("class") == "seqTun"
        and [t.get("uid") for t in sequence.findall("termList/*/dco/termList/*")]
        == ["27946", "27956", "27967", "27982", "27992", "28003"],
        "original pilot-error startup tunnel changed",
    )
    error_type(metadata, sequence.find("termList/*"))
    return (
        "Five parent graphs; four nets; 200-ms Wait then saved "
        "clock-sync request/handler; no error/return-code gate "
        "into card initialization"
    )


def validate_discovery(root, metadata):
    validate_discovery_wires(root)
    operations(
        unique(root, "diag", "21518"),
        [
            (None, "82435"),
            (None, "74407"),
            ("label", "74404"),
            (None, "74395"),
            ("forLoop", "74267"),
            (None, "74224"),
            ("prim", "74193"),
            ("gRef", "74186"),
            (None, "74172"),
            ("label", "22613"),
        ],
        "complete discovery parent",
    )
    operations(
        unique(root, "diag", "74296"),
        [
            ("propNode", "74345"),
            ("sharedVariableDynamicOpen", "74325"),
            (None, "74305"),
            ("prim", "74317"),
            (None, "74302"),
        ],
        "complete discovery body",
    )
    for uid, constants in (
        ("21518", {"82435", "74407", "74395", "74224"}),
        ("74296", {"74305"}),
    ):
        terms = {
            t.get("uid"): t
            for t in unique(root, "diag", uid).findall("nodeList/*/termList/*")
            if t.find("dco/ConstValue") is not None
        }
        require(set(terms) == constants, "discovery literal population changed")
        if uid == "21518":
            require(
                constant(unique(root, "diag", uid), "82435")
                == constant(unique(root, "diag", uid), "74407"),
                "unused discovery URI literal changed",
            )
            for port, ident in (
                ("82435", "VariableContainer"),
                ("74407", "VariableContainer"),
                ("74395", "PSPVariable"),
            ):
                node = desc(metadata, terms[port])
                require(
                    node.get("Type") == "Refnum"
                    and node.get("Ident") == ident
                    and node.get("TypeName") == "Variable",
                    "discovery refnum literal type changed",
                )
        else:
            require(
                desc(metadata, terms["74305"]).get("Type") == "NumUInt32",
                "discovery wait type changed",
            )
    local(root, "74186", "74189", 61, True)
    bank = desc(metadata, unique(root, "gRef", "74186").find("termList/*"))
    require(
        bank.get("Type") == "Array" and bank.get("Label") == "Refnum SVE 2",
        "discovery destination type changed",
    )
    return (
        "Two discovery graphs; 14 nets; auto-indexed open-reference array "
        "to local61; final loop error unused; no expected-name whitelist"
    )


def validate_disabled_parent(root, metadata):
    frame = unique(root, "diag", "1356")
    operations(
        frame,
        [("commentNode", "76550"), ("label", "2545")],
        "initialization disabled parent",
    )
    exact_wires(frame, (("1371", "76738"),), "initialization disabled parent")
    owner = unique(root, "commentNode", "76550")
    require(
        owner.findtext("activeDiag") == "01"
        and owner.findtext("defaultDiag") == "01"
        and owner.findtext("commentMode") == "True"
        and owner.findtext("CommentSelLabFlags") == "1C"
        and [d.get("uid") for d in owner.findall("diagramList/*")]
        == ["76558", "76564"],
        "initialization Diagram Disable saved metadata changed",
    )
    require(
        [t.get("uid") for t in owner.findall("termList/*")] == ["76738"]
        and owner.find("termList/*/dco").get("class") == "commentTun"
        and owner.findtext("termList/*/dco/objFlags") == "2099200"
        and [t.get("uid") for t in owner.findall("termList/*/dco/termList/*")]
        == ["76736", "76737", "76738"],
        "initialization comment tunnel changed",
    )
    error_type(metadata, owner.find("termList/*"))
    empty = unique(root, "diag", "76564")
    operations(empty, [], "initialization empty disabled arm")
    exact_wires(empty, (), "initialization empty disabled arm")
    require(
        not any(
            t.find("dco/ConstValue") is not None
            for t in empty.findall("nodeList/*/termList/*")
        ),
        "empty disabled arm acquired literal",
    )
    return (
        "Initialization parent/empty arm metadata pinned; activeDiag/defaultDiag "
        "01 are present here, unlike cooling; 73-net sibling requires separate proof"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_archive", type=Path)
    root, metadata = checked_vam(parser.parse_args().root_archive)
    print(validate_caller(root, metadata))
    print(validate_fallback(root, metadata))
    print(validate_parents(root, metadata))
    print(validate_discovery(root, metadata))
    print(validate_disabled_parent(root, metadata))
    print(
        "PASS: initializer caller frame, not complete Acquisition or hardware readiness"
    )


if __name__ == "__main__":
    main()
