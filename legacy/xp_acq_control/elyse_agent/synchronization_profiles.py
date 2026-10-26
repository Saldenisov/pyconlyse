"""Source-pinned counter settings, not measurements. Python 3.4; cold import."""
import copy

SUPERVISION_ROOT_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"
SUPERVISION_INIT_SHA256 = "CE8BCA30E727C9B8C1EE9681263FBCE1D60247C2DBECDD0B73A37A385C88104F"
SUPERVISION_INIT_XML_SHA256 = "3E4A29FF2DBBD54CD79EF3AF6123E5A0A68C8B035AFC585443DAE93BA8E01378"
SUPERVISION_ROOT_XML_SHA256 = "F629730C43DBF5EDA3C4E8BD1B22A89EAD90813E5770275A5C80CC28717665D7"
SUPERVISION_FRAMES = ("9978", "8666", "6900", "9448", "7229", "6943", "9487", "7856")
SUPERVISION_CHANNEL_NODES = ("10044", "8675", "8099", "9587", "7277", "10381", "10211", "7904")
SUPERVISION_START_NODES = ("9106", "9811", "8476", "12241", "8073", "10846", "11803", "10543")

_ROWS = (
    ("laser_hf", 7, 7), ("imac", 43520, 2000), ("laser", 40166, 200),
    ("oscilloscope_1", 43500, 200), ("oscilloscope_2", 43500, 2000),
    ("detection_1", 10000, 10000), ("detection_2", 6, 200),
    ("machine", 43500, 2000),
)


def supervision_counter_profile():
    """All eight source frames start. External PFI11 rate is not measured."""
    return [dict(output=i, label=row[0], physical_channel="Dev1/ctr{0}".format(i),
        task_name="SUPCOUNT{0}".format(i), initial_delay_ticks=0,
        low_ticks=row[1], high_ticks=row[2], trigger="/Dev1/PFI10",
        trigger_edge="rising", timebase="/Dev1/PFI11",
        timebase_active_edge="rising", idle_state="low", retriggerable=True,
        finite_samples=1, started_on_init=True, source_frame=SUPERVISION_FRAMES[i],
        physical_timebase_hz=None, source_tick_conversion_per_us=20)
        for i, row in enumerate(_ROWS)]


def source_timing_pairs(profile):
    """Nominal UI delay/width from Low/High ticks; not InitialDelay."""
    return tuple(value / 20.0 for row in profile
                 for value in (row["low_ticks"], row["high_ticks"]))


def synchronization_memory(profile, running, uncertain=()):
    return dict(owner="supervision", card="NI6602", device="Dev1",
        timing_pairs_us=source_timing_pairs(profile),
        counter_ticks=copy.deepcopy(profile), running_counters=list(running),
        uncertain_counters=list(uncertain), physical_readback=False,
        interpretation="Last returned software timing writes; external PFI11 clock not measured",
        source_vi_sha256=SUPERVISION_INIT_SHA256)
