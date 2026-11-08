# -*- coding: utf-8 -*-
"""Python 3.4 logical arrow rules; no voltages, physical limits, or DAQ writes.

Checked against the recovered ParameterRule crosswalk by the package builder.
An uninitialized field requires an explicit finite simulation seed, never zero.
"""
import math


def rules():
    result = []
    groups = (
        ("Page Fluides", "fluides", "T° CANON:", "C8NI6703.01", None,
         ((1, "< Canon", -0.1), (2, "> Canon", 0.1))),
        ("Page Fluides", "fluides", "T° SECTION:", "C8NI6703.02", None,
         ((4, "< Section", -0.1), (8, "> Section", 0.1))),
        ("Page HT", "ht", "Consigne HT", "C9NI6703.00", (6.0, 20.0),
         ((1, "<< HT", -1.0), (2, "< HT", -0.1), (4, "> HT", 0.1), (8, ">> HT", 1.0))),
        ("Page HT", "ht", "Consigne préampli", "C8NI6703.06", (200.0, 400.0),
         ((16, "<< Préampli", -5.0), (32, "< Préampli", -1.0),
          (64, "> Préampli", 1.0), (128, ">> Préampli", 5.0))),
        ("Page HF", "hf", "Cons Atténuateur HF", "C8NI6703.04", (0.0, 20.0),
         ((1, "<< Att HF", -5.0), (2, "< Att HF", -1.0),
          (4, "> Att HF", 1.0), (8, ">> Att HF", 1.0))),
        ("Page HF", "hf", "Consigne déphaseur HF", "C8NI6703.03", (-180.0, 180.0),
         ((16, "<< déphaseur HF", -10.0), (32, "< déphaseur HF", -1.0),
          (64, "> déphaseur HF", 1.0), (128, ">> déphaseur HF", 10.0))),
    )
    for page, slug, field, target, limits, arrows in groups:
        for mask, control, delta in arrows:
            result.append(dict(page=page, control=control, numeric_field=field, target=target,
                               delta=delta, native_limits=list(limits) if limits else None,
                               procedure="setpoint.{0}.{1}".format(slug, mask)))
    return result


def finite_number(value):
    if type(value) not in (int, float):
        raise ValueError("Explicit finite numeric base_value required")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise ValueError("Explicit finite numeric base_value required")
    if not math.isfinite(number):
        raise ValueError("Explicit finite numeric base_value required")
    return number


def adjusted(rule, base_value):
    value = finite_number(base_value) + rule["delta"]
    if not math.isfinite(value):
        raise ValueError("Non-finite setpoint result")
    limits = rule["native_limits"]
    if limits:
        value = min(max(value, limits[0]), limits[1])
    return value
