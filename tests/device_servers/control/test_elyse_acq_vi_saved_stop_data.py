"""Persisted source snapshots are not live reads or restart resets."""

import pytest
from DeviceServers.control.elyse_acq.vi_simulation.saved_stop_data import (
    saved_source_stop_snapshot,
)
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import (
    StopMemory,
    project_stop_reset,
)


def test_explicit_source_snapshot_has_four_persisted_false_values():
    assert saved_source_stop_snapshot() == StopMemory(False, False, False, False)


def test_each_snapshot_is_fresh_and_immutable():
    first = saved_source_stop_snapshot()
    second = saved_source_stop_snapshot()
    assert first is not second
    with pytest.raises(AttributeError):
        first.stop = True


def test_postinit_applied_to_explicit_source_snapshot_remains_false():
    after = project_stop_reset("post_init", saved_source_stop_snapshot())
    assert after.independent_assignments == ((45, False), (46, False))
    assert after.after == StopMemory(False, False, False, False)


def test_persisted_source_data_does_not_reset_stale_restart_memory():
    stale = StopMemory(True, True, True, True)
    saved_source_stop_snapshot()
    after = project_stop_reset("post_init", stale)
    assert after.after == StopMemory(True, False, False, True)
    assert stale == StopMemory(True, True, True, True)


def test_cleanup_still_clears_only_stop30():
    after = project_stop_reset("final_cleanup", StopMemory(True, True, True, True))
    assert after.independent_assignments == ((30, False),)
    assert after.after == StopMemory(False, True, True, True)


def test_initializer_still_requires_explicit_runtime_memory():
    with pytest.raises(TypeError, match="explicit StopMemory"):
        project_stop_reset("post_init", None)
