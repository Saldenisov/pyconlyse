"""Bounded source-derived SUP cores. Python 3.4 compatible; no native calls.

APP-19: supplied row/column and integration results surround the pure kernel.
APP-21/22: supplied positional cluster, no front-panel local scheduling claim.
"""
import math


class DomainRefusal(ValueError):
    pass


def _uint(value, maximum, label):
    if type(value) is not int or not 0 <= value <= maximum:
        raise DomainRefusal(label)
    return value


def _finite(value, label):
    if type(value) not in (int, float):
        raise DomainRefusal(label)
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise DomainRefusal(label)
    if not math.isfinite(result):
        raise DomainRefusal(label)
    return result


def _profile(buffer, extracted, integral, average, slot, label):
    if type(extracted) not in (tuple, list) or not extracted:
        raise DomainRefusal(label + ': nonempty supplied UInt8 profile required')
    profile = tuple(_uint(v, 255, label + ': UInt8 extraction') for v in extracted)
    if type(buffer) not in (tuple, list) or len(buffer) != average:
        raise DomainRefusal(label + ': buffer row count must equal averaging window')
    rows = []
    for row in buffer:
        if type(row) not in (tuple, list) or len(row) != len(profile):
            raise DomainRefusal(label + ': rectangular buffer with extracted width required')
        rows.append(tuple(_uint(v, 4294967295, label + ': UInt32 buffer') for v in row))
    accepted = _finite(integral, label + ': supplied finite integral') > 1000.0
    if accepted:
        rows[slot] = profile
    totals = tuple(sum(row[column] for row in rows) for column in range(len(profile)))
    if any(total > 4294967295 for total in totals):
        raise DomainRefusal(label + ': UInt32 accumulation overflow excluded')
    return tuple(rows), tuple(float(total) / average for total in totals), accepted


def profile_xy(buffer_x, buffer_y, extracted_row, extracted_column,
               integral_x, integral_y, average, iteration):
    """APP-19 bounded ring update/mean. External image/integration remain supplied."""
    _uint(average, 65535, 'UInt16 averaging window')
    if average == 0:
        raise DomainRefusal('zero averaging window excluded')
    _uint(iteration, 4294967295, 'UInt32 iteration')
    slot = iteration % average
    out_x, mean_x, gate_x = _profile(buffer_x, extracted_row, integral_x, average, slot, 'X')
    out_y, mean_y, gate_y = _profile(buffer_y, extracted_column, integral_y, average, slot, 'Y')
    return out_x, out_y, mean_x, mean_y, gate_x, gate_y, slot


def _discrepancy(rows, threshold, count, forced_false):
    if type(rows) not in (tuple, list) or len(rows) != count:
        raise DomainRefusal('exact source row count required')
    limit = _finite(threshold, 'finite DBL threshold required')
    if limit < 0.0:
        raise DomainRefusal('negative threshold excluded')
    output = []
    for index, row in enumerate(rows):
        if type(row) not in (tuple, list) or len(row) != 11:
            raise DomainRefusal('exact eleven-field source row required')
        if any(type(row[field]) is not bool for field in (0, 1, 2, 3, 4, 7, 8, 9, 10)):
            raise DomainRefusal('source state and trailing button fields must be Boolean')
        commanded = _finite(row[5], 'finite DBL Consigne required')
        observed = _finite(row[6], 'finite DBL Lecture required')
        difference = commanded - observed
        if not math.isfinite(difference):
            raise DomainRefusal('DBL subtraction overflow excluded')
        fields = list(row)
        fields[2] = False if index == forced_false else abs(difference) > limit
        output.append(tuple(fields))
    return tuple(output)


def discrepancy_vdirecte(rows, threshold):
    """APP-21: third row alarm is saved literal False, despite dead arithmetic."""
    return _discrepancy(rows, threshold, 11, 2)


def discrepancy_vdeviee(rows, threshold):
    """APP-22: all nine row alarm flags use strict absolute discrepancy."""
    return _discrepancy(rows, threshold, 9, None)
