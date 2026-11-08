"""Test candidate LabVIEW local-variable parameter mappings by type.

This is a negative-control check on lvkit's current paramIdx -> front-panel
z-order assumption.  A mismatch proves that candidate mapping is false for
that reference; a match alone cannot establish identity (many controls share
the same type).  Only XML exported from an offline VI is read.
"""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


TYPE_RE = re.compile(r"Heap TypeID\s+(\d+)\s+= Consolidated TypeID\s+\d+: (\w+)")
TYPE_ID_RE = re.compile(r"TypeID\((\d+)\)")


def broad_kind(raw: str | None) -> str:
    if not raw:
        return "unknown"
    if raw.startswith(("Num", "Unit")):
        return "number"
    if "Bool" in raw:
        return "boolean"
    if "Cluster" in raw:
        return "cluster"
    if "Array" in raw:
        return "array"
    if "String" in raw:
        return "string"
    if "Path" in raw:
        return "path"
    if "Refnum" in raw or "Ref" in raw:
        return "refnum"
    return raw.lower()


def type_id(element: ET.Element | None) -> int | None:
    if element is None or not element.text:
        return None
    match = TYPE_ID_RE.fullmatch(element.text.strip())
    return int(match.group(1)) if match else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    parser.add_argument("fphb_xml", type=Path)
    parser.add_argument("main_xml", type=Path)
    args = parser.parse_args()

    main_text = args.main_xml.read_text(encoding="utf-8")
    type_names = {int(idx): kind for idx, kind in TYPE_RE.findall(main_text)}
    tm80_text = main_text.split("<TM80>", 1)[1].split("</TM80>", 1)[0]
    tm80_types = {int(idx): kind for idx, kind in re.findall(r"<!-- TypeID\s+(\d+): (\w+) -->", tm80_text)}
    fp = ET.parse(args.fphb_xml).getroot()
    panel_controls = [node for node in fp.findall(".//*[@class='fPDCO']") if node.find("ddo") is not None]
    panel_by_uid = {node.get("uid", ""): node for node in panel_controls}
    bd = ET.parse(args.bdhb_xml).getroot()
    first_srn = bd.find(".//*[@class='sRN']")
    srn_controls = []
    if first_srn is not None:
        term_list = first_srn.find("termList")
        if term_list is not None:
            srn_controls = [panel_by_uid.get(term.find("dco").get("uid", "")) for term in term_list if term.find("dco") is not None]

    refs = []
    for node in bd.findall(".//*[@class='gRef']"):
        dco = node.find("termList/*/dco")
        if dco is None:
            continue
        idx_text = dco.findtext("paramIdx")
        if idx_text is None or not idx_text.isdigit():
            continue
        ref_type = type_names.get(type_id(dco.find("typeDesc")), "")
        refs.append((node.get("uid", ""), int(idx_text), broad_kind(ref_type), ref_type))

    print(f"gRefs with numeric paramIdx: {len(refs)}; fPDCOs: {len(panel_controls)}; first sRN terminals: {len(srn_controls)}")
    kinds_by_param: dict[int, set[str]] = defaultdict(set)
    for _uid, param_idx, ref_kind, _ref_type in refs:
        kinds_by_param[param_idx].add(ref_kind)
    mixed = {idx: kinds for idx, kinds in kinds_by_param.items() if len(kinds) > 1}
    print(f"unique paramIdx values: {len(kinds_by_param)}; values with multiple broad types: {len(mixed)}")
    for idx, kinds in sorted(mixed.items())[:12]:
        print(f"  paramIdx {idx}: {', '.join(sorted(kinds))}")
    tm80_scores = []
    for offset in range(0, 101):
        checked = matches = 0
        for _uid, param_idx, ref_kind, _ref_type in refs:
            candidate = broad_kind(tm80_types.get(param_idx + offset))
            if candidate == "unknown" or ref_kind == "unknown":
                continue
            checked += 1
            matches += candidate == ref_kind
        tm80_scores.append((matches / checked if checked else 0, offset, checked, matches))
    print("best TM80 TypeID offsets (type compatibility only):")
    for score, offset, checked, matches in sorted(tm80_scores, reverse=True)[:5]:
        print(f"  TypeID=paramIdx+{offset}: {matches}/{checked} matches ({score:.1%})")
    for sequence_name, sequence in (("FP XML order", panel_controls), ("first sRN term order", srn_controls)):
        for offset in (-1, 0, 1):
            checked = matches = mismatches = 0
            examples = []
            for uid, param_idx, ref_kind, ref_type in refs:
                pos = param_idx + offset
                if pos < 0 or pos >= len(sequence) or sequence[pos] is None:
                    continue
                control = sequence[pos]
                fp_type = type_names.get(type_id(control.find("typeDesc")), "")
                control_kind = broad_kind(fp_type)
                if ref_kind == "unknown" or control_kind == "unknown":
                    continue
                checked += 1
                if ref_kind == control_kind:
                    matches += 1
                else:
                    mismatches += 1
                    if len(examples) < 3:
                        examples.append(f"gRef {uid} param {param_idx}: {ref_type} vs fPDCO {control.get('uid')} {fp_type}")
            print(f"{sequence_name} offset {offset:+d}: checked={checked} matches={matches} mismatches={mismatches}")
            for example in examples:
                print(f"  {example}")


if __name__ == "__main__":
    main()
