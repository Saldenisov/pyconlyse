"""Translation of 1_ACQ_INIT_DIO96.vi at abstract DAQmx boundaries."""

from .boundary import (
    ErrorCluster,
    InitializerResult,
    ScriptedBoundary,
    SourceVi,
    require_boundary,
    require_error,
)

SOURCE = SourceVi(
    "1_ACQ_INIT_DIO96.vi",
    "F308D6A6E995A5C63D8EA57CC1FAB523AEA7DD3712FDD707C0B232B73AC308CA",
)
# Task field order is DI C3/C4/C5, then DO C3/C4/C5.
TASKS = (
    ("2471", "1345", "C3_IN_DIO", "3/port0:6", "create_di_channel", "23"),
    ("1134", "579", "C4_IN_DIO", "4/port0:7", "create_di_channel", "23"),
    ("1456", "912", "C5_IN_DIO", "5/port0:6", "create_di_channel", "23"),
    ("1801", "1740", "C3_OUT_DIO", "3/port7:11", "create_do_channel", "24"),
    ("1953", "1886", "C4_OUT_DIO", "4/port8:11", "create_do_channel", "24"),
    ("2119", "2047", "C5_OUT_DIO", "5/port7:11", "create_do_channel", "24"),
)


def initialize(
    boundary: ScriptedBoundary, *, error_in: ErrorCluster
) -> InitializerResult:
    require_boundary(boundary)
    require_error(error_in)
    offset, error, tasks = len(boundary.calls), error_in, []
    for create_uid, channel_uid, name, physical, operation, selector in TASKS:
        created = boundary.invoke(
            SOURCE,
            create_uid,
            "3",
            "create_task",
            error_in=error,
            name=name,
            auto_cleanup=True,
        )
        channel = boundary.invoke(
            SOURCE,
            channel_uid,
            "3",
            operation,
            task_in=created.task,
            error_in=created.error,
            physical_channel=physical,
            polymorphic_selector=selector,
        )
        tasks.append(channel.task)
        error = channel.error
    return InitializerResult(
        SOURCE, tuple(tasks), error, error, boundary.calls[offset:]
    )
