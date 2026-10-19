import math

import pytest

from DeviceServers.control.elyse_acq.contracts import RunState
from DeviceServers.control.elyse_acq.engine import ProcedureEngine
from DeviceServers.control.elyse_acq.plans import (
    ALL_MAGNET_ENABLES,
    C7_CONDITIONED_SETPOINTS,
    PROCEDURE_PLANS,
    get_plan,
)
from DeviceServers.control.elyse_acq.simulator import SimulatedHardware


class FastClock:
    def __init__(self):
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(float(seconds))


def make_engine():
    hardware = SimulatedHardware()
    clock = FastClock()
    return ProcedureEngine(hardware, clock=clock), hardware, clock


def test_catalog_covers_every_legacy_value_change_case_once():
    assert len(PROCEDURE_PLANS) == 23
    assert {plan.legacy_event_case for plan in PROCEDURE_PLANS.values()} == set(
        range(3, 26)
    )
    assert "magnets_power.pt" not in PROCEDURE_PLANS


def test_cooling_stop_preserves_active_low_pulse_order():
    engine, hardware, _clock = make_engine()

    result = engine.run_named("cooling.stop", "intent-cooling-stop")

    assert result.state == RunState.SUCCEEDED
    writes = [
        (item["target"], item["value"])
        for item in hardware.operations
        if item["operation"] == "write_digital"
    ]
    assert writes == [
        ("C3_OUT_DIO96.01", False),
        ("C3_OUT_DIO96.01", True),
        ("C3_OUT_DIO96.04", False),
        ("C3_OUT_DIO96.04", True),
    ]


def test_duplicate_intent_is_idempotent_and_does_not_repeat_writes():
    engine, hardware, _clock = make_engine()
    plan = get_plan("ht_power.start")

    first = engine.run(plan, "same-intent")
    operation_count = len(hardware.operations)
    second = engine.run(plan, "same-intent")

    assert first == second
    assert len(hardware.operations) == operation_count


def test_magnet_conditioning_reaches_exact_legacy_endpoints():
    engine, hardware, _clock = make_engine()

    result = engine.run_named("magnets_power.start", "intent-magnets-start")

    assert result.state == RunState.SUCCEEDED
    for target in C7_CONDITIONED_SETPOINTS:
        assert math.isclose(hardware.analog[target], 0.0, abs_tol=1e-10)
    for target in ALL_MAGNET_ENABLES:
        assert hardware.digital[target] is True

    sweep_entries = [
        entry
        for entry in engine.trace()
        if entry.operation == "analog_sweep" and entry.outcome == "SUCCEEDED"
    ]
    assert [entry.detail["iterations"] for entry in sweep_entries] == [
        160,
        320,
        320,
        160,
    ]
    assert [round(entry.detail["final"], 9) for entry in sweep_entries] == [
        16.0,
        -16.0,
        16.0,
        0.0,
    ]


def test_impulse_stop_preserves_counter_order_and_poll_bound():
    engine, hardware, _clock = make_engine()

    result = engine.run_named("modulator_impulse.stop", "intent-pulse-stop")

    assert result.state == RunState.SUCCEEDED
    stops = [
        item
        for item in hardware.operations
        if item["operation"] == "stop_counter_when_done"
    ]
    assert [item["target"] for item in stops] == [
        "C10_NI6602.ctr3",
        "C10_NI6602.ctr4",
    ]
    assert all(item["poll_interval_s"] == 0.001 for item in stops)
    assert all(item["max_loop_index"] == 40 for item in stops)


def test_unknown_procedure_fails_without_touching_hardware():
    engine, hardware, _clock = make_engine()

    with pytest.raises(KeyError):
        engine.run_named("magnets_power.pt", "orphaned-intent")

    assert hardware.operations == []
