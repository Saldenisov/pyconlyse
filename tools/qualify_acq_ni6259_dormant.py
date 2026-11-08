"""Compare the two NI6259 scaling arms with shared lvkit pure fragments.

No generated VI, DAQ, Mean, property or transport executes. Both arms use
supplied Mean-result vectors of length0..8; saved selector is False. Passing
this qualification does not activate dormant VIs or prove native Mean.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import random
from types import SimpleNamespace

from DeviceServers.control.elyse_acq.vi_simulation.ni6259_dormant import project_means
from inventory_control_lvkit import converter_fingerprint
from qualify_acq_lvkit import DEFAULT_CHECKOUT, DEFAULT_SOURCE, digest, verify_checkout
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6259_dormant import (
    INIT,
    READ,
    SOURCE_HASHES,
    checked_roots,
    validate_all,
)


def audit_fragment(source):
    tree = ast.parse(source)
    bound = {"means", "_lv"}
    allowed = (ast.Name, ast.Load, ast.Constant, ast.List, ast.Call, ast.Attribute)
    for statement in tree.body:
        require(
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name),
            "only simple array assignments permitted",
        )
        name = statement.targets[0].id
        require(name not in bound and not name.startswith("__"), "input reassignment")
        for node in ast.walk(statement.value):
            require(isinstance(node, allowed), "nonpure NI6259 syntax forbidden")
            if isinstance(node, ast.Name):
                require(node.id in bound, "unbound NI6259 name")
            elif isinstance(node, ast.Constant):
                require(
                    type(node.value) in (float, int) and math.isfinite(node.value),
                    "finite numeric coefficient literals only",
                )
            elif isinstance(node, ast.Attribute):
                require(
                    isinstance(node.value, ast.Name)
                    and node.value.id == "_lv"
                    and node.attr in ("mul", "add"),
                    "only pure numeric helpers permitted",
                )
            elif isinstance(node, ast.Call):
                require(
                    isinstance(node.func, ast.Attribute)
                    and len(node.args) == 2
                    and not node.keywords,
                    "two-argument numeric helper required",
                )
        bound.add(name)
    require(tree.body and tree.body[-1].targets[0].id == "result", "result missing")
    return tree


def fragments():
    verify_checkout(DEFAULT_CHECKOUT)
    from lvkit.codegen.context import CodeGenContext
    from lvkit.codegen.nodes import primitive
    from lvkit.graph import InMemoryVIGraph, LoadMode
    from lvkit.models import LVTypeKind

    # Match original binaries, not modified review copies or another device VI.
    for name in (INIT, READ):
        require(
            digest(DEFAULT_SOURCE / name) == SOURCE_HASHES[name],
            "original NI6259 source changed: " + name,
        )
    roots = checked_roots()
    bd = roots[READ]["vi_BDHb.xml"]
    graph = InMemoryVIGraph()
    key = graph.load_vi(DEFAULT_SOURCE / READ, mode=LoadMode.NONE)
    ctx = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
    ctx.vi_name = key
    ctx.bind(key + "::1000", "means")
    statements = []
    for uid in ("651", "675"):
        original = unique(bd, "prim", uid)
        node = graph._graph.nodes[key + "::" + uid]["node"]
        require(
            tuple(t.id.rsplit("::", 1)[-1] for t in node.terminals)
            == tuple(t.get("uid") for t in original.findall("termList/*")),
            "shared converter primitive terminals differ from original XML",
        )
        require(
            all(
                t.lv_type is not None
                and t.lv_type.kind == LVTypeKind.ARRAY
                and t.lv_type.dimensions == 1
                and t.lv_type.element_type.underlying_type == "NumFloat64"
                for t in node.terminals
            ),
            "shared converter DBL rank differs",
        )
        emitted = primitive.generate(node, ctx)
        require(
            not ctx.imports
            and emitted.imports <= {"from lvkit.runtime import lv as _lv"},
            "only pure array helper import permitted",
        )
        statements.extend(emitted.statements)
        for port, expression in emitted.bindings.items():
            ctx.bind(port, expression)
    result = ctx.resolve(key + "::677")
    require(result is not None, "NI6259 calibration output unresolved")
    statements.extend(ast.parse("result = " + result).body)
    calibrated = (
        ast.unparse(
            ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[]))
        )
        + "\n"
    )
    # False arm has only the independently proved passthrough wire999->1014.
    sources = {"False": "result = means\n", "True": calibrated}
    for source in sources.values():
        audit_fragment(source)
    return sources


def canonical(values):
    return [float(v).hex() for v in values]


def vectors():
    for n in range(9):
        yield [float(i + 1) for i in range(n)]
        yield [-0.0] * n
        yield [float((-1) ** i * (i + 1)) for i in range(n)]
        yield [math.nan, math.inf, -math.inf, -0.0, 0.0, 1e200, -1e200, 1.0][:n]
    rng = random.Random(6259)
    for _ in range(256):
        yield [rng.uniform(-1e6, 1e6) for _ in range(rng.randrange(9))]


def qualify():
    before = converter_fingerprint()
    proof = validate_all()
    sources = fragments()
    from lvkit.runtime import lv

    helpers = SimpleNamespace(mul=lv.mul, add=lv.add)
    corpus = hashlib.sha256()
    counts = {selector: 0 for selector in sources}
    codes = {
        selector: compile(audit_fragment(source), "<NI6259-pure-array>", "exec")
        for selector, source in sources.items()
    }
    for means in vectors():
        saved = canonical(means)
        for selector, code in codes.items():
            scope = {"__builtins__": {}, "means": means, "_lv": helpers}
            exec(code, scope)
            actual = scope["result"]
            expected = project_means(tuple(means), calibrated=selector == "True")
            require(
                type(actual) is list and canonical(actual) == canonical(expected),
                "NI6259 shared-lvkit array mismatch: " + selector,
            )
            require(canonical(means) == saved, "supplied Mean array mutated")
            corpus.update(
                json.dumps(
                    (selector, saved, canonical(actual)), separators=(",", ":")
                ).encode()
            )
            counts[selector] += 1
    require(
        converter_fingerprint() == before,
        "shared converter changed during qualification",
    )
    for name in (INIT, READ):
        require(
            digest(DEFAULT_SOURCE / name) == SOURCE_HASHES[name], "original VI changed"
        )
    return {
        "converter_fingerprint": before,
        "original_source_sha256": SOURCE_HASHES,
        "source_proof": proof,
        "generated_fragments": sources,
        "fixture_counts": counts,
        "array_cases": sum(counts.values()),
        "fixture_sha256": corpus.hexdigest().upper(),
        "saved_selector": False,
        "whole_acquisition_qualified": False,
        "native_mean_qualified": False,
        "deployable": False,
        "hardware_executed": False,
        "vi_executed": False,
    }


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, indent=2))
