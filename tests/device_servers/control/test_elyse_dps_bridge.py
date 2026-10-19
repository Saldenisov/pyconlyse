"""Cross-check DPS decoding against copied Supervision and ACQ inventories."""

import csv
from pathlib import Path

import pytest

from DeviceServers.control.elyse_acq.dps_bridge import (
    DPS_ACQ_EVENT_CASES,
    UnsupportedDpsIntent,
    first_asserted_dps_request,
    resolve_dps_request,
)


ROOT = Path(__file__).resolve().parents[3]
CROSSWALK = (
    ROOT
    / "Supervision/integration_analysis/SUP_ACQ_DPS_FIELD_CROSSWALK_2026-09-29.csv"
)


def _crosswalk_rows():
    with CROSSWALK.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_all_23_supervision_dps_requests_resolve_to_matching_acq_plans():
    rows = _crosswalk_rows()
    assert len(rows) == len(DPS_ACQ_EVENT_CASES) == 24
    assert [int(row["dps_bank_index"]) for row in rows] == list(range(24))

    for row in rows:
        index = int(row["dps_bank_index"])
        assert resolve_dps_request(index, False) is None
        if index == 22:
            assert row["static_status"] == "ORPHANED_DISPATCH_INTENT"
            assert DPS_ACQ_EVENT_CASES[index] is None
            with pytest.raises(UnsupportedDpsIntent):
                resolve_dps_request(index, True)
            continue
        plan = resolve_dps_request(index, True)
        assert plan is not None
        assert plan.legacy_event_case == int(row["acq_event_case"])
        assert row["static_status"] == "FIELD_AND_HANDLER_MATCH"
        assert row["supervision_event"]
        assert row["supervision_control"]


@pytest.mark.parametrize("index", [-1, 24, True, 0.0, "0"])
def test_invalid_dps_indices_fail_closed(index):
    with pytest.raises(ValueError):
        resolve_dps_request(index, True)


@pytest.mark.parametrize("asserted", [0, 1, None, "true"])
def test_dps_value_must_be_a_boolean(asserted):
    with pytest.raises(ValueError):
        resolve_dps_request(0, asserted)


def test_timeout_snapshot_uses_first_asserted_dps_field_only():
    flags = [False] * 24
    assert first_asserted_dps_request(flags) is None
    flags[23] = True
    flags[1] = True
    assert first_asserted_dps_request(flags).legacy_event_case == 4
    flags[0] = True
    assert first_asserted_dps_request(flags).legacy_event_case == 3


def test_orphaned_pt_wins_if_it_is_the_first_asserted_field():
    flags = [False] * 24
    flags[22] = True
    flags[23] = True
    with pytest.raises(UnsupportedDpsIntent):
        first_asserted_dps_request(flags)


def test_timeout_snapshot_requires_exact_boolean_procedure_slice():
    with pytest.raises(ValueError):
        first_asserted_dps_request([False] * 23)
    flags = [False] * 24
    flags[0] = 1
    with pytest.raises(ValueError):
        first_asserted_dps_request(flags)
