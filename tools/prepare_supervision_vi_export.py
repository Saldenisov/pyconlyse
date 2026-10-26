"""Audit original SuperVision and stage passive telemetry reference assets.

This is a filesystem source-plan builder, not a LabVIEW VI compiler. It opens
no LabVIEW/NI API and contains no network-protocol code. Filesystem paths are
trusted caller inputs; UNC paths or mapped drives may cause OS network I/O.
The copied Acq transport is network-capable but is never executed here. A new
Sup producer/lifecycle and raw-image serializer still need native authoring.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET


DEFAULT_RECEIPTS = Path(r"C:\dev\pyconlyse\Supervision\analysis\lvkit_eval\parser_release_20261003")
DEFAULT_HELPERS = Path(r"C:\dev\ELYSE-ACQ-telemetry\2026-10-14\auto_verified_readback_20261014\ELYSE_ACQ_TELEMETRY_AUTO_20261017")
ROOT_HASH = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
ROOT_XML_HASHES = (
    "F629730C43DBF5EDA3C4E8BD1B22A89EAD90813E5770275A5C80CC28717665D7",
    "E221D536F9D3C69D6492487C2906915E1F0F07AD00E1952370E3C5535849FF06",
    "C00E57C1E82FB2E8C00529F5B0856232622569BA688648DE9A169995284B8921")
SOURCE_PINS = {
    "00.json": (ROOT_HASH, ROOT_XML_HASHES),
    "01.json": (
        "CE8BCA30E727C9B8C1EE9681263FBCE1D60247C2DBECDD0B73A37A385C88104F",
        ("3E4A29FF2DBBD54CD79EF3AF6123E5A0A68C8B035AFC585443DAE93BA8E01378",
         "EA2F6DA059BAE0EAE8E7C0E52865AFEE07237B3DE9DD9BEC18401ED2FC238A08",
         "E0FF3B0D29C23F25E5A46EC8E2B67816D784BD704E8BCF1BDB66FD9EB8082A30")),
    "03.json": (
        "81F29F2C56C22DB6FB37CC8893D360362B2610B6488F9D95C8AFCE0CB21E0DCE",
        ("EA8896FD7FF03A78C296E13259E88D880577A458488EAE3088C3EA8FBF20656F",
         "BEED4CF9C6660AC721AA3787FF8377D5A427C393F6A57D118379396CD8A715BC",
         "DDED0D70828C8B56D8F09F8B6299B49B978FEC66932D25289C9AED4F004D2034"))}
HELPER_HASHES = {
    "ACQ_SharedState_Collect_Local.vi": "A63BAAAB3EB8D60B37FD5EC624C8A27446F4D513FAAA4472E719F3331DB1B472",
    "ACQ_SharedState_Queue_Latest.vi": "1FF9B3E0AAC58DBEA98EE9A2175EF70CBCCCB268D4604B3899B7DD16CC5D69F2",
    "ACQ_SharedState_Transport_Auto.vi": "6DDE82167C284A73318E5E130F32703445D9626375F56425CCA5A5857D6C1A9F"}
CONTROL_UIDS = {
    "C1NI6071E": "64060", "C2NI6071E": "63350", "C3_IN_DIO96": "64591", "C3_OUT_DIO96": "64979",
    "C4_IN_DIO96": "65583", "C4_OUT_DIO96": "65899", "C5_IN_DIO96": "66431", "C5_OUT_DIO96": "66819",
    "C6NI6703": "67288", "C7NI6703": "67169", "C8NI6703": "67054", "C9NI6703": "66939",
    "C10-11 NI6602": "30286", "DPS": "135293", "DPC": "134461", "EPS": "135061", "EPC": "134391",
    "C12NI1409": "38202", "VDM-A": "16491", "VDM-S": "84476", "VDD": "68068", "VAM-A": "197197",
    "VAM-S": "123991", "VAD": "97712", "VTA": "46527", "VTS": "177933", "VTL": "62410"}
WIRES = {
    "49696": {"57569": ("52027", "56484", "58818"), "54417": ("52990", "52020")},
    "70866": {"66465": ("61627", "59739", "70293", "70267")},
    "55043": {"57388": ("68149", "67629"), "57366": ("54780", "67626"),
              "56778": ("53308", "67620")},
    "20537": {"19409": ("15749", "14771"), "15281": ("15743", "21786"),
              "19471": ("52862", "15797", "21780")}}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def index(tree):
    return {node.get("uid"): node for node in tree.iter() if node.get("uid") and node.get("class")}


def control_catalog(fp):
    result = {}
    for node in fp.iter():
        if node.get("class") != "fPDCO":
            continue
        for label in node.findall("ddo/partsList/*"):
            if label.get("class") == "label" and label.findtext("partID") == "16":
                name = label.findtext("textRec/text", "").strip('"')
                if name in CONTROL_UIDS:
                    require(name not in result, "Ambiguous source control: " + name)
                    result[name] = node.get("uid")
    require(result == CONTROL_UIDS, "Original 27-control whitelist/identities changed")
    return result


def verify_wires(bd):
    nodes = index(bd)
    for diagram, wires in WIRES.items():
        require(diagram in nodes and nodes[diagram].get("class") == "diag", "Missing original diagram")
        observed = {wire.get("uid"): tuple(t.get("uid") for t in wire.findall("termList/*"))
                    for wire in nodes[diagram].findall("signalList/*")}
        for uid, terminals in wires.items():
            require(observed.get(uid) == terminals, "Original wire changed: " + diagram + "/" + uid)
    return WIRES


def heap_type(metadata, number):
    heap = metadata.find("DTHP/Section/TypeDescSlice")
    require(heap is not None and 1 <= number <= int(heap.get("Count")), "Original heap type missing")
    vctp = metadata.find("VCTP/Section")
    consolidated = int(heap.get("IndexShift")) + number - 1
    top = {int(t.get("Index")): int(t.get("FlatTypeID")) for t in vctp.find("TopLevel")}
    return vctp.findall("TypeDesc")[top[consolidated]]


def integration_plan(bd, fp, metadata):
    controls = control_catalog(fp)
    verify_wires(bd)
    nodes, panels = index(bd), index(fp)
    counter = heap_type(metadata, int(re.search(r"\d+", panels[controls["C10-11 NI6602"]].findtext("typeDesc"))[0]))
    descriptor = heap_type(metadata, int(re.search(r"\d+", panels[controls["C12NI1409"]].findtext("typeDesc"))[0]))
    flat = metadata.find("VCTP/Section").findall("TypeDesc")
    fields = [flat[int(t.get("TypeID"))] for t in counter.findall("TypeDesc")]
    require(counter.get("Type") == "Cluster" and len(fields) == 33
            and all(t.get("Type") == "NumFloat64" for t in fields), "Counter control is not the source33DBL cluster")
    require(descriptor.get("Type") == "String", "C12 must remain a String descriptor")
    require(nodes["15740"].findtext("label/textRec/text") == '"IMAQ Grab Acquire.vi"', "Original camera call changed")
    return dict(schema_version=1, purpose="offline native authoring plan, not deployable code",
        source_host="10.20.30.2", original_root_sha256=ROOT_HASH,
        original_controls=controls, existing_collector_27_names_reusable=True,
        counter=dict(control_uid="30286", local_param_index=170, field_count=33,
            supervision_slice=[16, 32], selector_index=32,
            semantics="observed_labview_control_memory; no physical pulse readback or successful-write proof",
            wires=WIRES["49696"], frequency_event_publication_wire=WIRES["70866"],
            native_initializer_call="66132", initializer_diagram="23159",
            native_writer_call="67590", writer_diagram="55043", writer_call_wires=WIRES["55043"]),
        descriptor=dict(control_uid="38202", type="String", maximum_transport_characters=4096,
            semantics="read original control unchanged; no fabricated pixel interpretation"),
        camera=dict(grab_call="15740", grab_diagram="20537", pre_rotate_wire="19409",
            pre_rotate_terminals=["15749", "14771"], frame_count_property="21773", frame_count_output="21792",
            frame_count_error_wire="15281", shared_session_wire="19471",
            image_terminal_types_in_original_parser="Void; native Vision connector qualification still required",
            existing_image_memory_mutable=True, borrowed_image_reference_may_be_queued=False,
            new_grab_or_session_open_allowed_in_exporter=False),
        existing_transport=dict(destination="127.0.0.1:8766", framing="u32 big-endian byte length + LabVIEW Variant XML",
            wire_encoding="cp1252", maximum_xml_bytes=262144, queue_capacity=1,
            dequeue_timeout_ms=100, tcp_timeout_ms_each_operation=1000,
            main_loop_tcp_operations=0, snapshot_atomic=False),
        proposed_typed_ingress=dict(destination="127.0.0.1:8768", native_serializer_authored=False,
            specification_owner="SuperVision VI typed ingress implementation; schema must be version-pinned before native authoring"),
        originals_modified=False, vi_executed=False, hardware_accessed=False,
        live_canonical_source_bound=False, authoring_workspace_bound=False,
        new_native_vi_authored=False, native_compile_verified=False, deployable=False,
        blockers=["Native read-only Sup producer/lifecycle not authored or compiled",
            "LabVIEW2012 strict JSON/base64/locale path unqualified for the new typed ingress",
            "Image reference connector/lifetime, owned conversion and source age unqualified",
            "VI bridge raw video requires explicit source-mode extension; cannot claim Python-native capture",
            "Federation must remain disabled until both source roles and freshness/provenance are qualified"])


def verified_receipt(path, source_pin, xml_pins):
    try:
        receipt = json.loads(Path(path).read_text(encoding="utf-8"))
        require(type(receipt) is dict and isinstance(receipt.get("source"), str)
                and receipt.get("sha256") == source_pin, "Original source receipt identity changed")
        require(digest(receipt["source"]) == source_pin, "Original source bytes changed")
        rows = receipt.get("xml")
        require(type(rows) is list and len(rows) == len(xml_pins), "Original extraction closure changed")
        for row, expected in zip(rows, xml_pins):
            require(type(row) is dict and set(row) == {"path", "sha256"}
                    and isinstance(row["path"], str) and row["sha256"] == expected,
                    "Original XML receipt changed")
            require(digest(row["path"]) == expected, "Original saved XML bytes changed")
        return receipt
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ValueError("Unqualified source receipt " + str(path) + ": " + str(error))


def audit(receipts=DEFAULT_RECEIPTS):
    verified = {name: verified_receipt(Path(receipts) / name, *pins) for name, pins in SOURCE_PINS.items()}
    receipt = verified["00.json"]
    trees = [ET.parse(row["path"]).getroot() for row in receipt["xml"]]
    plan = integration_plan(*trees)
    plan["source_receipt"] = str(Path(receipts) / "00.json")
    plan["verified_source_receipts"] = {name: dict(source=row["source"], sha256=row["sha256"], xml=row["xml"])
                                        for name, row in verified.items()}
    return plan


def stage(destination, receipts=DEFAULT_RECEIPTS, helpers=DEFAULT_HELPERS):
    destination, helpers = Path(destination), Path(helpers)
    require(not destination.exists(), "Existing authoring workspace preserved; use a new directory")
    plan = audit(receipts)
    for name, expected in HELPER_HASHES.items():
        require(digest(helpers / name) == expected, "Native-authored reference helper changed: " + name)
    destination.mkdir(parents=True)
    references = destination / "reference_helpers_do_not_autorun"
    references.mkdir()
    for name in sorted(HELPER_HASHES):
        shutil.copy2(helpers / name, references / name)
        require(digest(references / name) == HELPER_HASHES[name], "Copied reference hash mismatch")
    plan["reference_helper_sha256"] = HELPER_HASHES
    plan["hardware_main_or_launcher_copied"] = False
    (destination / "export_plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--helpers", type=Path, default=DEFAULT_HELPERS)
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    value = audit(options.receipts) if options.output is None else stage(options.output, options.receipts, options.helpers)
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
