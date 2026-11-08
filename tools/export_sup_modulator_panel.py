"""Export saved Modulateur palette/labels, not hardware meanings or commands."""

import argparse
import json

from export_sup_live_display_map import OUTPUT as WIRE_MAP
from export_sup_live_display_map import REPO, SOURCE_SHA, original
from validate_sup_modulator_request_gate import cluster_fields, require

OUTPUT = REPO / "web/frontend/src/elyseModulatorPanel.json"


def build_panel():
    _, roots = original()
    fp = roots["fp"]
    defs = {n.get("uid"): n for n in fp.iter() if n.get("class")}
    page = defs["56140"]
    require(page.get("class") == "stdClust", "Modulateur panel type changed")
    children = [defs[ref.get("uid")] for ref in page.findall("ddoList/*")]
    names = cluster_fields(roots["meta"], "Page Modulateur")
    require(len(children) == len(names) == 59, "Modulateur field order changed")
    for child, name in zip(children, names):
        require(
            child.findtext("partsList/*/textRec/text").strip('"') == name,
            "front-panel field/type order differs",
        )
    rules = json.loads(WIRE_MAP.read_text("utf-8"))["rules"]
    rows = {}
    for rule in rules:
        if rule["page"] != "modulateur":
            continue
        index = rule["target_field"]
        child = children[index]
        parts = child.findall("partsList/*")
        row = {"control_uid": child.get("uid"), "field": index}
        if rule["kind"] == "boolean":
            palette = next(p for p in parts if p.get("class") == "bigMultiCosm")
            colors = [item.findtext("BGColor") for item in palette.findall("table/*")]
            require(len(colors) >= 2, "saved Boolean states absent")
            expected = (
                ["001E4B00", "0064FF00"] if index >= 54 else ["0000C82D", "00FF3333"]
            )
            require(colors[:2] == expected, "saved palette changed")
            row.update(
                false_color="#" + colors[0][-6:], true_color="#" + colors[1][-6:]
            )
            buffers = [p.findtext("buf") for p in parts if p.find("buf") is not None]
            row["saved_text_buffer"] = buffers[0] if buffers else None
        else:
            row["saved_format"] = child.findtext("partsList/*/format").strip('"')
        rows[str(index)] = row
    require(len(rows) == 48, "display rule/palette join incomplete")
    return {
        "source_vi_sha256": SOURCE_SHA,
        "palette_scope": "SAVED_FRONT_PANEL_NOT_HARDWARE_SAFETY",
        "runtime_transitions_observed": False,
        "hardware_commands": False,
        "fields": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = build_panel()
    if args.write:
        OUTPUT.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    require(
        json.loads(OUTPUT.read_text("utf-8")) == value, "frontend palette map differs"
    )
    print("PASS: 34 saved Boolean palettes and 14 numeric formats; no commands")


if __name__ == "__main__":
    main()
