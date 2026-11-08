"""Qualify the saved NI6602 numeric chain against NI's documented rules.

Only two pure conversions and three fake-property assignments execute.
No VI, task lifecycle, driver, transport or hardware operation executes.
This is a source-and-documentation profile, not a native LabVIEW oracle.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import random
from decimal import ROUND_HALF_EVEN, Decimal
from zipfile import ZipFile

from inventory_control_lvkit import converter_fingerprint
from qualify_acq_counter_components import SOURCE_SHA256, validate_conversion_types
from qualify_acq_lvkit import (
    ARCHIVE,
    DEFAULT_CHECKOUT,
    DEFAULT_SOURCE,
    digest,
    verify_checkout,
)
from validate_acq_ni6602_writer import MEMBER, checked_roots, require, validate_writer


def numeric_fragment():
    from lvkit.codegen.context import CodeGenContext
    from lvkit.codegen.nodes import primitive, property_node
    from lvkit.graph import InMemoryVIGraph, LoadMode
    from lvkit.models import LVTypeKind

    path = DEFAULT_SOURCE / MEMBER
    require(digest(path) == SOURCE_SHA256, "NI6602 source hash changed")
    roots = checked_roots(ARCHIVE)
    proof = validate_writer(roots)
    with ZipFile(ARCHIVE) as archive:
        types = validate_conversion_types(
            roots, archive.read(MEMBER + "/vi.xml").decode("utf-8")
        )
    graph = InMemoryVIGraph()
    key = graph.load_vi(path, mode=LoadMode.NONE)
    ctx = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
    ctx.vi_name = key
    for uid, value in (
        ("13127", "delay_us"),
        ("13077", "width_us"),
        ("3085", "task"),
        ("3091", "supplied_error"),
    ):
        ctx.bind(key + "::" + uid, value)
    statements = []
    parsed_types = {}
    for uid in ("13352", "13369", "157", "183"):
        node = graph._graph.nodes[key + "::" + uid]["node"]
        for term in node.terminals:
            expected = (
                "NumInt32"
                if uid in ("157", "183") and term.index == 0
                else "NumFloat64"
            )
            require(
                term.lv_type is not None
                and term.lv_type.kind == LVTypeKind.PRIMITIVE
                and term.lv_type.underlying_type == expected,
                "numeric primitive representation changed",
            )
            parsed_types[term.id.rsplit("::", 1)[-1]] = expected
        fragment = primitive.generate(node, ctx)
        statements.extend(fragment.statements)
        ctx.merge(fragment.bindings)
    prop = graph._graph.nodes[key + "::3083"]["node"]
    timing = property_node.generate(prop, ctx)
    statements.extend(timing.statements)
    attrs = [statement.targets[0].attr for statement in timing.statements]
    temporaries = [ctx.resolve(key + "::" + uid) for uid in ("163", "201")]
    require(len(set(temporaries)) == 2, "numeric outputs aliased")
    source = (
        ast.unparse(
            ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[]))
        )
        + "\n"
    )
    require(digest(path) == SOURCE_SHA256, "source changed during generation")
    return (
        source,
        attrs,
        temporaries,
        {
            "wire_proof": proof,
            "archived_numeric_type_proof": types,
            "parsed_numeric_types": parsed_types,
            "timing_bindings": {
                u.rsplit("::", 1)[-1]: v for u, v in timing.bindings.items()
            },
        },
    )


def audit_numeric(source, attrs, temporaries):
    """Five assignments; arithmetic and four pure builtins only.

    This gate is not a general Python sandbox. Execution uses only bounded
    scalar fixtures, known builtins, and a SimpleNamespace fake property sink.
    """
    tree = ast.parse(source)
    require(len(tree.body) == 5, "numeric fragment must have five assignments")
    allowed = (
        ast.Module,
        ast.Assign,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Constant,
        ast.BinOp,
        ast.Mult,
        ast.BitAnd,
        ast.UnaryOp,
        ast.USub,
        ast.Call,
        ast.Attribute,
    )
    names = {"delay_us", "width_us", "task", "min", "max", "int", "round", *temporaries}
    for node in ast.walk(tree):
        require(isinstance(node, allowed), "numeric syntax outside allowlist")
        if isinstance(node, ast.Name):
            require(node.id in names, "numeric name outside allowlist")
        if isinstance(node, ast.Constant):
            require(type(node.value) in (int, float), "numeric constant required")
        if isinstance(node, ast.Attribute):
            require(
                isinstance(node.value, ast.Name)
                and node.value.id == "task"
                and node.attr in attrs
                and isinstance(node.ctx, ast.Store),
                "only fake timing property stores permitted",
            )
        if isinstance(node, ast.Call):
            require(
                isinstance(node.func, ast.Name)
                and node.func.id in ("min", "max", "int", "round")
                and not node.keywords
                and len(node.args) == (2 if node.func.id in ("min", "max") else 1),
                "only scalar conversion builtins permitted",
            )
    require(
        all(
            isinstance(statement, ast.Assign) and len(statement.targets) == 1
            for statement in tree.body
        ),
        "only single assignments permitted",
    )
    require(
        [
            statement.targets[0].id
            for statement in tree.body[:2]
            if isinstance(statement.targets[0], ast.Name)
        ]
        == temporaries
        and [
            statement.targets[0].attr
            for statement in tree.body[2:]
            if isinstance(statement.targets[0], ast.Attribute)
        ]
        == attrs,
        "numeric assignment targets changed",
    )
    return tree


def run_numeric(source, attrs, temporaries, delay, width):
    from types import SimpleNamespace

    require(
        all(
            type(v) in (int, float) and math.isfinite(v) and math.isfinite(v * 20.0)
            for v in (delay, width)
        ),
        "finite DBL fixtures required; nonfinite behavior unqualified",
    )
    tree = audit_numeric(source, attrs, temporaries)
    task = SimpleNamespace()
    namespace = {
        "__builtins__": {},
        "min": min,
        "max": max,
        "round": round,
        "int": int,
        "delay_us": delay,
        "width_us": width,
        "task": task,
    }
    exec(compile(tree, "<audited-counter-numeric>", "exec"), namespace)
    return tuple(getattr(task, attr) for attr in attrs)


def documented_ticks(microseconds):
    """Independent Decimal rounding and byte reinterpretation of finite DBL."""
    product = float(microseconds * 20.0)
    require(math.isfinite(product), "reference needs a finite DBL product")
    rounded = int(
        Decimal.from_float(product).to_integral_value(rounding=ROUND_HALF_EVEN)
    )
    if rounded > 2147483647:
        rounded = 2147483647
    elif rounded < -2147483648:
        rounded = -2147483648
    return int.from_bytes(rounded.to_bytes(4, "big", signed=True), "big", signed=False)


def vectors():
    values = [
        -1e300,
        -1e10,
        -0.16,
        -0.125,
        -0.075,
        -0.025,
        -0.0,
        0.0,
        0.025,
        0.075,
        0.125,
        0.16,
        1e10,
        1e300,
    ]
    for ticks in (
        -2147483649,
        -2147483648,
        -2147483647.5,
        -1.5,
        -0.5,
        0.5,
        1.5,
        2147483646.5,
        2147483647,
        2147483648,
        4294967295,
    ):
        value = ticks / 20.0
        values.extend(
            (math.nextafter(value, -math.inf), value, math.nextafter(value, math.inf))
        )
    rng = random.Random(6602)
    values.extend(rng.uniform(-3e8, 3e8) for _ in range(4096))
    return list(zip(values, reversed(values)))


def qualify():
    from DeviceServers.control.elyse_acq.vi_simulation.write_ni6602 import (
        labview_i32_to_u32_ticks,
    )

    before = converter_fingerprint()
    source, attrs, temporaries, proof = numeric_fragment()
    repeat, repeated_attrs, repeated_temps, _ = numeric_fragment()
    require(
        (source, attrs, temporaries) == (repeat, repeated_attrs, repeated_temps),
        "numeric generation is not reproducible",
    )
    cases = vectors()
    for delay, width in cases:
        expected = (
            documented_ticks(delay),
            documented_ticks(delay),
            documented_ticks(width),
        )
        require(
            run_numeric(source, attrs, temporaries, delay, width) == expected,
            "converter numeric discrepancy",
        )
        require(
            (labview_i32_to_u32_ticks(delay), labview_i32_to_u32_ticks(width))
            == (expected[0], expected[2]),
            "manual model numeric discrepancy",
        )
    require(converter_fingerprint() == before, "converter changed during qualification")
    return {
        "source": source,
        "receipt": {
            **proof,
            "source_sha256": SOURCE_SHA256,
            "converter_fingerprint": before,
            "fragment_sha256": hashlib.sha256(source.encode()).hexdigest().upper(),
            "numeric_cases": len(cases),
            "scalar_conversions_compared": 2 * len(cases),
            "vectors_sha256": hashlib.sha256(
                json.dumps(cases, separators=(",", ":")).encode()
            )
            .hexdigest()
            .upper(),
            "qualification": "FINITE_DBL_SOURCE_AND_DOCUMENTATION_AGREEMENT",
            "reference": (
                "NI 321526a pp. 2-4 and 4-10; "
                "Decimal ties-to-even and signed-byte reinterpretation"
            ),
            "full_writer_qualified": False,
            "deployable": False,
            "hardware_executed": False,
            "vi_executed": False,
            "limits": [
                "No native LabVIEW execution oracle or hash-matched screenshot",
                "NaN, infinity and overflowing DBL products rejected "
                "by Python-only fixture guard",
                "No property/driver errors, Stop/Clear/Start, timing "
                "or hardware acceptance proof",
                "U32 property coercion supports scalar I32 source only; "
                "other mismatched sources rejected",
                "Integer-input To Long Integer, other numeric representations "
                "and general coercion remain unqualified",
            ],
        },
    }


if __name__ == "__main__":
    verify_checkout(DEFAULT_CHECKOUT)
    print(json.dumps(qualify(), ensure_ascii=True, indent=2))
