"""Qualify24 reviewed scalar adjustment chains from the current shared lvkit.

Only Select, Add/Subtract and In Range and Coerce fragments are generated.
No main VI code, property node, reference cast, driver, wait or publication
is executed. Constants and explicit input bindings come from original XML.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import random

from DeviceServers.control.elyse_acq.vi_simulation.beamline_adjustment import (
    adjust_setpoint,
    adjustment_parameters,
)
from inventory_control_lvkit import converter_fingerprint
from qualify_acq_beamline_fragments import ROOT_ARCHIVE, SOURCE_SHA256
from qualify_acq_lvkit import DEFAULT_CHECKOUT, DEFAULT_SOURCE, digest, verify_checkout
from validate_acq_beamline_adjustment import (
    BRANCHES,
    aliases,
    ports,
    scalar_constant,
    terms,
    validate_adjustment,
)
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_vam_status import checked_vam


def audit_fragment(source):
    """Reject every statement/expression outside the finite scalar allowlist."""
    tree = ast.parse(source)
    allowed = (
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.IfExp,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Call,
        ast.UnaryOp,
        ast.USub,
    )
    bound = {"current", "x1_x10", "min", "max"}
    for statement in tree.body:
        require(
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name),
            "only scalar-name assignments permitted",
        )
        target = statement.targets[0].id
        require(
            target not in bound and not target.startswith("__"),
            "input/helper reassignment forbidden",
        )
        for node in ast.walk(statement.value):
            require(isinstance(node, allowed), "nonpure scalar syntax rejected")
            if isinstance(node, ast.Name):
                require(node.id in bound, "unresolved scalar name")
            if isinstance(node, ast.Constant):
                require(
                    type(node.value) in (int, float) and math.isfinite(node.value),
                    "finite numeric constants only",
                )
            if isinstance(node, ast.Call):
                require(
                    isinstance(node.func, ast.Name)
                    and node.func.id in ("min", "max")
                    and len(node.args) == 2
                    and not node.keywords,
                    "only two-operand scalar min/max calls permitted",
                )
            if isinstance(node, ast.IfExp):
                require(
                    isinstance(node.test, ast.Name) and node.test.id == "x1_x10",
                    "only fixture Boolean selects the step",
                )
            if isinstance(node, ast.UnaryOp):
                require(
                    isinstance(node.op, ast.USub)
                    and isinstance(node.operand, ast.Constant),
                    "unary minus permitted only on numeric literals",
                )
        bound.add(target)
    require(tree.body and tree.body[-1].targets[0].id == "result", "result absent")
    return tree


def fragments(root, meta, proof):
    verify_checkout(DEFAULT_CHECKOUT)
    from lvkit.codegen.context import CodeGenContext
    from lvkit.codegen.nodes import primitive
    from lvkit.graph import InMemoryVIGraph, LoadMode

    path = DEFAULT_SOURCE / "0_ACQ_ELYSE.vi"
    require(digest(path) == SOURCE_SHA256, "original VI hash changed")
    graph = InMemoryVIGraph()
    key = graph.load_vi(path, mode=LoadMode.NONE)
    result = []
    for event, button, index, leaf, ids in proof["fragments"]:
        branch = next(row for row in BRANCHES[event] if leaf in row[2])
        nested = unique(root, "select", branch[1])
        j = branch[2].index(leaf)
        count = len(branch[2])
        x1 = aliases(terms(nested)[1], count)[j]
        consigne = aliases(terms(nested)[2], count)[j]
        ctx = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
        ctx.vi_name = key
        ctx.bind(key + "::" + x1, "x1_x10")
        ctx.bind(key + "::" + consigne, "current")
        frame = unique(root, "diag", leaf)
        for literal in frame.findall("zPlaneList/*"):
            if literal.get("class") is None:
                uid = literal.get("uid")
                ctx.bind(key + "::" + uid, repr(scalar_constant(frame, meta, uid)))
        statements = []
        sign = "1051" if button in (128, 256) else "1050"
        for resource in ("1516", sign, "1127"):
            uid = ids[resource]
            raw = unique(root, "prim", uid)
            node = graph._graph.nodes[key + "::" + uid]["node"]
            require(
                node.prim_id == int(resource)
                and tuple(t.id.rsplit("::", 1)[-1] for t in node.terminals)
                == ports(raw),
                "shared converter primitive/port identity differs from XML",
            )
            emitted = primitive.generate(node, ctx)
            require(not emitted.imports, "scalar chain may not import anything")
            statements.extend(emitted.statements)
            for term, value in emitted.bindings.items():
                ctx.bind(term, value)
        output = ports(unique(root, "prim", ids["1127"]))[1]
        expression = ctx.resolve(key + "::" + output)
        require(expression is not None, "unresolved scalar result")
        statements.extend(ast.parse("result = " + expression).body)
        source = (
            ast.unparse(
                ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[]))
            )
            + "\n"
        )
        audit_fragment(source)
        result.append((event, button, index, leaf, source))
    require(digest(path) == SOURCE_SHA256, "original VI modified during qualification")
    return tuple(result)


def fixtures(parameters, button):
    small, large, lower, upper = parameters
    # Endpoints, over-range inputs, exact clipping transitions and both step modes.
    values = [0.0, -0.0, lower, upper, lower - 100.0, upper + 100.0, 1e200, -1e200]
    direction = -1.0 if button in (128, 256) else 1.0
    for step in (small, large):
        for bound in (lower, upper):
            transition = bound - direction * step
            values += [
                transition,
                math.nextafter(transition, -math.inf),
                math.nextafter(transition, math.inf),
            ]
    rng = random.Random(1660 + button + int(upper))
    values += [rng.uniform(lower - 150, upper + 150) for _ in range(180)]
    for value in values:
        for x1_x10 in (False, True):
            yield float(value), x1_x10


def qualify():
    before = converter_fingerprint()
    root, meta = checked_vam(ROOT_ARCHIVE)
    proof = validate_adjustment(root, meta)
    for (event, index, button), params in proof["rules"].items():
        require(
            adjustment_parameters(event, index, button) == params,
            "Python steps/bounds differ from independently wired constants",
        )
    generated = fragments(root, meta, proof)
    corpus = hashlib.sha256()
    cases = 0
    saved = {}
    for event, button, index, uid, source in generated:
        tree = audit_fragment(source)
        code = compile(tree, "<acq-pure-scalar-adjustment>", "exec")
        saved[uid] = source
        for current, x1_x10 in fixtures(proof["rules"][event, index, button], button):
            scope = {
                "__builtins__": {},
                "current": current,
                "x1_x10": x1_x10,
                "min": min,
                "max": max,
            }
            exec(code, scope)
            expected = adjust_setpoint(event, index, button, current, x1_x10)
            require(
                type(scope["result"]) is float
                and scope["result"].hex() == expected.hex(),
                f"lvkit scalar mismatch: diagram{uid} "
                f"input={current.hex()} X1/X10={x1_x10}",
            )
            corpus.update(
                json.dumps(
                    (uid, current.hex(), x1_x10, expected.hex()), separators=(",", ":")
                ).encode()
            )
            cases += 1
    require(
        converter_fingerprint() == before, "shared lvkit changed during qualification"
    )
    return {
        "converter_fingerprint": before,
        "source_vi_sha256": SOURCE_SHA256,
        "frame0_diagrams_checked": len(proof["diagram_uids"]),
        "frame0_direct_nets_checked": proof["direct_nets"],
        "scalar_fragments": len(generated),
        "scalar_cases": cases,
        "fixture_sha256": corpus.hexdigest().upper(),
        "generated_fragments": saved,
        "outer_default_independently_verified": False,
        "property_failures_qualified": False,
        "nonfinite_inputs_qualified": False,
        "whole_events_qualified": False,
        "whole_acquisition_qualified": False,
        "hardware_executed": False,
        "vi_executed": False,
        "deployable": False,
    }


if __name__ == "__main__":
    print(json.dumps(qualify(), indent=2, sort_keys=True))
