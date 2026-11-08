"""Original-source proof joins, not just a self-consistent schedule model."""

import pytest
from tools.audit_acq_fault_window import audit


@pytest.fixture(scope="module")
def report():
    return audit()


def test_source_proofs_cover_the_claimed_stop_to_cleanup_join(report):
    assert report["source_stop_memory_validation"]["stop_local_references"] == 20
    assert report["source_stop_memory_validation"]["literal_writers"] == 11
    phase = report["source_c9_phase_join_validation"]
    assert phase["runtime_loops_must_join_before_ramp"] == 5
    assert not phase["remote_receiver_overlaps_outer_ramp"]
    assert len(report["source_outer_tcp_and_general_selectors_validation"]) == 3
    assert len(report["source_cleanup_validation"]) == 4
    assert report["source_cleanup_validation"][-1] == (
        "No DAQ Stop/Clear or output-zero command is present in this final frame"
    )


def test_finite_window_keeps_all_outcomes_without_promoting_whole_coverage(report):
    assert report["orders"] == 39916800
    assert report["joint_outcomes"] == len(report["all_outcomes"]) == 128
    assert report["original_members_with_registered_facets"] == 17
    assert report["original_diagrams_with_registered_facets"] == 533
    assert not report["whole_acquisition_closed"]
    assert not report["native_evidence_complete"]
    assert not report["counts_are_probabilities"]
    assert not report["hardware_executed"]
    assert not report["psp_or_network_used"]
    assert any(
        row["entered_outer_frame"]
        and not row["stop_after"]
        and row["outer_tcp_selector"] is False
        for row in report["joined_outcomes"]
    )
