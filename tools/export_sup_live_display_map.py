"""Export bounded read-only display wires from pinned, original Supervision XML.

No VI, generated VI code, network endpoint, driver or hardware is executed.
The JSON is a display projection, not a controller or safety decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from validate_sup_modulator_request_gate import cluster_fields, require

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / "Supervision/analysis/lvkit_eval/parser_release_20261003/00.json"
RECEIPT_SHA = "FE605F15D9A481749C945AF7F406315C73BA78E572C8225A6658EC4396042FD5"
OUTPUT = REPO / "web/frontend/src/elyseLiveDisplayMap.json"
SOURCE_SHA = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"

# Explicit source and destination mux identities, independently named by the
# original local-reference ledger. Field ordinals come from raw dco/i wires.
SOURCES = {
    "1559": "C3_IN_DIO96",
    "54131": "C4_IN_DIO96",
    "55130": "C1NI6071E",
    "51345": "C4_IN_DIO96",
    "42353": "C4_IN_DIO96",
    "58476": "C2NI6071E",
    "29989": "C4_IN_DIO96",
    "48101": "C4_IN_DIO96",
    "51278": "C2NI6071E",
    "54181": "C2NI6071E",
    "30843": "EPS",
}
TARGETS = {
    "31571": ("fluides", "Page Fluides"),
    "51304": ("modulateur", "Page Modulateur"),
    "40520": ("modulateur", "Page Modulateur"),
    "58415": ("modulateur", "Page Modulateur"),
    "43587": ("radioprotection", "Page Radioprotection"),
    "48263": ("ht", "Page HT"),
    "51369": ("ht", "Page HT"),
    "8476": ("hf", "Page HF"),
    "61263": ("modulateur", "Page Modulateur"),
}
UNITS = {
    "fluides": {5: "°C", 22: "°C"},
    "modulateur": dict(
        zip(
            range(31, 45),
            ["kV", "A", "kA", "V", "A", "A", "A", "A", "V", "A", "V", "A", "A", "A"],
        )
    ),
    "ht": {2: "A", 3: "kV", 17: "kV"},
    "hf": {0: "dB", 12: "°", 22: "°", 23: "MW", 24: "MW"},
}
LABELS = {
    "fluides": {5: "Température CANON · lecture", 22: "Température SECTION · lecture"},
    "modulateur": dict(
        zip(
            range(31, 45),
            [
                "Mesure V LAR",
                "I fin de ligne",
                "I Thyratron",
                "V chauffage Thyratron",
                "I chauffage Thyratron",
                "I réservoir Thyratron",
                "Courant de prémagnétisation",
                "I Klystron",
                "V Klystron",
                "I chauffage Klystron",
                "V chauffage Klystron",
                "I Focale 1",
                "I Focale 2",
                "I Focale 3",
            ],
        )
    ),
    "ht": {2: "Mesure I HT", 3: "Mesure V HT", 17: "Lecture HT"},
    "hf": {
        0: "Position atténuateur HF · lecture",
        12: "Position déphaseur HF · lecture",
        22: "Position déphaseur manuel",
        23: "Niveau HF du CANON",
        24: "Niveau HF de la SECTION",
    },
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def original():
    require(digest(RECEIPT) == RECEIPT_SHA, "original source receipt changed")
    receipt = json.loads(RECEIPT.read_text("utf-8"))
    require(
        receipt["sha256"] == SOURCE_SHA and digest(receipt["source"]) == SOURCE_SHA,
        "original Supervision VI changed",
    )
    roots = {}
    for entry in receipt["xml"]:
        require(
            digest(entry["path"]) == entry["sha256"], "original XML identity changed"
        )
        suffix = (
            "bd"
            if entry["path"].endswith("_BDHb.xml")
            else "fp"
            if entry["path"].endswith("_FPHb.xml")
            else "meta"
        )
        roots[suffix] = ET.parse(entry["path"]).getroot()
    return receipt, roots


def build_map():
    receipt, roots = original()
    root, meta = roots["bd"], roots["meta"]
    defs = {n.get("uid"): n for n in root.iter() if n.get("class")}
    owners = {}
    for n in defs.values():
        if n.get("class") in ("term", "diag", "signal"):
            continue
        for t in n.findall("termList/*"):
            owners[t.get("uid")] = (n, t)
    wire_sets = [
        {t.get("uid") for t in n.findall("termList/*")}
        for n in root.iter()
        if n.get("class") == "signal"
    ]
    local_names = {row["uid"]: row["name"] for row in receipt["locals"]}

    def check_mux_identity(uid, expected, output):
        node = defs[uid]
        agg = node.find("dcoAgg").get("uid")
        ports = [
            t.get("uid")
            for t in node.findall("termList/*")
            if t.find("dco").get("uid") == agg
            and bool(int(t.findtext("objFlags") or "0") & 0x8000) != output
        ]
        require(len(ports) == 1, "mux aggregate direction changed")
        refs = {
            local_names[n.get("uid")]
            for group in wire_sets
            if ports[0] in group
            for term in group
            if term in owners
            for n, _ in [owners[term]]
            if n.get("class") == "gRef"
        }
        require(refs == {expected}, f"mux bank/page identity changed: {uid}: {refs}")

    for uid, bank in SOURCES.items():
        check_mux_identity(uid, bank, False)
    for uid, (_, label) in TARGETS.items():
        check_mux_identity(uid, label, True)

    def connected(a, b):
        require(any({a, b} <= group for group in wire_sets), f"wire changed: {a}->{b}")

    def slot(t):
        return int(t.findtext("dco/i") or "0")

    flat_types = meta.findall("VCTP/Section/TypeDesc")

    def top_slot(label, raw):
        cluster = next(
            n
            for n in flat_types
            if n.get("Type") == "Cluster" and n.get("Label") == label
        )
        flattened = []

        def append(node, path):
            flattened.append(path)
            if node.get("Type") == "Cluster":
                for j, child in enumerate(node):
                    append(flat_types[int(child.get("TypeID"))], path + (j,))

        for j, child in enumerate(cluster):
            append(flat_types[int(child.get("TypeID"))], (j,))
        require(
            raw < len(flattened) and len(flattened[raw]) == 1,
            "nested display target needs explicit mapping",
        )
        return flattened[raw][0]

    def rule(page, page_type, target, bank, index, source_term, target_term, **extra):
        fields = cluster_fields(meta, page_type)
        require(
            target < len(fields),
            f"{page_type}: target ordinal {target}, source {source_term}, "
            f"destination {target_term}",
        )
        label = fields[target]
        # Saved 2012 labels contain replacement characters. Do not fabricate
        # their encoding; repair only familiar spelling for presentation.
        clean = label
        for bad, good in [
            ("D�fauts", "Défauts"),
            ("d�bim�tre", "débitmètre"),
            ("R�sistivit�", "Résistivité"),
            ("S�curit�", "Sécurité"),
            ("l�g�re", "légère"),
            ("d�faut", "défaut"),
        ]:
            clean = clean.replace(bad, good)
        return dict(
            id=f"{page}:{target}",
            page=page,
            label=LABELS.get(page, {}).get(target, clean),
            bank=bank,
            index=index,
            unit=UNITS.get(page, {}).get(target, ""),
            kind="number" if target in UNITS.get(page, {}) else "boolean",
            role="software_flag" if bank == "EPS" else "readback",
            target_field=target,
            source_terminal=source_term,
            target_terminal=target_term,
            transform="identity",
            **extra,
        )

    rules = []
    for group in wire_sets:
        src = [
            (uid, *owners[uid])
            for uid in group
            if uid in owners
            and owners[uid][0].get("uid") in SOURCES
            and owners[uid][1].find("dco/i") is not None
        ]
        # Zero ordinal may omit i; exclude only the cluster input by checking
        # that the mux terminal is an output (objFlags bit 0x8000 is input).
        src += [
            (uid, *owners[uid])
            for uid in group
            if uid in owners
            and owners[uid][0].get("uid") in SOURCES
            and owners[uid][1].find("dco/i") is None
            and not (int(owners[uid][1].findtext("objFlags") or "0") & 0x8000)
        ]
        dest = [
            (uid, *owners[uid])
            for uid in group
            if uid in owners
            and owners[uid][0].get("uid") in TARGETS
            and owners[uid][1].find("dco") is not None
            and owners[uid][1].find("dco").get("class") == "nmxDCO"
            and int(owners[uid][1].findtext("objFlags") or "0") & 0x8000
        ]
        for suid, sn, st in src:
            for tuid, tn, tt in dest:
                page, pt = TARGETS[tn.get("uid")]
                rules.append(
                    rule(
                        page,
                        pt,
                        top_slot(pt, slot(tt)),
                        SOURCES[sn.get("uid")],
                        slot(st),
                        suid,
                        tuid,
                    )
                )

    # Three explicit focal-current multipliers: these are not direct wires.
    for source, prim, literal, output, index, target, scale in (
        ("50320", "73186", "161658", "42597", 5, 42, 3.0),
        ("43790", "47338", "172267", "42672", 13, 43, 4.11),
        ("61534", "84980", "131742", "42698", 6, 44, 4.14),
    ):
        node = defs[prim]
        require(node.findtext("primResID") == "1052", "focal multiplier changed")
        terms = node.findall("termList/*")
        connected(source, terms[2].get("uid"))
        connected(literal, terms[1].get("uid"))
        connected(terms[0].get("uid"), output)
        raw = owners[literal][1].findtext("dco/ConstValue")
        value = (
            struct.unpack(">d", bytes.fromhex(raw))[0]
            if len(raw) == 16
            else int(raw, 16)
        )
        require(value == scale, "focal scale changed")
        rules.append(
            rule(
                "modulateur",
                "Page Modulateur",
                target,
                "C2NI6071E",
                index,
                source,
                output,
                scale=scale,
            )
        )

    # Active pressure path: main sequence9424 frame9 -> autoindexed for115256.
    # Array order is explicit, then (raw - offset) * gain, then six page fields.
    offsets = [0.0026, 0.00305, 0.003, 0.0018, 0.0027, 0.0022]
    gains = [-4e-6, -2e-6, -2e-6, -2e-6, -1e-6, -1e-6]
    for uid, expected in [("136502", offsets), ("130869", gains)]:
        raw = bytes.fromhex(owners[uid][1].findtext("dco/ConstValue"))
        require(
            struct.unpack(">I6d", raw) == (6, *expected), "pressure calibration changed"
        )
    for a, b in [
        ("130869", "169278"),
        ("136502", "171824"),
        ("107680", "174474"),
        ("171820", "177035"),
        ("174470", "177038"),
        ("177032", "187042"),
        ("169274", "187039"),
        ("187036", "192062"),
        ("192063", "88486"),
        ("88483", "94078"),
        ("197457", "197483"),
    ]:
        connected(a, b)
    require(
        defs["177026"].findtext("primResID") == "1051"
        and defs["187030"].findtext("primResID") == "1052",
        "pressure arithmetic changed",
    )
    # Native Subtract positional slot1=y (offset), slot2=x (raw).
    for index, target, label, suid, build_port, out, dst in zip(
        range(12, 18),
        [3, 5, 7, 12, 9, 17],
        ["Sas Guide HF", "CANON", "SECTION", "MIROIR", "DIPOLE 1", "ECRAN N°1"],
        ["58018", "71860", "81335", "81340", "81343", "81346"],
        ["107683", "110234", "110239", "110242", "110245", "110248"],
        ["94081", "94084", "99573", "99570", "99567", "99564"],
        ["197467", "197470", "197473", "197476", "71662", "71677"],
    ):
        require(
            slot(owners[suid][1]) == index and slot(owners[dst][1]) == target,
            "pressure ordinal changed",
        )
        if index in (15, 16):
            # These two inputs pass through Mean PtByPt.vi (30 native
            # samples). A 1 Hz latest-only web client cannot reconstruct
            # the exact native filter state; expose that limit in the UI.
            inp, outp, nport = {
                15: ("186178", "186187", "186181"),
                16: ("191199", "191208", "191202"),
            }[index]
            connected(suid, inp)
            connected(outp, build_port)
            connected("216586", nport)
            require(
                owners["216586"][1].findtext("dco/ConstValue") == "0000001E",
                "native mean length changed",
            )
        else:
            connected(suid, build_port)
        connected(out, dst)
        rules.append(
            dict(
                id=f"vide:{target}",
                page="vide",
                label=label,
                bank="VAM-A",
                index=index,
                kind="number",
                unit="mbar",
                role="readback",
                transform="offset_gain",
                offset=offsets[index - 12],
                scale=gains[index - 12],
                native_filter_samples=30 if index in (15, 16) else 1,
                temporal_equivalence=index not in (15, 16),
                source_terminal=suid,
                target_terminal=dst,
                target_field=target,
            )
        )
    for index, target, label, src, dst in [
        (11, 1, "Chambre de préparation", "64175", "197464"),
        (10, 14, "TPG300 SECTION", "71846", "197461"),
    ]:
        connected(src, dst)
        rules.append(
            dict(
                id=f"vide:{target}",
                page="vide",
                label=label,
                bank="VAM-A",
                index=index,
                kind="number",
                unit="mbar",
                role="readback",
                transform="identity",
                source_terminal=src,
                target_terminal=dst,
                target_field=target,
            )
        )

    # Formula-node display conversions, copied literally, not Python eval.
    for uid, index, target, expected, transform in [
        (
            "62998",
            36,
            12,
            "y=(1.1309*x**3)-(5.746*x**2)-(40.368*x)+102.28;",
            "phase_polynomial",
        ),
        (
            "118669",
            37,
            22,
            "y=(1.1309*x**3)-(5.746*x**2)-(40.368*x)+102.28;",
            "phase_polynomial",
        ),
        (
            "75159",
            44,
            0,
            "y=-20*log(cos((2*3.1416/360)*(1.2087*x**3-6.5232*x**2-15.097*x+86.932)));",
            "attenuator_formula",
        ),
    ]:
        require(
            defs[uid].findtext("formula/text").strip('"') == expected,
            "HF formula changed",
        )
        # NI Formula Node log(x) is base 10, unlike C's log(x). Preserve the
        # literal 3.1416 and reject nonpositive cosine in the display projection.
        # https://www.ni.com/docs/en-US/bundle/labview/page/formula-node-and-expression-node-functions.html
        terms = defs[uid].findall("termList/*")
        src = next(
            t.get("uid") for t in defs["3100"].findall("termList/*") if slot(t) == index
        )
        dst = next(
            t.get("uid")
            for t in defs["8476"].findall("termList/*")
            if slot(t) == target
            and t.find("dco").get("uid") != defs["8476"].find("dcoAgg").get("uid")
        )
        connected(src, terms[0].get("uid"))
        connected(terms[1].get("uid"), dst)
        row = rule("hf", "Page HF", target, "C1NI6071E", index, src, dst)
        row["transform"] = transform
        rules.append(row)
    rules.sort(key=lambda row: (row["page"], row["target_field"]))
    require(
        len({row["id"] for row in rules}) == len(rules), "duplicate display destination"
    )
    return dict(
        schema_version=1,
        source_vi_sha256=SOURCE_SHA,
        source_receipt_sha256=RECEIPT_SHA,
        hardware_writes=False,
        whole_runtime_equivalence=False,
        color_polarity_qualified=False,
        atomic_snapshot=False,
        rules=rules,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    actual = build_map()
    if args.write:
        OUTPUT.write_text(
            json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    require(
        json.loads(OUTPUT.read_text("utf-8")) == actual,
        "frontend map differs from pinned wires",
    )
    print(
        f"PASS: {len(actual['rules'])} source-derived display projections; "
        "no native execution"
    )


if __name__ == "__main__":
    main()
