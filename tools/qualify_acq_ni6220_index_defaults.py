"""Differentially qualify only three saved NI6220 Index Array fragments.

The audited scalar grammar permits only _lv.index_array with DBL zero
default. Original nodes/wires/types and an independent inert caller model
are checked first. No generated VI, Mean, DAQ, property, wait or I/O runs.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import random
from types import SimpleNamespace

from DeviceServers.control.elyse_acq.vi_simulation.ni6220_runtime import (
    counter_frame,
    point_frame,
)
from inventory_control_lvkit import converter_fingerprint
from qualify_acq_beamline_fragments import ROOT_ARCHIVE, SOURCE_SHA256
from qualify_acq_lvkit import DEFAULT_CHECKOUT, DEFAULT_SOURCE, digest, verify_checkout
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_ni6220_index_defaults import INDEX_NODES, validate_indices
from validate_acq_vam_status import checked_vam


def audit_fragment(source, inputs):
    tree = ast.parse(source)
    bound = set(inputs) | {"_lv"}
    allowed = (ast.Name, ast.Load, ast.Constant, ast.Tuple, ast.Call, ast.Attribute)
    for statement in tree.body:
        require(
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name),
            "only scalar/tuple assignments permitted",
        )
        name = statement.targets[0].id
        require(name not in bound and not name.startswith("__"), "input reassignment")
        for item in ast.walk(statement.value):
            require(isinstance(item, allowed), "nonpure Index Array syntax forbidden")
            if isinstance(item, ast.Name):
                require(item.id in bound, "unbound Index Array name")
            elif isinstance(item, ast.Constant):
                require(
                    type(item.value) in (int, float)
                    and math.isfinite(item.value)
                    and item.value >= 0,
                    "finite nonnegative numeric literals only",
                )
            elif isinstance(item, ast.Attribute):
                require(
                    isinstance(item.value, ast.Name)
                    and item.value.id == "_lv"
                    and item.attr == "index_array",
                    "only the explicit pure index helper permitted",
                )
            elif isinstance(item, ast.Call):
                require(
                    isinstance(item.func, ast.Attribute)
                    and len(item.args) == 3
                    and not item.keywords
                    and isinstance(item.args[2], ast.Constant)
                    and type(item.args[2].value) is float
                    and item.args[2].value == 0.0,
                    "Index Array must have the proved DBL zero default",
                )
        bound.add(name)
    require(tree.body and tree.body[-1].targets[0].id == "result", "result missing")
    return tree


def generate_fragments(root):
    verify_checkout(DEFAULT_CHECKOUT)
    from lvkit.codegen.context import CodeGenContext
    from lvkit.codegen.nodes import primitive
    from lvkit.graph import InMemoryVIGraph, LoadMode

    path = DEFAULT_SOURCE / "0_ACQ_ELYSE.vi"
    require(digest(path) == SOURCE_SHA256, "original source hash changed")
    graph = InMemoryVIGraph()
    key = graph.load_vi(path, mode=LoadMode.NONE)
    generated = {}
    for uid, row in INDEX_NODES.items():
        _, array_port, _, pairs, _, _, _, indices = row
        ctx = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
        ctx.vi_name = key
        ctx.bind(key + "::" + array_port, "values")
        for position, (_, index_port) in enumerate(pairs):
            ctx.bind(
                key + "::" + index_port,
                "selected" if indices is None else str(indices[position]),
            )
        raw = unique(root, "aIndx", uid)
        node = graph._graph.nodes[key + "::" + uid]["node"]
        require(
            tuple(t.id.rsplit("::", 1)[-1] for t in node.terminals)
            == tuple(t.get("uid") for t in raw.findall("termList/*")),
            "shared converter Index Array terminals differ from original XML",
        )
        fragment = primitive.generate(node, ctx)
        require(
            fragment.imports == {"from lvkit.runtime import lv as _lv"}
            and not ctx.imports,
            "only the pure Index Array helper import permitted",
        )
        for port, expression in fragment.bindings.items():
            ctx.bind(port, expression)
        outputs = [ctx.resolve(key + "::" + out) for out, _ in pairs]
        require(all(v is not None for v in outputs), "unresolved scalar output")
        result = outputs[0] if uid == "48810" else "(" + ", ".join(outputs) + ",)"
        statements = fragment.statements + ast.parse("result = " + result).body
        source = (
            ast.unparse(
                ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[]))
            )
            + "\n"
        )
        inputs = ("values", "selected") if indices is None else ("values",)
        audit_fragment(source, inputs)
        generated[uid] = (source, inputs)
    require(digest(path) == SOURCE_SHA256, "original source modified")
    return generated


def canonical(value):
    """Keep type, NaN/Inf and signed-zero distinctions in the receipt corpus."""
    if type(value) is float:
        return ["DBL", value.hex()]
    if type(value) is tuple:
        return [canonical(v) for v in value]
    return value


def oracle(uid, fixture):
    if uid == "52275":
        return counter_frame(
            reader_values=fixture["values"],
            bank65=(10.0,) * 4,
            bank66=(20.0,) * 4,
            bank67=(30.0,) * 4,
            current_mean_return=0.0,
            previous_mean_return=0.0,
            counter_selector_snapshot=0,
            increment_read_snapshot=9,
            increment_return=10,
        ).bank65_previous
    point = point_frame(
        reader_values=fixture["values"] if uid == "48881" else (),
        point_mean_returns=(100.0, 101.0, 102.0, 103.0, 108.0, 109.0)
        if uid == "48881"
        else fixture["values"],
        bank63=0 if uid == "48881" else fixture["selected"],
    )
    return (
        tuple(call.input_value for call in point.calls)
        if uid == "48881"
        else point.indicator
    )


def qualify():
    before = converter_fingerprint()
    root, metadata = checked_vam(ROOT_ARCHIVE)
    proof = validate_indices(root, metadata)
    generated = generate_fragments(root)
    from lvkit.runtime import lv

    # Restrict the runtime object itself, not just its syntactic attribute use.
    helper = SimpleNamespace(index_array=lv.index_array)
    specials = [
        (-0.0, math.inf, -math.inf, math.nan) * 4,
        (math.nan,) * 10,
        (-1e200,) * 10,
        (1e200,) * 10,
    ]
    arrays = [tuple(float(i + 100) for i in range(n)) for n in range(17)] + specials
    rng = random.Random(52275)
    arrays += [
        tuple(rng.uniform(-100, 100) for _ in range(rng.randrange(32)))
        for _ in range(64)
    ]
    corpus, counts = hashlib.sha256(), {}
    for uid, (source, inputs) in generated.items():
        code = compile(audit_fragment(source, inputs), "<acq-index-scalar>", "exec")
        if uid == "48810":
            baseline = (100.0, 101.0, 102.0, 103.0, 108.0, 109.0)
            fixtures = (
                {"values": values, "selected": index}
                for values, indexes in [(baseline, range(2**16))]
                + [(values[:6], range(7)) for values in specials]
                for index in indexes
            )
        else:
            fixtures = ({"values": values} for values in arrays)
        counts[uid] = 0
        for fixture in fixtures:
            scope = {"__builtins__": {}, "_lv": helper, **fixture}
            exec(code, scope)
            actual = canonical(scope["result"])
            expected = canonical(oracle(uid, fixture))
            require(
                actual == expected,
                f"shared lvkit Index Array mismatch: {uid} {fixture}",
            )
            corpus.update(
                json.dumps(
                    (uid, {k: canonical(v) for k, v in fixture.items()}, actual),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
            counts[uid] += 1
    require(
        converter_fingerprint() == before,
        "shared converter changed during qualification",
    )
    return {
        "converter_fingerprint": before,
        "source_vi_sha256": SOURCE_SHA256,
        "source_proof": proof,
        "scalar_fragments": len(generated),
        "fixture_counts": counts,
        "scalar_cases": sum(counts.values()),
        "fixture_sha256": corpus.hexdigest().upper(),
        "generated_fragments": {uid: row[0] for uid, row in generated.items()},
        "whole_acquisition_qualified": False,
        "hardware_executed": False,
        "vi_executed": False,
        "deployable": False,
    }


if __name__ == "__main__":
    print(json.dumps(qualify(), indent=2, sort_keys=True))
