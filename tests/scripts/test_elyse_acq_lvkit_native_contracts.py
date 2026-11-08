"""Offline differential ACQ XML/parser and reviewed codegen boundaries."""

import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from tools.audit_acq_lvkit_native_contracts import audit, compare_structures


@pytest.fixture(scope="module")
def proof():
    return audit()


def test_original_17_members_preserve_all_structures_frames_and_net_members(proof):
    assert len(proof["members"]) == 17
    assert proof["totals"] == {
        "sequences": 53,
        "cases": 58,
        "loops": 33,
        "disable_structures": 4,
        "events": 1,
        "frames": 516,
        "saved_diagrams": 533,
        "nets": 3022,
        "psp_nodes": 110,
    }


def test_native_reviewed_static_selection_and_unsafe_error_omission(proof):
    assert proof["native_reviewed_disable_selections"] == {
        "76550": 1,
        "68772": 1,
        "14478": 0,
    }
    assert proof["empty_enabled_arms_lowered"] == ["76550", "68772"]
    assert len(proof["nonempty_error_cases_refused"]) == 9
    assert proof["controlled_stop"] == {"diagrams": 45, "nets": 152}


def test_structural_preservation_does_not_promote_to_full_acq_equivalence(proof):
    assert not proof["whole_acquisition_closed"]
    assert not proof["native_vi_executed"]
    assert not proof["hardware_or_psp_executed"]
    assert proof["lvkit"]["package"].replace("\\", "/").endswith("lvkit/src/lvkit")
    assert len(proof["lvkit"]["sha256"]) == 64


def test_missing_loop_is_detected_instead_of_passing_a_global_diagram_count():
    root = ET.fromstring(
        '<root><node class="whileLoop" uid="7"><diagramList>'
        '<SL__arrayElement class="diag" uid="8"/>'
        "</diagramList></node></root>"
    )
    parsed = SimpleNamespace(
        flat_sequences=[],
        case_structures=[],
        loops=[],
        disable_structures=[],
        event_structures=[],
    )
    with pytest.raises(AssertionError, match="loops population differs"):
        compare_structures(root, parsed)
