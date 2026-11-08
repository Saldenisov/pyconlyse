"""Print native saved lifecycle diagrams. Offline only; executes no VI."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from build_acq_saved_diagram_census import call_names


def inspect(directory: Path) -> dict:
    bd = ET.parse(next(directory.glob("*_BDHb.xml"))).getroot()
    metadata = ET.parse(
        next(
            p
            for p in directory.glob("*.xml")
            if not p.stem.endswith(("_BDHb", "_FPHb"))
        )
    ).getroot()
    calls = call_names(metadata)
    result = {
        "calls": calls,
        "execution": metadata.find("LVSR/Section/Execution").attrib,
        "diagrams": [],
    }
    for diagram in (n for n in bd.iter() if n.get("class") == "diag"):
        nodes = []
        for n in diagram.findall("zPlaneList/*"):
            row = {"uid": n.get("uid"), "class": n.get("class")}
            if n.get("class") == "prim":
                row["primitive"] = n.findtext("primResID")
            if n.get("class") == "bDConstDCO":
                row["value"] = n.findtext("ConstValue")
            if n.get("class") == "iUse":
                row["call"] = calls.get(n.get("uid"))
                row["flags"] = n.findtext("objFlags")
            row["terms"] = [
                {
                    "uid": t.get("uid"),
                    "parm": t.findtext("dco/parmIndex"),
                    "type": t.findtext("dco/typeDesc"),
                }
                for t in n.findall("termList/*")
            ]
            nodes.append(row)
        result["diagrams"].append(
            {
                "uid": diagram.get("uid"),
                "nodes": nodes,
                "wires": [
                    {
                        "terms": [t.get("uid") for t in w.findall("termList/*")],
                        "state": w.findtext("state"),
                    }
                    for w in diagram.findall("signalList/*")
                ],
            }
        )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.directory), indent=2))
