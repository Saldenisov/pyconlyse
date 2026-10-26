"""RAM-only source generations and conservative per-card sample age."""
import math
from .runtime_identity import valid_hex


def generation_vector(state):
    if not isinstance(state, dict):
        return None
    value = state.get("generation_vector")
    if not isinstance(value, (list, tuple)) or not value:
        return None
    result, seen = [], set()
    for pair in value:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or type(pair[0]) is not int or pair[0] in seen
                or not valid_hex(pair[1], 32)):
            return None
        seen.add(pair[0])
        result.append(tuple(pair))
    return tuple(result)


def source_age(sample):
    value = sample.get("source_age_seconds", 0.) if isinstance(sample, dict) else None
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Finite nonnegative source sample age required")
    return value


def selected_generations(state, devices):
    values = generation_vector(state)
    if values is None:
        return None
    selected = tuple(pair for pair in values if pair[0] in devices)
    return selected if {pair[0] for pair in selected} == set(devices) else None


def card_inputs_current(sample, state):
    health = sample.get("input_health") if isinstance(sample, dict) else None
    if health is None:
        return state is None  # Legacy single-owner samples have no vector.
    if (not isinstance(health, dict) or health.get("all_current") is not True
            or not isinstance(state, dict) or state.get("all_required_ready") is not True
            or generation_vector(health) is None
            or generation_vector(health) != generation_vector(state)):
        return False
    age = state.get("transport_age_seconds", 0.)
    return type(age) in (int, float) and math.isfinite(age) and 0 <= age < 2
