"""Differential fixtures from reviewed Supervision and TRANCON sources.

Only two hash-pinned pure functions may execute, after a deliberately small
AST audit. Unknown generated modules are never imported. CLI emits a bundle
for persistence with apply_patch; it does not edit source VIs or write files.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import hashlib
import itertools
import json
import math
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NamedTuple

from qualify_acq_lvkit import DEFAULT_CHECKOUT, REPO, digest, verify_checkout
from validate_acq_deviation_helpers import require, unique

SUP_SOURCE = REPO / "Supervision/extracted/PILOTAGE_ELYSE_SUP/SUPERVISION_VIs"
PROFILES = {
    "supervision_vacuum": {
        "source": SUP_SOURCE / "2_SUP_marche_defaut_VIDE.vi",
        "sha256": "FB7C3BE5A95B7701B8FB20DE81B6BD9CACCA108B07766F9052BAF08BA4C083B1",
        "prior_evaluation_sha256": (
            "E1D2BB8D8E6D5EEB2541A06E286BADE5610B5409037D5F918923E9B270D110AF"
        ),
        "screenshots": [
            REPO
            / "Supervision/analysis/screenshots"
            / "2_SUP_marche_defaut_VIDE_block_diagram_full.png"
        ],
        "native_capture_identity": (
            "Same-name archived capture corroborates topology; "
            "capture-time source SHA absent"
        ),
    },
    "trancon_log": {
        "source": Path("C:/dev/TRANCON/dependecies/-log bis_SD.vi"),
        "parse_copy": Path(
            "C:/dev/TRANCON-analysis/reports/continuation-2026-10-02"
            "/log-bis-source-copy/log_bis_SD.vi"
        ),
        "sha256": "2E1313A6D2064BB92E3371E1DF3B80A848542EFD72C4E9300C0266B95A638FA1",
        "screenshots": [],
        "native_capture_identity": (
            "PENDING: no native diagram screenshot for this hash"
        ),
    },
}


def wire_pairs(root):
    return {
        frozenset(t.get("uid") for t in signal.findall("termList/*"))
        for signal in root.findall(".//signalList/*")
    }


def require_pairs(root, pairs):
    actual = wire_pairs(root)
    for pair in pairs:
        require(frozenset(pair) in actual, f"missing source wire {pair}")


def validate_log(root):
    require(
        [n.get("uid") for n in root.iter() if n.get("class") == "diag"] == ["3"],
        "single diagram required",
    )
    require(
        unique(root, "prim", "63").findtext("primResID") == "1053", "division opcode"
    )
    require(unique(root, "prim", "202").findtext("primResID") == "1210", "log10 opcode")
    require(
        unique(root, "term", "248").findtext("dco/ConstValue") == "3FF0000000000000",
        "numerator literal 1.0",
    )
    require_pairs(root, [("248", "77"), ("116", "74"), ("71", "207"), ("204", "310")])
    return {
        "formula": "log10(1/Transmission)",
        "primitive_uids": ["63", "202"],
        "diagram": "3",
    }


# Each row: channel flat index, unbundle terminal pair, NOT UID and terminal
# pair, AND UID and terminal triple, output control terminal.
VACUUM_ROWS = (
    (2, ("1222", "1225"), "43", ("54", "51"), "747", ("887", "884", "881"), "810"),
    (4, ("1228", "1231"), "595", ("604", "601"), "910", ("922", "919", "916"), "870"),
    (6, ("1234", "1237"), "610", ("619", "616"), "930", ("945", "942", "939"), "913"),
    (10, ("1240", "1243"), "625", ("634", "631"), "951", ("963", "960", "957"), "1172"),
    (12, ("1246", "1249"), "640", ("649", "646"), "987", ("999", "996", "993"), "1190"),
    (
        8,
        ("1252", "1255"),
        "655",
        ("664", "661"),
        "1005",
        ("1017", "1014", "1011"),
        "1208",
    ),
)


def validate_vacuum(root):
    require(
        [n.get("uid") for n in root.iter() if n.get("class") == "diag"] == ["3"],
        "single vacuum diagram",
    )
    require_pairs(root, [("593", "1216"), ("1219", "614")])
    mux = unique(root, "nMux", "1210")
    indices = {t.get("uid"): t.findtext("dco/i") for t in mux.findall("termList/*")}
    for idx, (run, fault), not_uid, (not_in, not_out), and_uid, (
        a,
        b,
        out,
    ), indicator in VACUUM_ROWS:
        require(
            indices[run] == str(idx) and indices[fault] == str(idx + 1),
            "vacuum input field mapping",
        )
        require(
            unique(root, "prim", not_uid).findtext("primResID") == "1064", "NOT opcode"
        )
        require(
            unique(root, "prim", and_uid).findtext("primResID") == "1061", "AND opcode"
        )
        require_pairs(root, [(run, not_in), (not_out, a), (fault, b), (out, indicator)])
    return {
        "formula": "fault AND NOT running",
        "pairs": 6,
        "preparation_passthrough": 0,
    }


def audit_pure(source, profile):
    """Small known-helper grammar, not a general Python security sandbox."""
    tree = ast.parse(source)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    require(
        len(classes) == len(functions) == 1,
        "one result class and one function required",
    )
    cls, fn = classes[0], functions[0]
    require(
        not cls.decorator_list
        and not cls.keywords
        and len(cls.bases) == 1
        and isinstance(cls.bases[0], ast.Name)
        and cls.bases[0].id == "NamedTuple",
        "only result NamedTuple allowed",
    )
    require(
        all(
            isinstance(n, ast.AnnAssign)
            and n.value is None
            and isinstance(n.target, ast.Name)
            and not n.target.id.startswith("_")
            for n in cls.body
        ),
        "result fields only; no underscore prefix",
    )
    require(
        len(cls.body) == (7 if profile == "supervision_vacuum" else 1), "output count"
    )
    require(
        not fn.decorator_list
        and len(fn.args.args) == 1
        and not fn.args.vararg
        and not fn.args.kwarg
        and not fn.args.kwonlyargs
        and not fn.args.posonlyargs,
        "one explicit input",
    )
    require(
        all(isinstance(n, (ast.Assign, ast.Return)) for n in fn.body),
        "straight-line pure body required",
    )
    permitted = (
        ast.Module,
        ast.ImportFrom,
        ast.alias,
        ast.ClassDef,
        ast.FunctionDef,
        ast.AnnAssign,
        ast.Assign,
        ast.Return,
        ast.arguments,
        ast.arg,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Constant,
        ast.Subscript,
        ast.List,
        ast.Call,
        ast.keyword,
        ast.Attribute,
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.UnaryOp,
        ast.Not,
        ast.BinOp,
        ast.BitOr,
    )
    imports = {
        ("__future__", ("annotations",), (None,)),
        ("typing", ("Any", "NamedTuple"), (None, None)),
        ("lvkit.runtime", ("lv",), ("_lv",)),
    }
    for n in ast.walk(tree):
        require(isinstance(n, permitted), f"unreviewed syntax {type(n).__name__}")
        if isinstance(n, ast.ImportFrom):
            require(
                not n.level
                and (
                    n.module,
                    tuple(a.name for a in n.names),
                    tuple(a.asname for a in n.names),
                )
                in imports,
                "import outside pure allowlist",
            )
        if isinstance(n, ast.Name):
            require(not n.id.startswith("__"), "dunder forbidden")
        if isinstance(n, ast.Attribute):
            require(
                profile == "trancon_log"
                and isinstance(n.value, ast.Name)
                and n.value.id == "_lv"
                and n.attr in ("log10", "real64_divide"),
                "runtime call outside reviewed helpers",
            )
        if isinstance(n, ast.Call):
            require(
                (isinstance(n.func, ast.Name) and n.func.id == cls.name)
                or (profile == "trancon_log" and isinstance(n.func, ast.Attribute)),
                "call outside reviewed helpers",
            )
    returns = [n for n in fn.body if isinstance(n, ast.Return)]
    require(
        len(returns) == 1
        and fn.body[-1] is returns[0]
        and isinstance(returns[0].value, ast.Call)
        and isinstance(returns[0].value.func, ast.Name)
        and returns[0].value.func.id == cls.name,
        "explicit resolved result required",
    )
    require(
        not any(
            isinstance(n, ast.Constant) and n.value is None
            for n in ast.walk(returns[0])
        ),
        "None result forbidden",
    )
    return tree, fn.name


def load_pure(source, profile):
    from lvkit.runtime import lv

    tree, function_name = audit_pure(source, profile)
    tree.body = [n for n in tree.body if not isinstance(n, ast.ImportFrom)]
    namespace = {
        "__name__": "reviewed_control_fixture",
        "__builtins__": {
            "__build_class__": builtins.__build_class__,
            "bool": bool,
            "float": float,
            "list": list,
            "tuple": tuple,
        },
        "Any": Any,
        "NamedTuple": NamedTuple,
        "_lv": SimpleNamespace(log10=lv.log10, real64_divide=lv.real64_divide),
    }
    exec(compile(tree, "<reviewed-pure-fixture>", "exec"), namespace)
    return namespace[function_name]


def equal_float(actual, expected):
    if math.isnan(expected):
        require(math.isnan(actual), "NaN mask mismatch")
    elif math.isinf(expected):
        require(actual == expected, "Inf sign mismatch")
    else:
        require(
            math.isclose(actual, expected, rel_tol=2e-14, abs_tol=2e-14),
            "numeric mismatch",
        )


def qualify(profile_name):
    from inventory_control_lvkit import converter_fingerprint
    from lvkit.codegen.builder import build_module
    from lvkit.extractor import extract_vi_xml
    from lvkit.graph import InMemoryVIGraph, LoadMode

    converter_before = converter_fingerprint()

    profile = PROFILES[profile_name]
    original = profile["source"]
    parse_source = profile.get("parse_copy", original)
    require(
        digest(original) == profile["sha256"] == digest(parse_source),
        "source/copy hash changed",
    )
    bd = extract_vi_xml(parse_source)[0]
    root = ET.parse(bd).getroot()
    proof = (
        validate_vacuum(root)
        if profile_name == "supervision_vacuum"
        else validate_log(root)
    )
    graph = InMemoryVIGraph()
    key = graph.load_vi(parse_source, mode=LoadMode.NONE)
    source = build_module(graph.get_vi_context(key), key, graph=graph) + "\n"
    require(
        source == build_module(graph.get_vi_context(key), key, graph=graph) + "\n",
        "nondeterministic generation",
    )
    fn = load_pure(source, profile_name)
    cases = 0
    if profile_name == "supervision_vacuum":
        # Exhaust all 13 relevant Boolean inputs simultaneously (2**13).
        for bits in itertools.product((False, True), repeat=13):
            inputs = (bits[0], False, *bits[1:])
            expected = tuple(
                inputs[f] and not inputs[r]
                for r, f in ((8, 9), (4, 5), (6, 7), (10, 11), (2, 3), (12, 13))
            ) + (inputs[0],)
            require(tuple(fn(inputs)) == expected, "vacuum truth-table mismatch")
            cases += 1
    else:
        # Reference NumPy is independent of lvkit runtime helpers.
        import numpy as np

        rng = random.Random(1210)
        vectors = [
            [],
            [0.0],
            [-0.0],
            [-1.0],
            [1.0],
            [0.1, 1.0, 10.0],
            [math.inf, -math.inf, math.nan],
            [1e-308, 1e308],
            [5e-324],
            [rng.uniform(-1000, 1000) for _ in range(257)],
        ]
        for vector in vectors:
            saved = list(vector)
            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                expected = np.log10(
                    np.divide(1.0, np.asarray(vector, dtype=float))
                ).tolist()
            actual = fn(vector)[0]
            require(
                isinstance(actual, list) and len(actual) == len(expected),
                "output shape mismatch",
            )
            for a, e in zip(actual, expected):
                equal_float(a, e)
                cases += 1
            require(
                all(a is b or a == b for a, b in zip(vector, saved)), "input mutated"
            )
        require(fn(None)[0] == [], "unwired array default")
    require(
        digest(original) == profile["sha256"] == digest(parse_source),
        "VI changed during qualification",
    )
    require(converter_fingerprint() == converter_before, "converter changed")
    return source, {
        "profile": profile_name,
        "source": str(original),
        "source_sha256": profile["sha256"],
        "prior_evaluation_sha256": profile.get("prior_evaluation_sha256"),
        "generated_sha256": hashlib.sha256(source.encode()).hexdigest().upper(),
        "converter_fingerprint": converter_before,
        "parse_source": str(parse_source),
        "xml_sha256": digest(bd),
        "wire_proof": proof,
        "differential_cases": cases,
        "screenshots": [
            {"path": str(p), "sha256": digest(p)} for p in profile["screenshots"]
        ],
        "native_capture_identity": profile["native_capture_identity"],
        "qualification": "STATIC_WIRE_AND_PYTHON_ORACLE_AGREEMENT",
        "native_runtime_equivalence": False,
        "deployable": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT)
    args = parser.parse_args()
    verify_checkout(args.checkout)
    sources, records = {}, []
    for profile in PROFILES:
        source, result = qualify(profile)
        sources[profile + ".py"] = source
        records.append(result)
    print(
        json.dumps(
            {
                "generated_sources": sources,
                "summary": {
                    "members": records,
                    "whole_supervision_closed": False,
                    "whole_trancon_closed": False,
                    "hardware_executed": False,
                    "vi_executed": False,
                },
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
