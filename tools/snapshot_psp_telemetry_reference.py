"""Capture read-only lvkit evidence for the saved Everest PSP reader.

This records diagrams, not their execution. A successfully parsed VI is not a
proof of numeric equivalence. Parser warnings and unresolved dependencies must
remain visible to the reviewer. No LabVIEW, PSP, Tango or NI calls are made.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture_reference(source, output):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError("evidence output must be outside the VI source directory")
    if output.exists() and any(output.iterdir()):
        raise ValueError("evidence output directory must be empty")
    paths = sorted(source.rglob("*.vi"))
    if not paths or not (source / "psp_supervision.vi").is_file():
        raise ValueError("source must contain the saved psp_supervision.vi reader")
    before = {path: sha256(path) for path in paths}
    output.mkdir(parents=True, exist_ok=True)

    # Imports are delayed so safety/target checks also work without lvkit.
    from lvkit.extractor import extract_vi_xml
    from lvkit.graph import load_vi_by_path
    from lvkit.graph.netlist import build_netlist_from_graph, netlist_to_dict, render_lvnet
    from lvkit.load_mode import LoadMode

    records = []
    for path in paths:
        relative = path.relative_to(source)
        target = output / relative.with_suffix("")
        target.mkdir(parents=True, exist_ok=True)
        diagnostics = io.StringIO()
        record = {"source": str(path), "relative_path": relative.as_posix(),
                  "source_sha256": before[path], "executed": False}
        try:
            with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
                bd, fp, metadata = extract_vi_xml(path)
                for kind, artifact in (("diagram", bd), ("front_panel", fp), ("resource", metadata)):
                    if artifact is not None:
                        record[kind + "_sha256"] = sha256(artifact)
                        shutil.copy2(artifact, target / (kind + ".xml"))
                graph, key = load_vi_by_path(path, LoadMode.NONE)
                module = build_netlist_from_graph(graph, key)
                ir = netlist_to_dict(module, verbose=True)
                text = render_lvnet(module, display_name=graph.vi_display_name(key), verbose=True)
            (target / "netlist.json").write_text(
                json.dumps(ir, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            (target / "netlist.lvnet").write_text(text, encoding="utf-8")
            record["parsed"] = True
        except Exception as error:
            record["parsed"] = False
            record["parse_error"] = type(error).__name__ + ": " + str(error)
        (target / "diagnostics.txt").write_text(diagnostics.getvalue(), encoding="utf-8")
        record["source_unchanged"] = sha256(path) == before[path]
        if not record["source_unchanged"]:
            raise RuntimeError("VI source changed during evidence capture: " + str(path))
        records.append(record)

    report = {"source_directory": str(source), "load_mode": "none",
              "vi_count": len(records), "parsed_count": sum(r["parsed"] for r in records),
              "source_unchanged": all(sha256(p) == before[p] for p in paths),
              "runtime_equivalence_verified": False,
              "limits": ["No VI was run or saved.",
                         "No PSP, NI, Tango, socket or hardware calls were made.",
                         "Each VI is parsed independently; unresolved SubVI semantics are not inferred.",
                         "Saved constants/defaults are not live measurements.",
                         "Numeric equivalence requires matching acquisition data and PSP processing windows."],
              "vis": records}
    (output / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = capture_reference(args.source, args.output)
    print(json.dumps({key: report[key] for key in
                     ("vi_count", "parsed_count", "source_unchanged", "runtime_equivalence_verified")}))
    return 0 if report["parsed_count"] == report["vi_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
