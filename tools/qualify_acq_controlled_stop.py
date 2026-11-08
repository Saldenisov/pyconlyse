"""Compare current shared lvkit scalar stop predicates against wired oracles.

Only typed comparisons, subtraction and Boolean OR are emitted/executed. No
main VI, property/DAQ query, wait or publication is generated or executed.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import random
import struct

from DeviceServers.control.elyse_acq.vi_simulation.controlled_stop import (
    controlled_counter_should_stop,
    project_ht_ramp_iteration,
)
from inventory_control_lvkit import converter_fingerprint
from qualify_acq_beamline_fragments import ROOT_ARCHIVE, SOURCE_SHA256
from qualify_acq_lvkit import DEFAULT_CHECKOUT, DEFAULT_SOURCE, digest, verify_checkout
from validate_acq_controlled_stop import validate_stop
from validate_acq_counter_procedures import CONTROLLED_POLL_ROWS
from validate_acq_final_cleanup import constant
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_vam_status import checked_vam


def audit_fragment(source, inputs):
    tree = ast.parse(source)
    bound = set(inputs)
    allowed = (
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Compare,
        ast.Lt,
        ast.Gt,
        ast.Eq,
        ast.BinOp,
        ast.Sub,
        ast.BoolOp,
        ast.Or,
    )
    for stmt in tree.body:
        require(
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name),
            "only scalar assignments permitted",
        )
        name = stmt.targets[0].id
        require(
            name not in bound and not name.startswith("__"),
            "input reassignment forbidden",
        )
        for node in ast.walk(stmt.value):
            require(isinstance(node, allowed), "nonpure scalar syntax forbidden")
            if isinstance(node, ast.Name):
                require(node.id in bound, "unbound scalar name")
            if isinstance(node, ast.Constant):
                require(
                    type(node.value) in (bool, int, float)
                    and math.isfinite(node.value),
                    "finite scalar literals only",
                )
        bound.add(name)
    require(tree.body and tree.body[-1].targets[0].id == "result", "result missing")
    return tree


def generate_fragments(root, metadata):
    verify_checkout(DEFAULT_CHECKOUT)
    from lvkit.codegen.context import CodeGenContext
    from lvkit.codegen.nodes import compound, primitive
    from lvkit.graph import InMemoryVIGraph, LoadMode

    path = DEFAULT_SOURCE / "0_ACQ_ELYSE.vi"
    require(digest(path) == SOURCE_SHA256, "original source hash changed")
    graph = InMemoryVIGraph()
    key = graph.load_vi(path, mode=LoadMode.NONE)
    specs = [
        (
            "ht_exit",
            ("44754",),
            {
                "44766": "checked",
                "44763": repr(
                    struct.unpack(
                        ">d",
                        bytes.fromhex(constant(unique(root, "diag", "42212"), "46097")),
                    )[0]
                ),
            },
            "44760",
            ("checked",),
        ),
        (
            "ht_decrement",
            ("583",),
            {
                "40575": "checked",
                "40571": repr(
                    struct.unpack(
                        ">d",
                        bytes.fromhex(constant(unique(root, "diag", "47573"), "53615")),
                    )[0]
                ),
            },
            "40566",
            ("checked",),
        ),
    ]
    for body_uid, row in CONTROLLED_POLL_ROWS.items():
        compound_uid, cp, greater, equal, _, prop, literals, _, _ = row
        specs.append(
            (
                body_uid,
                (greater[0], equal[0], compound_uid),
                {
                    greater[1][1]: str(
                        int(constant(unique(root, "diag", body_uid), literals[2]), 16)
                    ),
                    greater[1][2]: "iteration",
                    equal[1][1]: "True",
                    prop[1][-1]: "done",
                },
                cp[0],
                ("iteration", "done"),
            )
        )
    result = {}
    for ident, nodes, bindings, output, inputs in specs:
        ctx = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
        ctx.vi_name = key
        for port, value in bindings.items():
            ctx.bind(key + "::" + port, value)
        statements = []
        for uid in nodes:
            raw = unique(root, "cpdArith" if uid in ("47878", "48161") else "prim", uid)
            node = graph._graph.nodes[key + "::" + uid]["node"]
            require(
                tuple(t.id.rsplit("::", 1)[-1] for t in node.terminals)
                == tuple(t.get("uid") for t in raw.findall("termList/*")),
                "shared converter terminal identity differs from original XML",
            )
            if raw.get("class") == "cpdArith":
                require(node.operation == "or", "shared converter OR mode differs")
                fragment = compound.generate_compound_arith(node, ctx)
            else:
                require(
                    node.prim_id == int(raw.findtext("primResID")),
                    "shared converter primitive differs",
                )
                fragment = primitive.generate(node, ctx)
            require(not fragment.imports, "no imports permitted")
            statements.extend(fragment.statements)
            for port, value in fragment.bindings.items():
                ctx.bind(port, value)
        expression = ctx.resolve(key + "::" + output)
        require(expression is not None, "unresolved output")
        statements.extend(ast.parse("result = " + expression).body)
        source = (
            ast.unparse(
                ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[]))
            )
            + "\n"
        )
        audit_fragment(source, inputs)
        result[ident] = (source, inputs)
    require(digest(path) == SOURCE_SHA256, "original source modified")
    return result


def qualify():
    before = converter_fingerprint()
    root, metadata = checked_vam(ROOT_ARCHIVE)
    proof = validate_stop(root, metadata)
    generated = generate_fragments(root, metadata)
    values = [
        0.0,
        -0.0,
        6.6,
        math.nextafter(6.6, -math.inf),
        math.nextafter(6.6, math.inf),
        6.5,
        6.7,
        -100.0,
        100.0,
        1e200,
        -1e200,
    ]
    rng = random.Random(51954)
    values += [rng.uniform(-100.0, 100.0) for _ in range(300)]
    corpus = hashlib.sha256()
    cases = 0
    for ident, (source, inputs) in generated.items():
        code = compile(audit_fragment(source, inputs), "<acq-stop-scalar>", "exec")
        if ident.startswith("ht_"):
            fixtures = ({"checked": v} for v in values)
        else:
            fixtures = (
                {"iteration": i, "done": done}
                for i in (*range(50), 2147483647)
                for done in (False, True)
            )
        for fixture in fixtures:
            scope = {"__builtins__": {}, **fixture}
            exec(code, scope)
            actual = scope["result"]
            if ident == "ht_exit":
                expected = project_ht_ramp_iteration(
                    (fixture["checked"],) + (0.0,) * 9, (0.0,) * 10
                ).should_stop
            elif ident == "ht_decrement":
                # The subtraction fragment is qualified independently even where
                # the enclosing True exit arm would not execute it.
                expected = fixture["checked"] - 0.1
            else:
                expected = controlled_counter_should_stop(
                    ident, fixture["iteration"], fixture["done"]
                )
            require(
                type(actual) is type(expected)
                and (
                    actual.hex() == expected.hex()
                    if type(expected) is float
                    else actual == expected
                ),
                f"shared lvkit mismatch: {ident} {fixture}",
            )
            corpus.update(
                json.dumps(
                    (ident, fixture, actual), sort_keys=True, separators=(",", ":")
                ).encode()
            )
            cases += 1
    require(
        converter_fingerprint() == before,
        "shared converter changed during qualification",
    )
    return {
        "converter_fingerprint": before,
        "source_vi_sha256": SOURCE_SHA256,
        "diagrams_checked": proof["diagrams"],
        "nets_checked": proof["nets"],
        "scalar_fragments": len(generated),
        "scalar_cases": cases,
        "fixture_sha256": corpus.hexdigest().upper(),
        "generated_fragments": {key: row[0] for key, row in generated.items()},
        "whole_acquisition_qualified": False,
        "hardware_executed": False,
        "vi_executed": False,
        "deployable": False,
    }


if __name__ == "__main__":
    print(json.dumps(qualify(), indent=2, sort_keys=True))
