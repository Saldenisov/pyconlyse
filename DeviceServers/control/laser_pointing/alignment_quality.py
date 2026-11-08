"""Hardware-free centering diagnostics and repeat-measurement decisions.

Ellipticity describes shape; it is deliberately not a centering penalty.
The repeatability guard is a robust scatter rule, not a confidence interval.
"""

from math import isfinite

import numpy as np


def finite_nonnegative(value, name):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def contour_centering(contours):
    """Use independently fitted ellipse centers, without forcing circularity."""
    centres = np.asarray([c["ellipse_centre"] for c in contours], dtype=float)
    if centres.ndim != 2 or centres.shape[1] != 2 or len(centres) < 3:
        raise ValueError("at least three ellipse centers are required")
    if not np.isfinite(centres).all():
        raise ValueError("ellipse centers must be finite")
    common = np.median(centres, axis=0)
    distances = np.linalg.norm(centres - common, axis=1)
    return {
        "alignment_centroid": common.tolist(),
        "centering_error_px": float(np.sqrt(np.mean(distances ** 2))),
        "centering_max_offset_px": float(np.max(distances)),
        "centering_contour_count": len(centres),
        "centering_method": "ellipse_centres_rms",
    }


def score_summary(scores):
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("scores must be a nonempty finite non-negative sequence")
    median = float(np.median(values))
    return {
        "scores": values.tolist(), "count": len(values), "median": median,
        "scatter": float(1.4826 * np.median(np.abs(values - median))),
        "maximum": float(np.max(values)),
    }


def confirm_improvement(reference, candidate, minimum_improvement=0.1, noise_multiplier=2.0):
    """Reject isolated lucky measurements and gains smaller than repeat scatter."""
    if len(reference) < 3 or len(candidate) < 3:
        raise ValueError("confirmation requires at least three independent measurements per position")
    minimum = finite_nonnegative(minimum_improvement, "minimum improvement")
    multiplier = finite_nonnegative(noise_multiplier, "noise multiplier")
    ref, cand = score_summary(reference), score_summary(candidate)
    required = max(minimum, multiplier * max(ref["scatter"], cand["scatter"]))
    gain = ref["median"] - cand["median"]
    votes = sum(value < ref["median"] - minimum for value in cand["scores"])
    accepted = bool(gain > required and votes >= (2 * len(candidate) + 2) // 3
                    and cand["maximum"] < ref["maximum"])
    return {
        "accepted": accepted, "reference": ref, "candidate": cand,
        "improvement_px": gain, "required_improvement_px": required,
        "confirming_measurements": votes,
    }


def centering_verification(measurements, tolerance_px, ellipticity_tolerance_pct=7.0):
    """Every repeat must satisfy centering; ellipse shape is a separate result."""
    if len(measurements) < 3:
        raise ValueError("verification requires at least three independent measurements")
    tolerance = finite_nonnegative(tolerance_px, "centering tolerance")
    ellipse_tolerance = finite_nonnegative(ellipticity_tolerance_pct, "ellipticity tolerance")
    scores = [finite_nonnegative(m["centering_error_px"], "centering error") for m in measurements]
    ellipses = [finite_nonnegative(m["ellipticity_error_pct"], "ellipticity error") for m in measurements]
    return {
        "centering_passed": all(value <= tolerance for value in scores),
        "centering_error_px": float(np.median(scores)),
        "centering_worst_px": max(scores), "centering_tolerance_px": tolerance,
        "centering_repeatability": score_summary(scores),
        "ellipticity_error_pct": float(np.median(ellipses)),
        "ellipticity_passed": all(value <= ellipse_tolerance for value in ellipses),
        "ellipticity_tolerance_pct": ellipse_tolerance,
        "measurement_repetitions": len(measurements),
        "score_metric": "centering_error_px",
    }
