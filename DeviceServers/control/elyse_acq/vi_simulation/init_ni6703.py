"""NI6703 configuration; deliberately retains discarded/unaccumulated errors.

The +/-10 V limits configure channel ranges, not physical output voltages.
All channel error inputs are UNWIRED; Create Task errors are discarded.
"""

from .boundary import (
    ErrorCluster,
    InitializerResult,
    ScriptedBoundary,
    SourceVi,
    require_boundary,
    require_error,
)

SOURCE = SourceVi(
    "1_ACQ_INIT_NI6703.vi",
    "2F9489A0F1E04DF0F052A8F25FFF8CA3AD813D27A112B989C5CB483C792B6205",
)
# Device, frame diagram, channel-loop diagram, Create Task UID, channel UID.
FRAMES = (
    (6, "1241", "773", "2471", "847"),
    (7, "2744", "4666", "4587", "4725"),
    (8, "1824", "1976", "1841", "2070"),
    (9, "355", "862", "400", "1429"),
)


def initialize(
    boundary: ScriptedBoundary, *, error_in: ErrorCluster
) -> InitializerResult:
    require_boundary(boundary)
    require_error(error_in)
    offset, error, tasks = len(boundary.calls), error_in, []
    for device, frame, body, create_uid, channel_uid in FRAMES:
        created = boundary.invoke(
            SOURCE,
            create_uid,
            frame,
            "create_task",
            error_in=error,
            name=f"C{device}_NI6703",
            auto_cleanup=True,
        )
        for i in range(10):
            channel = boundary.invoke(
                SOURCE,
                channel_uid,
                body,
                "create_ao_voltage_channel",
                iteration=i,
                task_in=created.task,
                physical_channel=f"{device}/ao{i}",
                minimum=-10.0,
                maximum=10.0,
                units_code=0x286C,
                terminal_configuration_code=0xFFFFFFFF,
                polymorphic_selector="20",
            )
        # Non-indexed loop outputs take the last iteration, not all errors.
        tasks.append(channel.task)
        error = channel.error
    return InitializerResult(
        SOURCE, tuple(tasks), error, error, boundary.calls[offset:]
    )
