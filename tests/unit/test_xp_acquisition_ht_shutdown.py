"""Collect synthetic HT shutdown tests under deny-network unit lane."""

from legacy.xp_acq_agent.tests.test_acquisition_ht_shutdown import (
    ExtendedStopBackendTests as ExtendedStopBackendTests,
)
from legacy.xp_acq_agent.tests.test_acquisition_ht_shutdown import (
    HTShutdownTests as HTShutdownTests,
)


def test_extended_package_is_explicit_cold_and_feedback_permission_is_false(tmp_path):
    import hashlib
    import json

    from tools.package_acquisition_runtime import build

    folder = tmp_path / "ht_extended"
    build(folder, control_profile="extended_ht_stop")
    config = json.loads((folder / "config.acquisition.json").read_text("utf-8"))
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    assert (
        config["control_profile"] == manifest["control_profile"] == "extended_ht_stop"
    )
    assert config["ht_shutdown"] == dict(
        feedback_verified=False, zero_tolerance_kv=0.0, timeout_seconds=10.0
    )
    assert config["focal_stop"]["resources_verified"] is False
    assert manifest["auto_initialize"] is False
    assert manifest["general_stop_includes_ht_supply_stop"] is True
    assert manifest["ht_feedback_commissioning_required"] is True
    assert (
        manifest["general_stop_scope"] == "python_8kv_ht_preamble_then_source_event_6"
    )
    assert any(
        r["path"] == "elyse_agent/acquisition_ht_shutdown.py" for r in manifest["files"]
    )
    for record in manifest["files"]:
        assert (
            hashlib.sha256((folder / record["path"]).read_bytes()).hexdigest()
            == record["sha256"]
        )


def test_extension_stop_parts_match_reviewed_source_event21_and_event24():
    from DeviceServers.control.elyse_acq.vi_simulation.procedure_sequences import (
        PROCEDURES,
    )
    from legacy.xp_acq_agent.elyse_agent.acquisition_ht_shutdown import (
        HT_HANDOFF_KV,
        HT_SUPPLY_STOP_DPS,
        HT_SUPPLY_STOP_EPS,
        HT_SUPPLY_STOP_FRAMES,
        PULSE_STOP_DPS,
        PULSE_STOP_EPS,
        PULSE_STOP_TASKS,
    )

    # validate_acq_linear_procedures pins these exact complete graphs to the
    # immutable original export. Match runnable constants to that projection.
    assert tuple(row[1] for row in HT_SUPPLY_STOP_FRAMES) == tuple(
        uid for uid, _ in PROCEDURES[21]
    )
    for (_index, _uid, assignments, wait), (_source_uid, effects) in zip(
        HT_SUPPLY_STOP_FRAMES, PROCEDURES[21]
    ):
        source_c4 = tuple(
            pair for e in effects if e[0] == "write" and e[1] == 15 for pair in e[2]
        )
        assert assignments == source_c4
        assert wait == sum(e[1] for e in effects if e[0] == "wait")
    effects21 = [e for _uid, effects in PROCEDURES[21] for e in effects]
    assert dict(HT_SUPPLY_STOP_EPS) == dict(
        next(e[2] for e in effects21 if e[:2] == ("write", 44))
    )
    assert dict(HT_SUPPLY_STOP_DPS) == dict(
        next(e[2] for e in effects21 if e[:2] == ("write", 36))
    )
    effects24 = [e for _uid, effects in PROCEDURES[24] for e in effects]
    assert PULSE_STOP_TASKS == tuple(
        e[2] for e in effects24 if e[0] == "counter_poll_stop_clear"
    )
    assert all(
        e[1] == 21 and e[4:] == (40, 1)
        for e in effects24
        if e[0] == "counter_poll_stop_clear"
    )
    assert dict(PULSE_STOP_EPS) == dict(
        next(e[2] for e in effects24 if e[:2] == ("write", 44))
    )
    assert dict(PULSE_STOP_DPS) == dict(
        next(e[2] for e in effects24 if e[:2] == ("write", 36))
    )
    assert HT_HANDOFF_KV == 8.0  # operator-requested extension, NOT source6.6


def test_ht_active_low_interpretation_matches_pinned_supervision_palette(monkeypatch):
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "tools"))
    from tools.export_sup_control_panels import build_panel

    panel = build_panel()
    indicator = panel["pages"]["ht"]["fields"]["27"]
    assert indicator["label"] == "HT en marche"
    assert indicator["control_uid"] == "51485"
    assert indicator["false_color"] == "#00C82D"
    assert indicator["true_color"] == "#B3B3B3"
    display_file = root / "web/frontend/src/elyseLiveDisplayMap.json"
    rules = json.loads(display_file.read_text("utf-8"))["rules"]
    rule = next(r for r in rules if r["id"] == "ht:27")
    assert (rule["bank"], rule["index"], rule["transform"]) == (
        "C4_IN_DIO96", 48, "identity"
    )
