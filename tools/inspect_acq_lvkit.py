"""Read-only, bounded diagnostics for the experimental local lvkit checkout."""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", type=Path)
    parser.add_argument("vi", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(args.checkout / "src"))
    from lvkit.extractor import extract_vi_xml
    from lvkit.graph import InMemoryVIGraph, LoadMode

    bd_path, fp_path, _ = extract_vi_xml(args.vi)
    for label, path, classes in (
        ("BD", bd_path, ("fPDCO", "gRef")),
        ("FP", fp_path, ("fPDCO",)),
    ):
        root = ET.parse(path).getroot()
        if args.summary and label == "BD":
            for diag in root.iter():
                if diag.get("class") == "diag":
                    print(
                        "DIAGRAM",
                        diag.get("uid"),
                        [
                            (n.get("class"), n.get("uid"))
                            for n in diag.findall("nodeList/*")
                        ],
                    )
            for node in root.iter():
                if node.get("class") in ("nMux", "prim", "gRef"):
                    print(
                        "NODE",
                        node.get("class"),
                        node.get("uid"),
                        node.findtext("primID"),
                        [
                            (
                                t.get("uid"),
                                t.findtext("dco/i"),
                                t.findtext("dco/paramIdx"),
                            )
                            for t in node.findall("termList/*")
                        ],
                    )
            continue
        if args.summary:
            continue
        for node in root.iter():
            if node.get("class") in classes:
                print(label, ET.tostring(node, encoding="unicode")[:1700])
    graph = InMemoryVIGraph()
    key = graph.load_vi(args.vi, mode=LoadMode.NONE)
    for _, data in graph._graph.nodes(data=True):
        node = data.get("node")
        if node and node.vi_path == key and node.node_type == "gRef":
            print("LOCAL", node.model_dump(exclude={"terminals"}))
    print(
        "IO",
        [
            (t.id, t.index, t.name)
            for t in graph.get_vi_context(key).inputs
            + graph.get_vi_context(key).outputs
        ],
    )


if __name__ == "__main__":
    main()
