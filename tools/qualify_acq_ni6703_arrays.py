"""Qualify four reviewed NI6703 scaling/offset fragments, never DAQmx code.

The original source and archived wires are pinned. Only a narrow numeric AST
is executed, with list inputs and three audited in-memory runtime helpers.
Nonlinear formulas, errors, driver calls and physical voltages are excluded.
"""

from __future__ import annotations

import ast
import hashlib
import json
import random
from math import isfinite
from types import SimpleNamespace

from inventory_control_lvkit import converter_fingerprint
from qualify_acq_lvkit import (
    ARCHIVE,
    DEFAULT_CHECKOUT,
    DEFAULT_SOURCE,
    digest,
    verify_checkout,
)
from validate_acq_ni6703_writer import (
    MEMBER,
    checked_writer_roots,
    numeric_array,
    require,
    validate_writer,
)

SOURCE_SHA256 = "5437FD979E7D5AB2F50257DF0F75B73D7C800684EFF0A45D28D6E51931893C3D"
# Original primitive UID, logical producer terminal, scaled output, slope constant.
BANKS = {
    6: ("802", "743", "808", "378"),
    7: ("1072", "859", "1081", "420"),
    8: ("549", "976", "555", "453"),
    9: ("769", "1087", "776", "485"),
}


def fragments():
    from lvkit.codegen.context import CodeGenContext
    from lvkit.codegen.nodes import primitive
    from lvkit.graph import InMemoryVIGraph, LoadMode
    from lvkit.models import LVTypeKind

    path = DEFAULT_SOURCE / MEMBER
    require(digest(path) == SOURCE_SHA256, "NI6703 source hash changed")
    roots = checked_writer_roots(ARCHIVE)
    proof = validate_writer(roots)
    root = roots["vi_BDHb.xml"].find("root")
    slopes = {card: numeric_array(root, data[3]) for card, data in BANKS.items()}
    offsets = numeric_array(root, "1246")
    graph = InMemoryVIGraph()
    key = graph.load_vi(path, mode=LoadMode.NONE)
    sources = {}
    for card, (uid, producer, output, _) in BANKS.items():
        ctx = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
        ctx.vi_name = key
        ctx.bind(key + "::" + producer, "logical")
        nodes = [graph._graph.nodes[key + "::" + uid]["node"]]
        if card == 8:
            nodes.append(graph._graph.nodes[key + "::295"]["node"])
        statements = []
        for node in nodes:
            require(
                all(
                    t.lv_type is not None
                    and t.lv_type.kind == LVTypeKind.ARRAY
                    and t.lv_type.dimensions == 1
                    and t.lv_type.element_type.underlying_type == "NumFloat64"
                    for t in node.terminals
                ),
                "reviewed numeric primitive representation changed",
            )
            emitted = primitive.generate(node, ctx)
            statements.extend(emitted.statements)
            for term, value in emitted.bindings.items():
                ctx.bind(term, value)
        result = ctx.resolve(key + "::" + ("620" if card == 8 else output))
        require(result is not None, "numeric fragment result is unresolved")
        statements.extend(ast.parse("result = " + result).body)
        sources[str(card)] = (
            ast.unparse(
                ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[]))
            )
            + "\n"
        )
    require(digest(path) == SOURCE_SHA256, "NI6703 source changed during generation")
    return sources, slopes, offsets, proof


def audit_fragment(source):
    tree = ast.parse(source)
    allowed = (
        ast.Module,
        ast.Assign,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.List,
        ast.Constant,
        ast.Call,
        ast.Attribute,
    )
    for node in ast.walk(tree):
        require(isinstance(node, allowed), "numeric fragment syntax outside allowlist")
        if isinstance(node, ast.Name):
            require(not node.id.startswith("__"), "dunder access forbidden")
        if isinstance(node, ast.Attribute):
            require(
                isinstance(node.value, ast.Name)
                and node.value.id == "_lv"
                and node.attr in ("add", "mul", "neg"),
                "only audited numeric helpers permitted",
            )
        if isinstance(node, ast.Call):
            require(
                isinstance(node.func, ast.Attribute)
                and len(node.args) == (1 if node.func.attr == "neg" else 2)
                and not node.keywords,
                "unexpected numeric helper call",
            )
    return tree


def run_fragment(source, logical):
    from lvkit.runtime import lv

    require(
        type(logical) is list
        and len(logical) == 10
        and all(type(x) is float and isfinite(x) for x in logical),
        "only ten DBL fixture values permitted",
    )
    scope = {
        "__builtins__": {},
        "logical": logical,
        "_lv": SimpleNamespace(add=lv.add, mul=lv.mul, neg=lv.neg),
    }
    exec(compile(audit_fragment(source), "<NI6703-numeric-fixture>", "exec"), scope)
    return scope["result"]


def vectors():
    yield [0.0] * 10
    yield [float(i) for i in range(10)]
    yield [float((-1) ** i * (i + 1)) for i in range(10)]
    yield [-0.0] * 10
    yield [1e200 if i % 2 else -1e200 for i in range(10)]
    rng = random.Random(6703)
    for _ in range(512):
        yield [rng.uniform(-1000.0, 1000.0) for _ in range(10)]


def qualify():
    before = converter_fingerprint()
    sources, slopes, offsets, proof = fragments()
    require(sources == fragments()[0], "nondeterministic numeric fragments")
    cases = 0
    fixture_hash = hashlib.sha256()
    for logical in vectors():
        fixture_hash.update(json.dumps(logical, separators=(",", ":")).encode())
        for card, source in sources.items():
            saved = list(logical)
            actual = run_fragment(source, logical)
            expected = [
                value * scale for value, scale in zip(logical, slopes[int(card)])
            ]
            if card == "8":
                expected = [value + offset for value, offset in zip(expected, offsets)]
            require(type(actual) is list and len(actual) == 10, "array shape mismatch")
            require(actual == expected, "NI6703 scaling/offset differential mismatch")
            require(logical == saved, "fixture input mutated")
            cases += 1
    require(converter_fingerprint() == before, "converter changed during qualification")
    return {
        "sources": sources,
        "receipt": {
            "member": MEMBER,
            "source_sha256": SOURCE_SHA256,
            "converter_fingerprint": before,
            "wire_proof": proof,
            "fragment_sha256": {
                card: hashlib.sha256(source.encode()).hexdigest().upper()
                for card, source in sources.items()
            },
            "vectors_sha256": fixture_hash.hexdigest().upper(),
            "bank_cases": cases,
            "scalar_values_compared": cases * 10,
            "slopes": slopes,
            "offsets": offsets,
            "qualification": "ISOLATED_TEN_DBL_ARRAY_SOURCE_AGREEMENT",
            "full_writer_qualified": False,
            "deployable": False,
            "hardware_executed": False,
            "vi_executed": False,
            "limits": [
                "Only four scaling primitives and C8 Add node 295, output 620",
                "No nonlinear formulas, disable structure, driver or error semantics",
                "Only ten finite DBL inputs; other shapes/representations unqualified",
                "No native execution oracle or hash-matched Acquisition screenshot",
                "Numeric requests are not measured or accepted physical voltages",
            ],
        },
    }


def main():
    verify_checkout(DEFAULT_CHECKOUT)
    print(json.dumps(qualify(), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
