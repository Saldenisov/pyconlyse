"""Pure finite comparison replay, original wires and mutation rejection."""

import copy
import json
import math
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_direct_comparison as trace


@pytest.fixture(scope="module")
def bundle():
    return trace.helper_sources()


def state():
    return [
        [True if col % 2 else False for col in range(5)]
        + [2.0, 1.0]
        + [True, False, True, False]
        for _ in range(11)
    ]


def test_whole_output_proof_reproduces_without_network(bundle, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network in comparison source replay")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    report = trace.verify(bundle)
    assert report == json.loads(trace.OUTPUT.read_text("utf-8"))
    assert report["complete_source_defined_output_model_within_domain"]
    assert report["arithmetic_nodes_accounted"] == 33
    assert report["unused_Phase_arithmetic_nodes"] == 3
    assert not report["native_connector_or_runtime_equivalence"]
    assert not report["full_Supervision_coverage"]


@pytest.mark.parametrize(
    "threshold,expected", [(0.5, True), (1.0, False), (2.0, False), (-1.0, True)]
)
def test_strict_deviation_threshold_and_phase_exception(threshold, expected):
    original = state()
    original[2][2] = True
    before = copy.deepcopy(original)
    output = trace.project(original, threshold)
    assert original == before
    assert all(
        row[2] == (False if i == trace.PHASE else expected)
        for i, row in enumerate(output)
    )
    assert all(
        output[i][j] == original[i][j] for i in range(11) for j in range(11) if j != 2
    )


@pytest.mark.parametrize("row", range(11))
def test_each_numeric_row_has_its_own_comparator(row):
    values = state()
    for r in values:
        r[5], r[6] = 0.0, 0.0
    values[row][5] = -3.0
    out = trace.project(values, 2.0)
    assert [i for i, r in enumerate(out) if r[2]] == (
        [] if row == trace.PHASE else [row]
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 1, True])
def test_nonfinite_and_non_float_thresholds_rejected(value):
    with pytest.raises(AssertionError, match="finite float"):
        trace.project(state(), value)


def test_overflow_and_malformed_carriers_rejected():
    values = state()
    values[0][5], values[0][6] = 1e308, -1e308
    with pytest.raises(AssertionError, match="finite difference"):
        trace.project(values, 1.0)
    with pytest.raises(AssertionError, match="11 rows"):
        trace.project([], 1.0)
    values = state()
    values[0][0] = 1
    with pytest.raises(AssertionError, match="Bool"):
        trace.project(values, 1.0)


def test_greater_to_greater_equal_mutation_rejected(bundle):
    altered = copy.deepcopy(bundle)
    node = next(
        n
        for n in altered[1]["bd"].iter()
        if n.get("uid") == "1400" and n.get("class") == "prim"
    )
    node.find("primResID").text = "1111"
    with pytest.raises(AssertionError, match="arithmetic census"):
        trace.verify(altered)


def test_forced_phase_false_mutation_rejected(bundle):
    altered = copy.deepcopy(bundle)
    node = next(
        n
        for n in altered[1]["bd"].iter()
        if n.get("uid") == "3056" and n.get("class") == "term"
    )
    node.find("dco/ConstValue").text = "0001"
    with pytest.raises(AssertionError, match="Phase orange False"):
        trace.verify(altered)
