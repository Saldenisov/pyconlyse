"""Pinned vacuum display identity and valve-wire proof; native screen layout.

Geometry is a transcription of the observed Supervision Vide page, not a
physical length scale or a fabricated beamline connection diagram.
"""

import argparse
import json
import struct

from export_sup_live_display_map import REPO, SOURCE_SHA, original
from validate_sup_modulator_request_gate import require

OUTPUT = REPO / "web/frontend/src/elyseVacuumPanel.json"


def build_panel():
    receipt, roots = original()
    bd = roots["bd"]
    defs = {n.get("uid"): n for n in bd.iter() if n.get("class")}
    fp = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    page = fp["161366"]
    children = [r.get("uid") for r in page.findall("ddoList/*")]
    require(len(children) == 18, "Page Vide field order changed")
    pressures = []
    for field, uid, x, y in [
        (3, "32481", 0, 5),
        (5, "35582", 0, 75),
        (1, "28683", 0, 145),
        (14, "84017", 164, 55),
        (7, "62002", 164, 123),
        (12, "83992", 329, 87),
        (9, "83942", 493, 87),
        (17, "69689", 658, 55),
    ]:
        require(children[field] == uid, "vacuum numeric control identity changed")
        pressures.append({"field": field, "control_uid": uid, "x": x, "y": y})

    groups = [
        {t.get("uid") for t in n.findall("termList/*")}
        for n in bd.iter()
        if n.get("class") == "signal"
    ]

    def wire(a, b):
        require(
            any({a, b} <= group for group in groups), f"vacuum wire changed: {a}->{b}"
        )

    require(
        next(r["name"] for r in receipt["locals"] if r["uid"] == "59007")
        == "C5_IN_DIO96",
        "vacuum valve input bank changed",
    )
    require(
        defs["59007"].findtext("termList/*/dco/paramIdx") == "27",
        "vacuum valve reference changed",
    )
    valves = []
    specs = [
        (
            "CATHODE",
            15,
            "26950",
            [15, 14],
            "59015",
            ["59020", "59023"],
            "59853",
            "59865",
            "59063",
            "59027",
            ["59072", "59079"],
            ["59053", "59043"],
            562,
            0,
        ),
        (
            "INJECTION",
            16,
            "29440",
            [17, 16],
            "59873",
            ["59878", "59881"],
            "60325",
            "60338",
            "55405",
            "59885",
            ["55451", "55458"],
            ["59906", "59900"],
            808,
            3,
        ),
    ]
    for (
        name,
        field,
        uid,
        indices,
        mux_uid,
        sources,
        array_uid,
        conv_uid,
        case_uid,
        prop_uid,
        outs,
        targets,
        x,
        y,
    ) in specs:
        require(children[field] == uid, "vacuum valve FP identity changed")
        mux, array, conv, case, prop = [
            defs[u] for u in (mux_uid, array_uid, conv_uid, case_uid, prop_uid)
        ]
        wire("59010", mux.find("termList/*").get("uid"))
        mux_terms = {t.get("uid"): t for t in mux.findall("termList/*")}
        for source, index, target in zip(
            sources, indices, array.findall("termList/*")[1:]
        ):
            require(
                int(mux_terms[source].findtext("dco/i")) == index,
                "vacuum valve bit ordinal changed",
            )
            wire(source, target.get("uid"))
        require(conv.findtext("primResID") == "1815", "vacuum bit packing changed")
        wire(
            array.find("termList/*").get("uid"),
            conv.findall("termList/*")[1].get("uid"),
        )
        wire(conv.find("termList/*").get("uid"), case.find("termList/*").get("uid"))
        require(
            [
                (
                    int(r.findtext("start")),
                    int(r.findtext("end")),
                    int(r.findtext("diagramIdx")),
                )
                for r in case.findall("SelectRangeArray32/*")
            ]
            == [(i, i, i) for i in range(4)],
            "vacuum valve case labels changed",
        )
        require(
            case.find("SelectDefaultCase") is None, "vacuum default metadata changed"
        )
        require(prop.find("ddo").get("uid") == uid, "vacuum property target changed")
        for out, target, expected in zip(outs, targets, ["Colors [4]", "Strings [4]"]):
            wire(out, target)
            term = next(t for t in prop.findall("termList/*") if t.get("uid") == target)
            require(
                term.findtext("dco/propList/*/PropItemName").strip('"') == expected,
                "vacuum property identity changed",
            )
        states = []
        for i, frame in enumerate(case.find("diagramList")):
            constants = [
                t
                for t in frame.findall("nodeList/*/termList/*")
                if t.find("dco/ConstValue") is not None
            ]
            require(len(constants) == 2, "vacuum case literal set changed")
            state = {}
            for term in constants:
                raw = bytes.fromhex(term.findtext("dco/ConstValue"))
                color = len(raw) == 8
                if color:
                    a, b = struct.unpack(">II", raw)
                    require(a == b, "vacuum Boolean-state color differs")
                    state["color"] = f"#{a:06X}"
                else:
                    require(
                        int.from_bytes(raw[:4], "big") == len(raw) - 4,
                        "vacuum label length changed",
                    )
                    state["text"] = raw[4:].decode("ascii")
                arrays = [
                    n
                    for n in frame.findall("zPlaneList/*")
                    if n.get("class") == "aBuild"
                    and any(
                        {term.get("uid"), t.get("uid")} <= g
                        for t in n.findall("termList/*")[1:]
                        for g in groups
                    )
                ]
                require(len(arrays) == 1, "vacuum literal-to-array wire changed")
                border = next(
                    t
                    for t in case.findall("termList/*")
                    if t.get("uid") == outs[0 if color else 1]
                ).find("dco")
                wire(
                    arrays[0].find("termList/*").get("uid"),
                    border.findall("termList/*")[i].get("uid"),
                )
            require(
                state["text"]
                == f"VANNE {name}\n"
                + ["ENTROUVERTE", "OUVERTE", "FERMEE", "EN DEFAUT"][i],
                "vacuum valve state text changed",
            )
            require(
                state["color"] == ("#00C82D" if i == 1 else "#FF3333"),
                "vacuum valve palette changed",
            )
            states.append(state)
        valves.append(
            {
                "name": name,
                "bank": "C5_IN_DIO96",
                "indices": indices,
                "states": states,
                "x": x,
                "y": y,
                "case_uid": case_uid,
            }
        )
    return {
        "source_vi_sha256": SOURCE_SHA,
        "hardware_commands": False,
        "layout_basis": "Native Supervision Vide screen observed 2026-10-16",
        "layout_is_physical_length_scale": False,
        "canvas_width": 900,
        "pressure_width": 158,
        "pressures": pressures,
        "valves": valves,
        "pressure_alarm_inputs_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    panel = build_panel()
    if args.write:
        OUTPUT.write_text(
            json.dumps(panel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    require(
        json.loads(OUTPUT.read_text("utf-8")) == panel, "vacuum frontend map differs"
    )
    print(
        "PASS: eight source identities, native screen placement, two four-case valves"
    )


if __name__ == "__main__":
    main()
