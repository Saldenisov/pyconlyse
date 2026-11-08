"""Qualify isolated NI6602 loop/property fragments, never a hardware writer.

The original VI and archived wires are pinned. Execution accepts a tiny AST
grammar and injects only a bounded fake task and non-sleeping clock. Full-VI
error propagation, driver boundaries and coercion remain unqualified.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from types import SimpleNamespace
from zipfile import ZipFile

from inventory_control_lvkit import converter_fingerprint
from qualify_acq_lvkit import (
    ARCHIVE,
    DEFAULT_CHECKOUT,
    DEFAULT_SOURCE,
    digest,
    verify_checkout,
)
from validate_acq_ni6602_writer import MEMBER, checked_roots, require, validate_writer

SOURCE_SHA256 = "4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211"


def validate_conversion_types(roots, metadata_text):
    """Independent archived heap -> consolidated -> flat descriptor check."""
    bd, meta = roots["vi_BDHb.xml"], roots["vi.xml"]
    heap_map = {
        int(h): int(c)
        for h, c in re.findall(
            r"Heap TypeID\s+(\d+)\s*=\s*Consolidated TypeID\s+(\d+):",
            metadata_text,
        )
    }
    flat_map = {
        int(t.get("Index")): int(t.get("FlatTypeID"))
        for t in meta.findall("VCTP/Section/TopLevel/TypeDesc")
    }
    descriptors = meta.findall("VCTP/Section/TypeDesc")
    records = {}
    for uid, heap, expected in (
        ("201", 104, "NumInt32"),
        ("163", 106, "NumInt32"),
        ("3097", 61, "NumUInt32"),
        ("3103", 64, "NumUInt32"),
        ("3109", 67, "NumUInt32"),
    ):
        terms = [
            n for n in bd.iter() if n.get("class") == "term" and n.get("uid") == uid
        ]
        require(
            len(terms) == 1 and terms[0].findtext("dco/typeDesc") == f"TypeID({heap})",
            "conversion/property heap type changed",
        )
        consolidated = heap_map[heap]
        flat = flat_map[consolidated]
        require(
            descriptors[flat].get("Type") == expected,
            "conversion/property numeric representation changed",
        )
        records[uid] = {
            "heap": heap,
            "consolidated": consolidated,
            "flat": flat,
            "type": expected,
        }
    return records


def fragments():
    from lvkit.codegen.builder import generate_body
    from lvkit.codegen.context import CodeGenContext
    from lvkit.codegen.nodes import loop, property_node
    from lvkit.graph import InMemoryVIGraph, LoadMode

    path = DEFAULT_SOURCE / MEMBER
    require(digest(path) == SOURCE_SHA256, "NI6602 source hash changed")
    roots = checked_roots(ARCHIVE)
    proof = validate_writer(roots)
    with ZipFile(ARCHIVE) as archive:
        raw_types = validate_conversion_types(
            roots, archive.read(MEMBER + "/vi.xml").decode("utf-8")
        )
    graph = InMemoryVIGraph()
    key = graph.load_vi(path, mode=LoadMode.NONE)
    ctx = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
    ctx.vi_name = key
    ctx._body_generator = generate_body
    ctx.bind(key + "::2758", "task")
    # Unlike build_module's exception model, this isolated nominal fixture
    # explicitly supplies the input error wire. It is not an error adapter.
    ctx.bind(key + "::13028", "supplied_error")
    poll = loop.generate(graph._graph.nodes[key + "::3129"]["node"], ctx)
    read = graph._graph.nodes[key + "::3202"]["node"]
    write = graph._graph.nodes[key + "::3083"]["node"]
    for uid, value in (
        ("3085", "task"),
        ("3091", "supplied_error"),
        ("3097", "delay_ticks"),
        ("3103", "delay_ticks"),
        ("3109", "high_ticks"),
    ):
        ctx.bind(key + "::" + uid, value)
    timing = property_node.generate(write, ctx)
    require(
        poll.bindings[key + "::3143"] == "task"
        and poll.bindings[key + "::3131"] == "supplied_error"
        and timing.bindings[key + "::3088"] == "task"
        and timing.bindings[key + "::3094"] == "supplied_error",
        "reference/error flow-through identity mismatch",
    )
    from lvkit.codegen.ast_utils import to_var_name

    attrs = [to_var_name(p.name) for p in [*read.properties, *write.properties]]
    sources = {
        name: ast.unparse(
            ast.fix_missing_locations(ast.Module(body=f.statements, type_ignores=[]))
        )
        + "\n"
        for name, f in (("poll", poll), ("timing", timing))
    }
    require(digest(path) == SOURCE_SHA256, "source changed during generation")
    return (
        sources,
        attrs,
        {
            "wire_proof": proof,
            "archived_numeric_type_proof": raw_types,
            "loop_bindings": {
                u.rsplit("::", 1)[-1]: v for u, v in poll.bindings.items()
            },
            "timing_bindings": {
                u.rsplit("::", 1)[-1]: v for u, v in timing.bindings.items()
            },
            "property_value_uids": {
                "3202": [
                    u.rsplit("::", 1)[-1] for u in read.property_value_terminal_ids
                ],
                "3083": [
                    u.rsplit("::", 1)[-1] for u in write.property_value_terminal_ids
                ],
            },
            "conversion_output_types": {
                uid: graph._graph.nodes[key + "::" + uid]["node"]
                .terminals[0]
                .lv_type.underlying_type
                for uid in ("157", "183")
            },
        },
    )


def audit_fragment(source, attrs, *, polling):
    """Only arithmetic/control plus named fake attributes and clock.sleep."""
    tree = ast.parse(source)
    allowed = (
        ast.Module,
        ast.Assign,
        ast.AugAssign,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Constant,
        ast.While,
        ast.If,
        ast.Break,
        ast.Expr,
        ast.Call,
        ast.Attribute,
        ast.BinOp,
        ast.Div,
        ast.Add,
        ast.BitAnd,
        ast.BoolOp,
        ast.Or,
        ast.Compare,
        ast.Eq,
        ast.Gt,
        ast.Lt,
    )
    for node in ast.walk(tree):
        require(isinstance(node, allowed), "fragment syntax outside allowlist")
        if isinstance(node, ast.Name):
            require(not node.id.startswith("__"), "dunder access forbidden")
        if isinstance(node, ast.Attribute):
            require(
                isinstance(node.value, ast.Name)
                and (
                    (node.value.id == "task" and node.attr in attrs)
                    or (node.value.id == "time" and node.attr == "sleep")
                ),
                "attribute outside fake task/clock allowlist",
            )
        if isinstance(node, ast.Call):
            require(
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "time"
                and node.func.attr == "sleep"
                and len(node.args) == 1
                and not node.keywords,
                "only fake clock.sleep call permitted",
            )
    loops = [n for n in ast.walk(tree) if isinstance(n, ast.While)]
    require(
        len(loops) == int(polling), "one polling loop or zero timing loops required"
    )
    if polling:
        require(
            isinstance(loops[0].test, ast.Constant) and loops[0].test.value is True,
            "do-while shape changed",
        )
        require(
            not any(
                isinstance(n.ctx, ast.Store)
                for n in ast.walk(tree)
                if isinstance(n, ast.Attribute)
            ),
            "poll writes a task property",
        )
    return tree


class FakeTask:
    """Bounded supplied Boolean returns and in-memory property assignments."""

    def __init__(self, attrs, done_at):
        object.__setattr__(self, "attrs", attrs)
        object.__setattr__(self, "done_at", done_at)
        object.__setattr__(self, "reads", [])
        object.__setattr__(self, "writes", [])

    def __getattr__(self, name):
        require(name == self.attrs[0], "unexpected fake task read")
        index = len(self.reads)
        require(index < 22, "poll exceeded saved 22-iteration bound")
        value = index == self.done_at
        self.reads.append(value)
        return value

    def __setattr__(self, name, value):
        require(name in self.attrs[1:], "unexpected fake task write")
        self.writes.append((name, value))


def run_fragment(source, attrs, *, polling, done_at=None, delay=200, high=500):
    tree = audit_fragment(source, attrs, polling=polling)
    task, waits = FakeTask(attrs, done_at), []

    def wait(seconds):
        require(seconds == 0.001, "saved Wait(1 ms) changed")
        require(len(waits) < 22, "fake wait exceeded bound")
        waits.append(seconds)

    namespace = {
        "__builtins__": {},
        "task": task,
        "time": SimpleNamespace(sleep=wait),
        "supplied_error": object(),
        "delay_ticks": delay,
        "high_ticks": high,
    }
    exec(compile(tree, "<audited-counter-fragment>", "exec"), namespace)
    return task, waits, namespace


def qualify():
    from DeviceServers.control.elyse_acq.vi_simulation import (
        NO_ERROR,
        CallKey,
        ScriptedBoundary,
        TaskReference,
        record_ni6602_reconfiguration,
    )
    from DeviceServers.control.elyse_acq.vi_simulation.write_ni6602 import (
        POLL_UID,
        SOURCE,
    )

    before = converter_fingerprint()
    sources, attrs, receipt = fragments()
    repeat, _, _ = fragments()
    require(sources == repeat, "fragment generation is not reproducible")
    traces = []
    for done_at in [*range(22), None]:
        values = tuple(i == done_at for i in range(22))
        boundary = ScriptedBoundary(
            data={CallKey(SOURCE.name, POLL_UID, i): (v,) for i, v in enumerate(values)}
        )
        expected = record_ni6602_reconfiguration(
            boundary,
            task=TaskReference("counter-fixture"),
            delay_microseconds=10,
            width_microseconds=25,
            error_in=NO_ERROR,
        )
        actual, waits, ns = run_fragment(
            sources["poll"], attrs, polling=True, done_at=done_at
        )
        require(len(actual.reads) == expected.poll_iterations, "poll count mismatch")
        require(len(waits) == expected.poll_iterations, "wait count mismatch")
        require(actual.reads[-1] is expected.final_pulse_done, "Done value mismatch")
        counters = [v for k, v in ns.items() if k.startswith("while_index_")]
        require(counters == [expected.poll_iterations - 1], "final index mismatch")
        traces.append({"done_at": done_at, "iterations": len(actual.reads)})
    timing_cases = 0
    for delay, high in ((0, 0), (200, 500), (500, 200), (0xFFFFFFFF, 1)):
        task, waits, _ = run_fragment(
            sources["timing"], attrs, polling=False, delay=delay, high=high
        )
        require(
            task.writes == list(zip(attrs[1:], (delay, delay, high))),
            "timing write order/value mismatch",
        )
        require(
            not waits and not task.reads, "timing fragment unexpectedly reads/waits"
        )
        timing_cases += 1
    require(converter_fingerprint() == before, "converter changed during qualification")
    return {
        "sources": sources,
        "receipt": {
            **receipt,
            "source_sha256": SOURCE_SHA256,
            "fragment_sha256": {
                name: hashlib.sha256(source.encode()).hexdigest().upper()
                for name, source in sources.items()
            },
            "converter_fingerprint": before,
            "poll_traces": traces,
            "timing_cases": timing_cases,
            "qualification": "ISOLATED_NOMINAL_COMPONENT_AGREEMENT",
            "full_writer_qualified": False,
            "deployable": False,
            "hardware_executed": False,
            "vi_executed": False,
            "limits": [
                "Explicitly injected nominal error wire; no driver error semantics",
                "No Stop/Clear/Start execution or task-replacement behavior",
                "Timing inputs already ticks; no microseconds-to-I32 conversion test",
                "Wait is counted, not timed; no wall-clock equivalence",
                "No hash-matched native Acquisition screenshot",
            ],
        },
    }


if __name__ == "__main__":
    verify_checkout(DEFAULT_CHECKOUT)
    print(json.dumps(qualify(), ensure_ascii=True, indent=2))
