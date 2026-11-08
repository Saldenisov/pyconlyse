"""Extract native line controls, forty display wires and original synoptic PNG.

No VI or vendor code is executed. Native defaults never become telemetry.
"""

import argparse
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path

from export_sup_live_display_map import OUTPUT, SOURCE_SHA, original
from validate_sup_modulator_request_gate import require

WORKSPACE_OUTPUT = OUTPUT.with_name("elyseSupervisionWorkspace.json")
IMAGE_OUTPUT = OUTPUT.parent / "assets" / "elyse-synoptique-original.png"
COMMANDS = {
    "direct": [
        ("C7NI6703", 8),
        ("C7NI6703", 5),
        ("C8NI6703", 5),
        ("C6NI6703", 0),
        ("C6NI6703", 1),
        ("C6NI6703", 2),
        ("C6NI6703", 3),
        ("C7NI6703", 0),
        ("C7NI6703", 1),
        ("C6NI6703", 4),
        ("C6NI6703", 5),
    ],
    "deviated": [
        ("C7NI6703", 6),
        ("C7NI6703", 7),
        ("C7NI6703", 3),
        ("C7NI6703", 4),
        ("C6NI6703", 6),
        ("C6NI6703", 7),
        ("C7NI6703", 9),
        ("C6NI6703", 8),
        ("C6NI6703", 9),
    ],
}
READINGS = {
    "direct": [28, 20, 45, 29, 22, 30, 23, 16, 24, 31, 32],
    "deviated": [19, 27, 25, 18, 40, 33, 21, 34, 34],
}
# Literal terminal identities in the original corrector arithmetic diagrams.
# Each tuple: action selector, nested row selector, corrector diagram ordinal,
# subtraction/addition node, selected-step node, two literal terminals.
CORRECTOR_BUTTONS = {
    "direct": (
        (128, "8243", "8641", 3, "7706", "7692", "7837", "7817"),
        (256, "8243", "16826", 3, "17308", "17294", "17246", "17258"),
        (512, "8243", "8489", 3, "7558", "9486", "9384", "9414"),
        (1024, "8243", "10539", 3, "6230", "11439", "11391", "11403"),
    ),
    "deviated": (
        (128, "34080", "34331", 1, "34848", "34834", "34785", "34797"),
        (256, "34080", "34950", 1, "35455", "35420", "35372", "35384"),
        (512, "34080", "35756", 1, "45702", "45671", "45623", "45635"),
        (1024, "34080", "45787", 1, "46287", "46256", "46208", "46220"),
    ),
}
BUTTON_FIELDS = (
    (0, "M/A", "power", 1),
    (4, "X1/X10", "step_mode", 16),
    (7, "<<", "coarse_decrease", 128),
    (8, "<", "fine_decrease", 256),
    (9, ">", "fine_increase", 512),
    (10, ">>", "coarse_increase", 1024),
)
RANGES = {
    "direct": [
        "-16A à 16A",
        "0 à 120A",
        "0 à 360°",
        *["-5A à 5A"] * 4,
        "-16A à 16A",
        "-16A à 16A",
        "-5A à 5A",
        "-5A à 5A",
    ],
    "deviated": [
        *["-16A à 16A"] * 4,
        "-5A à 5A",
        "-5A à 5A",
        "-16A à 16A",
        "-5A à 5A",
        "-5A à 5A",
    ],
}
SOURCES = {
    "12716": "C6NI6703",
    "12815": "C7NI6703",
    "16244": "C8NI6703",
    "12095": "C1NI6071E",
    "24159": "C6NI6703",
    "23900": "C7NI6703",
    "28989": "C1NI6071E",
}
TARGETS = {
    "11207": ("direct", "consigne", 6),
    "12099": ("direct", "lecture", 7),
    "24030": ("deviated", "consigne", 6),
    "29056": ("deviated", "lecture", 7),
}


def corrector_step_choices(roots):
    """Validate step choices in original VI; do not infer X1/X10 polarity."""
    defs = {n.get("uid"): n for n in roots["bd"].iter() if n.get("class")}
    nets = [
        {t.get("uid") for t in n.findall("termList/*")}
        for n in defs.values()
        if n.get("class") == "signal"
    ]

    def ports(uid):
        return {t.get("uid") for t in defs[uid].findall("termList/*")}

    def linked(a, b):
        return any(a & net and b & net for net in nets)

    result = {}
    for line, paths in CORRECTOR_BUTTONS.items():
        actions = {}
        for code, outer, nested, frame, arithmetic, step, low, high in paths:
            outer_ranges = defs[outer].findall("SelectRangeArray32/*")
            matches = [
                r
                for r in outer_ranges
                if r.findtext("start") == r.findtext("end") == str(code)
            ]
            require(len(matches) == 1, "native arrow action case changed")
            branch = defs[outer].findall("diagramList/*")[
                int(matches[0].findtext("diagramIdx"))
            ]
            require(defs[nested] in branch.iter(), "native arrow row selector changed")
            diagram = defs[nested].findall("diagramList/*")[frame]
            ranges = [
                (
                    int(r.findtext("start")),
                    int(r.findtext("end")),
                    int(r.findtext("diagramIdx")),
                )
                for r in defs[nested].findall("SelectRangeArray32/*")
            ]
            rows = (3, 4, 5, 6, 9, 10) if line == "direct" else (4, 5, 7, 8)
            require(
                all(
                    any(a <= row <= b and i == frame for a, b, i in ranges)
                    for row in rows
                ),
                "native corrector row grouping changed",
            )
            require(
                defs[arithmetic] in diagram.iter() and defs[step] in diagram.iter(),
                "native corrector arithmetic diagram changed",
            )
            require(
                defs[arithmetic].findtext("primResID")
                == ("1051" if code < 512 else "1050")
                and defs[step].findtext("primResID") == "1516",
                "native arrow arithmetic primitive changed",
            )
            choices = []
            for uid in (low, high):
                raw = defs[uid].findtext("dco/ConstValue")
                require(
                    raw is not None and len(raw) == 16, "native step literal changed"
                )
                choices.append(struct.unpack(">d", bytes.fromhex(raw))[0])
                require(linked({uid}, ports(step)), "native step literal wire changed")
            expected = [0.1, 1.0] if code in (128, 1024) else [0.01, 0.1]
            require(
                choices == expected and linked(ports(step), ports(arithmetic)),
                "native corrector step choices changed",
            )
            actions[code] = dict(
                step_choices=choices,
                diagram_uid=diagram.get("uid"),
                arithmetic_uid=arithmetic,
                step_selector_uid=step,
                literal_terminals=[low, high],
            )
        result[line] = actions
    return result


def native_buttons(fields, labels, line, is_corrector, steps):
    """Preserve six distinct native controls, not guessed live switch states."""
    controls = []
    for index, label, role, code in BUTTON_FIELDS:
        require(labels[index] == label, "native button identity changed")
        control = dict(
            native_uid=fields[index].get("uid"),
            field_index=index,
            label=label,
            role=role,
            action_code=code,
            commands_enabled=False,
        )
        if is_corrector and code in steps[line]:
            control.update(steps[line][code])
            control["unit"] = "A"
            control["boolean_to_step_polarity_qualified"] = False
        controls.append(control)
    return controls


def embedded_synoptic(receipt, roots):
    fp = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    image = fp["4865"]
    require(image.findtext("image/ImageResID") == "75", "synoptic resource changed")
    directory = Path(receipt["xml"][0]["path"]).parent
    data = (directory / "vi_DSIM75.bin").read_bytes()
    require(
        hashlib.sha256(data).hexdigest()
        == "60f30c52990ed31669df714e21774a6207cebdb8012ff79784d247792a6ed667",
        "synoptic resource bytes changed",
    )
    start = data.index(b"\x89PNG\r\n\x1a\n")
    cursor = start + 8
    while cursor < len(data):
        size = struct.unpack_from(">I", data, cursor)[0]
        kind = data[cursor + 4 : cursor + 8]
        content = data[cursor + 8 : cursor + 8 + size]
        checksum = struct.unpack_from(">I", data, cursor + 8 + size)[0]
        require(zlib.crc32(kind + content) == checksum, "synoptic PNG checksum changed")
        cursor += size + 12
        if kind == b"IEND":
            break
    png = data[start:cursor]
    require(
        Path(receipt["source"]).read_bytes().find(png) >= 0,
        "synoptic PNG is not present verbatim in pinned original VI",
    )
    require(struct.unpack_from(">II", png, 16) == (866, 596), "synoptic size changed")
    return png


def build_workspace(receipt=None, roots=None):
    if roots is None:
        receipt, roots = original()
    steps = corrector_step_choices(roots)
    fp = {n.get("uid"): n for n in roots["fp"].iter() if n.get("class")}
    defs = {n.get("uid"): n for n in roots["bd"].iter() if n.get("class")}
    owners = {
        t.get("uid"): (n, t)
        for n in defs.values()
        if n.get("class") not in ("term", "diag", "signal", "selTun", "nmxDCO")
        for t in n.findall("termList/*")
    }
    nets = [
        {t.get("uid") for t in n.findall("termList/*")}
        for n in defs.values()
        if n.get("class") == "signal"
    ]
    local_names = {r["uid"]: r["name"] for r in receipt["locals"]}
    for uid, expected in {
        **SOURCES,
        **{
            u: "Voie directe" if t[0] == "direct" else "Voie déviée"
            for u, t in TARGETS.items()
        },
    }.items():
        node = defs[uid]
        agg = node.find("dcoAgg").get("uid")
        ports = {
            t.get("uid")
            for t in node.findall("termList/*")
            if t.find("dco").get("uid") == agg
        }
        names = {
            local_names.get(owners[p][0].get("uid"))
            for net in nets
            if ports & net
            for p in net
            if p in owners and owners[p][0].get("class") == "gRef"
        }
        require(names == {expected}, f"line mux identity changed: {uid}")
    bindings = {}
    for net in nets:
        src = [
            (p, *owners[p])
            for p in net
            if p in owners
            and owners[p][0].get("uid") in SOURCES
            and not int(owners[p][1].findtext("objFlags", "0")) & 0x8000
        ]
        dst = [
            (p, *owners[p])
            for p in net
            if p in owners
            and owners[p][0].get("uid") in TARGETS
            and int(owners[p][1].findtext("objFlags", "0")) & 0x8000
        ]
        for suid, source, st in src:
            for tuid, target, tt in dst:
                line, field, leaf = TARGETS[target.get("uid")]
                slot = int(tt.findtext("dco/i", "0"))
                require(slot % 12 == leaf, "line nested field changed")
                row = slot // 12
                bank, index = SOURCES[source.get("uid")], int(st.findtext("dco/i", "0"))
                expected = (
                    COMMANDS[line][row]
                    if field == "consigne"
                    else ("C1NI6071E", READINGS[line][row])
                )
                require((bank, index) == expected, "line source field changed")
                key = (line, row, field)
                require(key not in bindings, "duplicate line binding")
                bindings[key] = dict(
                    bank=bank,
                    index=index,
                    source_terminal=suid,
                    target_terminal=tuid,
                    native_flat_slot=slot,
                )
    require(len(bindings) == 40, "line display wire count changed")
    lines = {}
    for line, uid in (("direct", "7618"), ("deviated", "83226")):
        page = fp[uid]
        children = [fp[r.get("uid")] for r in page.findall("ddoList/*")]
        require(len(children) == len(COMMANDS[line]), "native line row count changed")
        coords = [
            tuple(map(int, re.findall(r"-?\d+", row.findtext("bounds"))))
            for row in children
        ]
        xs, ys = sorted({r[1] for r in coords}), sorted({r[0] for r in coords})
        rows = []
        for index, (row, box) in enumerate(zip(children, coords)):
            name = row.findtext("partsList/*/textRec/text").strip('"')
            fields = [fp[r.get("uid")] for r in row.findall("ddoList/*")]
            labels = [c.findtext("partsList/*/textRec/text").strip('"') for c in fields]
            require(
                len(fields) == 11
                and labels[0] == "M/A"
                and labels[4:7] == ["X1/X10", "Consigne", "Lecture"]
                and labels[7:] == ["<<", "<", ">", ">>"],
                "native line control field order changed",
            )
            range_labels = [
                c
                for c in row.iter()
                if c.get("class") == "label"
                and re.fullmatch(
                    r"-?\d+A? à -?\d+[A°]", c.findtext("textRec/text", "").strip('"')
                )
            ]
            require(
                len(range_labels) == 1, "native line range label missing or ambiguous"
            )
            range_label = range_labels[0].findtext("textRec/text").strip('"')
            require(
                range_label == RANGES[line][index], "native line range label changed"
            )
            formats = {
                key: fields[slot]
                .findtext("partsList/*[@class='numLabel']/format", "")
                .strip('"')
                for key, slot in (("consigne", 5), ("lecture", 6))
            }
            require(
                all(
                    f in ("%.0f", "%.1f", "%.2f", "%.2g", "%#_g")
                    for f in formats.values()
                ),
                "native line numeric format unsupported",
            )
            rows.append(
                dict(
                    index=index,
                    uid=row.get("uid"),
                    label=name,
                    column=xs.index(box[1]) + 1,
                    row=ys.index(box[0]) + 1,
                    native_bounds=list(box),
                    native_range_label=range_label,
                    native_range_uid=range_labels[0].get("uid"),
                    native_formats=formats,
                    native_buttons=native_buttons(
                        fields, labels, line, name.startswith("Correcteur"), steps
                    ),
                    unit="°" if name == "Phase HF / Laser" else "A",
                    consigne=bindings[line, index, "consigne"],
                    lecture=bindings[line, index, "lecture"],
                    status_qualified=False,
                    commands_enabled=False,
                )
            )
        lines[line] = dict(rows=rows, columns=len(xs), row_count=len(ys))
    png = embedded_synoptic(receipt, roots)
    return dict(
        source_vi_sha256=SOURCE_SHA,
        hardware_writes=False,
        saved_values_used_as_telemetry=False,
        display_wire_count=len(bindings),
        lines=lines,
        synoptic=dict(
            resource_id=75,
            width=866,
            height=596,
            png_sha256=hashlib.sha256(png).hexdigest(),
            static_diagram=True,
        ),
        limits=[
            "M/A, X1/X10 and three status lamps are not qualified live controls",
            "C6[8] is Réserve; physical H5 identity remains unqualified",
            "Native H5 and V5 Lecture both read C1[34]; not silently corrected",
            "Synoptic is the original static picture, not live equipment state",
        ],
    ), png


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    workspace, png = build_workspace()
    if args.write:
        WORKSPACE_OUTPUT.write_text(
            json.dumps(workspace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        IMAGE_OUTPUT.parent.mkdir(exist_ok=True)
        IMAGE_OUTPUT.write_bytes(png)
    print(
        json.dumps(
            dict(
                rows={k: len(v["rows"]) for k, v in workspace["lines"].items()},
                display_wires=workspace["display_wire_count"],
                synoptic=workspace["synoptic"],
            )
        )
    )
