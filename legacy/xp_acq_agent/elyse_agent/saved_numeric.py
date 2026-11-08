"""Bounded NI string-number replay with an explicit decimal separator.

Python 3.4 stdlib only. A supplied separator is replay input, not evidence of
original system locale. Native rounding, exceptional numbers and undocumented
text prefixes remain outside this domain.
"""
import math
import re
from decimal import Decimal, ROUND_HALF_UP, localcontext


class NumericSemanticGap(ValueError):
    pass


def _separator(use_system_decimal_point, supplied_decimal_separator):
    if type(use_system_decimal_point) is not bool:
        raise NumericSemanticGap('decimal selector requires Boolean')
    if supplied_decimal_separator not in ('.', ',') or type(supplied_decimal_separator) is not str:
        raise NumericSemanticGap('explicit period/comma replay profile required')
    return supplied_decimal_separator if use_system_decimal_point else '.'


def fract_exp_to_dbl(text, offset=0, default=0.0, use_system_decimal_point=True,
                     supplied_decimal_separator=None):
    """Return (DBL number, I32 offset) for an unambiguous ASCII numeric prefix."""
    sep = _separator(use_system_decimal_point, supplied_decimal_separator)
    if type(text) is not str or any(ord(c) > 127 for c in text) or len(text) > 256:
        raise NumericSemanticGap('bounded ASCII text required')
    if type(offset) is not int or not -(1 << 31) <= offset < (1 << 31):
        raise NumericSemanticGap('I32 offset required')
    if type(default) is not float or not math.isfinite(default):
        raise NumericSemanticGap('finite DBL default required')
    start = max(0, offset)
    if start >= len(text):
        raise NumericSemanticGap('empty/beyond-input parse not qualified')
    suffix = text[start:]
    pattern = r'[+-]?(?:[0-9]+(?:SEP[0-9]*)?|SEP[0-9]+)(?:[eE][+-]?[0-9]+)?'
    match = re.match(pattern.replace('SEP', re.escape(sep)), suffix)
    if not match:
        raise NumericSemanticGap('whitespace/non-numeric/sign-only prefix not qualified')
    token = match.group(0)
    rest = suffix[len(token):]
    if rest.startswith(('e', 'E')):
        raise NumericSemanticGap('incomplete exponent not qualified')
    value = float(token.replace(sep, '.'))
    if not math.isfinite(value) or (value and not 1e-20 <= abs(value) <= 1e20):
        raise NumericSemanticGap('parsed value outside bounded finite DBL domain')
    if value == 0 and token.startswith('-'):
        raise NumericSemanticGap('negative zero parse not qualified')
    return value, start + len(token)


def dbl_to_exp_string(number, width, precision, use_system_decimal_point=True,
                      supplied_decimal_separator=None):
    """Documented e-format, normalized exponent and left padding; ties refused."""
    sep = _separator(use_system_decimal_point, supplied_decimal_separator)
    if type(number) is not float or not math.isfinite(number):
        raise NumericSemanticGap('finite DBL number required')
    if type(width) is not int or not 0 <= width <= 256:
        raise NumericSemanticGap('bounded nonnegative I16 width required')
    if type(precision) is not int or not 0 <= precision <= 12:
        raise NumericSemanticGap('bounded nonnegative I16 precision required')
    if number == 0 and math.copysign(1.0, number) < 0:
        raise NumericSemanticGap('negative zero format not qualified')
    if number and not 1e-12 <= abs(number) <= 1e12:
        raise NumericSemanticGap('number outside bounded finite DBL domain')
    with localcontext() as context:
        context.prec = 100
        exact = Decimal.from_float(abs(number))
        exponent = exact.adjusted() if number else 0
        scaled = exact.scaleb(precision - exponent)
        integral = scaled.to_integral_value(rounding='ROUND_FLOOR')
        if scaled - integral == Decimal('0.5'):
            raise NumericSemanticGap('native tie rounding not qualified')
        rounded = scaled.to_integral_value(rounding=ROUND_HALF_UP)
        if rounded >= 10 ** (precision + 1):
            exponent += 1
            rounded /= 10
        mantissa = rounded.scaleb(-precision)
        result = ('-' if number < 0 else '') + format(mantissa, '.' + str(precision) + 'f')
        result = result.replace('.', sep) + 'e' + str(exponent)
    return result.rjust(width)


def replay_payload(payload):
    """Strict JSON replay policy; no native locale/coercion or acquisition binding."""
    if type(payload) is not dict:
        raise ValueError('numeric replay requires object')
    operation = payload.get('operation')
    common = {'operation', 'decimal_separator', 'use_system_decimal_point'}
    if operation == 'parse':
        expected = common | {'text', 'offset', 'default'}
        if set(payload) != expected:
            raise ValueError('parse replay fields differ')
        number, offset = fract_exp_to_dbl(payload['text'], payload['offset'], payload['default'],
                                        payload['use_system_decimal_point'], payload['decimal_separator'])
        return dict(number=number, offset_past_number=offset)
    if operation == 'format':
        expected = common | {'number', 'width', 'precision'}
        if set(payload) != expected:
            raise ValueError('format replay fields differ')
        return dict(text=dbl_to_exp_string(payload['number'], payload['width'], payload['precision'],
                                         payload['use_system_decimal_point'], payload['decimal_separator']))
    raise ValueError('unknown numeric replay operation')
