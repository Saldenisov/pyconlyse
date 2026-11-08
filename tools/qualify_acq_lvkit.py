"""Differential qualification of two hash-pinned, non-actuating ACQ VIs.

Use the separate GitHub checkout, never overwrite the old evaluation venv.
No VI/hardware execution. Only tightly whitelisted generated pure Python
is executed, against an independently authored oracle and wire proof.
This gate does NOT establish whole-Acquisition coverage or production safety.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import importlib.metadata
import json
import math
import random
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

from validate_acq_deviation_helpers import (
    PROFILES,
    checked_roots,
    require,
    validate_tree,
)

REPO = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "d8058677e15c47094e725439bd72417fe9527754"
DEFAULT_CHECKOUT = Path("C:/dev/ELYSE-ACQ-analysis/converter/lvkit")
DEFAULT_SOURCE = Path("C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs")
ARCHIVE = (
    REPO
    / "legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def verify_checkout(checkout):
    commit = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    require(commit == UPSTREAM_COMMIT, "checkout must match the pinned upstream commit")
    sys.path.insert(0, str(checkout / "src"))
    import lvkit

    require(
        Path(lvkit.__file__).resolve().is_relative_to(checkout.resolve()),
        "lvkit import came from another installation",
    )


def audit_generated(source):
    """Reject IO, imports outside three pure modules, loops and unresolved code.

    This is a deliberately small grammar, not a general Python sandbox.
    Source VI hashes and the graph proof are also mandatory.
    """
    tree = ast.parse(source)
    allowed_imports = {
        ("__future__", ("annotations",)),
        ("typing", ("Any", "NamedTuple")),
        ("lvkit.positional_cluster", ("replace_fields",)),
    }
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    require(
        len(classes) == len(functions) == 1,
        "one result class and pure function required",
    )
    result_class, function = classes[0], functions[0]
    require(
        not result_class.decorator_list
        and len(result_class.bases) == 1
        and isinstance(result_class.bases[0], ast.Name)
        and result_class.bases[0].id == "NamedTuple"
        and not result_class.keywords,
        "only NamedTuple result class permitted",
    )
    require(
        not function.decorator_list
        and len(function.args.args) == 2
        and not function.args.vararg
        and not function.args.kwarg
        and not function.args.kwonlyargs
        and not function.args.posonlyargs,
        "two explicit pure helper inputs required",
    )
    allowed_nodes = (
        ast.Module,
        ast.ImportFrom,
        ast.alias,
        ast.ClassDef,
        ast.FunctionDef,
        ast.arguments,
        ast.arg,
        ast.AnnAssign,
        ast.Assign,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Constant,
        ast.Subscript,
        ast.Tuple,
        ast.BinOp,
        ast.Sub,
        ast.Call,
        ast.keyword,
        ast.Compare,
        ast.Gt,
        ast.Return,
        ast.Expr,
    )
    for node in ast.walk(tree):
        require(
            isinstance(node, allowed_nodes),
            f"generated syntax outside pure grammar: {type(node).__name__}",
        )
        if isinstance(node, ast.ImportFrom):
            key = (node.module, tuple(n.name for n in node.names))
            require(
                key in allowed_imports
                and not node.level
                and not any(n.asname for n in node.names),
                "generated import outside allowlist",
            )
        if isinstance(node, ast.Call):
            require(
                isinstance(node.func, ast.Name)
                and node.func.id in ("abs", "replace_fields", result_class.name),
                "generated call outside allowlist",
            )
        if isinstance(node, ast.Name):
            require(not node.id.startswith("__"), "dunder access forbidden")
    require(
        all(
            isinstance(n, ast.AnnAssign) and n.value is None for n in result_class.body
        ),
        "result class may only declare fields",
    )
    require(
        all(isinstance(n, (ast.Assign, ast.Expr, ast.Return)) for n in function.body),
        "pure function statement grammar exceeded",
    )
    returns = [n for n in function.body if isinstance(n, ast.Return)]
    require(
        len(returns) == 1
        and function.body[-1] is returns[0]
        and isinstance(returns[0].value, ast.Call)
        and isinstance(returns[0].value.func, ast.Name)
        and returns[0].value.func.id == result_class.name,
        "explicit result constructor required",
    )
    require(
        not any(
            isinstance(n, ast.Constant) and n.value is None
            for n in ast.walk(returns[0])
        ),
        "unresolved None output forbidden",
    )
    return tree, function.name


def load_pure_generated(source):
    from lvkit.positional_cluster import replace_fields

    tree, name = audit_generated(source)
    # Remove even permitted imports; inject already inspected trusted symbols.
    tree.body = [n for n in tree.body if not isinstance(n, ast.ImportFrom)]
    namespace = {
        "__name__": "acq_qualified_pure",
        "__builtins__": {
            "__build_class__": builtins.__build_class__,
            "abs": abs,
            "float": float,
            "dict": dict,
            "str": str,
        },
        "Any": Any,
        "NamedTuple": NamedTuple,
        "replace_fields": replace_fields,
    }
    exec(compile(tree, "<audited-acq-helper>", "exec"), namespace)
    return namespace[name]


def make_cluster(count, command, readback, orange=True):
    return tuple(
        (False, True, orange, False, True, command, readback, False, True, False, True)
        for _ in range(count)
    )


def differential_fixtures(count):
    values = (
        (0.0, 0.0, 0.5),
        (0.5, 0.0, 0.5),
        (math.nextafter(0.5, math.inf), 0.0, 0.5),
        (math.nextafter(0.5, -math.inf), 0.0, 0.5),
        (-0.75, 0.0, 0.5),
        (0.75, 0.0, 0.5),
        (math.nan, 0.0, 0.5),
        (math.inf, 0.0, 0.5),
        (math.inf, math.inf, 0.5),
        (0.0, 0.0, -0.1),
        (1.0, 0.0, math.nan),
        (1.0, 0.0, math.inf),
    )
    for command, readback, threshold in values:
        yield threshold, make_cluster(count, command, readback)
    # Distinguishable channels catch accidentally shared/wrong orange fields.
    for selected in range(count):
        for sign in (-1.0, 1.0):
            cluster = list(make_cluster(count, 0.0, 0.0))
            channel = cluster[selected]
            cluster[selected] = channel[:5] + (sign, 0.0) + channel[7:]
            yield 0.5, tuple(cluster)
    rng = random.Random(6602 + count)
    for _ in range(200):
        cluster = tuple(
            tuple(
                rng.choice((True, False))
                if i not in (5, 6)
                else rng.uniform(-10.0, 10.0)
                for i in range(11)
            )
            for _ in range(count)
        )
        yield rng.uniform(0.0, 2.0), cluster


def qualify(profile_name, checkout, source_dir):
    from lvkit.codegen.builder import build_module
    from lvkit.graph import InMemoryVIGraph, LoadMode
    from lvkit.reviewed_locals import configure_reviewed_locals

    sys.path.insert(0, str(REPO))
    from DeviceServers.control.elyse_acq.vi_simulation.deviation_helpers import (
        compare_line_cluster,
    )

    profile = PROFILES[profile_name]
    source_vi = source_dir / profile["member"]
    before = digest(source_vi)
    require(before == profile["sha256"], "source VI hash is not qualified")
    wire_proof = validate_tree(checked_roots(ARCHIVE)[profile_name], profile)
    graph = InMemoryVIGraph()
    key = graph.load_vi(source_vi, mode=LoadMode.NONE)
    configure_reviewed_locals(graph, key, profile["locals"])
    generated = build_module(graph.get_vi_context(key), key, graph=graph) + "\n"
    require(
        generated == build_module(graph.get_vi_context(key), key, graph=graph) + "\n",
        "codegen is not reproducible",
    )
    function = load_pure_generated(generated)
    cases = 0
    for threshold, cluster in differential_fixtures(profile["channels"]):
        expected = compare_line_cluster(
            cluster, threshold, direct=profile_name == "direct"
        )
        actual = function(threshold, cluster)[0]
        require(
            type(actual) is tuple and len(actual) == len(expected),
            "result cluster missing/malformed",
        )
        for original, returned, wanted in zip(cluster, actual, expected):
            require(
                type(returned) is tuple and len(returned) == 11,
                "nested output shape changed",
            )
            for i, (value, golden) in enumerate(zip(returned, wanted)):
                if i == 2:
                    require(value is golden, "orange differential mismatch")
                else:
                    require(
                        value is original[i] or value == golden,
                        "untargeted field changed",
                    )
        require(cluster == tuple(cluster), "input mutated")
        cases += 1
    require(digest(source_vi) == before, "source VI changed")
    return generated, {
        "member": profile["member"],
        "source_sha256": before,
        "differential_cases": cases,
        "wire_proof": wire_proof,
        "generated_sha256": hashlib.sha256(generated.encode()).hexdigest().upper(),
        "qualification": "PURE_HELPER_MODEL_AGREEMENT_NOT_LABVIEW_RUNTIME_EQUIVALENCE",
        "local_bindings": profile["locals"],
        "native_evidence": (
            "Supervision screenshots corroborate topology; "
            "original ACQ hash-matched captures pending"
        ),
        "hardware_executed": False,
        "vi_executed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help=(
            "intended artifact directory label; CLI emits a JSON bundle, does not write"
        ),
    )
    args = parser.parse_args()
    verify_checkout(args.checkout)
    sources, results = {}, []
    for name in PROFILES:
        generated, result = qualify(name, args.checkout, args.source)
        sources[name + ".py"] = generated
        results.append(result)
    summary = {
        "upstream_commit": UPSTREAM_COMMIT,
        "upstream_version": "0.8.6",
        "overlay_sha256": digest(REPO / "tools/acq_lvkit_overlay.patch"),
        "runtime": {
            "python": sys.version.split()[0],
            **{
                package: importlib.metadata.version(package)
                for package in ("pylabview", "networkx", "pydantic")
            },
        },
        "members": results,
        "whole_acquisition_closed": False,
        "deployable": False,
    }
    # Authored/generated artifacts always use the standard patch writer.
    # Print JSON and source for the caller to persist; repeat runs are read-only.
    print(
        json.dumps(
            {
                "output_directory": str(args.output),
                "summary": summary,
                "generated_sources": sources,
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
