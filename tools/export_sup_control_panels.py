"""Export saved RP/HT/HF/power panel palettes; never execute a VI or hardware.

Only the existing pinned wire map supplies live field bindings. Saved Boolean
defaults and SUP-local setpoints are never used as telemetry substitutes.
"""

import argparse
import json
import re
import struct

from export_sup_live_display_map import REPO, SOURCE_SHA, original
from validate_sup_modulator_request_gate import cluster_fields, require

OUTPUT = REPO / "web/frontend/src/elyseControlPanels.json"
PAGES = {
    "radioprotection": ("Page Radioprotection", "28035", 12),
    "ht": ("Page HT", "54878", 28),
    "hf": ("Page HF", "36888", 26),
    "alimentations": ("Page Alimentations", "29896", 14),
}


def power_state(roots, receipt):
    """Prove only the four-state display. This is never an interlock decision."""
    defs = {n.get("uid"): n for n in roots["bd"].iter() if n.get("class")}
    locals_ = {r["uid"]: r["name"] for r in receipt["locals"]}
    owners = {
        t.get("uid"): n
        for n in defs.values()
        if n.get("class") not in ("term", "diag", "signal", "nmxDCO", "selTun")
        for t in n.findall("termList/*")
    }
    groups = [
        {t.get("uid") for t in n.findall("termList/*")}
        for n in roots["bd"].iter()
        if n.get("class") == "signal"
    ]

    def wire(a, b):
        require(
            any({a, b} <= g for g in groups), f"power display wire changed: {a}->{b}"
        )

    indices = [31, 28, 35, 37, 39, 41, 12, 14, 43, 45, 24, 26, 20, 47, 49, 53]
    for uid, mux_uid, operation in [("85339", "89131", 2), ("79116", "80695", 3)]:
        node, mux = defs[uid], defs[mux_uid]
        require(
            (int(node.findtext("objFlags")) >> 16) & 7 == operation,
            "power AND/OR changed",
        )
        agg = mux.find("dcoAgg").get("uid")
        agg_port = next(
            t.get("uid")
            for t in mux.findall("termList/*")
            if t.find("dco").get("uid") == agg
        )
        banks = {
            locals_.get(owners[t].get("uid"))
            for g in groups
            if agg_port in g
            for t in g
            if t in owners and owners[t].get("class") == "gRef"
        }
        require(banks == {"C3_IN_DIO96"}, "power source bank changed")
        source_ports = mux.findall("termList/*")[1:]
        inputs = node.findall("termList/*")[1:]
        require(len(source_ports) == len(inputs) == 16, "power aggregate arity changed")
        for index, src, dst in zip(indices, source_ports, inputs):
            require(int(src.findtext("dco/i")) == index, "power bit ordinal changed")
            require(
                bool(int(dst.findtext("dco/objFlags")) & 0x10000),
                "power input inversion changed",
            )
            wire(src.get("uid"), dst.get("uid"))
    require(defs["82758"].get("class") == "sLoc", "power sequence local changed")
    wire("85345", "82919")
    wire("46911", "86593")
    require(
        {"82919", "46911"}
        <= {t.get("uid") for t in defs["82758"].findall("termList/*")},
        "power local path changed",
    )
    wire("80632", "86596")
    require(
        [t.get("uid") for t in defs["86586"].findall("termList/*")]
        == ["86590", "86593", "86596"],
        "power bit order changed",
    )
    require(defs["86600"].findtext("primResID") == "1815", "power bit packing changed")
    wire("86590", "86605")
    wire("86602", "86189")
    case = defs["86187"]
    ranges = [
        (
            int(r.findtext("start")),
            int(r.findtext("end")),
            int(r.findtext("diagramIdx")),
        )
        for r in case.findall("SelectRangeArray32/*")
    ]
    require(ranges == [(i, i, i) for i in range(4)], "power display cases changed")
    prop = defs["70170"]
    require(prop.find("ddo").get("uid") == "278", "power display target changed")
    for src, dst, label in [
        ("86196", "86174", "Colors [4]"),
        ("86203", "86168", "Strings [4]"),
    ]:
        wire(src, dst)
        term = next(t for t in prop.findall("termList/*") if t.get("uid") == dst)
        require(
            term.findtext("dco/propList/*/PropItemName").strip('"') == label,
            "power display property changed",
        )
    states = []
    for frame in case.find("diagramList"):
        data = [
            bytes.fromhex(t.findtext("dco/ConstValue"))
            for t in frame.findall("nodeList/*/termList/*")
            if t.find("dco/ConstValue") is not None
        ]
        require(len(data) == 2, "power state constants changed")
        colors = next(v for v in data if len(v) == 8)
        a, b = struct.unpack(">II", colors)
        require(a == b, "power state has unequal colors")
        text = next(v for v in data if len(v) != 8)
        require(
            int.from_bytes(text[:4], "big") == len(text) - 4,
            "power text length changed",
        )
        states.append(dict(color=f"#{a & 0xFFFFFF:06X}", text=text[4:].decode("ascii")))
    return dict(
        bank="C3_IN_DIO96",
        indices=indices,
        states=states,
        expression="AND(NOT bits) + 2 * OR(NOT bits)",
        inputs_inverted=True,
        temporal_equivalence=False,
        permission_decision=False,
    )


def build_panel():
    receipt, roots = original()
    fp = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    pages = {}
    for key, (label, uid, count) in PAGES.items():
        page = fp[uid]
        require(page.get("class") == "stdClust", "panel cluster type changed")
        children = [fp[r.get("uid")] for r in page.findall("ddoList/*")]
        names = cluster_fields(roots["meta"], label)
        require(len(children) == len(names) == count, "panel field order changed")
        fields = {}
        for index, (child, name) in enumerate(zip(children, names)):
            require(
                child.findtext("partsList/*/textRec/text").strip('"') == name,
                "panel FP/type identity differs",
            )
            row = {"control_uid": child.get("uid"), "label": name}
            if child.get("class") == "stdBool":
                parts = child.findall("partsList/*")
                palette = next(p for p in parts if p.get("class") == "bigMultiCosm")
                colors = [p.findtext("BGColor") for p in palette.findall("table/*")]
                labels = re.findall(
                    r'"([^"]*)"',
                    next(
                        p.findtext("buf")
                        for p in parts
                        if p.get("class") == "multiLabel"
                    ),
                )
                require(len(colors) >= 2 and labels, "Boolean palette absent")
                row.update(
                    false_color="#" + colors[0][-6:],
                    true_color="#" + colors[1][-6:],
                    false_text=labels[0],
                    true_text=labels[min(1, len(labels) - 1)],
                )
            elif child.get("class") == "stdNum":
                row["saved_format"] = child.findtext("partsList/*/format").strip('"')
            fields[str(index)] = row
        pages[key] = {"control_uid": uid, "fields": fields}
    return dict(
        source_vi_sha256=SOURCE_SHA,
        hardware_commands=False,
        palette_scope="SAVED_FRONT_PANEL_NOT_HARDWARE_SAFETY",
        saved_values_used_as_telemetry=False,
        pages=pages,
        power_state=power_state(roots, receipt),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    panel = build_panel()
    if args.write:
        OUTPUT.write_text(
            json.dumps(panel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    require(json.loads(OUTPUT.read_text("utf-8")) == panel, "panel export differs")
    print("PASS: four pinned control panels; no native or hardware execution")


if __name__ == "__main__":
    main()
