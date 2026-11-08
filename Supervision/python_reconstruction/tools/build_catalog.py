"""Build evidence catalog and non-executable stub module for each VI in scope.

Reads copied LabVIEW/lvkit artifacts only. It never starts LabVIEW, generated code,
drivers, remote desktop, or hardware.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import unicodedata
from pathlib import Path
from typing import Any, Iterator


PROJECT = Path(__file__).resolve().parents[1]
CATALOG = PROJECT / "src" / "supervision_reconstruction" / "catalog"
REPO = PROJECT.parents[1]
SUPERVISION = REPO / "Supervision"
VI_ROOT = SUPERVISION / "extracted" / "PILOTAGE_ELYSE_SUP" / "SUPERVISION_VIs"
MOTOR = SUPERVISION / "extracted" / "PILOTAGE_ELYSE_SUP" / "PILOTAGE_ELYSE_SUP_moteurs" / "Moteurs SdC GoTo.vi"
ANALYSIS = SUPERVISION / "analysis"
LVKIT_ROOT = ANALYSIS / "lvkit_eval"
LVKIT_CONTEXTS = {
    "base": LVKIT_ROOT / "batch_0_8_4",
    "minimal_vilib": LVKIT_ROOT / "batch_0_8_4_minimal_vilib",
}
EXPORT_ROOT = ANALYSIS / "labview_print_hidden_frames"
EXPORT_MANIFEST = CATALOG / "labview_hidden_frame_manifest.json"
LABVIEW_2020 = Path(r"C:\Program Files (x86)\National Instruments\LabVIEW 2020")
GLOBAL_DIAGRAMLESS_SECTIONS = {"Global Variables.vi"}

STATE_OVERRIDES = {
    "0_SUP_ELYSE.vi": ("failed", "Print and both lvkit descriptions establish outer lifecycle and major loop/event topology, but both lvkit generated root paths fail compilation/generation and controller/UI/PSP/DAQ/CmdLib/camera/filesystem semantics remain unvalidated; static non-executable inventory only"),
    "1_SUP_INIT_NI6602.vi": ("partial", "eight sequence frames captured; hardware timing semantics remain unvalidated"),
    "1_SUP_PROFILS XY.vi": ("partial", "structural visual/lvkit agreement around unresolved IMAQ terminal layout"),
    "1_SUP_WRITE_NI6602.vi": ("partial", "diagram and generated broad structure agree; generated DAQmx semantics mismatch"),
    "Initialize.vi": ("partial", "single-element path array and Working Visible/Blinking property intent agree in both lvkit contexts and Print evidence"),
    "Check Special Tags.vi": ("partial", "Print and both lvkit descriptions establish <ERR>/<APPEND> ASCII-case tag priority; arbitrary Match Pattern regex dialect remains unvalidated"),
    "Find Tag.vi": ("partial", "Print and both lvkit descriptions establish tag-removal loop topology and indexed outputs; arbitrary Match Pattern regex dialect and non-ASCII byte-offset semantics remain unvalidated"),
    "Format Message String.vi": ("partial", "Print and both lvkit descriptions establish CRLF prefix, B-tag removal, and ordered value-then-bold branch; GUI execution, arbitrary regex dialect, and non-ASCII byte offsets remain unvalidated"),
    "Search and Replace Pattern.vi": ("partial", "Print and both lvkit descriptions establish replacement feedback/termination topology; arbitrary Match Pattern regex dialect and non-ASCII byte-offset semantics remain unvalidated"),
    "BuildHelpPath.vi": ("partial", "Print and both lvkit descriptions establish GetHelpDir then Build Path wiring; runtime VI Library and LabVIEW path-platform semantics remain unvalidated"),
    "GetHelpDir.vi": ("partial", "Print and both lvkit descriptions establish VI Library then Strip Path then help Build Path wiring; runtime/path-platform semantics remain unvalidated"),
    "FW102x Error Message.vi": ("partial", "Print and both lvkit descriptions establish U32 size wired to I32 array dimension plus zero-buffer/extFunc preparation and return-code error bundle wiring; above-I32 coercion, external driver binding, and text contract remain unvalidated"),
    "FW102x IVI Error Converter.vi": ("partial", "Print and both lvkit descriptions establish outer error-status/nonzero-IVI-code gate and 256-byte buffer preparation; IVI calls and message-builder contract remain unvalidated"),
    "FW102x Close.vi": ("partial", "Print and both lvkit descriptions establish ungated concurrent external-close/IVI-delete topology; bindings, results, session lifetime, and converter output remain unvalidated"),
    "FW102x Get Position.vi": ("partial", "Print and both lvkit descriptions establish error-status gate and extFunc/converter terminal wiring; driver result and error-frame position/default-tunnel semantics remain unvalidated"),
    "FW102x Initialize.vi": ("partial", "Print and both lvkit descriptions establish error-status gate, Boolean-to-U16/U32 coercions, extFunc, IVI New Session, and converter topology; bindings and session/output semantics remain unvalidated"),
    "FW102x Set Position.vi": ("partial", "Print and both lvkit descriptions establish error-status gate and extFunc/converter terminal wiring; driver binding, result, and converter output remain unvalidated"),
    "Convert property node font to graphics font.vi": ("partial", "Print and both lvkit descriptions establish U16/Color-U32 cluster remap to Size-I16 and forced Outline/Shadow false; out-of-shared-range coercion and downstream font rendering remain unvalidated"),
    "Longest Line Length in Pixels.vi": ("partial", "Print and both lvkit descriptions establish I16 right-left feedback selected to I32 over Get Text Rect outputs; overflow, text encoding, line enumeration, font metrics, and platform rendering remain unvalidated"),
    "Set Bold Text.vi": ("partial", "Print establishes visible selection-control writes and 0 versus 1,Default case labels; I32 overflow, refnum/property/error, and rendering semantics remain unvalidated"),
    "Add Item.vi": ("partial", "Print and both lvkit descriptions establish file then patterned-folder List Folder/tree-invoke phases; filesystem/path/tree/error semantics remain unvalidated"),
    "Directory to Tree.vi": ("partial", "Print and both lvkit descriptions establish Initialize/Validate/Add Item worklist topology, disconnected Files found connector, local Parent Tag, and Working lifecycle; traversal/path/tree/error semantics remain unvalidated"),
    "sous vi LigneCentroide2.vi": ("partial", "Print Formula Node and both lvkit descriptions establish +/-10 Formula/Bundle geometry after conversion; floating To Long Integer semantics remain unvalidated"),
    "Init_Open_Close.vi": ("partial", "Print and both lvkit descriptions establish Delete Tree Items(True) → Directory to Tree → Open/Close All(False); refnum/tree/error/traversal semantics remain unvalidated"),
    "Details Display Dialog.vi": ("partial", "Print and both lvkit descriptions establish six-value DialogTypeEnum, multi-sequence control/event topology, and dialog-type==1 initial OK visibility; modal UI/event/property/geometry contracts remain unvalidated"),
    "General Error Handler CORE.vi": ("partial", "Print and both lvkit descriptions establish incoming/local error selection, exception-action=1 code/source suppression, and no-error branch; password database, formatting, GUI, Help, Stop, and event effects remain unvalidated"),
    "General Error Handler.vi": ("partial", "Print and both lvkit descriptions establish localized-ring frames 0..4 remapped to CORE enum 0,1,2,4,5; CORE external/UI effects remain unvalidated"),
    "Not Found Dialog.vi": ("partial", "Print and both lvkit descriptions establish dialog-type groups, Center/Right choice gates, Help-path wiring, and auto-dialog Stop distinction; OS dialogs, Help, Stop, shortcuts, Escape, close-event, refnum, and error semantics remain unvalidated"),
    "Three Button Dialog CORE.vi": ("partial", "Print and both lvkit descriptions establish visible initialization sequences, FP.Closeable wiring, geometry/property phases, and connector choice ordering; modal/event/shortcut/Escape/Panel Close/refnum/UI timing semantics remain unvalidated"),
    "Three Button Dialog.vi": ("partial", "Print and both lvkit descriptions establish direct wrapper wiring to CORE; modal/event/UI semantics remain unvalidated"),
    "2_SUP_Ecart_lu_ecr_VDéviée.vi": ("failed", "lvkit loses output-cluster and per-channel orange routing"),
    "2_SUP_Ecart_lu_ecr_VDirecte.vi": ("failed", "lvkit emits abs(0) and None output instead of cluster behavior"),
    "2_SUP_Graph _Radioprot.vi": ("failed", "lvkit has unresolved quotient/remainder, empty cases, and runtime NameError"),
    "2_SUP_Journal_des _erreurs.vi": ("partial", "diagram captured; generated code fails at spreadsheet-file terminal resolution"),
    "2_SUP_marche_defaut_VIDE.vi": ("partial", "core boolean graph matches lvkit and synthetic truth table, but no deployable reconstruction"),
    "3_SUP_en_défaut_alims.vi": ("failed", "lvkit collapses input logic and outputs to None; H4/H5 mapping remains a review item"),
    "Error Code Database.vi": ("open", "block diagram is password-protected; visual behavior remains blocked"),
    "Moteurs SdC GoTo.vi": ("failed", "generated motor translation has empty cases, misrouted arguments, and placeholders"),
    "Validate.vi": ("partial", "Print and both lvkit description contexts show invalid-ref rejection, Strip Path, and exact .LNK/.lnk comparisons; generated lvkit Python remains unresolved and is not validating evidence"),
}
VISUAL_OVERRIDES = {
    "Error Code Database.vi": (
        "BLOCKED_VISUAL",
        "The LabVIEW export contains connector/front-panel images only; the block diagram is password-protected.",
    ),
}
DOMAIN_MODELS = {
    "0_SUP_ELYSE.vi": "supervision_reconstruction.domain.supervision_orchestrator",
    "1_SUP_INIT_NI6602.vi": "supervision_reconstruction.domain.ni6602",
    "1_SUP_PROFILS XY.vi": "supervision_reconstruction.domain.profiles",
    "1_SUP_WRITE_NI6602.vi": "supervision_reconstruction.domain.ni6602",
    "Initialize.vi": "supervision_reconstruction.domain.file_dialog",
    "Check Special Tags.vi": "supervision_reconstruction.domain.message_text",
    "Find Tag.vi": "supervision_reconstruction.domain.message_text",
    "Format Message String.vi": "supervision_reconstruction.domain.message_text",
    "Search and Replace Pattern.vi": "supervision_reconstruction.domain.message_text",
    "BuildHelpPath.vi": "supervision_reconstruction.domain.help_paths",
    "GetHelpDir.vi": "supervision_reconstruction.domain.help_paths",
    "FW102x Error Message.vi": "supervision_reconstruction.domain.fw102x_errors",
    "FW102x IVI Error Converter.vi": "supervision_reconstruction.domain.fw102x_errors",
    "FW102x Close.vi": "supervision_reconstruction.domain.fw102x_operations",
    "FW102x Get Position.vi": "supervision_reconstruction.domain.fw102x_operations",
    "FW102x Initialize.vi": "supervision_reconstruction.domain.fw102x_operations",
    "FW102x Set Position.vi": "supervision_reconstruction.domain.fw102x_operations",
    "Convert property node font to graphics font.vi": "supervision_reconstruction.domain.font_ui",
    "Longest Line Length in Pixels.vi": "supervision_reconstruction.domain.font_ui",
    "Set Bold Text.vi": "supervision_reconstruction.domain.font_ui",
    "Add Item.vi": "supervision_reconstruction.domain.tree_plans",
    "Directory to Tree.vi": "supervision_reconstruction.domain.tree_plans",
    "Error Code Database.vi": "supervision_reconstruction.domain.error_code_database",
    "sous vi LigneCentroide2.vi": "supervision_reconstruction.domain.application_plans",
    "Init_Open_Close.vi": "supervision_reconstruction.domain.application_plans",
    "Details Display Dialog.vi": "supervision_reconstruction.domain.application_plans",
    "General Error Handler CORE.vi": "supervision_reconstruction.domain.dialog_error",
    "General Error Handler.vi": "supervision_reconstruction.domain.dialog_error",
    "Not Found Dialog.vi": "supervision_reconstruction.domain.dialog_error",
    "Three Button Dialog CORE.vi": "supervision_reconstruction.domain.dialog_error",
    "Three Button Dialog.vi": "supervision_reconstruction.domain.dialog_error",
    "2_SUP_Ecart_lu_ecr_VDirecte.vi": "supervision_reconstruction.domain.deviation",
    "2_SUP_Ecart_lu_ecr_VDéviée.vi": "supervision_reconstruction.domain.deviation",
    "2_SUP_Graph _Radioprot.vi": "supervision_reconstruction.domain.radioprotection",
    "2_SUP_Journal_des _erreurs.vi": "supervision_reconstruction.domain.journal",
    "2_SUP_marche_defaut_VIDE.vi": "supervision_reconstruction.domain.vacuum",
    "3_SUP_en_défaut_alims.vi": "supervision_reconstruction.domain.power_supplies",
    "Moteurs SdC GoTo.vi": "supervision_reconstruction.domain.motor_planner",
    "Validate.vi": "supervision_reconstruction.domain.file_dialog",
}
SCREENSHOT_PREFIXES = {
    "1_SUP_INIT_NI6602.vi": ["1_SUP_INIT_NI6602_"],
    "1_SUP_PROFILS XY.vi": ["1_SUP_PROFILS_XY_"],
    "1_SUP_WRITE_NI6602.vi": ["1_SUP_WRITE_NI6602_"],
    "2_SUP_Ecart_lu_ecr_VDéviée.vi": ["2_SUP_Ecart_lu_ecr_VDeviee_"],
    "2_SUP_Ecart_lu_ecr_VDirecte.vi": ["2_SUP_Ecart_lu_ecr_VDirecte_"],
    "2_SUP_Graph _Radioprot.vi": ["2_SUP_Graph_Radioprot_"],
    "2_SUP_Journal_des _erreurs.vi": ["2_SUP_Journal_des_erreurs_"],
    "2_SUP_marche_defaut_VIDE.vi": ["2_SUP_marche_defaut_VIDE_"],
    "3_SUP_en_défaut_alims.vi": ["3_SUP_en_defaut_alims_"],
    "Moteurs SdC GoTo.vi": ["Moteurs_SdC_GoTo_"],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def raster_dimensions(path: Path) -> dict[str, Any]:
    """Return dimensions from actual file bytes, not an unreliable filename suffix."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return {"width": width, "height": height, "format": "png"}
    if data[:2] == b"\xff\xd8":
        offset = 2
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            while offset < len(data) and data[offset] == 0xFF:
                offset += 1
            marker = data[offset]
            offset += 1
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            segment_length = struct.unpack(">H", data[offset:offset + 2])[0]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                return {"width": width, "height": height, "format": "jpeg"}
            offset += segment_length
    raise ValueError(f"unsupported raster data: {path}")


def rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def artifact(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
    if path.suffix.lower() == ".png":
        data["dimensions"] = raster_dimensions(path)
    return data


def module_name(name: str) -> str:
    base = unicodedata.normalize("NFKD", Path(name).stem).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9]+", "_", base).strip("_").lower()
    return f"vi_{base}" if not base or base[0].isdigit() else base


def walk_instances(value: Any, path: str = "$") -> Iterator[dict[str, str]]:
    """Yield every nested lvkit instance with its JSON location."""
    if isinstance(value, dict):
        if value.get("kind") == "instance":
            name = value.get("qualified_name") or value.get("name")
            if name:
                yield {"name": str(name), "json_path": path}
        for key, child in value.items():
            yield from walk_instances(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_instances(child, f"{path}[{index}]")


def extract_dependencies_from_data(description: dict[str, Any]) -> list[dict[str, str]]:
    return sorted(walk_instances(description), key=lambda entry: (entry["name"].casefold(), entry["json_path"]))


def extract_dependencies(description_path: Path | None) -> list[dict[str, str]]:
    if description_path is None or not description_path.is_file():
        return []
    return extract_dependencies_from_data(json.loads(description_path.read_text(encoding="utf-8")))


def screenshot_evidence(vi: str) -> list[dict[str, Any]]:
    normalized = unicodedata.normalize("NFKD", Path(vi).stem).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_") + "_"
    prefixes = [*SCREENSHOT_PREFIXES.get(vi, []), normalized]
    return [
        artifact(path)
        for path in sorted((ANALYSIS / "screenshots").glob("*.png"))
        if any(path.name.casefold().startswith(prefix.casefold()) for prefix in prefixes)
    ]


def parse_export_sections(document: Path) -> list[dict[str, Any]]:
    """Associate hidden-frame PNGs with their named VI HTML section."""
    # LabVIEW 2012 print exports have no charset declaration and use the local
    # Windows code page for French filenames.
    text = document.read_text(encoding="cp1252", errors="strict")
    anchors = list(re.finditer(r'<A\s+NAME="[^"]+"></A>\s*<H2>(.*?)</H2>', text, re.IGNORECASE | re.DOTALL))
    sections: list[dict[str, Any]] = []
    for index, anchor in enumerate(anchors):
        end = anchors[index + 1].start() if index + 1 < len(anchors) else len(text)
        names = re.findall(r'<IMG\s+SRC="([^"]+)"', text[anchor.end():end], re.IGNORECASE)
        # LabVIEW sanitizes the NAME anchor (for example `VD_vi_e`) but keeps
        # the authoritative VI name in H2/ALT. Use the latter for matching.
        sections.append({"vi_name": anchor.group(1), "frames": [artifact(EXPORT_ROOT / name) for name in names]})
    return sections


def build_export_manifest() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    documents = sorted(EXPORT_ROOT.glob("*.html"), key=lambda path: path.name.casefold())
    sections_by_vi: dict[str, list[dict[str, Any]]] = {}
    document_records: list[dict[str, Any]] = []
    for document in documents:
        sections = parse_export_sections(document)
        document_metadata = artifact(document)
        document_records.append({"document": document_metadata, "sections": sections})
        for section in sections:
            sections_by_vi.setdefault(section["vi_name"], []).append({"document": document_metadata, "frames": section["frames"]})
    pngs = sorted(EXPORT_ROOT.glob("*.png"), key=lambda path: path.name.casefold())
    return ({
        "schema_version": 1,
        "source_directory": rel(EXPORT_ROOT),
        "summary": {"html_documents": len(documents), "png_frames": len(pngs)},
        "documents": document_records,
        "all_png_frames": [artifact(path) for path in pngs],
    }, sections_by_vi)


def section_evidence_identity(name: str, sections: list[dict[str, Any]]) -> str:
    """Stable identity for a print-export section whose source file is unknown."""
    material = [name]
    for section in sections:
        material.append(section["document"]["sha256"])
        material.extend(frame["sha256"] for frame in section["frames"])
    digest = hashlib.sha256("|".join(material).encode("utf-8")).hexdigest()
    return f"labview-export:{digest[:32]}"


def source_candidates() -> dict[str, list[tuple[Path, str]]]:
    """Index only copied source and the LabVIEW 2020 installation used by lvkit."""
    candidates: dict[str, list[tuple[Path, str]]] = {}
    for root, provenance in ((SUPERVISION / "extracted" / "PILOTAGE_ELYSE_SUP", "copied"), (LABVIEW_2020, "installed")):
        for extension in ("*.vi", "*.ctl"):
            for path in root.rglob(extension):
                candidates.setdefault(path.name.casefold(), []).append((path, provenance))
    return candidates


def resolve_source(name: str, candidates: dict[str, list[tuple[Path, str]]]) -> dict[str, Any]:
    """Resolve exact name only when one copied or installed candidate exists.

    Copied artifacts take precedence over installation artifacts; duplicates within
    either tier are deliberately left unresolved rather than guessed.
    """
    matches = candidates.get(name.casefold(), [])
    copied = [path for path, provenance in matches if provenance == "copied"]
    installed = [path for path, provenance in matches if provenance == "installed"]
    if len(copied) == 1:
        path = copied[0]
        kind = "copied_vendor" if "external_dependencies" in path.parts else "copied_source"
        return {"source_status": "resolved", "source": artifact(path), "boundary_kind": kind}
    if not copied and len(installed) == 1:
        return {"source_status": "resolved", "source": artifact(installed[0]), "boundary_kind": "labview_builtin"}
    reason = "no copied or installed candidate" if not matches else "ambiguous candidate basename"
    return {
        "source_status": "unresolved",
        "source": None,
        "boundary_kind": "unresolved_dependency",
        "resolution_reason": reason,
        "candidate_paths": [rel(path) for path, _ in matches],
    }


def non_vi_inventory(exports: dict[str, list[dict[str, Any]]], candidates: dict[str, list[tuple[Path, str]]]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for name, sections in sorted(exports.items(), key=lambda item: item[0].casefold()):
        suffix = Path(name).suffix.lower()
        if suffix == ".ctl":
            classification = "CTL"
        elif name in GLOBAL_DIAGRAMLESS_SECTIONS:
            classification = "EXPECTED_DIAGRAMLESS_GLOBAL"
        else:
            continue
        resolved = resolve_source(name, candidates)
        identity = (
            f"supervision-control:{resolved['source']['sha256'].lower()[:16]}"
            if resolved["source_status"] == "resolved"
            else section_evidence_identity(name, sections)
        )
        inventory.append({
            "identity": identity,
            "section_name": name,
            "classification": classification,
            "source_status": resolved["source_status"],
            "source": resolved["source"],
            "boundary": {"kind": resolved["boundary_kind"], "intended_as": "non_executable_evidence"},
            "resolution_reason": resolved.get("resolution_reason"),
            "candidate_paths": resolved.get("candidate_paths", []),
            "labview_hidden_frames": {"manifest": rel(EXPORT_MANIFEST), "sections": sections},
        })
    return inventory


def load_contexts() -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for context, directory in LVKIT_CONTEXTS.items():
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        result[context] = {item["vi"]: item for item in manifest["items"]}
    return result


def context_evidence(context: str, item: dict[str, Any] | None) -> dict[str, Any]:
    directory = LVKIT_CONTEXTS[context]
    manifest_path = directory / "manifest.json"
    if item is None:
        return {"manifest": artifact(manifest_path), "item_present": False}
    description = Path(item["description_path"])
    log = directory / "logs" / f"{description.stem}.json"
    return {
        "manifest": artifact(manifest_path), "item_present": True,
        "description": artifact(description), "render": artifact(Path(item["render_path"])), "log": artifact(log),
        "generation_exit": item.get("generate_exit"), "compile_ok": item.get("compile_ok"),
        "python_file_count": item.get("python_file_count"),
        "primitive_resolution_needed": item.get("primitive_resolution_needed"),
        "vilib_resolution_needed": item.get("vilib_resolution_needed"),
        "pass_statements": item.get("pass_statements"), "none_assignments": item.get("none_assignments"),
        "abs_zero": item.get("abs_zero"),
        "generated_python": [artifact(Path(value)) for value in item.get("python_files", [])],
    }


def context_verdict(base: dict[str, Any] | None, minimal: dict[str, Any] | None) -> dict[str, Any]:
    if base is None or minimal is None:
        return {"verdict": "MISSING_CONTEXT", "differing_fields": [], "note": "At least one lvkit context lacks this VI."}
    fields = ("generate_exit", "compile_ok", "python_file_count", "primitive_resolution_needed", "vilib_resolution_needed", "pass_statements", "none_assignments", "abs_zero")
    differing = [field for field in fields if base.get(field) != minimal.get(field)]
    return {
        "verdict": "CONTEXT_DISAGREEMENT" if differing else "CONTEXT_AGREEMENT_NOT_VALIDATION",
        "differing_fields": differing,
        "note": "Agreement between lvkit contexts is not behavioral validation against LabVIEW.",
    }


def motor_artifacts() -> list[dict[str, Any]]:
    roots = [LVKIT_ROOT / "motor_minimal_vilib", LVKIT_ROOT / "motor_minimal_vilib_v2"]
    return [
        artifact(path) for root in roots for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".py", ".svg"} and "__pycache__" not in path.parts
    ]


def source_record(path: Path, items: dict[str, dict[str, dict[str, Any]]], exports: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    vi = path.name
    identity = f"supervision-vi:{sha256(path).lower()[:16]}"
    base, minimal = items["base"].get(vi), items["minimal_vilib"].get(vi)
    if vi in STATE_OVERRIDES:
        state, rationale = STATE_OVERRIDES[vi]
    elif minimal is not None and minimal.get("generate_exit") != 0:
        state, rationale = "failed", "lvkit minimal-vilib Python generation command failed; visual cross-validation is incomplete"
    else:
        state, rationale = "open", "parsed artifacts exist but no completed LabVIEW/lvkit behavioral cross-validation"
    visual_status, visual_rationale = VISUAL_OVERRIDES.get(
        vi, ("EXPORTED", "Hidden-frame LabVIEW export is evidence only; it does not establish semantic completeness.")
    )
    dependencies = {
        (entry["name"], entry["json_path"])
        for item in (base, minimal) if item is not None
        for entry in extract_dependencies(Path(item["description_path"]))
    }
    if vi == MOTOR.name and not dependencies:
        dependencies = {(name, "$.manual_motor_observation") for name in ["RelativeMove.vi", "GetErrorMsg.vi", "GetMotionDone.vi", "GetPosition.vi", "AbortMotion.vi"]}
    return {
        "identity": identity, "vi_name": vi, "section_classification": "VI", "module": f"supervision_reconstruction.catalog.{module_name(vi)}",
        "record_scope": "application_scope", "source": artifact(path), "source_status": "resolved",
        "boundary": {"kind": "application_scope", "intended_as": "application_reconstruction"},
        "conversion_state": state, "state_rationale": rationale,
        "visual_status": visual_status, "visual_rationale": visual_rationale,
        "implementation": "stub_raises_not_implemented",
        "domain_model": DOMAIN_MODELS.get(vi),
        "evidence": {
            "reports": [rel(ANALYSIS / "LOCAL_LABVIEW_2020_FINDINGS.md"), rel(ANALYSIS / "lvkit_eval" / "CROSS_VALIDATION_STATUS.md")],
            "screenshots": screenshot_evidence(vi),
            "labview_hidden_frames": {"manifest": rel(EXPORT_MANIFEST), "sections": exports.get(vi, [])},
            "lvkit": {
                "contexts": {"base": context_evidence("base", base), "minimal_vilib": context_evidence("minimal_vilib", minimal)},
                "context_verdict": context_verdict(base, minimal),
            },
            "standalone_motor_artifacts": motor_artifacts() if vi == MOTOR.name else [],
        },
        "dependencies": {
            "parsed_instances": [{"name": name, "json_path": json_path} for name, json_path in sorted(dependencies, key=lambda value: (value[0].casefold(), value[1]))],
            "note": "Every nested lvkit JSON body is traversed. Parsed instances are static evidence, not a proven runtime call graph.",
        },
    }


def dependency_record(name: str, sections: list[dict[str, Any]], candidates: dict[str, list[tuple[Path, str]]]) -> dict[str, Any]:
    """Catalog an exported dependency as a contract boundary, never an implementation."""
    resolved = resolve_source(name, candidates)
    identity = (
        f"supervision-vi:{resolved['source']['sha256'].lower()[:16]}"
        if resolved["source_status"] == "resolved"
        else section_evidence_identity(name, sections)
    )
    return {
        "identity": identity,
        "vi_name": name,
        "section_classification": "VI",
        "module": f"supervision_reconstruction.catalog.{module_name(name)}",
        "record_scope": "dependency_scope",
        "source": resolved["source"],
        "source_status": resolved["source_status"],
        "resolution_reason": resolved.get("resolution_reason"),
        "candidate_paths": resolved.get("candidate_paths", []),
        "boundary": {"kind": resolved["boundary_kind"], "intended_as": "black_box_adapter_contract"},
        "conversion_state": "open",
        "state_rationale": "Dependency contract is exported visually but has no approved behavioral reconstruction.",
        "visual_status": "EXPORTED",
        "visual_rationale": "Hidden-frame LabVIEW export is evidence only; it does not establish semantic completeness.",
        "implementation": "stub_raises_not_implemented",
        "domain_model": None,
        "evidence": {
            "reports": [rel(ANALYSIS / "lvkit_eval" / "CROSS_VALIDATION_STATUS.md")],
            "screenshots": [],
            "labview_hidden_frames": {"manifest": rel(EXPORT_MANIFEST), "sections": sections},
            "lvkit": {
                "contexts": {
                    context: {"manifest": artifact(directory / "manifest.json"), "item_present": False}
                    for context, directory in LVKIT_CONTEXTS.items()
                },
                "context_verdict": {
                    "verdict": "NOT_BATCHED_DEPENDENCY",
                    "differing_fields": [],
                    "note": "The 38-VI lvkit batches did not include this dependency section.",
                },
            },
            "standalone_motor_artifacts": [],
        },
        "dependencies": {
            "parsed_instances": [],
            "note": "No dependency behavior is inferred from export presence alone; use this record as an adapter/contract boundary.",
        },
    }


def write_stub(record: dict[str, Any]) -> None:
    module = record["module"].rsplit(".", 1)[-1]
    (CATALOG / f"{module}.py").write_text(
        "\"\"\"Non-executable reconstruction stub for " + record["vi_name"] + ".\"\"\"\n\n"
        "from __future__ import annotations\n\nfrom .runtime import unverified_behavior\n\n"
        f"IDENTITY = {record['identity']!r}\nSOURCE_SHA256 = {record['source']['sha256'] if record['source'] else None!r}\n"
        f"CONVERSION_STATE = {record['conversion_state']!r}\nDOMAIN_MODEL = {record['domain_model']!r}\n\n"
        "def reconstruct(*args: object, **kwargs: object) -> None:\n"
        "    \"\"\"Block execution until this VI has a reviewed, safe reconstruction.\"\"\"\n"
        "    del args, kwargs\n    unverified_behavior(IDENTITY, CONVERSION_STATE)\n",
        encoding="utf-8",
    )


def main() -> None:
    export_manifest, exports = build_export_manifest()
    EXPORT_MANIFEST.write_text(json.dumps(export_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    items = load_contexts()
    source_paths = sorted(VI_ROOT.glob("*.vi"), key=lambda path: path.name.casefold()) + [MOTOR]
    application_records = [source_record(path, items, exports) for path in source_paths]
    application_names = {record["vi_name"] for record in application_records}
    candidates = source_candidates()
    dependency_records = [
        dependency_record(name, sections, candidates)
        for name, sections in sorted(exports.items(), key=lambda item: item[0].casefold())
        if Path(name).suffix.lower() == ".vi" and name not in application_names and name not in GLOBAL_DIAGRAMLESS_SECTIONS
    ]
    records = application_records + dependency_records
    non_vi_records = non_vi_inventory(exports, candidates)
    if len({record["identity"] for record in records}) != len(records) or len({record["module"] for record in records}) != len(records):
        raise ValueError("VI identities or module names are not unique")
    catalog = {
        "schema_version": 3,
        "scope": {
            "application_scope": "38 root VIs from SUPERVISION.llb plus Moteurs SdC GoTo.vi",
            "dependency_scope": "every additional .vi section in root_and_dependencies_all_hidden.html",
            "non_vi_inventory": "all .ctl sections and expected diagramless global sections",
        },
        "safety": "non-executable; every generated stub raises NotImplementedError",
        "records": records,
        "non_vi_evidence": non_vi_records,
    }
    (CATALOG / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for record in records:
        write_stub(record)
    print(
        f"wrote {len(records)} VI records ({len(application_records)} application, {len(dependency_records)} dependency), "
        f"{len(non_vi_records)} non-VI records, stubs, and {export_manifest['summary']['png_frames']} export frames"
    )


if __name__ == "__main__":
    main()
