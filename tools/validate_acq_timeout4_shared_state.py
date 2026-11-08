"""Offline proof of the native copied-ACQ Timeout frame-4 telemetry hook.

No VI execution, UI control, PSP/VISA/NI operation, or network access. A hook
connected to a queue is not proof of queue ownership or Python/Everest delivery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from validate_acq_publication_refactor import call_port
from validate_acq_runtime_io_frame import heap_type
from validate_acq_shared_state_helpers import (
    BANKS,
    COLLECTOR,
    ERROR_SHAPE,
    Export,
    node,
    require,
    validate_pressure_inclusion,
)
from validate_acq_shared_state_helpers import (
    audit as audit_helpers,
)

BEFORE = "xp_snapshot_before_timeout4_20261013"
AFTER = "xp_snapshot_timeout4_safeopen_20261013"
FILES = ("vi.xml", "vi_FPHb.xml", "vi_BDHb.xml")
PINS = {
    BEFORE: (
        "057C999EA75F6739B206C7713E2F14482FF6FECC81E3DAB3D442FF68AA1BB657",
        "386486FD80D694E4502C9258DD459D8E796D9FD4FDE1C3B4F28A9AC29CA27488",
        "0C0B7A9EFE306C659BD1163B1072C4E08F5033F6859BC1F8AF69D0B9F73EF57A",
        "26BB55C5B528D17FFB5F752E026C9D5703D842BD1F3B00470ECCB5E81A3EB251",
    ),
    AFTER: (
        "4DF22D4E0EB63ECA9025068CAAF4C49236017027ADF1CF87A862A88AF1C010FB",
        "5C40296719C2B225FA05C33A5D6DB885FC8455CC8970C103C7E63828CCF2643C",
        "D6BD44E68473C0AFBE693A4FC40C10AF59822929AF9D4F90E813E0F14B413FE1",
        "3BA3A2A22283B64DEC7449EDCDA89B8C419DF93D27688984F34550AB1DF6B2B8",
    ),
}
OLD_FRAMES = ("10115", "10526", "22247", "42045")
NEW_FRAME = "8210"
NEW_CALL = "18502"
ERROR_CONTROL = "67359"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


class Types:
    """Resolve relocated heap/flat IDs; retain descriptor data and labels."""

    def __init__(self, metadata):
        section = metadata.find("VCTP/Section")
        self.flat = section.findall("TypeDesc")
        self.top = {
            int(n.get("Index")): int(n.get("FlatTypeID"))
            for n in section.find("TopLevel")
        }
        self.shift = int(metadata.find("DTHP/Section/TypeDescSlice").get("IndexShift"))
        self.cache = {}

    def heap(self, index):
        return self.flat_type(self.top[self.shift + index - 1])

    def consolidated(self, index):
        return self.flat_type(self.top[index])

    def flat_type(self, index, trail=()):
        require(
            index not in trail, "recursive type descriptor requires separate review"
        )
        if index not in self.cache:
            self.cache[index] = self.element(self.flat[index], trail + (index,))
        return self.cache[index]

    def element(self, item, trail):
        if item.tag == "TypeDesc" and "TypeID" in item.attrib:
            return "resolved-TypeDesc", self.flat_type(int(item.get("TypeID")), trail)
        return (
            item.tag,
            tuple(sorted(item.attrib.items())),
            (item.text or "").strip(),
            tuple(self.element(c, trail) for c in item),
        )


# Diagram view, geometry, and compiler clump/index allocation are not behavior.
# No execution flag, primitive ID, literal, selector, direction, or net is dropped.
PRESENTATION = {
    "bounds",
    "pBounds",
    "termBounds",
    "contRect",
    "dIdx",
    "clumpNum",
    "firstNodeIdx",
}
# Only these observed native-editor bookkeeping deltas are normalized. This
# does not grant arbitrary object-flag changes elsewhere in the saved graph.
BOOKKEEPING_FLAGS = {
    ("diag", "53"): {896, 17280},
    ("timeout-sequence", "10111"): {268501888, 268518272},
    **{
        ("gRef", uid): {4608, 512}
        for uid in ("14489", "14473", "14467", "14442", "14436", "14405", "14360")
    },
}


def objects(root):
    items = [n for n in root.iter() if n.get("class") and n.get("uid")]
    result = {n.get("uid"): n for n in items}
    require(len(items) == len(result), "ambiguous saved object UID")
    return result


def signature(item, types, *, at_root=True, parent_class=None, parent_uid=None):
    if not at_root and item.get("class") and item.get("uid"):
        return "object-reference", item.tag, tuple(sorted(item.attrib.items()))
    value = (item.text or "").strip()
    if len(item) == 0:
        match = re.fullmatch(r"TypeID\((\d+)\)", value)
        if match:
            value = types.heap(int(match[1]))
        elif item.tag in {"oMId", "overrideType"} and value:
            value = types.consolidated(int(value, 16))
        elif item.tag == "objFlags" and (parent_class, parent_uid) in BOOKKEEPING_FLAGS:
            allowed = BOOKKEEPING_FLAGS[parent_class, parent_uid]
            require(int(value) in allowed, "unreviewed native-editor object flags")
            value = str(min(allowed))
    children = list(item)
    attrs = dict(item.attrib)
    if item.tag == "diagramList" and parent_class == "timeout-sequence":
        children = children[:4]
        attrs["elements"] = "4"
    klass = (
        "timeout-sequence"
        if item.get("class") == "sequence" and item.get("uid") == "10111"
        else item.get("class", parent_class)
    )
    owner_uid = item.get("uid", parent_uid)
    # selLabel text caches the displayed case/event name. Actual selectors and
    # event specifications remain checked on their structural objects.
    excluded = PRESENTATION | (
        {"textRec"} if item.get("class") == "selLabel" else set()
    )
    return (
        item.tag,
        tuple(sorted(attrs.items())),
        value,
        tuple(
            signature(c, types, at_root=False, parent_class=klass, parent_uid=owner_uid)
            for c in children
            if c.tag not in excluded
        ),
    )


def validate_preservation(before, after):
    old, new = objects(before.bd), objects(after.bd)
    require(set(old) <= set(new), "existing block-diagram object removed")
    old_types, new_types = Types(before.metadata), Types(after.metadata)
    for uid, item in old.items():
        require(
            signature(item, old_types) == signature(new[uid], new_types),
            "existing object semantics/topology changed: " + uid,
        )
    old_diags = {u for u, n in old.items() if n.get("class") == "diag"}
    new_diags = {u for u, n in new.items() if n.get("class") == "diag"}
    require(
        len(old_diags) == 475 and new_diags == old_diags | {NEW_FRAME},
        "unexpected added/removed diagram",
    )
    require(
        set(after.calls.items()) - set(before.calls.items())
        == {(NEW_CALL, COLLECTOR + ".vi")},
        "unexpected new subVI call",
    )
    require(
        set(before.calls.items()) <= set(after.calls.items()),
        "old subVI dependency changed",
    )
    # The front panel adds an indicator, not a new command or connector.
    old_controls = {
        n.get("uid"): n for n in before.fp.iter() if n.get("class") == "fPDCO"
    }
    new_controls = {
        n.get("uid"): n for n in after.fp.iter() if n.get("class") == "fPDCO"
    }
    require(
        set(new_controls) == set(old_controls) | {ERROR_CONTROL},
        "unexpected front-panel control added/removed",
    )
    for uid, control in old_controls.items():
        require(
            signature(control, old_types) == signature(new_controls[uid], new_types),
            "original front-panel control contract changed: " + uid,
        )
    return len(old), len(old_diags), len(old_controls)


def validate_hook(before, after):
    old_seq = node(before.bd, "sequence", "10111")
    new_seq = node(after.bd, "sequence", "10111")
    require(
        tuple(n.get("uid") for n in old_seq.findall("diagramList/*")) == OLD_FRAMES,
        "unreviewed old Timeout frame order",
    )
    require(
        tuple(n.get("uid") for n in new_seq.findall("diagramList/*"))
        == OLD_FRAMES + (NEW_FRAME,),
        "telemetry frame must follow all four original frames",
    )
    timeout = node(after.bd, "diag", "53")
    require(
        any(n is new_seq for n in timeout.findall("zPlaneList/*")),
        "telemetry sequence not in Timeout event",
    )
    event = node(after.bd, "eventStruct", "43")
    require(
        event.find("diagramList/*") is timeout,
        "telemetry not in first Timeout event diagram",
    )
    frame = node(after.bd, "diag", NEW_FRAME)
    require(
        Counter((n.get("class"), n.get("uid")) for n in frame.findall("zPlaneList/*"))
        == Counter(
            (
                ("label", "69780"),
                (None, "67361"),
                ("ctlRefConst", "37793"),
                ("iUse", NEW_CALL),
            )
        ),
        "unexpected operation inside telemetry frame",
    )
    ref = node(after.bd, "ctlRefConst", "37793")
    require(
        ref.findtext("label/textRec/text") == '"ce VI"'
        and ref.findtext("shortCount") == "2",
        "self-VI reference changed",
    )
    ref_type, _ = heap_type(
        after.metadata, int(ref.findtext("termList/*/dco/typeDesc")[7:-1])
    )
    require(
        ref_type.get("Type") == "Refnum"
        and ref_type.get("RefType") == "LVObjCtl"
        and ref_type.get("CtlFlags") == "0x0002"
        and ref_type.get("HasItem") == "0",
        "source must be targetless native self-VI Server reference",
    )
    require(
        Types(after.metadata).consolidated(int(ref.findtext("oMId"), 16))
        == (
            "TypeDesc",
            (
                ("CtlFlags", "0x0002"),
                ("Format", "inline"),
                ("HasItem", "0"),
                ("RefType", "LVObjCtl"),
                ("Type", "Refnum"),
            ),
            "",
            (),
        ),
        "self-reference object class changed",
    )
    call = node(after.bd, "iUse", NEW_CALL)
    require(after.calls.get(NEW_CALL) == COLLECTOR + ".vi", "wrong collector called")
    require(
        call_port(call, 5) == "18831" and call_port(call, 0) == "18568",
        "collector connector identity changed",
    )
    nets = [
        (tuple(t.get("uid") for t in n.findall("termList/*")), n.findtext("state"))
        for n in frame.findall("signalList/*")
    ]
    require(
        Counter(nets)
        == Counter(((("37840", "18831"), "1"), (("18568", "67361"), "1"))),
        "self-reference/diagnostic wiring changed",
    )
    terminal = node(after.bd, "fPTerm", "67361")
    require(
        terminal.find("dco").get("uid") == ERROR_CONTROL,
        "error output must go only to its dedicated indicator",
    )
    control = node(after.fp, "fPDCO", ERROR_CONTROL)
    require(
        control.findtext("objFlags") == "1"
        and control.findtext("conNum", "-1") == "-1",
        "telemetry diagnostic must be a non-connector indicator",
    )
    require(
        after.shape(int(control.findtext("typeDesc")[7:-1])) == ERROR_SHAPE,
        "telemetry diagnostic error type changed",
    )
    label = [
        p.findtext("textRec/text")
        for p in control.findall("ddo/partsList/*")
        if p.get("class") == "label" and p.findtext("partID") == "16"
    ]
    require(
        label == ['"Shared-state telemetry error"'],
        "dedicated diagnostic label changed",
    )
    exec_before = before.metadata.find("LVSR/Section/Execution")
    exec_after = after.metadata.find("LVSR/Section/Execution")
    require(exec_after.get("RunOnOpen") == "0", "copied main must not run when opened")
    require(
        {k: v for k, v in exec_before.attrib.items() if k != "RunOnOpen"}
        == {k: v for k, v in exec_after.attrib.items() if k != "RunOnOpen"},
        "unexpected execution-setting change",
    )
    require(
        exec_after.get("State") == "1"
        and all(
            exec_after.get(k) == "0"
            for k in ("BadSignal", "BadNode", "BadSubVILink", "BadSubVI", "BadCompile")
        ),
        "saved copied main has compilation errors",
    )


def validate(before, after, collector):
    counts = validate_preservation(before, after)
    validate_hook(before, after)
    pressure = validate_pressure_inclusion(collector, after.bd)
    return {
        "scope": "saved native frame-4 hook and bounded preservation audit",
        "main_timeout_integrated": True,
        "outer_frame": 2,
        "event": "Timeout",
        "telemetry_frame": 4,
        "sequence_uid": "10111",
        "new_diagram_uid": NEW_FRAME,
        "collector_call_uid": NEW_CALL,
        "preserved_bd_objects": counts[0],
        "preserved_diagrams": counts[1],
        "preserved_front_panel_controls": counts[2],
        "original_timeout_frames_preserved": list(OLD_FRAMES),
        "banks": list(BANKS),
        "bank_count": len(BANKS),
        "pressure": pressure,
        "run_on_open": False,
        "saved_compile_errors": 0,
        "telemetry_error_separate_from_stop": True,
        "telemetry_complete": False,
        "native_vi_executed": False,
        "new_transport_delivered": False,
        "queue_owner_connected": False,
        "consumer_connected": False,
        "limitations": [
            "Collector reads local ACQ controls sequentially, "
            "not an atomic PSP snapshot.",
            "Queue owner/consumer for ELYSE_ACQ_SHARED_STATE_LATEST_V1 remain absent.",
            "No new aggregate XML/JSON delivery to Python/Everest has been proven.",
            "Main/helper execution, read timing and comparison "
            "with PSP remain untested.",
            "20-ms event timeout is not a guaranteed 20-ms sampling period.",
            "Pressure numeric fields do not include discarded "
            "TPG sensor Status outputs.",
            "Original source contains hardware writes; this copy "
            "must not run alongside production.",
            "Compiler PropTypesIssues=1 remains inherited despite "
            "zero native error-list entries.",
            "Geometry, selected views/cached selector labels, compiler clump/index "
            "allocation and nine fixed editor-flag deltas are excluded "
            "from the preservation signature.",
            "Front-panel check covers original control UID/type/direction/connector "
            "contracts, not unparsed DFDS default-value resources.",
        ],
    }


def audit(root, helper_root, library, main_fp):
    root = Path(root)
    exports = []
    for dirname in (BEFORE, AFTER):
        paths = [root / dirname / "ACQUISITION.llb"] + [
            root / dirname / "export/0_ACQ_ELYSE" / f for f in FILES
        ]
        require(
            tuple(digest(p) for p in paths) == PINS[dirname],
            "unreviewed main source/export",
        )
        exports.append(Export(root / dirname / "export/0_ACQ_ELYSE"))
    old_members = {p.name: digest(p) for p in (root / BEFORE / "members").glob("*.vi")}
    new_members = {p.name: digest(p) for p in (root / AFTER / "members").glob("*.vi")}
    require(
        len(old_members) == 17 and old_members.keys() == new_members.keys(),
        "LLB member census changed",
    )
    changed = [n for n in old_members if old_members[n] != new_members[n]]
    require(changed == ["0_ACQ_ELYSE.vi"], "non-main LLB member changed")
    helper_report = audit_helpers(helper_root, library, main_fp)
    report = validate(*exports, Export(Path(helper_root) / "export" / COLLECTOR))
    report["unchanged_llb_members"] = 16
    report["main_source_pins"] = PINS
    report["collector_source_sha256"] = helper_report["source_sha256"]
    report["validator_sha256"] = digest(__file__)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--helpers", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--main-fp", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit(args.root, args.helpers, args.library, args.main_fp)
    if args.report:
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
