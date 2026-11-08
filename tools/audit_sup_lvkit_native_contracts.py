"""Version-bound Supervision parser audit and selected visual/source facets.

39 application VIs = 38 original LLB members plus the motor helper. Native
images without capture-time source identity corroborate only the displayed
fragment. They never close every frame, external ABI or runtime behavior.
No VI, generated application, camera, network, PSP or hardware is executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from audit_acq_lvkit_native_contracts import (
    CHECKOUT,
    compare_structures,
    source_fingerprint,
)
from validate_sup_ht_request_gate import validate_tree as validate_ht
from validate_sup_modulator_request_gate import (
    require,
)
from validate_sup_modulator_request_gate import (
    validate_tree as validate_modulator,
)

REPO = Path(__file__).resolve().parents[1]
ANALYSIS = REPO / "Supervision/analysis"
RECEIPT = ANALYSIS / "lvkit_eval/parser_release_20261003/receipt.json"
RECEIPT_SHA = "266206C05CADD3798B5EF4C6C43A76B8AD737830F53DBFC15E080BAF405743FB"
MOTOR = ANALYSIS / "lvkit_eval/parser_motor_release_20261003/receipt.json"
MOTOR_SHA = "1A8B1ED604D2D1365981973F9C89D9D542161753B6C1A274AC89448A9BA17825"
CACHE = REPO / ".tmp/sup_native_contracts_20261016"
MAIN_SHA = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
MUTABLE_MAIN_SHA = "2257C86FF6285E1E144BCC5039B4CA5455A34E0DB95B8A15D4DA8503C3A8686B"
LIBRARY = REPO / "Supervision/source/PILOTAGE_ELYSE_SUP/SUPERVISION.llb"
LIBRARY_SHA = "D427B2BA8544E4FFD6868F4E2EF74762363C7C713E30B2FF151E5F5AD168BCF4"
REFERENCES = {
    "0_SUP_ELYSE.vi": {
        "16661": "Buffer V1",
        "12435": "Buffer V2",
        "22996": "Buffer V3",
        "16124": "Buffer V4",
        "18769": "Buffer V5",
        "19276": "Buffer V6",
        "21880": "Buffer V7",
        "27300": "Buffer V8",
        "19908": "Buffer V9",
    },
    "1_SUP_PROFILS XY.vi": {"666": "Image IN", "1080": "Image IN 2"},
}
IMAGES = {
    "0_SUP_ELYSE_outer_frame_2_event_case_15_full.png": (
        "B8A77B4CB0145C817604164441D6EEAFF4DE9CBF375B8D3694904FC0033EB6CD",
        "Event15 Page HT; displayed True/True/1: subtract1, bounds6..20, "
        "C9 command field and arrow reset; not the DPS False arm",
    ),
    "0_SUP_ELYSE_outer_frame_2_event_case_18_full.png": (
        "B89781EB37BBD22D782DA77305A29EAE42662C3D52C469B0A9573AA10A134AE8",
        "Event18 Page Modulateur; False arm, no-other-request gate, "
        "eleven named button->DPS wires, PSP writer and Error handler",
    ),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def pinned_json(path, expected):
    require(digest(path) == expected, f"evidence identity changed: {path}")
    return json.loads(Path(path).read_text("utf-8"))


def validate_references(name, parsed, fp_root):
    """Keep reference identity and saved type; infer no image/driver ABI."""
    from lvkit.graph import InMemoryVIGraph

    expected = REFERENCES.get(name, {})
    controls = {c.uid: c for c in parsed.front_panel.controls}
    raw_order = [n.get("uid") for n in fp_root.findall("root/ddoList/*")]
    recovered = []
    for uid, label in expected.items():
        require(uid in controls, f"reference typedef control dropped: {name}:{uid}")
        control = controls[uid]
        require(
            control.name == label and control.control_type == "stdRefNum",
            f"reference replaced by wrapper payload: {name}:{uid}",
        )
        require(
            control.lv_type is not None
            and control.lv_type.underlying_type == "Refnum"
            and control.lv_type.ref_type == "UsrDefTagFlt"
            and (control.lv_type.typedef_name or "").endswith("IMAQ Image.ctl"),
            f"saved IMAQ type lost: {name}:{uid}",
        )
        index = raw_order.index(uid)
        require(
            parsed.front_panel.local_control_uids.get(index) == uid,
            "reference missing or reindexed in local table",
        )
        recovered.append({"uid": uid, "name": label, "param_idx": index})

    graph = InMemoryVIGraph()
    graph._add_vi_to_graph(
        parsed.block_diagram,
        parsed.front_panel,
        parsed.connector_pane,
        {},
        name,
        name,
        parsed.metadata.type_map,
    )
    locals_checked = []
    by_index = {r["param_idx"]: r for r in recovered}
    for node in parsed.block_diagram.nodes:
        if node.node_type != "gRef" or node.param_idx not in by_index:
            continue
        target = by_index[node.param_idx]
        alias = graph._graph.nodes[name + "::" + node.uid]["node"]
        require(
            alias.control_name == target["name"] and alias.control_terminal_id,
            "reference local alias lost",
        )
        locals_checked.append(node.uid)
    return {"controls": recovered, "local_nodes_checked": locals_checked}


def audit():
    sys.path.insert(0, str(CHECKOUT / "src"))
    import lvkit
    from lvkit.extractor import extract_vi_xml
    from lvkit.parser import parse_vi

    require(
        Path(lvkit.__file__).resolve().is_relative_to(CHECKOUT.resolve()),
        "lvkit import came from another installation",
    )
    before = source_fingerprint()
    require(digest(LIBRARY) == LIBRARY_SHA, "original Supervision LLB changed")
    receipt = pinned_json(RECEIPT, RECEIPT_SHA)
    require(receipt["recovered_members"] == 38, "original LLB member count changed")
    require(receipt["source_original_main_sha256"] == MAIN_SHA, "Main identity changed")
    rows = [(r["vi"], pinned_json(r["path"], r["sha256"])) for r in receipt["rows"]]
    rows.append(("Moteurs SdC GoTo.vi", pinned_json(MOTOR, MOTOR_SHA)))
    require(
        len(rows) == 39 and len({name for name, _ in rows}) == 39,
        "application VI scope changed",
    )

    totals = Counter()
    results, references, refreshed = [], {}, []
    for index, (name, entry) in enumerate(rows):
        require(
            digest(entry["source"]) == entry["sha256"],
            f"original VI bytes changed: {name}",
        )
        for item in entry["xml"]:
            require(
                digest(item["path"]) == item["sha256"],
                f"source XML identity changed: {name}",
            )
        bd, fp, meta = (Path(item["path"]) for item in entry["xml"])
        if name in REFERENCES:
            # Historical metadata contains corrupt-stub Void descriptors.
            # Retain it unchanged; re-extract the same original bytes with
            # the updated reader. Independent BD/FP hashes must still agree.
            fresh_bd, fresh_fp, fresh_meta = extract_vi_xml(
                entry["source"], output_dir=CACHE / f"{index:02d}"
            )
            require(
                digest(fresh_bd) == digest(bd) and digest(fresh_fp) == digest(fp),
                "metadata recovery changed the source diagram/panel",
            )
            bd, fp, meta = fresh_bd, fresh_fp, fresh_meta
            refreshed.append(
                {
                    "vi": name,
                    "metadata": str(meta),
                    "sha256": digest(meta),
                    "diagram_and_panel_unchanged": True,
                }
            )
        parsed = parse_vi(
            bd_xml=bd, fp_xml=fp, main_xml=meta, source_override=entry["source"]
        )
        raw = ET.parse(bd).getroot()
        counts = compare_structures(raw, parsed.block_diagram)
        totals.update(counts)
        results.append({"vi": name, "sha256": entry["sha256"], **counts})
        if name in REFERENCES:
            references[name] = validate_references(name, parsed, ET.parse(fp).getroot())
        if name == "0_SUP_ELYSE.vi":
            require(
                entry["sha256"] == MAIN_SHA, "resaved Main substituted for original"
            )
            metadata = ET.parse(meta).getroot()
            commands = {
                "HT": validate_ht(raw, metadata),
                "Modulateur": validate_modulator(raw, metadata),
            }
            for uid in ("38758", "30946"):
                case = parsed.block_diagram.get_case_structure(uid)
                require(
                    case is not None
                    and case.selector_type == "boolean"
                    and [f.selector_value for f in case.frames] == ["False", "True"],
                    "lvkit changed reviewed DPS gate polarity",
                )

    images = []
    for name, (sha, observed) in IMAGES.items():
        path = ANALYSIS / "screenshots" / name
        require(digest(path) == sha, "manually inspected image changed")
        images.append(
            {
                "path": str(path),
                "sha256": sha,
                "observed": observed,
                "source_sha_at_capture": None,
                "original_source_capture_binding_qualified": False,
            }
        )
    require(source_fingerprint() == before, "shared lvkit changed during audit")
    require(
        all(digest(entry["source"]) == entry["sha256"] for _, entry in rows),
        "original VI bytes changed during audit",
    )
    return {
        "scope": "39 application VIs; excludes 87 additional catalog dependency VIs",
        "lvkit": before,
        "original_library_sha256": LIBRARY_SHA,
        "original_main_sha256": MAIN_SHA,
        "resaved_main_sha256_not_substituted": MUTABLE_MAIN_SHA,
        "totals": dict(totals),
        "members": results,
        "restored_reference_controls": references,
        "updated_reader_metadata": refreshed,
        "historical_stub_metadata_is_not_type_or_default_authority": True,
        "fresh_metadata_does_not_close_DFDS_defaults_or_native_ABI": True,
        "original_request_maps": commands,
        "raw_event_NewVal_decoder_qualified": False,
        "manually_inspected_images_this_pass": images,
        "all_native_frames_reviewed": False,
        "whole_supervision_closed": False,
        "protected_error_database_implemented": False,
        "native_or_hardware_or_psp_executed": False,
    }


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(audit(), indent=2))


if __name__ == "__main__":
    main()
