"""Source-derived scalar C9[0] command transfer, with injected callbacks only.

The saved Acquisition Timeout frame10115 reads a ten-DBL C9NI6703 image at
reader10449 into local12. The independent AO writer7386 calls the original
1_ACQ_WRITE_NI6703.vi; C9[0] maps logical kV to volts with gain0.5. This
adapter replaces only field0 in the caller-owned last-successful command
image, then commits the complete bank once. It neither reads PSP nor starts
an autonomous ramp. No EPS permit or Supervision operating clamp is added.

Python policy, NOT a recovered operating permit: reject logical commands
outside [-20, 20] before callbacks because gain0.5 exceeds the NI6703 +/-10V
driver domain. Other fields remain unchanged; the caller's complete-bank
driver must still validate their conversions and serialize competing writes.
Normal commit return acknowledges only callback completion, never physical HT.
A raised commit may already have applied: retain the prior successful image,
mark the attempted command uncertain, and never retry, roll back, or release
resources here. The owning backend must latch that uncertainty independently.
"""

import math


BANK_NAME = "C9NI6703"
BANK_SIZE = 10
HT_FIELD = 0
HT_GAIN_TO_VOLTS = 0.5
HT_DRIVER_MIN_KV = -20.0
HT_DRIVER_MAX_KV = 20.0
DRIVER_DOMAIN_POLICY = "python_driver_domain_gain0.5_ni6703_plus_minus10V"
SOURCE_PROVENANCE = {
    "source_id": "APP-00",
    "timeout_frame_uid": "10115",
    "dynamic_reader_uid": "10449",
    "local_bank": 12,
    "writer_subvi_uid": "7386",
    "writer_subvi": "1_ACQ_WRITE_NI6703.vi",
    "writer_original_sha256":
        "5437FD979E7D5AB2F50257DF0F75B73D7C800684EFF0A45D28D6E51931893C3D",
    "logical_bank": BANK_NAME,
    "logical_field": HT_FIELD,
    "logical_scale_to_volts": HT_GAIN_TO_VOLTS,
    "logical_offset_to_volts": 0.0,
}


class HTVoltageError(RuntimeError):
    def __init__(self, report):
        self.report = report
        RuntimeError.__init__(self, "{0}: {1}".format(
            report["operation"], report["status"]))


class HTVoltageCancelled(HTVoltageError):
    pass


def _finite_number(value):
    # bool is an int subclass; reject it and coercible strings explicitly.
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _snapshot(value):
    if (type(value) is not tuple or len(value) != BANK_SIZE
            or any(not _finite_number(item) for item in value)):
        raise ValueError("Complete finite ten-number C9NI6703 tuple required")
    return value


def execute_ht_voltage(command_kv, read_bank, commit_bank, cancelled,
                       observer=None):
    """Commit one source-qualified logical C9[0] command, without hardware I/O.

    read_bank('C9NI6703') returns the complete last-successful software command
    tuple. commit_bank('C9NI6703', tuple10) commits exactly one complete logical
    image; a normal return need not return a value. The caller owns output
    serialization, NI authorization, driver validation, and uncertainty latch.
    cancelled() must return an exact bool. observer(stage) optionally receives
    read_bank, commit_bank, and complete; it never receives a writable bank.

    All static arguments and the driver domain are checked before callbacks.
    Cancellation is checked before reading and immediately before committing.
    Cancellation/observer failure after a successful commit never restores an
    old image; its report retains the newly successful software command. A
    failed commit is ambiguous regardless of whether it raised before or after
    applying. No other stage, counter, publication, wait, or cleanup is called.
    """
    if (not _finite_number(command_kv)
            or not HT_DRIVER_MIN_KV <= command_kv <= HT_DRIVER_MAX_KV):
        raise ValueError("Finite HT command in driver domain [-20, 20] kV required; "
                         "not an Acquisition operating permit")
    if any(not callable(callback) for callback in
           (read_bank, commit_bank, cancelled)):
        raise TypeError("HT command callbacks must be callable")
    if observer is not None and not callable(observer):
        raise TypeError("HT command observer must be callable or None")
    requested = float(command_kv)
    report = {
        "operation": "alimentation_ht.voltage",
        "status": "EXECUTING",
        "requested_command_kv": requested,
        "attempted_command_kv": None,
        "last_successful_command_kv": None,
        "bank_before": None,
        "requested_bank": None,
        "last_successful_bank": None,
        "commit_attempted": False,
        "commit_completed": False,
        "command_uncertain": False,
        "cancelled": False,
        "failures": [],
        "driver_target_volts": requested * HT_GAIN_TO_VOLTS,
        "driver_domain_policy": DRIVER_DOMAIN_POLICY,
        "software_command_only": True,
        "hardware_acknowledged": False,
        "operating_permit_qualified": False,
        "source_path": dict(SOURCE_PROVENANCE),
    }
    stage = "before_read"

    # Do not treat a callback's public HTVoltageError/HTVoltageCancelled as
    # this invocation's report. In particular a nested write error must retain
    # this invocation's uncertainty and last-successful command image.
    class CancelledSignal(Exception):
        pass

    def check_cancel():
        value = cancelled()
        if type(value) is not bool:
            raise ValueError("HT cancellation result must be Boolean")
        if value:
            report["status"] = "CANCELLED"
            report["cancelled"] = True
            raise CancelledSignal()

    def observe(name):
        if observer is not None:
            observer(name)

    try:
        check_cancel()
        stage = "read_bank_observer"
        observe("read_bank")
        check_cancel()
        stage = "read_bank"
        before = _snapshot(read_bank(BANK_NAME))
        report["bank_before"] = before
        report["last_successful_bank"] = before
        report["last_successful_command_kv"] = before[HT_FIELD]
        after = list(before)
        after[HT_FIELD] = requested
        after = tuple(after)
        report["requested_bank"] = after
        stage = "before_commit"
        check_cancel()
        stage = "commit_bank_observer"
        observe("commit_bank")
        check_cancel()
        stage = "commit_bank"
        report["attempted_command_kv"] = requested
        report["commit_attempted"] = True
        report["command_uncertain"] = True
        commit_bank(BANK_NAME, after)
        report["commit_completed"] = True
        report["command_uncertain"] = False
        report["last_successful_bank"] = after
        report["last_successful_command_kv"] = requested
        stage = "after_commit"
        check_cancel()
        stage = "complete_observer"
        observe("complete")
        check_cancel()
        report["status"] = "COMPLETE"
        return report
    except CancelledSignal:
        raise HTVoltageCancelled(report)
    except Exception as error:
        report["status"] = "FAILED"
        report["failures"].append({
            "stage": stage,
            "error_type": type(error).__name__,
            "message": str(error),
        })
        raise HTVoltageError(report)
