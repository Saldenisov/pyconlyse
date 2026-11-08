"""Compare current lvkit with pinned ACQ XML and source/native review facets.

This is structural preservation plus selected codegen safety, not whole-VI
execution equivalence. No LabVIEW, driver, network or hardware is operated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from build_acq_saved_diagram_census import diagram_rows
from validate_acq_controlled_stop import validate_stop
from validate_acq_initialization_error_gates import GATES, validate_tree
from validate_acq_modulator_start_event_guards import require

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = (
    REPO
    / "legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip"
)
ARCHIVE_SHA = "645694B964BA594F0563DAE37E67E49A03A0B57B4BA6C2A0639C916717F04A2F"
CACHE = REPO / ".tmp/acq_original_diagram_census_20261001"
CHECKOUT = Path("C:/dev/ELYSE-ACQ-analysis/converter/lvkit")
MAIN = "0_ACQ_ELYSE.vi"
FAULT_WRITES = {
    "28682": {"43027", "43040"},
    "40346": {"50011", "50019"},
    "40205": {"85095", "68231"},
}
DISABLE_ACTIVE = {"76550": 1, "68772": 1, "14478": 0}


def _sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def source_fingerprint():
    import lvkit

    package = Path(lvkit.__file__).parent
    files = sorted(p for p in package.rglob("*") if p.suffix in (".py", ".json"))
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(package).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {
        "package": str(package),
        "files": len(files),
        "sha256": digest.hexdigest().upper(),
    }


def _direct_inner(diagram):
    refs = [n.get("uid") for n in diagram.findall("nodeList/*")]
    refs.extend(
        n.get("uid")
        for n in diagram.findall("zPlaneList/*")
        if n.get("class") == "label"
        or n.find("diagramList") is not None
        or n.find("sequenceList") is not None
    )
    return {uid for uid in refs if uid}


def compare_structures(root, parsed):
    """Independent raw ownership/frame/net census; no parser helper reused."""
    count = Counter()
    groups = (
        (("sequence", "seq", "flatSequence"), parsed.flat_sequences, "sequences"),
        (("select", "caseStruct"), parsed.case_structures, "cases"),
        (("whileLoop", "forLoop"), parsed.loops, "loops"),
        (("commentNode",), parsed.disable_structures, "disable_structures"),
        (("eventStruct",), parsed.event_structures, "events"),
    )
    for classes, models, name in groups:
        raw = {
            n.get("uid"): n
            for n in root.iter()
            if n.get("class") in classes
            and (
                n.find("diagramList") is not None or n.find("sequenceList") is not None
            )
        }
        require(
            len(models) == len(raw) and {m.uid for m in models} == set(raw),
            f"lvkit {name} population differs",
        )
        count[name] = len(raw)
        for model in models:
            source = raw[model.uid]
            container = source.find("diagramList")
            if container is None:
                container = source.find("sequenceList")
            frames = list(container)
            if name == "loops":
                require(
                    len(frames) == 1
                    and model.inner_diagram_uid == frames[0].get("uid"),
                    "loop body identity differs",
                )
                require(
                    set(model.inner_node_uids) == _direct_inner(frames[0]),
                    "loop direct ownership differs",
                )
                count["frames"] += 1
                continue
            require(
                len(model.frames) == len(frames), f"frame count differs at {model.uid}"
            )
            count["frames"] += len(frames)
            for frame, original in zip(model.frames, frames):
                diagrams = original.find("diagramList")
                expected = (
                    set().union(*(_direct_inner(d) for d in diagrams))
                    if diagrams is not None
                    else _direct_inner(original)
                )
                require(
                    set(frame.inner_node_uids) == expected,
                    f"frame ownership differs at {model.uid}",
                )
                if name == "sequences":
                    require(
                        frame.uid == original.get("uid"),
                        "sequence order/identity differs",
                    )

    # Compare complete undirected net membership, including fan-out. This
    # does not promote the serialized first endpoint to a proven data source.
    source_nets = {}
    for signal in root.findall(".//signalList/*[@class='signal']"):
        endpoints = {t.get("uid") for t in signal.findall("termList/*") if t.get("uid")}
        require(len(endpoints) >= 2, "source net has fewer than two endpoints")
        source_nets[signal.get("uid")] = endpoints
    parsed_nets = {}
    for wire in parsed.wires:
        uid = wire.uid.split("_", 1)[0]
        parsed_nets.setdefault(uid, set()).update((wire.from_term, wire.to_term))
    require(parsed_nets == source_nets, "lvkit net membership differs")
    count["nets"] = len(source_nets)
    raw_psp = {
        n.get("uid")
        for n in root.iter()
        if n.get("class")
        in {"sharedVariableDynamic" + op for op in ("Read", "Write", "Open", "Close")}
    }
    model_psp = {
        n.uid for n in parsed.nodes if n.node_type.startswith("sharedVariableDynamic")
    }
    require(raw_psp == model_psp, "PSP node population differs")
    count["psp_nodes"] = len(raw_psp)
    return dict(count)


def audit(cache=CACHE):
    sys.path.insert(0, str(CHECKOUT / "src"))
    import lvkit

    require(
        Path(lvkit.__file__).resolve().is_relative_to(CHECKOUT.resolve()),
        "lvkit import came from another installation",
    )
    before = source_fingerprint()
    from lvkit.codegen.context import CodeGenContext
    from lvkit.codegen.nodes import generate
    from lvkit.codegen.nodes.base import UnknownNodeError
    from lvkit.graph import InMemoryVIGraph
    from lvkit.parser import parse_vi

    require(
        _sha(ARCHIVE.read_bytes()) == ARCHIVE_SHA,
        "original XML archive identity differs",
    )
    totals = Counter()
    members = []
    with ZipFile(ARCHIVE) as archive:
        names = sorted({name.split("/")[0] for name in archive.namelist()})
        require(len(names) == 17, "original member count differs")
        for name in names:
            folder = Path(cache) / Path(name).stem
            for leaf in ("vi.xml", "vi_BDHb.xml", "vi_FPHb.xml"):
                require(
                    _sha((folder / leaf).read_bytes())
                    == _sha(archive.read(name + "/" + leaf)),
                    f"cached XML differs from pinned archive: {name}/{leaf}",
                )
            raw = ET.parse(folder / "vi_BDHb.xml").getroot()
            metadata = ET.parse(folder / "vi.xml").getroot()
            parsed = parse_vi(
                bd_xml=folder / "vi_BDHb.xml",
                fp_xml=folder / "vi_FPHb.xml",
                main_xml=folder / "vi.xml",
                source_override=name,
            )
            counts = compare_structures(raw, parsed.block_diagram)
            counts["saved_diagrams"] = len(
                list(diagram_rows(name, "archive-pinned", raw, metadata))
            )
            totals.update(counts)
            members.append({"vi": name, **counts})
            if name == MAIN:
                main_raw, main_meta, main_parsed = raw, metadata, parsed

    require(totals["saved_diagrams"] == 533, "original diagram census differs")
    stop = validate_stop(main_raw, main_meta)
    validate_tree(main_raw)
    graph = InMemoryVIGraph()
    graph._add_vi_to_graph(
        main_parsed.block_diagram,
        main_parsed.front_panel,
        main_parsed.connector_pane,
        {},
        MAIN,
        MAIN,
        main_parsed.metadata.type_map,
    )
    context = CodeGenContext(graph=graph, vi_name=MAIN)
    rejected = []
    expected_errors = {row[3]: {row[-3]} for row in GATES}
    expected_errors.update(
        {
            "2105": {"2134", "4034", "7931", "1198", "2239"},
            "2239": {"2268"},
            **FAULT_WRITES,
        }
    )
    for uid, expected in expected_errors.items():
        node = graph._graph.nodes[MAIN + "::" + uid]["node"]
        require(
            [f.selector_value for f in node.frames] == ["0", "1"],
            "reviewed error selector identity differs",
        )
        try:
            generate(node, context)
        except UnknownNodeError as exc:
            require(
                "nonempty error frame" in str(exc)
                and exc.node_id == node.id
                and all(MAIN + "::" + child in str(exc) for child in expected),
                "error refusal lost a reviewed recovery/fault operation",
            )
            rejected.append(uid)
        else:
            raise AssertionError(f"unsafe error-frame omission at {uid}")

    empty_disables = []
    selections = {}
    for uid, active in DISABLE_ACTIVE.items():
        node = graph._graph.nodes[MAIN + "::" + uid]["node"]
        require(
            node.active_frame == active, "native-reviewed disable selection differs"
        )
        selections[uid] = active
        if active == 1:
            fragment = generate(node, context)
            require(
                not fragment.statements and not fragment.bindings,
                "disabled named opens/old counter block became executable",
            )
            empty_disables.append(uid)
    require(source_fingerprint() == before, "shared lvkit changed during audit")
    return {
        "scope": (
            "structural preservation and selected fail-closed codegen, "
            "not full ACQ equivalence"
        ),
        "lvkit": before,
        "original_xml_archive_sha256": ARCHIVE_SHA,
        "totals": dict(totals),
        "members": members,
        "native_reviewed_disable_selections": selections,
        "empty_enabled_arms_lowered": empty_disables,
        "nonempty_error_cases_refused": rejected,
        "controlled_stop": {"diagrams": stop["diagrams"], "nets": stop["nets"]},
        "whole_acquisition_closed": False,
        "native_vi_executed": False,
        "hardware_or_psp_executed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=CACHE)
    args = parser.parse_args()
    print(json.dumps(audit(args.cache), indent=2))


if __name__ == "__main__":
    main()
