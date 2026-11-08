"""Audit the native XP repair of the obsolete initialization telemetry hook.

No VI execution or network access. The 27-bank Timeout-4 snapshot remains
the telemetry source. This shim intentionally does not enqueue initialization
packets; it is not a replacement hardware/publication error handler.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from build_acq_saved_diagram_census import call_names
from build_acq_telemetry_release import GOOD, PINS
from validate_acq_publication_refactor import call_port
from validate_acq_shared_state_helpers import Export, check_execution, node, require

EVIDENCE = Path("C:/dev/ELYSE-ACQ-telemetry/2026-10-16")
NAME = "ACQ_Telemetry_Publish"
BEFORE = EVIDENCE / "xp_readback"
AFTER = EVIDENCE / "startup_error1100_readback"
SOURCE = AFTER / (NAME + ".vi")
SOURCE_SHA256 = "10D9D3055CE9C268EA33302B29617833293816DEC28918904AF92A4FFB9FE943"
RESOURCE_SHA256 = {
    "bd": "A6D0EC5096EDD2B576137EEF3CF0BA990F2B2045C660B15D5FF5F7C25A884BE8",
    "fp": "02DFD8B229F7AFFAF525BD6C3D89B190AB5EAEB2D03BE6D1E6F40947A1D3A564",
    "metadata": "1BA2456F90E6394738F6647F564EB73E5BD46D4E0805F62EF2BBBB1A6EA081FE",
}
LEGACY_CALLS = {"46110", "55269", "60695", "66371", "71603", "75904", "80767"}
CALLER_EXPORT_SHA256 = {
    "vi.xml": "5C40296719C2B225FA05C33A5D6DB885FC8455CC8970C103C7E63828CCF2643C",
    "vi_BDHb.xml": "3BA3A2A22283B64DEC7449EDCDA89B8C419DF93D27688984F34550AB1DF6B2B8",
}


class NativeExport(Export):
    def __init__(self, directory):
        self.directory = Path(directory)
        for attr, suffix in (("bd", "_BDHb"), ("fp", "_FPHb"), ("metadata", "")):
            setattr(
                self,
                attr,
                ET.parse(self.directory / (NAME + suffix + ".xml")).getroot(),
            )
        self.calls = call_names(self.metadata)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def contract(export):
    return {
        n.get("uid"): (
            int(n.findtext("conNum", "0")),
            bool(int(n.findtext("objFlags", "0")) & 1),
            export.shape(int(n.findtext("typeDesc")[7:-1])),
        )
        for n in export.fp.iter()
        if n.get("class") == "fPDCO"
    }


def wires(diagram):
    return Counter(
        tuple(t.get("uid") for t in w.findall("termList/*"))
        for w in diagram.findall("signalList/*")
    )


def validate_caller_outputs_unused(main):
    calls = {uid for uid, name in main.calls.items() if name == NAME + ".vi"}
    require(calls == LEGACY_CALLS, "legacy caller inventory changed")
    nodes = {n.get("uid"): n for n in main.bd.iter() if n.get("class") == "iUse"}
    used = Counter(
        t.get("uid")
        for s in main.bd.iter()
        if s.get("class") == "signal"
        for t in s.findall("termList/*")
    )
    # Connector 0 = telemetry error, 3 = not enqueued. Neither may participate
    # in original card/PSP error guards or other control flow.
    require(
        all(used[call_port(nodes[uid], slot)] == 0 for uid in calls for slot in (0, 3)),
        "retired helper output affects caller control flow",
    )


def validate(before, fixed):
    check_execution(fixed)
    require(
        contract(before) == contract(fixed) and len(contract(fixed)) == 6,
        "legacy connector types/directions changed",
    )
    require(not fixed.calls, "shim must not call another VI")
    structure = node(fixed.bd, "commentNode", "212")
    require(
        structure.findtext("commentMode") == "True"
        and structure.findtext("activeDiag") == "01"
        and structure.findtext("defaultDiag") == "01",
        "legacy queue body must remain disabled",
    )
    diagrams = structure.findall("diagramList/*")
    require(
        [d.get("uid") for d in diagrams] == ["358", "364"],
        "disable frame order changed",
    )
    disabled, active = diagrams
    primitives = lambda tree: Counter(  # noqa: E731
        (n.get("uid"), n.findtext("primResID"))
        for n in tree.iter()
        if n.get("class") == "prim"
    )
    require(
        primitives(disabled) == primitives(before.bd),
        "original legacy body not retained",
    )
    require(
        primitives(fixed.bd) == primitives(disabled), "operation outside retired body"
    )
    require(
        not any(
            n.get("class")
            in {
                "iUse",
                "invokeNode",
                "propertyNode",
                "gRef",
                "sharedVariableDynamicWrite",
                "sharedVariableDynamicRead",
            }
            for n in fixed.bd.iter()
        ),
        "unexpected hardware/PSP/dynamic operation",
    )
    require(
        node(active, "bDConstDCO", "613").findtext("ConstValue")
        == "00000000000000000000",
        "shim telemetry error must be no error",
    )
    require(
        node(active, "bDConstDCO", "650").findtext("ConstValue") == "01",
        "retired hook must report not enqueued=True",
    )
    require(
        wires(active) == Counter({("652", "534"): 1, ("615", "515"): 1}),
        "active shim outputs disconnected",
    )
    require(
        wires(fixed.bd.find("root")) == Counter({("535", "594"): 1, ("518", "516"): 1}),
        "output connector wiring changed",
    )
    for attr, expected in RESOURCE_SHA256.items():
        require(
            hashlib.sha256(ET.tostring(getattr(fixed, attr))).hexdigest().upper()
            == expected,
            "unreviewed native resource: " + attr,
        )


def audit():
    before = NativeExport(EVIDENCE / "startup_error1100_static" / NAME)
    fixed = NativeExport(EVIDENCE / "startup_error1100_fixed_static" / NAME)
    validate(before, fixed)
    require(digest(SOURCE) == SOURCE_SHA256, "patched native helper hash differs")
    old_files = {
        p.relative_to(BEFORE).as_posix(): digest(p)
        for p in BEFORE.rglob("*")
        if p.is_file()
    }
    new_files = {
        p.relative_to(AFTER).as_posix(): digest(p)
        for p in AFTER.rglob("*")
        if p.is_file()
    }
    require(old_files.keys() == new_files.keys(), "readback inventory changed")
    changed = [n for n in old_files if old_files[n] != new_files[n]]
    require(changed == [NAME + ".vi"], "change extends beyond obsolete helper")
    require(
        digest(BEFORE / "ACQUISITION.llb") == PINS["ACQUISITION.llb"]
        and digest(GOOD / "ACQUISITION.llb") == PINS["ACQUISITION.llb"],
        "caller LLB identity changed",
    )
    caller_export = GOOD / "export" / "0_ACQ_ELYSE"
    for filename, expected in CALLER_EXPORT_SHA256.items():
        require(digest(caller_export / filename) == expected, "caller export changed")
    main = Export(caller_export)
    validate_caller_outputs_unused(main)
    return {
        "changed_files": changed,
        "compared_files": len(old_files),
        "source_sha256": SOURCE_SHA256,
        "hardware_main_llb_unchanged": True,
        "launcher_worker_psp_vendor_files_unchanged": True,
        "connector_controls_preserved": 6,
        "legacy_calls_with_both_outputs_unwired": 7,
        "legacy_queue_body_disabled": True,
        "active_queue_or_hardware_operations": 0,
        "not_enqueued": True,
        "telemetry_error": {"status": False, "code": 0, "source": ""},
        "scope": (
            "Static retirement audit only; not proof of hardware startup, "
            "safe shutdown, DAQ health, sustained delivery or all 73 publications."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
