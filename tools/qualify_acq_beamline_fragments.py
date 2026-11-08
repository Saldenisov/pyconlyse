"""Qualify only reviewed beam-line Bundle/Unbundle fragments from shared lvkit.

Original XML proves field indices independently. Generated fragments receive
explicit pure tuple fixtures; only positional-cluster replacement is allowed.
No whole main-VI generation/execution, local-write handler or I/O is permitted.
"""

from __future__ import annotations

import ast
import hashlib
import json
import random
from types import MappingProxyType

from DeviceServers.control.elyse_acq.vi_simulation.beamline_commands import (
    SETPOINT_COPIES,
    project_setpoint_frame,
)
from inventory_control_lvkit import converter_fingerprint
from qualify_acq_lvkit import (
    DEFAULT_CHECKOUT,
    DEFAULT_SOURCE,
    REPO,
    digest,
    verify_checkout,
)
from validate_acq_beamline_commands import BUNDLES, SOURCES, validate_tail
from validate_acq_modulator_start_event_guards import require
from validate_acq_vam_status import checked_vam

SOURCE_SHA256 = "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF"
ROOT_ARCHIVE = (
    REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
)


def fragments():
    verify_checkout(DEFAULT_CHECKOUT)
    from lvkit.codegen.context import CodeGenContext
    from lvkit.codegen.nodes import nmux
    from lvkit.graph import InMemoryVIGraph, LoadMode

    path = DEFAULT_SOURCE / "0_ACQ_ELYSE.vi"
    require(digest(path) == SOURCE_SHA256, "original main VI hash changed")
    proof = validate_tail(*checked_vam(ROOT_ARCHIVE))
    require(proof == dict(SETPOINT_COPIES), "wire-derived maps disagree with model")
    graph = InMemoryVIGraph()
    key = graph.load_vi(path, mode=LoadMode.NONE)
    sources = {}
    for event in (1, 2):
        ctx = CodeGenContext.from_vi_context(graph.get_vi_context(key), graph=graph)
        ctx.vi_name = key
        source = SOURCES[event]
        ctx.bind(key + "::" + source[1], "cells")
        for row in BUNDLES[event]:
            ctx.bind(key + "::" + row[2], f"bank{row[0]}")
        nodes = [source[3], *(row[5] for row in BUNDLES[event])]
        statements, imports = [], set()
        for uid in nodes:
            node = graph._graph.nodes[key + "::" + uid]["node"]
            expected = (
                (
                    (source[4], "input", "agg", None),
                    *((port, "output", "list", field) for port, field in source[5]),
                )
                if uid == source[3]
                else next(
                    (
                        (row[6], "output", "agg", None),
                        (row[7], "input", "agg", None),
                        *((port, "input", "list", field) for port, field, _ in row[8]),
                    )
                    for row in BUNDLES[event]
                    if row[5] == uid
                )
            )
            require(
                tuple(
                    (
                        t.id.rsplit("::", 1)[-1],
                        t.direction,
                        t.nmux_role,
                        t.nmux_field_index,
                    )
                    for t in node.terminals
                )
                == expected,
                "parsed beam-line Bundle/Unbundle ports differ from original XML",
            )
            emitted = nmux.generate(node, ctx)
            statements.extend(emitted.statements)
            imports.update(emitted.imports)
            for term, value in emitted.bindings.items():
                ctx.bind(term, value)
        require(
            imports == {"from lvkit.positional_cluster import replace_fields"},
            "beam-line fragment imports outside pure helper",
        )
        outputs = [ctx.resolve(key + "::" + row[6]) for row in BUNDLES[event]]
        require(
            all(value is not None for value in outputs),
            "unresolved command-bank output",
        )
        statements.extend(ast.parse("result = (" + ", ".join(outputs) + ",)").body)
        sources[event] = (
            ast.unparse(
                ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[]))
            )
            + "\n"
        )
        audit_fragment(sources[event])
    require(
        digest(path) == SOURCE_SHA256,
        "original main VI changed during fragment generation",
    )
    return sources


def audit_fragment(source):
    tree = ast.parse(source)
    allowed = (
        ast.Module,
        ast.Assign,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Tuple,
        ast.Constant,
        ast.Subscript,
        ast.Call,
    )
    bound = {"cells", "bank9", "bank10", "bank11", "replace_fields"}
    for statement in tree.body:
        require(
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name),
            "fragment must contain only scalar-name assignments",
        )
        target = statement.targets[0].id
        require(
            target not in bound and not target.startswith("__"),
            "fixture/helper reassignment forbidden",
        )
        for node in ast.walk(statement.value):
            require(
                isinstance(node, allowed),
                "fragment syntax outside pure cluster allowlist",
            )
            if isinstance(node, ast.Name):
                require(node.id in bound, "unresolved or unsafe fragment name")
            if isinstance(node, ast.Constant):
                require(
                    type(node.value) is int and node.value >= 0,
                    "only non-negative tuple indices permitted",
                )
            if isinstance(node, ast.Subscript):
                require(
                    isinstance(node.slice, ast.Constant)
                    and type(node.slice.value) is int
                    and node.slice.value >= 0,
                    "only constant positional indexing permitted",
                )
            if isinstance(node, ast.Call):
                require(
                    isinstance(node.func, ast.Name)
                    and node.func.id == "replace_fields"
                    and len(node.args) == 2
                    and not node.keywords,
                    "only the audited positional-cluster helper may be called",
                )
        bound.add(target)
    require(
        tree.body and tree.body[-1].targets[0].id == "result",
        "explicit result required",
    )
    return tree


def run_fragment(source, event, cells, snapshots):
    from lvkit.positional_cluster import replace_fields

    # The independent model validates every nested fixture type before exec.
    project_setpoint_frame(
        event, apply_setpoints=True, cells=cells, read_snapshots=snapshots
    )
    scope = {"__builtins__": {}, "cells": cells, "replace_fields": replace_fields}
    scope.update({f"bank{bank}": value for bank, value in snapshots.items()})
    exec(
        compile(audit_fragment(source), "<beam-line-pure-cluster-fixture>", "exec"),
        scope,
    )
    return scope["result"]


def fixtures(event):
    rng = random.Random(1660 if event == 1 else 16917)
    count = 11 if event == 1 else 9
    indices = (9, 10, 11) if event == 1 else (9, 10)
    for case in range(260):
        scalar = (
            (lambda: 0.0)
            if case == 0
            else (lambda: -0.0)
            if case == 1
            else (lambda: 1e200)
            if case == 2
            else (lambda: -1e200)
            if case == 3
            else (lambda: rng.uniform(-1000.0, 1000.0))
        )
        cells = tuple(
            tuple(bool(rng.getrandbits(1)) for _ in range(5))
            + (scalar(), scalar())
            + tuple(bool(rng.getrandbits(1)) for _ in range(4))
            for _ in range(count)
        )
        snapshots = {bank: tuple(scalar() for _ in range(10)) for bank in indices}
        yield cells, snapshots


def qualify():
    before = converter_fingerprint()
    sources = fragments()
    cases, bank_cases, corpus = 0, 0, hashlib.sha256()
    for event, source in sources.items():
        for cells, snapshots in fixtures(event):
            original = (cells, dict(snapshots))
            expected = tuple(
                w.value
                for w in project_setpoint_frame(
                    event, apply_setpoints=True, cells=cells, read_snapshots=snapshots
                )
            )
            actual = run_fragment(source, event, cells, snapshots)
            require(
                tuple(tuple(v.hex() for v in bank) for bank in actual)
                == tuple(tuple(v.hex() for v in bank) for bank in expected),
                "generated beam-line bank values differ from original wire model",
            )
            require((cells, snapshots) == original, "fragment mutated input snapshots")
            corpus.update(
                json.dumps(
                    (event, cells, snapshots), sort_keys=True, separators=(",", ":")
                ).encode()
            )
            cases += 1
            bank_cases += len(expected)
    require(
        converter_fingerprint() == before, "shared lvkit changed during qualification"
    )
    return MappingProxyType(
        {
            "converter_fingerprint": before,
            "source_vi_sha256": SOURCE_SHA256,
            "fixture_sha256": corpus.hexdigest().upper(),
            "event_cases": cases,
            "bank_cases": bank_cases,
            "scalar_values_compared": bank_cases * 10,
            "generated_fragments": sources,
            "full_events_qualified": False,
            "full_acquisition_qualified": False,
            "deployable": False,
            "hardware_executed": False,
            "vi_executed": False,
        }
    )


if __name__ == "__main__":
    print(json.dumps(dict(qualify()), indent=2, sort_keys=True))
