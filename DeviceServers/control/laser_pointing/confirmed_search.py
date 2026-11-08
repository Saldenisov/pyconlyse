"""Centering-first search with fresh reference/candidate repeat confirmation.

All hardware access is supplied as callbacks. Importing this module performs
no device discovery, network access, camera acquisition or motion.
"""

from dataclasses import replace

from .alignment_quality import confirm_improvement, finite_nonnegative, score_summary
from .automatic_search import bounded_pattern_search


class CenteringSearchCancelled(RuntimeError):
    pass


def confirmed_centering_search(measure_at, restore, start, bounds, parameters, *,
                               repetitions=3, noise_multiplier=2.0,
                               cancelled=lambda: False, on_observation=lambda record: None,
                               step_limit=None, direction_order=None):
    if not 3 <= repetitions <= 5:
        raise ValueError("measurement repetitions must be between 3 and 5")
    parameters.validate()
    best_position = tuple(start)
    best_measurements = []
    decisions = []
    measurement_count = 0

    def checkpoint():
        if cancelled():
            raise CenteringSearchCancelled("centering search cancelled")

    def repeated(position):
        nonlocal measurement_count
        values = []
        for _ in range(repetitions):
            checkpoint()
            value = dict(measure_at(position))
            finite_nonnegative(value["centering_error_px"], "centering error")
            finite_nonnegative(value["ellipticity_error_pct"], "ellipticity error")
            values.append(value)
            measurement_count += 1
        return values

    def scores(measurements):
        return [m["centering_error_px"] for m in measurements]

    def objective(position):
        nonlocal best_position, best_measurements
        checkpoint()
        position = tuple(position)
        candidate = repeated(position)
        if not best_measurements:
            best_position, best_measurements = position, candidate
            on_observation({"position": position, "confirmed": True, "baseline": True,
                            "quality": score_summary(scores(candidate)),
                            "measurements": candidate})
            return max(scores(candidate))

        original = list(best_measurements)
        screening = confirm_improvement(scores(original), scores(candidate),
                                        parameters.minimum_improvement_px, noise_multiplier)
        decision = {"position": position, "reference_position": best_position,
                    "screening": screening, "confirmed": False}
        if screening["accepted"]:
            # Leave the candidate, freshly measure the retained reference,
            # then revisit the candidate. This tests physical return as well
            # as temporal image repeatability; no cached minimum is sufficient.
            fresh_reference = repeated(best_position)
            revisited = repeated(position)
            fresh = confirm_improvement(scores(fresh_reference), scores(revisited),
                                        parameters.minimum_improvement_px, noise_multiplier)
            retained = confirm_improvement(scores(original), scores(revisited),
                                           parameters.minimum_improvement_px, noise_multiplier)
            decision.update(fresh_confirmation=fresh, retained_confirmation=retained)
            if fresh["accepted"] and retained["accepted"]:
                best_position, best_measurements = position, revisited
                decision["confirmed"] = True
            else:
                best_measurements = fresh_reference
        decisions.append(decision)
        observed = best_measurements if decision["confirmed"] else candidate
        on_observation({**decision, "quality": score_summary(scores(observed)),
                        "measurements": observed})
        if not decision["confirmed"]:
            checkpoint()
            restore(best_position)
            # A rejected noisy low score must never enter the optimizer's
            # best-position or convergence bookkeeping.
            return 1.0e12
        return max(scores(best_measurements))

    result = bounded_pattern_search(
        objective, start, bounds, parameters, cancelled=cancelled,
        step_limit=step_limit, direction_order=direction_order,
    )
    checkpoint()
    restore(best_position)
    # Final independent repeats are mandatory even for an already-good baseline.
    final_measurements = repeated(best_position)
    final_score = max(scores(final_measurements))
    result = replace(result, best_position=best_position, best_score=final_score,
                     reason="tolerance" if final_score <= parameters.tolerance_px else result.reason)
    if result.reason == "tolerance" and final_score > parameters.tolerance_px:
        result = replace(result, reason="verification_failed")
    return result, {
        "decisions": decisions, "measurements": final_measurements,
        "measurement_count": measurement_count,
        "confirmed_position": list(best_position),
        "confirmed_measurements": best_measurements,
    }
