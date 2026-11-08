"""All eight NI6602 configuration frames, with six abstract Start Task calls."""

from .boundary import (
    ErrorCluster,
    InitializerResult,
    ScriptedBoundary,
    SourceVi,
    require_boundary,
    require_error,
)

SOURCE = SourceVi(
    "1_ACQ_INIT_NI6602.vi",
    "3341C22226FA587F488C78027FF60B9E3E990462763C6F1C7E322C3634994442",
)
# Diagram, Create, channel, trigger, retrigger properties, channel properties,
# Timing, optional Start Task. UIDs are from the original saved diagram.
FRAMES = (
    ("9978", "7021", "10044", "10247", "7408", "8977", "9021", "9106"),
    ("8666", "9650", "8675", "8736", "9701", "9723", "9751", "9811"),
    ("6900", "8238", "8099", "8161", "8366", "8388", "8416", "8476"),
    ("9448", "11266", "9587", "11181", "12062", "12149", "12177", None),
    ("7229", "7740", "7277", "7519", "7903", "7982", "8010", None),
    ("6943", "10673", "10381", "10485", "10724", "10749", "10778", "10846"),
    ("9487", "11449", "10211", "11389", "11613", "11687", "11743", "11803"),
    ("7856", "11318", "7904", "8260", "8896", "10259", "10365", "10543"),
)
HIGH_TICKS = (20, 3620000, 200, 60, 60, 2000, 56, 100000)
LOW_TICKS = (31, 200, 43558, 43658, 43500, 101600, 43500, 20)
TRIGGER_PFI = (34, 34, 30, 34, 30, 30, 30, 10)


def initialize(
    boundary: ScriptedBoundary, *, error_in: ErrorCluster
) -> InitializerResult:
    require_boundary(boundary)
    require_error(error_in)
    offset, error, tasks = len(boundary.calls), error_in, []
    for i, (
        frame,
        create,
        channel,
        trigger,
        retrigger,
        props,
        timing,
        start,
    ) in enumerate(FRAMES):
        result = boundary.invoke(
            SOURCE,
            create,
            frame,
            "create_task",
            error_in=error,
            name=f"OUT{i}",
            auto_cleanup=True,
        )

        def next_call(uid, operation, **arguments):
            return boundary.invoke(
                SOURCE,
                uid,
                frame,
                operation,
                task_in=result.task,
                error_in=result.error,
                **arguments,
            )

        result = next_call(
            channel,
            "create_co_pulse_ticks_channel",
            physical_channel=f"10/ctr{i}",
            timebase_source="/10/PFI11",
            initial_delay=0,
            high_ticks=HIGH_TICKS[i],
            low_ticks=LOW_TICKS[i],
            idle_state_code=0x27E6,
            polymorphic_selector="33",
        )
        result = next_call(
            trigger,
            "configure_start_trigger",
            source=f"/10/PFI{TRIGGER_PFI[i]}",
            edge_code=0x27BB if i == 7 else 0x2828,
            polymorphic_selector="03",
        )
        result = next_call(
            retrigger, "set_start_retriggerable", retriggerable=True, property_code=6415
        )
        result = next_call(
            props,
            "set_counter_channel_properties",
            idle_state_code=0x27E6,
            timebase_edge_code=0x2828,
            idle_property_code=4464,
            timebase_edge_property_code=833,
        )
        result = next_call(
            timing,
            "configure_implicit_timing",
            sample_mode_code=0x27C2,
            samples_per_channel=1,
            polymorphic_selector="06",
        )
        if start is not None:
            result = next_call(start, "start_task")
        tasks.append(result.task)
        error = result.error
    return InitializerResult(
        SOURCE, tuple(tasks), error, error, boundary.calls[offset:]
    )
