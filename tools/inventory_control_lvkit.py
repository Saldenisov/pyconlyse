"""Quarantined generation queue for saved Acquisition/Supervision/TRANCON VIs.

Parse/generate/compile != behavioral qualification. No generated code is
executed, no dependency VI is run, and originals are hash checked afterward.
Each VI runs in a bounded subprocess. Generated artifacts can be written
to a NEW directory; existing reports and source files are never overwritten.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from qualify_acq_lvkit import (
    DEFAULT_CHECKOUT,
    DEFAULT_SOURCE,
    REPO,
    digest,
    verify_checkout,
)

SUP_MANIFEST = (
    REPO / "Supervision/analysis/lvkit_eval/batch_0_8_4_minimal_vilib/manifest.json"
)
TRANCON_LEDGER = (
    REPO / "docs/data-treatment/TRANCON_CLIENT_SOURCE_LEDGER_2026-10-02.csv"
)
WIRE_LEDGERS = [
    REPO / f"docs/data-treatment/TRANCON_CLIENT_{name}_2026-10-02.csv"
    for name in ("WIRE_EVIDENCE", "CONTINUATION_WIRES")
]
ACQ_MANIFEST = DEFAULT_SOURCE.parent.parent / "member_manifest.json"
ACQ_MANIFEST_SHA256 = "1DCE49EAD711CBDD7AB75578D5655AACEFA6A47C6B445D8FED2C4D402A0A37E0"


def acquisition_inventory():
    """Only the 17 original members; current hashes must match the pinned ledger."""
    if digest(ACQ_MANIFEST) != ACQ_MANIFEST_SHA256:
        raise RuntimeError("Original Acquisition member manifest changed")
    manifest = json.loads(ACQ_MANIFEST.read_text(encoding="utf-8"))
    if manifest["member_count"] != 17 or len(manifest["members"]) != 17:
        raise RuntimeError("Original Acquisition member census changed")
    records = []
    for row in manifest["members"]:
        source = DEFAULT_SOURCE / row["name"]
        expected = row["sha256"].upper()
        if digest(source) != expected:
            raise RuntimeError("Original Acquisition source changed: " + row["name"])
        records.append(
            {
                "corpus": "acquisition",
                "source": str(source),
                "prior_sha256": expected,
                "manual_evidence": (
                    "Original XML archive and wire validators available; "
                    "this batch supplies no reviewed local-variable bindings"
                ),
            }
        )
    return records


def inventory():
    reviewed = set()
    for path in WIRE_LEDGERS:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reviewed.update(row["source_relative"] for row in csv.DictReader(stream))
    records = []
    for row in json.loads(SUP_MANIFEST.read_text(encoding="utf-8"))["items"]:
        records.append(
            {
                "corpus": "supervision",
                "source": row["source_path"],
                "prior_sha256": row["sha256"].upper(),
                "prior_generation_exit": row["generate_exit"],
                "manual_evidence": (
                    "Existing screenshot corpus; per-VI reconciliation pending"
                ),
            }
        )
    with TRANCON_LEDGER.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            records.append(
                {
                    "corpus": "trancon",
                    "source": row["source_absolute"],
                    "parse_source": row["parse_copy_absolute"]
                    or row["source_absolute"],
                    "prior_sha256": row["source_sha256"].upper(),
                    "manual_evidence": "STATIC_WIRE_RECORDS"
                    if row["source_relative"] in reviewed
                    else "NO_WIRE_RECORD_IN_CLIENT_AUDIT",
                    "prior_report": row["report_absolute"],
                }
            )
    return records


def inspect_generated(source):
    """Find review priorities. Absence of markers never qualifies a module."""
    tree = ast.parse(source)
    compile(tree, "<quarantined-generation>", "exec")
    markers = Counter()
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and n.value is None:
            markers["none_literal"] += 1
        if isinstance(n, ast.Raise):
            markers["raise_statement"] += 1
        if isinstance(n, (ast.While, ast.For)):
            markers["loop_requires_semantic_review"] += 1
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            markers["attribute_call_requires_IO_review"] += 1
        if isinstance(n, ast.ImportFrom) and n.module not in (
            "__future__",
            "typing",
            "lvkit.runtime",
            "lvkit.positional_cluster",
        ):
            markers["unreviewed_import"] += 1
    for token in ("WARNING:", "placeholder", "unresolved"):
        if token in source:
            markers[token] += source.count(token)
    return dict(markers)


def converter_fingerprint():
    """Pin Python generators and resolver data, including untracked overlay."""
    fingerprint = hashlib.sha256()
    root = DEFAULT_CHECKOUT / "src"
    for path in sorted(p for p in root.rglob("*") if p.suffix in (".py", ".json")):
        fingerprint.update(str(path.relative_to(root)).replace("\\", "/").encode())
        fingerprint.update(b"\0")
        fingerprint.update(bytes.fromhex(digest(path)))
    return fingerprint.hexdigest().upper()


def probe(path, load_mode="none"):
    from lvkit.codegen.builder import build_module
    from lvkit.graph import InMemoryVIGraph, LoadMode

    graph = InMemoryVIGraph()
    before = converter_fingerprint()
    result = {
        "converter_fingerprint": before,
        "load_mode": load_mode,
        "parse": "PENDING",
        "generation": "PENDING",
        "compile": "PENDING",
        "generated_execution": False,
        "behavioral_qualification": "NOT_QUALIFIED",
        "deployable": False,
    }
    warnings = io.StringIO()
    unresolved = []
    with contextlib.redirect_stderr(warnings):
        try:
            key = graph.load_vi(
                path,
                mode=LoadMode(load_mode),
                search_paths=[
                    path.parent,
                    Path("C:/dev/TRANCON"),
                    REPO / "Supervision/extracted/PILOTAGE_ELYSE_SUP",
                ],
            )
            result["parse"] = "OK"
            result["locals_requiring_binding_review"] = sum(
                1
                for _, data in graph._graph.nodes(data=True)
                if (node := data.get("node"))
                and node.vi_path == key
                and node.node_type == "gRef"
            )
            result["source"] = (
                build_module(
                    graph.get_vi_context(key),
                    key,
                    graph=graph,
                    soft_unresolved=True,
                    unresolved_sink=unresolved,
                )
                + "\n"
            )
            result["generation"] = "OK"
            result["markers"] = inspect_generated(result["source"])
            result["compile"] = "OK"
        except Exception as exc:
            result["error"] = {"type": type(exc).__name__, "message": str(exc)[:4000]}
            if result["parse"] == "PENDING":
                result["parse"] = "FAILED"
            elif result["generation"] == "PENDING":
                result["generation"] = "FAILED"
            else:
                result["compile"] = "FAILED"
    result["unresolved"] = [
        {"type": type(e).__name__, "message": str(e)[:2000]} for e in unresolved
    ]
    result["parser_warnings"] = warnings.getvalue()[:6000]
    if converter_fingerprint() != before:
        raise RuntimeError(
            "Converter changed while generating; retry in a stable checkout"
        )
    return result


def batch(records, timeout=30, load_mode="none"):
    results, sources = [], {}
    environment = dict(os.environ, PYTHONIOENCODING="utf-8")
    for row in records:
        original = Path(row["source"])
        if not original.exists():
            results.append(
                dict(
                    row,
                    status="SOURCE_MISSING",
                    behavioral_qualification="NOT_QUALIFIED",
                )
            )
            continue
        before = digest(original)
        copy_path = Path(row.get("parse_source", original))
        base = dict(
            row,
            current_sha256=before,
            changed_since_prior=before != row["prior_sha256"],
        )
        if row["corpus"] in ("trancon", "acquisition") and base["changed_since_prior"]:
            results.append(dict(base, status="SOURCE_CHANGED_REVIEW_REQUIRED"))
            continue
        if not copy_path.exists() or digest(copy_path) != before:
            results.append(dict(base, status="PARSE_COPY_MISSING_OR_DIFFERENT"))
            continue
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--probe",
                    str(copy_path),
                    "--load-mode",
                    load_mode,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=environment,
                timeout=timeout,
            )
            if completed.returncode:
                result = {"status": "PROBE_FAILED", "error": completed.stderr[-4000:]}
            else:
                result = json.loads(completed.stdout)
                source = result.pop("source", None)
                if source:
                    artifact = (
                        row["corpus"]
                        + "_"
                        + hashlib.sha256(str(original).encode()).hexdigest()[:16]
                        + ".py.txt"
                    )
                    sources[artifact] = source
                    result["generated_artifact"] = "quarantine/" + artifact
                    result["generated_sha256"] = (
                        hashlib.sha256(source.encode()).hexdigest().upper()
                    )
        except subprocess.TimeoutExpired:
            result = {"status": "TIMEOUT", "timeout_seconds": timeout}
        if digest(original) != before or digest(copy_path) != before:
            raise RuntimeError(f"Source changed during probe: {original}")
        results.append(dict(base, **result))
    counts = Counter(
        (row.get("generation", row.get("status", "UNKNOWN"))) for row in results
    )
    return {
        "summary": {
            "selected": len(records),
            "counts": dict(counts),
            "behaviorally_qualified": 0,
            "generated_python_execution": False,
            "vi_execution": False,
            "hardware_access": False,
            "load_mode": load_mode,
            "whole_business_logic_covered": False,
        },
        "items": results,
        "generated_sources": sources,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path)
    parser.add_argument(
        "--corpus", choices=("control", "acquisition"), default="control"
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--load-mode", choices=("none", "minimal"), default="none")
    parser.add_argument("--source-filter", help="case-insensitive literal substring")
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        help="new generated-artifact directory, never overwritten",
    )
    args = parser.parse_args()
    verify_checkout(DEFAULT_CHECKOUT)
    if args.output and args.output.exists():
        parser.error("output directory already exists; choose a new run directory")
    if args.probe:
        result = probe(args.probe, args.load_mode)
    else:
        rows = acquisition_inventory() if args.corpus == "acquisition" else inventory()
        # All Supervision roots first, then TRANCON paths with no prior wire
        # records, then those already reviewed. This is not a coverage claim.
        rows.sort(
            key=lambda r: (
                r["corpus"] != "supervision",
                r["manual_evidence"] == "STATIC_WIRE_RECORDS",
                r["source"],
            )
        )
        if args.source_filter:
            rows = [
                r for r in rows if args.source_filter.lower() in r["source"].lower()
            ]
        if args.limit is not None:
            rows = rows[: args.limit]
        started = time.perf_counter()
        result = (
            {"items": rows, "total": len(rows)}
            if args.inventory_only
            else batch(rows, args.timeout, args.load_mode)
        )
        if "summary" in result:
            result["summary"]["elapsed_seconds"] = round(
                time.perf_counter() - started, 3
            )
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
        generated = result.pop("generated_sources", {})
        quarantine = args.output / "quarantine"
        quarantine.mkdir()
        for name, source in generated.items():
            (quarantine / name).write_text(source, encoding="utf-8", newline="\n")
        (args.output / "manifest.json").write_text(
            json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(result.get("summary", {"total": result.get("total")}), indent=2)
        )
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
