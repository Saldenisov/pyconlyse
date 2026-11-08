"""Bounded saved NI6220 mean-loop projection on supplied completed returns.

No DAQ/task/clock/timeout/stop or live data access. N also bounds channel
iterations in the saved VI. Python validation is replay policy; Mean(empty),
negative N, coercions and native Mean floating-point parity remain unqualified.
"""
import math
from collections import namedtuple
from .saved_xnode import ErrorValue

SOURCE_ID = "APP-08"
BODY_UID = "612"
ReadMeansResult = namedtuple("ReadMeansResult", "values error")


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def project_ni6220_channel_means(returned_channels, sample_count):
    """Preserve the existing pure model: min(N, row count) unscaled means."""
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 0:
        raise ValueError("sample_count must be a nonnegative integer in this bounded model")
    rows = tuple(tuple(row) for row in returned_channels)
    selected = rows[:sample_count]
    if any(not row for row in selected):
        raise ValueError("empty sample rows are outside this bounded model")
    return tuple(sum(row) / len(row) for row in selected)


def project_saved_ni6220_read(returned_channels, sample_count, returned_error):
    """Error1317->979 is independent of the data path; retain supplied error.

    This models a completed DAQ return only. It cannot make a blocked read
    return, suppress an error handler or guarantee cleanup/stop latency.
    """
    if type(returned_error) is not ErrorValue:
        raise TypeError("explicit returned ErrorValue required")
    return ReadMeansResult(project_ni6220_channel_means(returned_channels, sample_count), returned_error)


def replay_saved_ni6220_read(payload):
    """Strict JSON storage domain for a stateless supplied-return replay."""
    fields = {"source_id", "uid", "returned_channels", "sample_count", "read_error"}
    if type(payload) is not dict or set(payload) != fields:
        raise ValueError("saved NI6220 replay requires source_id, uid, returned_channels, sample_count, read_error")
    if type(payload["source_id"]) is not str or type(payload["uid"]) is not str or payload["source_id"] != SOURCE_ID or payload["uid"] != BODY_UID:
        raise ValueError("only qualified APP-08 loop612 is supported")
    count = payload["sample_count"]
    if type(count) is not int or not 0 <= count < 2 ** 31:
        raise ValueError("explicit nonnegative I32 sample_count required")
    rows = payload["returned_channels"]
    if type(rows) is not list or len(rows) > 64 or any(type(row) is not list for row in rows):
        raise ValueError("bounded JSON row lists required")
    widths = set(len(row) for row in rows)
    if len(widths) > 1 or sum(len(row) for row in rows) > 4096:
        raise ValueError("rectangular returned rows within4096 cells required")
    if any(not _finite(value) for row in rows for value in row):
        raise ValueError("explicit finite numeric sample values required")
    error = payload["read_error"]
    if type(error) is not dict or set(error) != {"status", "code", "source"}:
        raise ValueError("explicit read_error status/code/source required")
    if type(error["status"]) is not bool or type(error["source"]) is not str:
        raise ValueError("explicit Boolean/String returned error fields required")
    if type(error["code"]) is not int or not -(2 ** 31) <= error["code"] < 2 ** 31:
        raise ValueError("explicit I32 returned error code required")
    supplied_error = ErrorValue(error["status"], error["code"], error["source"])
    doubles = [[float(value) for value in row] for row in rows]
    result = project_saved_ni6220_read(doubles, count, supplied_error)
    if any(not math.isfinite(value) for value in result.values):
        raise ValueError("nonfinite means are outside JSON replay domain")
    return dict(source_id=SOURCE_ID, uid=BODY_UID, outputs=dict(values=list(result.values), read_error=dict(result.error._asdict())),
                loop_iterations=len(result.values), supplied_row_count=len(rows),
                scope="SUPPLIED_COMPLETED_READ_PROJECTION", acquired_data_bound=False,
                native_mean_bitwise_equivalence=False, execution_allowed=False, hardware_writes=False)
