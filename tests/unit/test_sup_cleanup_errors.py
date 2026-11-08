"""Read-only source/contract and mutation checks, not native shutdown tests."""

import copy
import ctypes
import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import trace_sup_cleanup_errors as trace


@pytest.fixture(scope="module")
def inputs():
    return trace.original(), trace.native_evidence(), trace.load_added()


@pytest.fixture(scope="module")
def graphs(inputs):
    _, (_, libraries, _), (_, extra, _) = inputs
    T, _ = trace.components()
    return {
        name: trace.graph(bundle, T) for name, bundle in {**libraries, **extra}.items()
    }


@pytest.fixture(scope="module")
def report(inputs):
    return trace.verify(*inputs)


def motion(graphs, inputs, abort=None, shutdown=None, docs=None):
    return trace.motion(
        graphs["AbortMotion"] if abort is None else abort,
        graphs["Shutdown"] if shutdown is None else shutdown,
        inputs[2][2] if docs is None else docs,
    )


def images(graphs, inputs, **replacements):
    names = (
        "IMAQ_Close",
        "imgClose",
        "IMAQUnregisterSession",
        "IMAQ_Dispose",
        "imgUpdateErrorCluster",
    )
    return trace.images(*(replacements.get(n, graphs[n]) for n in names), inputs[2][2])


def test_reproduces_without_network_or_native_loading(inputs, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Only saved-source analysis is allowed")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(ctypes, "CDLL", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    assert trace.verify(*inputs) == json.loads(trace.OUTPUT.read_text("utf-8"))


def test_abort_failure_is_not_successful_motion_completion(report):
    m = report["observations"]["motion"]
    assert m["Abort_false_return"] == {
        "status": True,
        "code": 1,
        "source": "AbortMotion.vi I/O Error.",
    }
    assert m["Shutdown_wrapper_entered_after_Abort_returns"]
    assert m["Shutdown_error_input_direct_to_DotNet_invoke"] == ["598", "352"]
    assert "NOT invoked" in m["contract_based_conclusion"]
    assert not m["LV2012_runtime_short_circuit_experiment"]


@pytest.mark.parametrize(
    "field,value", [("methName", '"Close"'), ("invokeFlags", "00")]
)
def test_shutdown_identity_or_flags_mutation_rejected(graphs, inputs, field, value):
    g = copy.deepcopy(graphs["Shutdown"])
    g.nodes["340"].find(field).text = value
    with pytest.raises(AssertionError, match="invoke metadata"):
        motion(graphs, inputs, shutdown=g)


def test_shutdown_error_bypass_mutation_rejected(graphs, inputs):
    g = copy.deepcopy(graphs["Shutdown"])
    g.nodes["273"].find("termList/SL__arrayElement").set("uid", "355")
    with pytest.raises(AssertionError):
        motion(graphs, inputs, shutdown=g)


def test_abort_false_branch_polarity_mutation_rejected(graphs, inputs):
    g = copy.deepcopy(graphs["AbortMotion"])
    g.nodes["938"].find("SelectRangeArray32/SL__arrayElement/diagramIdx").text = "1"
    with pytest.raises(AssertionError, match="polarity"):
        motion(graphs, inputs, abort=g)


def test_dotnet_conclusion_requires_documented_contract(graphs, inputs):
    docs = dict(inputs[2][2])
    docs["Invoke_Node_NET"] = "Unknown input-error policy"
    with pytest.raises(AssertionError, match="contract"):
        motion(graphs, inputs, docs=docs)


def test_close_is_ref_guarded_not_error_guarded(report):
    i = report["observations"]["image"]
    assert not i["incoming_error_used_as_close_selector"]
    assert i["native_close"]["clean"] == 1
    assert not i["native_close"]["native_error_cluster_input"]
    assert i["prior_error_can_hide_close_error"]
    assert "generic skip-on-error" in i["documentation_conflict"]
    assert "not verified deployed NI2012" in i["library_identity"]


@pytest.mark.parametrize("name,uid", [("IMAQ_Close", "109"), ("imgClose", "107")])
def test_imaq_selector_primitive_mutation_rejected(graphs, inputs, name, uid):
    g = copy.deepcopy(graphs[name])
    g.nodes[uid].find("primResID").text = "1064"
    with pytest.raises(AssertionError, match="primitive"):
        images(graphs, inputs, **{name: g})


@pytest.mark.parametrize("name,uid", [("IMAQ_Close", "90"), ("imgClose", "115")])
def test_imaq_selector_case_mutation_rejected(graphs, inputs, name, uid):
    g = copy.deepcopy(graphs[name])
    g.nodes[uid].find("SelectRangeArray32/SL__arrayElement/diagramIdx").text = "1"
    with pytest.raises(AssertionError, match="polarity"):
        images(graphs, inputs, **{name: g})


@pytest.mark.parametrize(
    "name,port",
    [("imgClose", "304"), ("IMAQUnregisterSession", "241"), ("IMAQ_Dispose", "202")],
)
def test_native_error_terminal_mutation_rejected(graphs, inputs, name, port):
    g = copy.deepcopy(graphs[name])
    g.nets.append(("injected-error-link", ["999999", port]))
    with pytest.raises(AssertionError):
        images(graphs, inputs, **{name: g})


def test_merge_priority_mutation_rejected(graphs, inputs):
    g = copy.deepcopy(graphs["IMAQ_Close"])
    term_list = g.nodes["341"].find("termList")
    out, first, second = list(term_list)
    term_list[:] = [out, second, first]
    with pytest.raises(AssertionError, match="priority"):
        images(graphs, inputs, IMAQ_Close=g)


def test_dispose_entry_does_not_prove_disposal_on_error(report):
    d = report["observations"]["image"]["Dispose"]
    assert not d["diagram_error_gate"]
    assert d["error_cluster_is_native_argument"]
    assert not d["DLL_internal_error_short_circuit_verified"]
    assert d["image_type_opaque"]
    assert report["observations"]["Main"]["Dispose_initial_error"] is False
    assert report["observations"]["Main"]["image_count"] == 9


@pytest.mark.parametrize(
    "returned,error,expected",
    [
        (True, True, False),
        (True, False, True),
        (False, False, False),
        (False, True, False),
    ],
)
def test_supplied_abort_states_under_standard_contract(returned, error, expected):
    r = trace.dispatch_witness(
        abort_returned=returned,
        abort_error_status=error,
        session_non_null=True,
        interface_id=1,
    )
    assert r["Shutdown_wrapper_eligible"] == returned
    assert r["Shutdown_method_eligible_under_standard_contract"] == expected
    assert not r["resource_release_confirmed"]


@pytest.mark.parametrize(
    "session,interface,disposed,unregistered,expected",
    [
        (True, 7, True, True, True),
        (False, 7, True, True, False),
        (True, 0, True, True, False),
        (True, 7, False, True, False),
        (True, 7, True, False, False),
    ],
)
def test_supplied_imaq_states_are_dispatch_not_release(
    session, interface, disposed, unregistered, expected
):
    r = trace.dispatch_witness(
        abort_returned=True,
        abort_error_status=True,
        session_non_null=session,
        interface_id=interface,
        disposal_returned=disposed,
        unregister_returned=unregistered,
    )
    assert r["IMAQ_candidate_native_close_eligible"] == expected
    assert not r["resource_release_confirmed"]


def test_limits_are_preserved(report):
    for key in (
        "screen_used",
        "VI_run_or_save",
        "native_library_loaded",
        "network_io",
        "hardware_io",
        "production_changes",
        "guaranteed_resource_release",
        "full_Supervision_coverage",
    ):
        assert report[key] is False
    assert len(report["saved_screenshots"]) == 4
    assert any("bit-level semantics" in text for text in report["unknowns"])
    assert any("LV_Dispose" in text for text in report["unknowns"])
