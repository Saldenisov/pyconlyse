"""Check four saved Acquisition initializer error gates, without execution.

Usage: python tools/validate_acq_initialization_error_gates.py SOURCE_EXPORT_ZIP
The check proves root-VI wiring, not Clear Errors.vi internals or task validity.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from validate_acq_cooling_start_completion import checked_root, require, unique
from validate_acq_controlled_stop_wait_tunnels import direct


# Initializer call, label, error-output terminal, Case UID, selector terminal,
# output tunnel terminal, no-error diagram/input/output, error diagram/input/
# output, Clear Errors.vi call/input/output.
GATES = (
    ("593", "1_ACQ_INIT_NI6602.vi", "598", "1242", "1266", "374",
     "1256", "1265", "356", "1250", "1264", "361", "383", "402", "390"),
    ("262", "1_ACQ_INIT_NI6071E.vi", "448", "1503", "1505", "1510",
     "1517", "1508", "1513", "1526", "1509", "1514", "1532", "1547", "1535"),
    ("500", "1_ACQ_INIT_DIO96.vi", "505", "1203", "1215", "1220",
     "1227", "1218", "1223", "1410", "1219", "1224", "1416", "1431", "1419"),
    ("620", "1_ACQ_INIT_NI6703.vi", "625", "342", "557", "562",
     "1609", "560", "565", "1837", "561", "566", "1843", "1858", "1846"),
)
NEXT_ERROR_INPUTS = ("436", "517", "637", "1131")
TASK_REFERENCE_WRITES = (
    ("601", "1053", "1156", "21"),
    ("442", "431", "1692", "23"),
    ("445", "419", "1668", "24"),
    ("508", "1170", "1360", "22"),
    ("628", "325", "335", "25"),
)


def validate_tree(root: ET.Element) -> list[str]:
    outer = unique(root, "sequence", "359")
    initialization = unique(root, "sequence", "201")
    require(initialization in outer.find("diagramList")[1].iter(),
            "initialization sequence moved outside outer frame 1")
    frames = initialization.find("diagramList")
    require(frames is not None and len(frames) == 6
            and frames[1].get("uid") == "227", "initialization frame changed")
    frame = frames[1]
    require({node.get("uid") for node in frame.findall("zPlaneList/*")}
            == {"254", "1317", "1314", "1303", "431", "419", "262",
                "314", "342", "325", "1503", "1203", "1170", "1242",
                "1053", "620", "593", "500"},
            "initializer frame gained/removed top-level operations")
    calls = [node for node in frame.iter() if node.get("class") == "iUse"]
    require({node.get("uid") for node in calls}
            == {row[0] for row in GATES} | {row[-3] for row in GATES},
            "initializer frame has added/removed calls")
    refs = [node for node in frame.iter() if node.get("class") == "gRef"]
    require({node.findtext("termList/*/dco/paramIdx") for node in refs}
            == {"21", "22", "23", "24", "25"},
            "initializer frame local-reference set changed")

    for row, next_input in zip(GATES, NEXT_ERROR_INPUTS):
        (call_uid, name, error_uid, gate_uid, selector_uid, output_uid,
         pass_uid, pass_input, pass_output, fail_uid, fail_input,
         fail_output, clear_uid, clear_input, clear_output) = row
        call = unique(root, "iUse", call_uid)
        gate = unique(root, "select", gate_uid)
        require(call in frame.findall("zPlaneList/*")
                and call.findtext("label/textRec/text") == f'"{name}"'
                and gate in frame.findall("zPlaneList/*"),
                f"initializer {name} or gate moved")
        direct(frame, error_uid, selector_uid)
        direct(frame, output_uid, next_input)
        require([(item.findtext("start"), item.findtext("diagramIdx"))
                 for item in gate.findall("SelectRangeArray32/*")]
                == [("0", "0"), ("1", "1")], "error Case arms changed")
        arms = gate.find("diagramList")
        require(arms is not None and len(arms) == 2
                and [arm.get("uid") for arm in arms] == [pass_uid, fail_uid],
                "error Case frame order changed")
        selector, output = gate.findall("termList/*")
        require(selector.get("uid") == selector_uid
                and selector.find("dco").get("class") == "caseSel"
                and [port.get("uid") for port in selector.findall("dco/termList/*")]
                == [pass_input, fail_input, selector_uid],
                "Case selector frame-port mapping changed")
        require(output.get("uid") == output_uid
                and output.find("dco").get("class") == "selTun"
                and [port.get("uid") for port in output.findall("dco/termList/*")]
                == [pass_output, fail_output, output_uid],
                "Case output tunnel mapping changed")
        require(len(arms[0].find("zPlaneList")) == 0,
                "no-error arm is no longer a pass-through")
        direct(arms[0], pass_input, pass_output)
        active_fail_nodes = arms[1].findall("zPlaneList/*")
        require(len(active_fail_nodes) == 1
                and active_fail_nodes[0].get("uid") == clear_uid,
                "error arm has operations other than Clear Errors")
        clear = unique(root, "iUse", clear_uid)
        require(clear is active_fail_nodes[0]
                and clear.findtext("label/textRec/text") == '"Clear Errors.vi"',
                "error-arm called VI changed")
        direct(arms[1], fail_input, clear_input)
        direct(arms[1], clear_output, fail_output)

    for output_uid, ref_uid, ref_term_uid, parameter in TASK_REFERENCE_WRITES:
        ref = unique(root, "gRef", ref_uid)
        require(ref in frame.findall("zPlaneList/*")
                and ref.findtext("termList/*/dco/paramIdx") == parameter,
                "task-reference local destination changed")
        direct(frame, output_uid, ref_term_uid)

    # Last error gate feeds an initialization sequence local, not a stop flag.
    local = unique(root, "sLoc", "1063")
    require(local in initialization.findall("seqLocDCOList/*")
            and local.findtext("diagDefined") == "01"
            and [term.get("uid") for term in local.findall("termList/*")]
            == ["20369", "1131", "1195", "1366", "21525", "7587"],
            "initialization sequence-local frame mapping changed")
    direct(frames[2], "1195", "2639")
    read = unique(root, "iUse", "287")
    require(read in frames[2].findall("zPlaneList/*")
            and read.findtext("label/textRec/text") == '"1_ACQ_READ_NI6071E.vi"'
            and read.findtext("termList/*[@uid='2639']/dco/paramIdx") == "8",
            "next-frame NI6071E reader error-input destination changed")
    require(not any("Clear Task" in node.findtext("label/textRec/text", "")
                    or "Stop Task" in node.findtext("label/textRec/text", "")
                    for node in frame.iter()),
            "initializer frame gained an explicit task stop/clear")
    return [
        "Initializer chain: NI6602 -> error gate -> NI6071E -> error gate "
        "-> DIO96 -> error gate -> NI6703 -> error gate",
        "Each no-error arm passes its cluster through; each error arm "
        "calls only Clear Errors.vi and forwards its output",
        "Five task-reference outputs write local banks 21,23,24,22,25 "
        "outside those error Cases; last gate output reaches the next "
        "NI6071E read via sequence local 1063",
        "No explicit Stop/Clear Task, retry, or local stop-flag assignment "
        "exists in this initialization frame; subVI internals and "
        "whether a returned task reference is valid remain unverified",
    ]


def validate(path: Path) -> list[str]:
    return validate_tree(checked_root(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    for line in validate(parser.parse_args().source_export_zip):
        print(line)
    print("PASS: ACQ four initialization error gates and task-reference wires")


if __name__ == "__main__":
    main()
