"""Regenerate bounded TRANCON numeric modules with the pinned private lvkit fork.

Only the runtime import is adapted in generated VI bodies. No devices or
LabVIEW UI are accessed. Native diagram verification remains a separate gate.
"""

import argparse
import ast
import csv
import hashlib
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "legacy" / "trancon_client"
UPSTREAM_COMMIT = "d8058677e15c47094e725439bd72417fe9527754"
SOURCE_HASHES = {
    "Raw_data_to_data.vi": "a062b8bbea298c8e4169719e0d79b7e7c3e9dde0403d94658cbc10d6cf08cabc",
    "-log bis_SD.vi": "2e1313a6d2064bb92e3371e1df3b80a848542efd72c4e9300c0266b95a638fa1",
    "ScaleUp_corrSD.vi": "84a9eb8cf1c02880f3987161806971a80540d29d74fb62f19a51eadecd60d0ea",
    "Raw_BG_corrSD.vi": "38a2f312a2236e5425f73d14b2858d83385633ab296ae2cb9d59016f9c2ea83a",
    "average_array_poly.vi": "2e984c1c6566c9f4dddb9f31ee4d07d72ec59800e04b20dfba2cb03bd7aeb42b",
    "average-2Darray-SD_double.vi": "caac499824ac2a09a371c67fb46b7c63df443d6cd65cb25606fb21e44a7e7816",
    "average-2Darray-SD_int.vi": "f3593311293fda510eecf3795e16ba194fca71a236df82a113aec67d3e950548",
}
JOBS = (
    ("raw_data", "Raw_data_to_data.vi", "raw_data_to_data", "exp_data"),
    ("log_transmission", "-log bis_SD.vi", "_log_bis_sd", "output_logxlog1x"),
    ("scale", "ScaleUp_corrSD.vi", "scaleup_corrsd", "data_corrected"),
    ("raw_background", "Raw_BG_corrSD.vi", "raw_bg_corrsd", "data_corrected"),
)
RUNTIME_FUNCTIONS = {
    "_binop", "_unop", "sub", "mul", "_real64_divide_scalar", "real64_divide",
    "_real64_log10_scalar", "log10", "index_array_nd", "mean_real64", "array_size",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converter", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--vi-root", type=Path, default=Path(r"C:\dev\TRANCON"))
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    args.converter = args.converter.resolve(strict=True)
    upstream = subprocess.check_output(
        ["git", "-C", str(args.converter), "rev-parse", "HEAD"], text=True).strip()
    if upstream != UPSTREAM_COMMIT:
        raise RuntimeError(f"Expected lvkit base {UPSTREAM_COMMIT}; found {upstream}")
    for filename, expected in SOURCE_HASHES.items():
        source = args.vi_root / "dependecies" / filename
        if digest(source) != expected:
            raise RuntimeError(f"Source fingerprint changed: {source}")
    env = {**os.environ, "PYTHONPATH": str(args.converter / "src")}
    records = []

    def record(kind, path, note="", source_hash=""):
        records.append({"kind": kind, "path": str(path), "sha256": digest(path),
                        "generated_original_sha256": source_hash, "note": note})

    TARGET.mkdir(parents=True, exist_ok=True)
    exports = [
        '"""Offline lvkit translations; native diagram verification is pending.',
        "",
        "Inputs are nested Python lists, RAW channel order BGI/BGII/IeI/IeII/I0I/I0II.",
        "Qualified numeric domain: rectangular arrays and counts 0..65535.",
        'No automatic rejection of shot slots or NaN/Inf cleanup is applied."""',
    ]
    for package, filename, function, field in JOBS:
        source = args.vi_root / "dependecies" / filename
        record("source_vi", source, "Native screenshots not verified")
        job_work = args.work / package
        result = subprocess.run(
            [str(args.python), "-m", "lvkit", "generate", str(source), "-o", str(job_work),
             "--load-mode", "minimal", "--no-auto-vilib"],
            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        job_work.mkdir(parents=True, exist_ok=True)
        (job_work / "generation.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode or "-> FAILED" in result.stdout or "# ERROR generating" in result.stdout:
            raise RuntimeError(f"Generation failed for {source}: {result.stdout}\n{result.stderr}")
        destination = TARGET / package
        destination.mkdir(exist_ok=True)
        module = None
        for original in sorted(job_work.glob("*/*.py")):
            content = original.read_text(encoding="utf-8")
            if "# ERROR generating" in content:
                raise RuntimeError(f"Unqualified generated variant in {original}")
            adapted = content.replace("from lvkit.runtime import lv as _lv",
                                      "from .. import _lv_runtime as _lv")
            ast.parse(adapted)
            output = destination / original.name
            output.write_text(adapted, encoding="utf-8", newline="\n")
            record("generated_python", output, "Only runtime import adapted", digest(original))
            if any(isinstance(n, ast.FunctionDef) and n.name == function
                   for n in ast.parse(adapted).body):
                module = original.stem
        if module is None:
            raise RuntimeError(f"No generated function {function}")
        exports.append(f"from .{package}.{module} import {function} as {package}")

    # Extract exact runtime definitions rather than hand-reimplementing formulas.
    runtime_path = args.converter / "src/lvkit/runtime/lv.py"
    tree = ast.parse(runtime_path.read_text(encoding="utf-8"))
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in RUNTIME_FUNCTIONS]
    if {n.name for n in selected} != RUNTIME_FUNCTIONS:
        raise RuntimeError("Pinned runtime helper set changed")
    runtime = (
        '"""Extracted lvkit runtime subset, locally modified; see LVKIT_LICENSE.\n'
        'Source fingerprint: ' + digest(runtime_path) + '\n"""\n'
        'from __future__ import annotations\nimport math as _math\n'
        'import operator as _op\nfrom collections.abc import Callable\n\n'
        + "\n\n".join(ast.unparse(n) for n in selected) + "\n"
    )
    local_runtime = TARGET / "_lv_runtime.py"
    local_runtime.write_text(runtime, encoding="utf-8", newline="\n")
    record("runtime_subset", local_runtime, "AST-extracted from private fork", digest(runtime_path))
    license_path = TARGET / "LVKIT_LICENSE"
    license_path.write_bytes((args.converter / "LICENSE").read_bytes())
    record("license", license_path)
    init = TARGET / "__init__.py"
    init.write_text("\n".join(exports) + "\n", encoding="utf-8", newline="\n")
    record("public_exports", init)
    for filename in ("average_array_poly.vi", "average-2Darray-SD_double.vi", "average-2Darray-SD_int.vi"):
        record("source_dependency", args.vi_root / "dependecies" / filename,
               "Only selected numeric outputs qualified")
    for path in sorted((args.converter / "src/lvkit").rglob("*.py")):
        record("converter_python", path)
    record("converter_version", args.converter / "pyproject.toml")
    for patch in (ROOT / "tools/acq_numeric_lvkit_overlay.patch",
                  ROOT / "tools/trancon_lvkit_overlay.patch"):
        if patch.exists():
            record("converter_patch", patch)
    for script in (Path(__file__), Path(__file__).with_name("test_trancon_lvkit_converter.py"),
                   Path(__file__).with_name("verify_trancon_generated_numeric.py"),
                   Path(__file__).with_name("audit_trancon_saved_pairs.py")):
        record("driver_or_test", script)
    manifest = ROOT / "docs/data-treatment/TRANCON_LVKIT_PROVENANCE_2026-10-03.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"Generated {len(JOBS)} entry points; manifest={manifest}")


if __name__ == "__main__":
    main()
