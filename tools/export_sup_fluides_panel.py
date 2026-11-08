"""Export original Fluides palettes and both wired four-state valve displays.

Reads hash-pinned saved XML only. No VI, driver, network or hardware execution.
Local setpoints and Eau Foc defaults are not substituted for live observations.
"""

import argparse
import json
import re
import struct

from export_sup_live_display_map import OUTPUT as WIRE_MAP
from export_sup_live_display_map import REPO, SOURCE_SHA, original
from validate_sup_modulator_request_gate import cluster_fields, require

OUTPUT = REPO / "web/frontend/src/elyseFluidesPanel.json"


def build_panel():
    receipt, roots = original()
    fp_defs = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    page = fp_defs["125053"]
    children = [fp_defs[r.get("uid")] for r in page.findall("ddoList/*")]
    names = cluster_fields(roots["meta"], "Page Fluides")
    require(len(names) == len(children) == 23, "Fluides field order changed")
    fields = {}
    for i, (child, name) in enumerate(zip(children, names)):
        require(
            child.findtext("partsList/*/textRec/text").strip('"') == name,
            "Fluides FP/type field identity differs",
        )
        row = {"control_uid": child.get("uid"), "label": name}
        if child.get("class") == "stdBool":
            palette = next(
                p
                for p in child.findall("partsList/*")
                if p.get("class") == "bigMultiCosm"
            )
            colors = [p.findtext("BGColor") for p in palette.findall("table/*")]
            text = next(
                p.findtext("buf")
                for p in child.findall("partsList/*")
                if p.get("class") == "multiLabel"
            )
            labels = re.findall(r'"([^"]*)"', text)
            require(len(colors) >= 2 and labels, "Fluides saved Boolean states absent")
            row.update(
                false_color="#" + colors[0][-6:],
                true_color="#" + colors[1][-6:],
                false_text=labels[0],
                true_text=labels[min(1, len(labels) - 1)],
            )
        elif child.get("class") == "stdNum":
            row["saved_format"] = child.findtext("partsList/*/format").strip('"')
        fields[str(i)] = row

    bd = roots["bd"]
    defs = {n.get("uid"): n for n in bd.iter() if n.get("class")}
    owners = {
        t.get("uid"): (n, t)
        for n in defs.values()
        if n.get("class") not in ("term", "diag", "signal")
        for t in n.findall("termList/*")
    }
    groups = [
        {t.get("uid") for t in n.findall("termList/*")}
        for n in bd.iter()
        if n.get("class") == "signal"
    ]

    def wire(a, b):
        require(any({a, b} <= g for g in groups), f"Fluides wire changed: {a}->{b}")

    require(
        next(r["name"] for r in receipt["locals"] if r["uid"] == "43802")
        == "C3_IN_DIO96",
        "valve source bank identity changed",
    )
    require(
        defs["43802"].findtext("termList/*/dco/paramIdx") == "31",
        "valve source local reference changed",
    )
    valves = {}
    specs = [
        (
            "CANON",
            [2, 3],
            "43817",
            ["43842", "43845"],
            "42885",
            "60648",
            "59422",
            "39678",
            "10",
            ["59431", "59438"],
            ["59389", "59377"],
        ),
        (
            "SECTION",
            [8, 9],
            "30320",
            ["47358", "47361"],
            "52480",
            "52506",
            "51860",
            "45380",
            "2",
            ["51888", "51928"],
            ["51818", "51812"],
        ),
    ]
    for (
        name,
        indices,
        mux_id,
        sources,
        array_id,
        conv_id,
        case_id,
        prop_id,
        field,
        outs,
        props,
    ) in specs:
        mux, array, conv, case, prop = [
            defs[u] for u in (mux_id, array_id, conv_id, case_id, prop_id)
        ]
        wire("43808", mux.find("termList/*").get("uid"))
        inputs = array.findall("termList/*")[1:]
        require(len(inputs) == 2, "valve input array length changed")
        for index, source, target in zip(indices, sources, inputs):
            require(
                int(owners[source][1].findtext("dco/i")) == index,
                "valve source ordinal changed",
            )
            wire(source, target.get("uid"))
        require(conv.findtext("primResID") == "1815", "Boolean Array To Number changed")
        wire(
            array.find("termList/*").get("uid"),
            conv.findall("termList/*")[1].get("uid"),
        )
        wire(conv.find("termList/*").get("uid"), case.find("termList/*").get("uid"))
        ranges = [
            (
                int(r.findtext("start")),
                int(r.findtext("end")),
                int(r.findtext("diagramIdx")),
            )
            for r in case.findall("SelectRangeArray32/*")
        ]
        require(
            ranges == [(i, i, i) for i in range(4)]
            and case.findtext("SelectDefaultCase") == "03",
            "valve cases changed",
        )
        require(
            prop.find("ddo").get("uid") == fields[field]["control_uid"],
            "valve property target changed",
        )
        for out, target, label in zip(outs, props, ["Colors [4]", "Strings [4]"]):
            wire(out, target)
            require(
                owners[target][1].findtext("dco/propList/*/PropItemName").strip('"')
                == label,
                "valve display property changed",
            )
        states = []
        for i, frame in enumerate(case.find("diagramList")):
            constants = [
                (t, t.findtext("dco/ConstValue"))
                for t in frame.findall("nodeList/*/termList/*")
                if t.find("dco/ConstValue") is not None
            ]
            require(len(constants) == 2, "valve case constants changed")
            decoded = {}
            for term, raw in constants:
                data = bytes.fromhex(raw)
                kind = "color" if len(data) == 8 else "text"
                if kind == "color":
                    a, b = struct.unpack(">II", data)
                    require(a == b, "valve false/true property colors differ")
                    decoded[kind] = f"#{a:06X}"
                else:
                    require(
                        struct.unpack(">I", data[:4])[0] == len(data) - 4,
                        "valve string length changed",
                    )
                    decoded[kind] = data[4:].decode("ascii")
                targets = [
                    (n, t)
                    for g in groups
                    if term.get("uid") in g
                    for uid in g
                    if uid in owners
                    for n, t in [owners[uid]]
                    if n.get("class") == "aBuild"
                ]
                require(len(targets) == 1, "valve constant-to-array wire changed")
                output = targets[0][0].find("termList/*").get("uid")
                border_uid = outs[0 if kind == "color" else 1]
                border = next(
                    t for t in case.findall("termList/*") if t.get("uid") == border_uid
                ).find("dco")
                wire(output, border.findall("termList/*")[i].get("uid"))
            require(
                decoded["text"]
                == f"VANNE {name}\n"
                + ["REGULATION", "FERMEE", "OUVERTE", "EN DEFAUT"][i],
                "valve state text changed",
            )
            require(
                decoded["color"] == ["#00C82D", "#EE9A28", "#EE9A28", "#FF3333"][i],
                "valve state color changed",
            )
            states.append(decoded)
        valves[name] = {
            "bank": "C3_IN_DIO96",
            "indices": indices,
            "encoding": "closed_bit + 2 * open_bit",
            "case_uid": case_id,
            "states": states,
        }

    rules = json.loads(WIRE_MAP.read_text("utf-8"))["rules"]
    require(
        len([r for r in rules if r["page"] == "fluides"]) == 11,
        "Fluides direct-wire projection changed",
    )
    return {
        "source_vi_sha256": SOURCE_SHA,
        "hardware_commands": False,
        "fields": fields,
        "valves": valves,
        "unavailable_live_fields": [4, 16, 21],
        "limits": (
            "Local SUP setpoints and Eau Foc display not observed through ACQ telemetry"
        ),
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
        json.loads(OUTPUT.read_text("utf-8")) == value, "Fluides frontend map differs"
    )
    print(
        "PASS: Fluides palettes, 11 direct fields, "
        "both four-case valve displays; no commands"
    )


if __name__ == "__main__":
    main()
