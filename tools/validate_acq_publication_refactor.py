"""Offline wire/type audit of the native eight-bank PSP publication refactor.

Reads lvkit XML only. Never executes a VI or contacts PSP/NI. This proves a
bounded refactor, not telemetry delivery, whole-Acquisition equivalence, timing,
or successful compilation in LabVIEW.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from build_acq_saved_diagram_census import call_names, diagram_rows
from inventory_acq_telemetry_publishers import inventory
from validate_acq_final_cleanup import constant, exact_wires
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_runtime_io_frame import heap_type
from validate_acq_runtime_publication import PUBLICATIONS, URI_PREFIX, case, local


GROUP = "ACQ_Publish_Input_Status"
ORIGINAL_BD_SHA256 = "36E2857BF3031A1C7AB5A5BE9C8A0C2FADEB91E32D60A29652F536F7F3DDB5CB"
ORIGINAL_FILES_SHA256 = {
    "vi_BDHb.xml": ORIGINAL_BD_SHA256,
    "vi.xml": "71E0929301A628DB3DB814C1ADF8C679C6AEF1C10416BFAFD139EED636C59AAC",
    "vi_FPHb.xml": "000E82C66074929C7A9C7434B66629ADF6934C411AB85109E663BF0474F49E72",
}


class Export:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.bd = ET.parse(self.directory / "vi_BDHb.xml").getroot()
        self.fp = ET.parse(self.directory / "vi_FPHb.xml").getroot()
        self.metadata = ET.parse(self.directory / "vi.xml").getroot()
        self.calls = call_names(self.metadata)

    @property
    def root(self):
        return self.bd.find("root")

    def ports(self):
        controls = {n.get("uid"): n for n in self.fp.iter()
                    if n.get("class") == "fPDCO"}
        result = {}
        for terminal in self.bd.iter():
            if terminal.get("class") != "fPTerm":
                continue
            control = controls[terminal.find("dco").get("uid")]
            labels = [p.findtext("textRec/text", "").strip('"')
                      for p in control.findall("ddo/partsList/*")
                      if p.get("class") == "label"]
            require(bool(labels), "front-panel control label absent")
            name = labels[0]
            require(name not in result, "ambiguous front-panel control label")
            result[name] = {
                "terminal": terminal.get("uid"),
                "connector": int(control.findtext("conNum", "0")),
                "output": bool(int(control.findtext("objFlags", "0")) & 1),
                "type": self.shape(control.findtext("typeDesc")),
            }
        return result

    def shape(self, descriptor):
        match = re.fullmatch(r"TypeID\((\d+)\)", descriptor or "")
        require(match is not None, "unresolved heap type")
        td, flat = heap_type(self.metadata, int(match[1]))

        def walk(node, seen):
            kind = node.get("Type")
            require(kind in {"Cluster", "Array", "SubArray", "Boolean",
                             "String", "NumInt32", "NumFloat64", "Refnum", "Tag"},
                    "unsupported payload type: " + str(kind))
            fields = []
            for reference in node.findall("TypeDesc"):
                idx = int(reference.get("TypeID"))
                require(idx not in seen, "recursive payload type")
                child = flat[idx]
                fields.append((child.get("Label", ""), walk(child, seen | {idx})))
            dimensions = [tuple(sorted(d.attrib.items())) for d in node.findall("Dimension")]
            return kind, tuple(fields), tuple(dimensions)

        return walk(td, set())


def call_port(node, slot):
    found = [t for t in node.findall("termList/*")
             if int(t.findtext("dco/paramIdx", "0")) == slot]
    require(len(found) == 1, f"call connector slot {slot} absent/ambiguous")
    return found[0].get("uid")


def named_call(export, frame, filename):
    found = [n for n in frame.findall("zPlaneList/*")
             if n.get("class") == "iUse" and export.calls.get(n.get("uid")) == filename]
    require(len(found) == 1, f"expected one call to {filename}")
    return found[0]


def fixed_uri(frame, port, expected):
    value = bytes.fromhex(constant(frame, port))
    require(value == len(expected).to_bytes(4, "big") + expected.encode("ascii"),
            "fixed PSP URI changed")


def assert_only_operations(export, allowed):
    classes = {n.get("class") for n in export.bd.iter() if n.get("class")}
    require(classes <= allowed, "unexpected operation inside publisher: " + str(classes - allowed))


BASE_CLASSES = {"oHExt", "diag", "sRN", "term", "fPTerm", "bDConstDCO",
                "Image", "label", "textHair", "annex", "stdRefNum", "stdTag",
                "multiCosm", "selLabel", "cosm", "signal"}


def validate_fixed_writer(export, bank, expected_shape):
    assert_only_operations(export, BASE_CLASSES | {"sharedVariableDynamicWrite", "sharedVariableDynamicDCO"})
    writers = [n for n in export.bd.iter() if n.get("class") == "sharedVariableDynamicWrite"]
    require(len(writers) == 1, "publisher must contain exactly one PSP writer")
    writer = writers[0]
    ports = export.ports()
    data = ports[bank]
    incoming = [p for p in ports.values() if not p["output"] and p is not data]
    outgoing = [p for p in ports.values() if p["output"]]
    require(len(ports) == 3 and len(incoming) == len(outgoing) == 1, "publisher interface changed")
    require(data["type"] == expected_shape and not data["output"], "publisher data type changed")
    terms = writer.findall("termList/*")
    require([t.findtext("dco/terminal_ID", "") for t in terms] == ["0B", "03", "08", "", "0A"],
            "PSP writer terminal identity changed")
    url, _unused, error_in, error_out, payload = [t.get("uid") for t in terms]
    constants = export.root.findall("nodeList/*/termList/*/dco/ConstValue/..")
    require(len(constants) == 1, "publisher fixed URI constant absent/ambiguous")
    const_port = next(t.get("uid") for t in export.root.findall("nodeList/*/termList/*")
                      if t.find("dco/ConstValue") is not None)
    fixed_uri(export.root, const_port, URI_PREFIX + bank)
    exact_wires(export.root, ((const_port, url), (data["terminal"], payload),
                             (incoming[0]["terminal"], error_in), (error_out, outgoing[0]["terminal"])),
                bank + " publisher")
    require(export.shape(terms[-1].findtext("dco/typeDesc")) == expected_shape,
            "PSP payload terminal type changed")
    return ports


def validate_c1(wrapper, inner, expected_shape):
    assert_only_operations(wrapper, BASE_CLASSES | {"iUse", "iUseDCO"})
    assert_only_operations(inner, BASE_CLASSES | {"sharedVariableDynamicWrite", "sharedVariableDynamicDCO"})
    wrapped = named_call(wrapper, wrapper.root, "ACQ_Publish_C1NI6071E.vi")
    require(len(wrapper.calls) == 1 and len(wrapper.root.findall("zPlaneList/*[@class='iUse']")) == 1,
            "unexpected additional C1 wrapper call")
    outer_ports, inner_ports = wrapper.ports(), inner.ports()
    data = outer_ports["C1NI6071E"]
    output = next(p for p in outer_ports.values() if p["output"])
    require(len(outer_ports) == 2 and data["type"] == expected_shape and not data["output"],
            "C1 wrapper data/interface changed")
    inner_data = inner_ports["C1NI6071E"]
    inner_output = next(p for p in inner_ports.values() if p["output"])
    ref = next(p for name, p in inner_ports.items() if name != "C1NI6071E" and not p["output"])
    require(len(inner_ports) == 3 and inner_data["type"] == expected_shape,
            "C1 inner interface changed")
    const_port = next(t.get("uid") for t in wrapper.root.findall("nodeList/*/termList/*")
                      if t.find("dco/ConstValue") is not None)
    fixed_uri(wrapper.root, const_port, URI_PREFIX + "C1NI6071E")
    exact_wires(wrapper.root, ((const_port, call_port(wrapped, ref["connector"])),
                              (data["terminal"], call_port(wrapped, inner_data["connector"])),
                              (call_port(wrapped, inner_output["connector"]), output["terminal"])), "C1 wrapper")
    writers = [n for n in inner.bd.iter() if n.get("class") == "sharedVariableDynamicWrite"]
    require(len(writers) == 1, "C1 inner writer changed")
    terms = writers[0].findall("termList/*")
    require([t.findtext("dco/terminal_ID", "") for t in terms] == ["0B", "03", "08", "", "0A"],
            "C1 writer terminal identity changed")
    exact_wires(inner.root, ((ref["terminal"], terms[0].get("uid")),
                            (inner_data["terminal"], terms[4].get("uid")),
                            (terms[3].get("uid"), inner_output["terminal"])), "C1 inner, error-in remains unwired")
    return outer_ports


def validate(original, copied, group, helpers):
    copied_frame = unique(copied.bd, "diag", "7392")
    expected_types = {row[5]: original.shape(unique(original.bd, "sharedVariableDynamicWrite", row[0])
                                            .findall("termList/*")[-1].findtext("dco/typeDesc"))
                      for row in PUBLICATIONS}
    error_shape = original.shape(unique(original.bd, "sharedVariableDynamicWrite", PUBLICATIONS[0][0])
                                 .findall("termList/*")[3].findtext("dco/typeDesc"))
    group_ports = group.ports()
    require(set(group_ports) == set(expected_types) | {"sortie d'erreur"}, "group interface changed")
    require(group_ports["sortie d'erreur"]["output"]
            and group_ports["sortie d'erreur"]["type"] == error_shape, "group PSP error type changed")
    assert_only_operations(group, {"oHExt", "diag", "sRN", "term", "fPTerm", "iUse", "iUseDCO",
                                   "Image", "label", "textHair", "signal"})
    require(len(group.calls) == 8 and len(group.root.findall("zPlaneList/*[@class='iUse']")) == 8,
            "group call count changed")
    links, previous, rows = [], None, []
    for row in PUBLICATIONS:
        old_uid, alias, field, source_port, _old_const, bank, _old_ports = row
        stem = "ACQ_Publish_" + bank + ("_State" if bank == "C1NI6071E" else "")
        helper = helpers[stem]
        ports = (validate_c1(helper, helpers["ACQ_Publish_C1NI6071E"], expected_types[bank])
                 if bank == "C1NI6071E" else validate_fixed_writer(helper, bank, expected_types[bank]))
        require(all(p["type"] == error_shape for name, p in ports.items() if name != bank),
                "bank PSP error type changed")
        call = named_call(group, group.root, stem + ".vi")
        require(group_ports[bank]["type"] == expected_types[bank] and not group_ports[bank]["output"],
                "group data type changed")
        links.append((group_ports[bank]["terminal"], call_port(call, ports[bank]["connector"])))
        output = next(p for p in ports.values() if p["output"])
        if previous:
            incoming = next(p for name, p in ports.items() if name != bank and not p["output"])
            links.append((previous, call_port(call, incoming["connector"])))
        previous = call_port(call, output["connector"])
        local(copied.bd, alias, source_port, field)
        require(copied.shape(unique(copied.bd, "gRef", alias).findtext("termList/*/dco/typeDesc")) == expected_types[bank],
                "caller local type changed")
        rows.append({"bank": bank, "original_writer_uid": old_uid, "original_local_uid": alias,
                     "local_param_index": field, "helper": stem + ".vi", "group_call_uid": call.get("uid"),
                     "psp_uri": URI_PREFIX + bank, "data_type_shape": expected_types[bank],
                     "telemetry_hook_installed": False})
    links.append((previous, group_ports["sortie d'erreur"]["terminal"]))
    exact_wires(group.root, links, "group data/error order")
    main_call = named_call(copied, copied_frame, GROUP + ".vi")
    require({(n.get("class"), n.get("uid")) for n in copied_frame.find("zPlaneList")}
            == {("iUse", main_call.get("uid")), ("label", "11738"), ("select", "40346")}
            | {("gRef", row[1]) for row in PUBLICATIONS}
            and len(copied_frame.find("zPlaneList")) == 11,
            "unexpected operation in caller publication frame")
    caller_links = [(row[3], call_port(main_call, group_ports[row[5]]["connector"])) for row in PUBLICATIONS]
    caller_links.append((call_port(main_call, group_ports["sortie d'erreur"]["connector"]), "47171"))
    exact_wires(copied_frame, caller_links, "caller locals and error guard")
    true = case(copied.bd, "40346", "49991", "50030")
    require({(n.get("class"), n.get("uid")) for n in true.find("zPlaneList")}
            == {("gRef", "50011"), ("gRef", "50019"), (None, "49997")}
            and len(true.find("zPlaneList")) == 3, "unexpected operation in runtime fault arm")
    require(constant(true, "49997") == "01", "runtime fault assignment changed")
    local(copied.bd, "50011", "50014", 30, True)
    local(copied.bd, "50019", "50022", 45, True)
    exact_wires(true, (("49997", "50014", "50022"),), "runtime stop/TCP ED fault assignment")
    # Structural count and bank identities, including writers in unreviewed cases.
    old_count = Counter(n.get("uid") for n in original.bd.iter() if n.get("class") == "sharedVariableDynamicWrite")
    new_count = Counter(n.get("uid") for n in copied.bd.iter() if n.get("class") == "sharedVariableDynamicWrite")
    require(len(old_count) == 73 and len(new_count) == 65, "remaining writer census changed")
    require(set(new_count) == set(old_count) - {r[0] for r in PUBLICATIONS}, "wrong writers extracted")
    require(all(n == 1 for n in old_count.values()) and all(n == 1 for n in new_count.values()), "duplicate writer UID")
    return {"runtime_bank_order": [r[5] for r in PUBLICATIONS], "banks": rows,
            "main_remaining_psp_writers": 65, "encapsulated_psp_writers": 8,
            "total_psp_publication_sites": 73, "group_typed_inputs": 8,
            "first_writer_error_in_unwired": True, "final_stop_tcp_fault_guard_preserved": True,
            "telemetry_complete": False, "native_vi_executed": False, "hardware_access": False,
            "scheduling_limit": "The new group starts after all eight caller inputs are available. Timing, concurrent local-reference updates and subVI reentrancy are not certified by this static audit.",
            "claim_limit": "Static eight-bank wiring/type/URI audit only; does not prove full-VI equivalence, execution timing, native compilation or telemetry delivery."}


def audit(original_dir, export_dir):
    original_dir, export_dir = Path(original_dir), Path(export_dir)
    for filename, expected in ORIGINAL_FILES_SHA256.items():
        require(hashlib.sha256((original_dir / filename).read_bytes()).hexdigest().upper() == expected,
                "original publication export changed: " + filename)
    original, copied, group = Export(original_dir), Export(export_dir / "0_ACQ_ELYSE"), Export(export_dir / GROUP)
    helpers = {p.name: Export(p) for p in export_dir.iterdir() if p.name.startswith("ACQ_Publish_") and p.name != GROUP}
    report = validate(original, copied, group, helpers)
    original_sites = inventory(original_dir / "vi_BDHb.xml")
    copied_sites = inventory(export_dir / "0_ACQ_ELYSE" / "vi_BDHb.xml")
    expected = {r["writer_uid"]: r["uri"] for r in original_sites["sites"]}
    require(all(expected[r["writer_uid"]] == r["uri"] for r in copied_sites["sites"]), "remaining PSP destination changed")
    report["remaining_psp_uris_unchanged"] = True
    scopes = {r["diagram_uid"]: r for r in diagram_rows("0_ACQ_ELYSE.vi", "pinned original",
                                                       original.bd, original.metadata)}
    runtime = {r["original_writer_uid"]: r for r in report["banks"]}
    current_direct = {r["writer_uid"]: r for r in copied_sites["sites"]}
    report["publication_sites"] = []
    for record in original_sites["sites"]:
        row = dict(record)
        scope = scopes[row["diagram_uid"]]
        row["original_scope_path"] = scope["scope_path"]
        row["ancestor_diagram_disable_uids"] = scope["ancestor_diagram_disable_uids"]
        row["runtime_reachability_verified"] = False
        row["telemetry_delivery_verified"] = False
        if row["writer_uid"] in runtime:
            row["current_implementation"] = "typed_bank_subvi_inside_" + GROUP
            row["current_helper"] = runtime[row["writer_uid"]]["helper"]
            row["runtime_refactor_wire_audited"] = True
        else:
            row["current_implementation"] = "direct_PSP_writer"
            row["current_copy_diagram_uid"] = current_direct[row["writer_uid"]]["diagram_uid"]
            row["runtime_refactor_wire_audited"] = False
        report["publication_sites"].append(row)
    report["original_export_file_sha256"] = ORIGINAL_FILES_SHA256
    # Existing init hooks are counted independently from the PSP refactor.
    # Their presence is not a claim that the queue has an owner/consumer.
    report["existing_top_level_telemetry_helper_call_uids"] = sorted(
        uid for uid, name in copied.calls.items() if name == "ACQ_Telemetry_Publish.vi")
    report["existing_top_level_telemetry_helper_calls"] = len(report["existing_top_level_telemetry_helper_call_uids"])
    report["new_runtime_telemetry_hooks"] = 0
    report["validator_path"] = str(Path(__file__).resolve())
    report["validator_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["export_file_sha256"] = {str(p.relative_to(export_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted(export_dir.rglob("*.xml"))}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_export", type=Path)
    parser.add_argument("copied_export", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit(args.original_export, args.copied_export)
    if args.report:
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print("PASS: 8 typed bank publishers, ordered PSP error chain, 73 total sites; telemetry not installed in these 8.")


if __name__ == "__main__":
    main()
