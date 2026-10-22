"""Python 3.4 controller procedures. Import performs no I/O.

General start transcribes original ACQ event 5, diagram34531/sequence34597.
General stop transcribes event 6, diagram25330/sequence26556, with explicit
Python failure reporting instead of suppressing the focal helper error.
Explicit bank commits replace LabVIEW's concurrent local-value writer; nominal
waits are preserved, but physical pulse-width equivalence is not claimed.
"""
import time


SOURCE_ARCHIVE_SHA256 = "6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527"
GENERAL_START_FRAMES = (
    # frame, source diagram, C4 assignments, nominal wait milliseconds
    (0, "34617", ((0, True),), 150),
    (1, "34859", ((0, False),), 0),
    (2, "35005", (), 1000),
    (3, "35043", ((2, True),), 150),
    (4, "25037", ((2, False),), 0),
    (5, "29225", (), 1000),
    (6, "31989", ((2, True),), 150),
    (7, "33223", ((2, False),), 0),
    (8, "35413", (), 0),
    (9, "35570", (), 100),
)
GENERAL_START_EPS = ((11, False), (8, True), (6, False))
GENERAL_START_DPS = ((2, False),)

# Original event 6, diagram25330/sequence26556. Not acquisition task cleanup.
GENERAL_STOP_FRAMES = (
    (0, "26598", (), 150),  # parallel with Focales OFF -> 500 ms
    (1, "55133", ((8, False),), 150),
    (2, "31199", ((8, True),), 0),
    (3, "27271", (), 1000),
    (4, "33229", ((17, False),), 150),
    (5, "35308", ((17, True),), 0),
    (6, "35199", (), 1000),
    (7, "36873", ((6, False),), 150),
    (8, "23583", ((6, True),), 0),
    (9, "23519", (), 1000),
    (10, "25035", ((4, False),), 150),
    (11, "29452", ((4, True),), 0),
    (12, "23628", (), 2000),
    (13, "29980", ((1, False),), 150),
    (14, "32864", ((1, True),), 0),
    (15, "28661", (), 0),
    (16, "35146", (), 100),
)
GENERAL_STOP_EPS = ((8, False), (14, False), (20, False), (26, False),
                    (32, False), (9, False), (11, True), (17, True),
                    (23, True), (29, True), (35, True))
GENERAL_STOP_DPS = ((3, False),)

# Explicit commissioning subset, NOT a substitute for the full event-6 stop.
# Only the low-level General stop pulse and its own software status literals
# are selected. Chroma, focal, heating, PREMA and HT stages are not executed.
GENERAL_ONLY_STOP_FRAMES = GENERAL_STOP_FRAMES[13:]
GENERAL_ONLY_STOP_EPS = tuple(row for row in GENERAL_STOP_EPS if row[0] in (8, 9, 11))
GENERAL_ONLY_STOP_DPS = GENERAL_STOP_DPS


class ProcedureCancelled(Exception):
    pass


class GeneralStopError(Exception):
    """Stop was attempted through its last stage, but not fully successful."""
    def __init__(self, failures):
        self.failures = tuple(failures)
        Exception.__init__(self, "; ".join(self.failures))


def execute_general_only_stop(commit_c4, assign_status, wait_seconds,
                              frame_observer=None, operator_confirmed=False,
                              execution_wait=None):
    """General-only test: event-6 frames 13..16, restricted status subset.

    Other stages must already be OFF. This function does not stop them, cannot
    confirm physical OFF, and is not an emergency/installation shutdown.
    A failed assertion/release/wait is reported; release is retried in finally.
    Unlike the legacy full sequence, do not assign software OK after a failure.
    No Chroma callback is accepted by this API.
    """
    if operator_confirmed is not True:
        raise ValueError("Explicit General-only Arret operator confirmation required")
    if execution_wait is not None and not callable(execution_wait):
        raise ValueError("Execution wait must be callable or None")
    failures, uncertain = [], False

    def attempt(label, callback, *args):
        try:
            callback(*args)
            return True
        except Exception as error:
            failures.append(label + ": " + type(error).__name__ + ": " + str(error))
            return False

    try:
        for index, source_uid, assignments, milliseconds in GENERAL_ONLY_STOP_FRAMES:
            if frame_observer is not None:
                attempt("frame observer", frame_observer, index, source_uid)
            for line, value in assignments:
                if not value:
                    uncertain = True
                if attempt("C4[{0}]={1}".format(line, value), commit_c4, line, value) and value:
                    uncertain = False
            if index == 15 and not failures:
                attempt("General-only EPS/DPS assignments", assign_status,
                        GENERAL_ONLY_STOP_EPS, GENERAL_ONLY_STOP_DPS)
            if milliseconds:
                if execution_wait is None:
                    attempt("frame {0} wait".format(index), wait_seconds, milliseconds / 1000.0)
                else:
                    attempt("frame {0} wait".format(index), execution_wait,
                            milliseconds / 1000.0, not uncertain,
                            dict(operation="modulator.general.stop", phase="source_wait",
                                 frame=index, source_uid=source_uid))
    finally:
        if uncertain:
            attempt("restore C4[1]=True", commit_c4, 1, True)
    if failures:
        raise GeneralStopError(failures)


def execute_general_stop(commit_c4, focal_off, assign_status, wait_seconds,
                         frame_observer=None, operator_confirmed=False, clock=None,
                         execution_wait=None):
    """Best-effort event-6 stop on the existing card owner, never task release.

    Unlike start, this sequence is not cancellable by a GUI close/deinit. Focal
    errors do not gate later C4 stops (the VI clears that error), but Python
    retains every failure and does not label a partial stop as success. Status
    literals are source assignments, not acknowledgments of electrical state.
    """
    if operator_confirmed is not True:
        raise ValueError("Explicit General Arret operator confirmation required")
    if execution_wait is not None and not callable(execution_wait):
        raise ValueError("Execution wait must be callable or None")
    clock = clock or time.monotonic
    failures, uncertain = [], set()

    def attempt(label, callback, *args):
        try:
            callback(*args)
            return True
        except Exception as error:
            failures.append(label + ": " + type(error).__name__ + ": " + str(error))
            return False

    def wait(seconds, index, source_uid, safe):
        if execution_wait is None:
            return wait_seconds(seconds)
        return execution_wait(seconds, safe,
                              dict(operation="modulator.general.stop", phase="source_wait",
                                   frame=index, source_uid=source_uid))

    try:
        for index, source_uid, assignments, milliseconds in GENERAL_STOP_FRAMES:
            if frame_observer is not None:
                attempt("frame observer", frame_observer, index, source_uid)
            if index == 0:
                started = clock()
                focal_completed = attempt("Focales OFF", focal_off)
                attempt("post-focal wait", wait, .5, index, source_uid, focal_completed)
                # 150 ms is a parallel branch, not an additional 150 ms wait.
                remaining = .15 - (clock() - started)
                if remaining > 0:
                    attempt("frame-0 parallel wait", wait, remaining, index,
                            source_uid, focal_completed)
                continue
            for line, value in assignments:
                if not value:
                    uncertain.add(line)  # an exception can follow a partial write
                if attempt("C4[{0}]={1}".format(line, value), commit_c4, line, value) and value:
                    uncertain.discard(line)
            if index == 15:
                attempt("source EPS/DPS assignments", assign_status, GENERAL_STOP_EPS, GENERAL_STOP_DPS)
            if milliseconds:
                attempt("frame {0} wait".format(index), wait,
                        milliseconds / 1000.0, index, source_uid, not uncertain)
    finally:
        # Explicit Python failure cleanup: retry a failed pulse release, and
        # continue restoring other lines even if one restoration also fails.
        for line in sorted(uncertain):
            attempt("restore C4[{0}]=True".format(line), commit_c4, line, True)
    if failures:
        raise GeneralStopError(failures)


def execute_general_start(commit_c4, assign_status, wait_seconds, cancelled,
                          frame_observer=None, operator_confirmed=False,
                          execution_wait=None):
    """Synchronous single-owner procedure; only injected callbacks actuate.

    Cancellation/exception restores any asserted pulse before returning. This
    is an explicit Python cleanup policy, not a recovered LabVIEW guarantee.
    EPS OK is a software assignment, never independent hardware readiness.
    No PSP publication, voltage setpoint, heating, cooling, focal or HT start.
    """
    if operator_confirmed is not True:
        raise ValueError("Explicit General Marche operator confirmation required")
    if execution_wait is not None and not callable(execution_wait):
        raise ValueError("Execution wait must be callable or None")
    active_pulse = None
    try:
        for index, source_uid, assignments, milliseconds in GENERAL_START_FRAMES:
            if cancelled():
                raise ProcedureCancelled()
            if frame_observer is not None:
                frame_observer(index, source_uid)
            for line, value in assignments:
                # Track before the call: a driver exception may follow a
                # partial physical write. Restore is attempted on that path.
                if value:
                    active_pulse = line
                commit_c4(line, value)
                if not value and active_pulse == line:
                    active_pulse = None
            if index == 8:
                assign_status(GENERAL_START_EPS, GENERAL_START_DPS)
            if milliseconds:
                if execution_wait is None:
                    wait_seconds(milliseconds / 1000.0)
                else:
                    execution_wait(milliseconds / 1000.0, active_pulse is None,
                                   dict(operation="modulator.general.start", phase="source_wait",
                                        frame=index, source_uid=source_uid))
                if cancelled():
                    raise ProcedureCancelled()
    finally:
        if active_pulse is not None:
            commit_c4(active_pulse, False)
