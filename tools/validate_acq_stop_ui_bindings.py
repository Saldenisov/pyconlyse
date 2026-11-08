"""Pin the original front-panel identities behind stop UI property requests.

DisabledEnum writes change UI availability, not Boolean stop values. This
facet does not infer loaded defaults, UI actions or indirect VI Server writes.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from validate_acq_helper_source_facets import ARCHIVE
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6220_read_error_contract import ALL_MEMBERS_ARCHIVE_SHA256
from validate_acq_runtime_io_frame import heap_type
from validate_acq_vam_status import checked_vam

FP_SHA256 = "000E82C66074929C7A9C7434B66629ADF6934C411AB85109E663BF0474F49E72"
# fPDCO, attached DDO, widget, heap type, label, flags, saved terminal count.
CONTROLS = (
    ("79101", "79089", "stdNum", 11, "ETAPES:", "64", "8"),
    ("40749", "40722", "stdBool", 19, "Arrêt général", "64", "3"),
    ("70723", "70708", "stdNum", 13, "Lecture alimentation HT:", "65", "2"),
    ("11774", "8957", "stdNum", 17, "Cmd alimentation HT:", "65", "2"),
    ("44213", "11783", "stdBool", 15, "TCP ED", "65", "6"),
    ("1732", "1627", "stdBool", 21, "stop", "64", "10"),
    ("45855", "45845", "stdBool", 339, "stop urgence", "64", "5"),
)
PROPERTY_TARGETS = {
    "45759": "79089",
    "45718": "40722",
    "45693": "70708",
    "45668": "8957",
    "45440": "11783",
    "14044": "79089",
    "120269": "40722",
    "119644": "70708",
    "119018": "8957",
    "117145": "11783",
}


def checked_trees(path=ARCHIVE):
    require(
        hashlib.sha256(path.read_bytes()).hexdigest().upper()
        == ALL_MEMBERS_ARCHIVE_SHA256,
        "original17-member archive changed",
    )
    with ZipFile(path) as archive:
        raw = archive.read("0_ACQ_ELYSE.vi/vi_FPHb.xml")
    require(
        hashlib.sha256(raw).hexdigest().upper() == FP_SHA256,
        "original Acquisition front panel changed",
    )
    bd, metadata = checked_vam(ARCHIVE.parent / "0_ACQ_ELYSE_XML_sha6fe8.zip")
    return bd, ET.fromstring(raw), metadata


def validate_trees(bd, fp, metadata):
    require(
        len([x for x in fp.iter() if x.get("class") == "fPDCO"]) == 69,
        "original front-panel control population changed",
    )
    for control, ddo, widget, heap, label, flags, count in CONTROLS:
        node = unique(fp, "fPDCO", control)
        display = node.find("ddo")
        descriptor, _ = heap_type(metadata, heap)
        require(
            display is not None
            and display.get("uid") == ddo
            and display.get("class") == widget
            and unique(fp, widget, ddo) is display
            and display.findtext("partsList/*[@class='label']/textRec/text")
            == '"' + label + '"'
            and node.findtext("typeDesc") == f"TypeID({heap})"
            and descriptor.get("Type")
            == ("Boolean" if widget == "stdBool" else "NumFloat64")
            and descriptor.get("Label") == label
            and node.findtext("objFlags") == flags
            and node.findtext("conNum") == "-1"
            and node.findtext("termListLength") == count,
            "stop front-panel identity/label/type changed",
        )
    targets = {row[1] for row in CONTROLS}
    attached = [
        x
        for x in bd.iter()
        if x.get("class") == "propNode"
        and x.find("ddo") is not None
        and x.find("ddo").get("uid") in targets
    ]
    require(
        len(attached) == 10
        and {x.get("uid"): x.find("ddo").get("uid") for x in attached}
        == PROPERTY_TARGETS,
        "directly attached stop UI property population changed",
    )
    for node in attached:
        props = node.findall(".//propList/*")
        items = [
            t.find("dco")
            for t in node.findall("termList/*")
            if t.find("dco") is not None and t.find("dco").get("class") == "propItem"
        ]
        require(len(items) == 1, "stop UI property data terminal changed")
        heap = items[0].findtext("typeDesc", "")
        require(
            heap.startswith("TypeID(") and heap.endswith(")"),
            "stop UI property heap type absent",
        )
        descriptor, _ = heap_type(metadata, int(heap[7:-1]))
        require(
            len(props) == 1
            and props[0].findtext("PropItemCode") == "104013885"
            and props[0].findtext("PropItemName") == '"DisabledEnum"'
            and props[0].findtext("objFlags") == "4096"
            and descriptor.get("Type") == "UnitUInt8"
            and [x.text for x in descriptor.findall("EnumLabel")]
            == ["Enabled", "Disabled", "Disabled and Grayed Out"],
            "direct stop UI property is not a DisabledEnum write",
        )
    return {
        "front_panel_controls": 7,
        "direct_disabled_properties": 10,
        "direct_value_property_writers": (),
        "initial_values_proven": False,
        "indirect_writers_excluded": False,
    }


if __name__ == "__main__":
    print(validate_trees(*checked_trees()))
