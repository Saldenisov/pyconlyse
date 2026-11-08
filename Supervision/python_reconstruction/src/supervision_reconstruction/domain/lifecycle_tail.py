"""Passive main-VI cleanup/retired-code inventory; never a shutdown executor.

Outer frame 3 has three independent resource/error chains and resets local
stop=False. Outer frame 4, labelled POUBELLE, contains 15 formulas whose inputs
are all zero-wired and outputs have no consumers. Expressions are retained as
source text, not evaluated or promoted to live engineering-unit calibrations.
"""

from dataclasses import dataclass, field

SOURCE_VI_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
EVIDENCE_PATH = "analysis/lifecycle_tail_evidence_20261004.json"
EVIDENCE_SHA256 = "35DDAB1AECDE187101A9F2BF721DC10D4DC4AA6AE032B73CB3AFF1BA0B3118AA"


@dataclass(frozen=True)
class CleanupGroupPlan:
    resource_family: str
    visible_resource_count: int
    wire_order: tuple[str, ...]
    initial_error_boundary: str
    external_effects_blocked: bool = field(default=True, init=False)
    hardware_safe_state_established: bool = field(default=False, init=False)


CLEANUP_GROUPS = (
    CleanupGroupPlan(
        "PSP",
        13,
        ("Close Variable Connection for indexed references", "Simple Error Handler.vi"),
        "uninitialized error shift register; retained error is not assumed clear",
    ),
    CleanupGroupPlan(
        "IMAQ",
        9,
        (
            "IMAQ Dispose per indexed buffer, all=True",
            "IMAQ Close.vi for supplied session",
            "General Error Handler.vi",
        ),
        "explicit no-error constant initializes disposal-loop shift register",
    ),
    CleanupGroupPlan(
        "CmdLib",
        1,
        (
            "AbortMotion.vi for supplied address",
            "Shutdown.vi",
            "General Error Handler.vi",
        ),
        "AbortMotion error input unwired; callee default/error behavior unresolved",
    ),
)


@dataclass(frozen=True)
class RetiredFormulaPlan:
    node_uid: int
    expression: str
    all_inputs_zero_wired: bool = field(default=True, init=False)
    output_has_consumers: bool = field(default=False, init=False)
    live_calibration: bool = field(default=False, init=False)


RETIRED_FORMULAS = tuple(
    RetiredFormulaPlan(uid, expression)
    for uid, expression in (
        (36464, "y=0.18032*x*x + 0.40507*x + 0.35931;"),
        (36496, "y=(x+0.073)/0.52;"),
        (36506, "y=(1.07*(x+0.099)/0.516)*2;"),
        (36518, "y=1.07*(x+0.067)/0.522;"),
        (36687, "y=(x+0.081)/0.522;"),
        (37244, "y=1.07*(x+0.061)/0.519;"),
        (37267, "y=(x+0.081)/0.522;"),
        (37536, "y=436.3+(40*(a-b)/c);"),
        (37971, "y=(x+0.081)/0.522;"),
        (38174, "y=382.5+(40*(b-a)/c);"),
        (39117, "y=(x+0.081)/0.522;"),
        (39348, "y=(1.1309*x**3)-(5.746*x**2)-40.368*x+102.28;"),
        (42243, "y=(x+0.073)/0.52;"),
        (42702, "y=(x+0.073)/0.52;"),
        (43269, "y=(x+0.073)/0.52;"),
    )
)


@dataclass(frozen=True)
class LifecycleTailPlan:
    cleanup_groups: tuple[CleanupGroupPlan, ...] = CLEANUP_GROUPS
    retired_formulas: tuple[RetiredFormulaPlan, ...] = RETIRED_FORMULAS
    stop_local_reset_value: bool = field(default=False, init=False)
    resource_groups_have_total_order: bool = field(default=False, init=False)
    all_stop_paths_reach_cleanup_proven: bool = field(default=False, init=False)
    hardware_safe_state_established: bool = field(default=False, init=False)


def build_lifecycle_tail_plan() -> LifecycleTailPlan:
    """Return reviewed evidence; do not close resources or evaluate formulas."""

    return LifecycleTailPlan()
