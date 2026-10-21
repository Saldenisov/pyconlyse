"""Declarative procedures transcribed from ACQUISITION.llb event cases 3..25."""

from __future__ import annotations

from typing import Dict, Iterable, Tuple

from .contracts import Operation, ProcedurePlan, Step


def c3_do(index: int) -> str:
    return f"C3_OUT_DIO96.{index:02d}"


def c4_do(index: int) -> str:
    return f"C4_OUT_DIO96.{index:02d}"


def c6_ao(index: int) -> str:
    return f"C6NI6703.{index:02d}"


def c7_ao(index: int) -> str:
    return f"C7NI6703.{index:02d}"


def wait(seconds: float, label: str = "wait") -> Step:
    return Step(Operation.WAIT, label, duration_s=seconds)


def digital(target: str, value: bool, label: str) -> Step:
    return Step(Operation.WRITE_DIGITAL, label, targets=(target,), value=value)


def digital_group(targets: Iterable[str], value: bool, label: str) -> Step:
    return Step(
        Operation.WRITE_DIGITAL_GROUP,
        label,
        targets=tuple(targets),
        value=value,
    )


def analog_zero(targets: Iterable[str], label: str) -> Step:
    return Step(
        Operation.WRITE_ANALOG_GROUP,
        label,
        targets=tuple(targets),
        value=0.0,
    )


def pulse(
    target: str,
    *,
    active: bool,
    idle: bool,
    duration_s: float,
    label: str,
) -> Tuple[Step, ...]:
    return (
        digital(target, active, f"{label}: assert"),
        wait(duration_s, f"{label}: hold"),
        digital(target, idle, f"{label}: restore"),
    )


def focal(enabled: bool, label: str) -> Step:
    return Step(Operation.SET_FOCAL_SUPPLIES, label, value=enabled)


def sweep(
    targets: Iterable[str],
    *,
    initial: float,
    delta: float,
    iterations: int,
    period_s: float,
    label: str,
) -> Step:
    return Step(
        Operation.ANALOG_SWEEP,
        label,
        targets=tuple(targets),
        metadata={
            "initial": initial,
            "delta": delta,
            "iterations": iterations,
            "period_s": period_s,
        },
    )


def plan(case: int, name: str, description: str, *steps: Step) -> ProcedurePlan:
    return ProcedurePlan(name, tuple(steps), case, description)


RESET_LOW_LEVEL = c4_do(2)

C6_MAGNET_SETPOINTS = tuple(c6_ao(i) for i in (0, 1, 2, 3, 4, 5, 6, 7, 9))
C7_MAGNET_SETPOINTS = tuple(c7_ao(i) for i in (0, 1, 3, 4, 5, 6, 7, 8, 9))
C7_CONDITIONED_SETPOINTS = tuple(c7_ao(i) for i in (0, 1, 3, 4, 6, 7, 8, 9))
ALL_MAGNET_SETPOINTS = C6_MAGNET_SETPOINTS + C7_MAGNET_SETPOINTS
ZERO_V_SETPOINTS = C6_MAGNET_SETPOINTS + C7_CONDITIONED_SETPOINTS

MAGNET_ENABLE_GROUP_1 = tuple(c3_do(i) for i in (9, 11, 15, 17, 21, 23))
MAGNET_ENABLE_GROUP_2 = tuple(c3_do(i) for i in (27, 29))
MAGNET_ENABLE_GROUP_3 = tuple(c3_do(i) for i in range(25, 40) if i not in (26, 27, 28, 29, 30))
ALL_MAGNET_ENABLES = (
    MAGNET_ENABLE_GROUP_1 + MAGNET_ENABLE_GROUP_2 + MAGNET_ENABLE_GROUP_3
)


_plans = [
    plan(
        3,
        "cooling.start",
        "Start gun and section cooling, then low-level modulator and reset.",
        *pulse(c3_do(0), active=True, idle=False, duration_s=1.0, label="gun cooling start"),
        wait(0.8, "gun-to-section delay"),
        *pulse(c3_do(3), active=True, idle=False, duration_s=1.0, label="section cooling start"),
        *pulse(c4_do(0), active=True, idle=False, duration_s=1.0, label="low-level modulator start"),
        wait(0.5, "pre-reset delay"),
        *pulse(RESET_LOW_LEVEL, active=True, idle=False, duration_s=1.0, label="low-level reset"),
        wait(5.0, "legacy completion dwell"),
    ),
    plan(
        4,
        "cooling.stop",
        "Stop gun and section cooling with active-low pulses.",
        *pulse(c3_do(1), active=False, idle=True, duration_s=0.150, label="gun cooling stop"),
        wait(0.4, "gun-to-section delay"),
        *pulse(c3_do(4), active=False, idle=True, duration_s=0.150, label="section cooling stop"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        5,
        "modulator.general.start",
        "Start low-level modulator and apply the legacy double reset.",
        *pulse(c4_do(0), active=True, idle=False, duration_s=0.150, label="low-level start"),
        wait(1.0, "pre-reset delay"),
        *pulse(RESET_LOW_LEVEL, active=True, idle=False, duration_s=0.150, label="low-level reset 1"),
        wait(1.0, "inter-reset delay"),
        *pulse(RESET_LOW_LEVEL, active=True, idle=False, duration_s=0.150, label="low-level reset 2"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        6,
        "modulator.general.stop",
        "Ordered focal, relay, premagnetization, heating, and low-level stop.",
        focal(False, "disable three focal supplies"),
        wait(0.5, "focal supply settle"),
        *pulse(c4_do(8), active=False, idle=True, duration_s=0.150, label="klystron focal stop"),
        wait(1.0, "focal-to-relay delay"),
        *pulse(c4_do(17), active=False, idle=True, duration_s=0.150, label="HT relay stop"),
        wait(1.0, "relay-to-prema delay"),
        *pulse(c4_do(6), active=False, idle=True, duration_s=0.150, label="premagnetization stop"),
        wait(1.0, "prema-to-heating delay"),
        *pulse(c4_do(4), active=False, idle=True, duration_s=0.150, label="heating stop"),
        wait(2.0, "heating-to-low-level delay"),
        *pulse(c4_do(1), active=False, idle=True, duration_s=0.150, label="low-level stop"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        7,
        "modulator.heating.stop",
        "Stop modulator heating.",
        *pulse(c4_do(4), active=False, idle=True, duration_s=0.150, label="heating stop"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        8,
        "modulator.prema.stop",
        "Stop premagnetization.",
        *pulse(c4_do(6), active=False, idle=True, duration_s=0.150, label="premagnetization stop"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        9,
        "modulator.relay_ht.stop",
        "Stop modulator HT relay 1.",
        *pulse(c4_do(17), active=False, idle=True, duration_s=0.150, label="HT relay stop"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        10,
        "modulator.focale.stop",
        "Disable focal supplies and stop klystron focal.",
        focal(False, "disable three focal supplies"),
        wait(0.5, "focal supply settle"),
        *pulse(c4_do(8), active=False, idle=True, duration_s=0.150, label="klystron focal stop"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        11,
        "modulator.reset",
        "Pulse the low-level modulator reset.",
        *pulse(RESET_LOW_LEVEL, active=True, idle=False, duration_s=0.150, label="low-level reset"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        12,
        "modulator.heating.start",
        "Start heating, wait, then reset low-level modulator.",
        *pulse(c4_do(3), active=True, idle=False, duration_s=0.150, label="heating start"),
        wait(3.0, "heating settle"),
        *pulse(RESET_LOW_LEVEL, active=True, idle=False, duration_s=0.150, label="low-level reset"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        13,
        "modulator.prema.start",
        "Start premagnetization and reset low-level modulator.",
        *pulse(c4_do(5), active=True, idle=False, duration_s=0.150, label="premagnetization start"),
        wait(0.5, "pre-reset delay"),
        *pulse(RESET_LOW_LEVEL, active=True, idle=False, duration_s=0.150, label="low-level reset"),
        wait(0.250, "post-reset delay"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        14,
        "modulator.relay_ht.start",
        "Start HT relay 1 and reset low-level modulator.",
        *pulse(c4_do(16), active=True, idle=False, duration_s=0.150, label="HT relay start"),
        wait(0.5, "pre-reset delay"),
        *pulse(RESET_LOW_LEVEL, active=True, idle=False, duration_s=0.150, label="low-level reset"),
        wait(0.250, "post-reset delay"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        15,
        "modulator.focale.start",
        "Start klystron focal, enable three focal supplies, and reset.",
        *pulse(c4_do(7), active=True, idle=False, duration_s=0.150, label="klystron focal start"),
        wait(29.0, "klystron focal warm-up"),
        focal(True, "enable three focal supplies"),
        wait(1.5, "focal supply settle"),
        *pulse(RESET_LOW_LEVEL, active=True, idle=False, duration_s=0.150, label="low-level reset"),
        wait(0.250, "post-reset delay"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        16,
        "magnets_power.start",
        "Enable magnet supplies and run the four-sweep conditioning waveform.",
        digital_group(MAGNET_ENABLE_GROUP_1, True, "enable triplet and quadrupole supplies"),
        wait(0.5, "magnet enable group delay 1"),
        digital_group(MAGNET_ENABLE_GROUP_2, True, "enable dipole supplies"),
        wait(0.5, "magnet enable group delay 2"),
        digital_group(MAGNET_ENABLE_GROUP_3, True, "enable focal and steering supplies"),
        analog_zero(ALL_MAGNET_SETPOINTS, "initialize all magnet setpoints to zero"),
        sweep(C7_CONDITIONED_SETPOINTS, initial=0.0, delta=0.1, iterations=160, period_s=0.1, label="condition magnets 0 to +16"),
        wait(20.0, "conditioning dwell at +16"),
        sweep(C7_CONDITIONED_SETPOINTS, initial=16.0, delta=-0.1, iterations=320, period_s=0.1, label="condition magnets +16 to -16"),
        wait(20.0, "conditioning dwell at -16"),
        sweep(C7_CONDITIONED_SETPOINTS, initial=-16.0, delta=0.1, iterations=320, period_s=0.1, label="condition magnets -16 to +16"),
        wait(20.0, "conditioning dwell at +16"),
        sweep(C7_CONDITIONED_SETPOINTS, initial=16.0, delta=-0.1, iterations=160, period_s=0.1, label="condition magnets +16 to 0"),
        wait(0.2, "legacy completion dwell"),
    ),
    plan(
        17,
        "magnets_power.stop",
        "Zero setpoints, then disable every magnet supply output.",
        analog_zero(ALL_MAGNET_SETPOINTS, "zero all magnet setpoints"),
        wait(1.0, "zero-setpoint settle"),
        digital_group(ALL_MAGNET_ENABLES, False, "disable all magnet supplies"),
        wait(0.2, "legacy completion dwell"),
    ),
    plan(
        18,
        "hf_att_deph.start",
        "Latch attenuator/dephaser power on.",
        digital(c4_do(29), True, "enable attenuator/dephaser power"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        19,
        "hf_att_deph.stop",
        "Latch attenuator/dephaser power off.",
        digital(c4_do(29), False, "disable attenuator/dephaser power"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        20,
        "ht_power.start",
        "Start the HT supply.",
        *pulse(c4_do(18), active=True, idle=False, duration_s=0.150, label="HT supply start"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        21,
        "ht_power.stop",
        "Stop the HT supply.",
        *pulse(c4_do(19), active=False, idle=True, duration_s=0.150, label="HT supply stop"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        22,
        "ht_power.reset",
        "Reset the HT supply.",
        *pulse(c4_do(20), active=True, idle=False, duration_s=0.150, label="HT supply reset"),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        23,
        "modulator_impulse.start",
        "Start NI6602 modulator and HF counters.",
        Step(
            Operation.START_COUNTERS,
            "start modulator and HF counters",
            targets=("C10_NI6602.ctr3", "C10_NI6602.ctr4"),
        ),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        24,
        "modulator_impulse.stop",
        "Wait for pulse completion, then stop NI6602 modulator and HF counters.",
        Step(
            Operation.STOP_COUNTER_WHEN_DONE,
            "stop modulator counter",
            targets=("C10_NI6602.ctr3",),
            metadata={"poll_interval_s": 0.001, "max_loop_index": 40},
        ),
        Step(
            Operation.STOP_COUNTER_WHEN_DONE,
            "stop HF counter",
            targets=("C10_NI6602.ctr4",),
            metadata={"poll_interval_s": 0.001, "max_loop_index": 40},
        ),
        wait(0.1, "legacy completion dwell"),
    ),
    plan(
        25,
        "magnets_power.zero_v",
        "Zero the legacy C6/C7 setpoint subset without disabling supplies.",
        analog_zero(ZERO_V_SETPOINTS, "zero selected magnet setpoints"),
        wait(1.0, "zero-setpoint settle"),
        wait(0.2, "legacy completion dwell"),
    ),
]


PROCEDURE_PLANS: Dict[str, ProcedurePlan] = {item.name: item for item in _plans}

if len(PROCEDURE_PLANS) != 23:
    raise RuntimeError("expected exactly 23 legacy Value Change procedure plans")
if {item.legacy_event_case for item in _plans} != set(range(3, 26)):
    raise RuntimeError("legacy event cases 3..25 must be represented exactly once")


def get_plan(name: str) -> ProcedurePlan:
    try:
        return PROCEDURE_PLANS[str(name).strip()]
    except KeyError as exc:
        raise KeyError(f"unknown ELYSE ACQ procedure: {name}") from exc

