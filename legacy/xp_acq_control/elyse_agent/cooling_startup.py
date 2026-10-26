"""Bounded repeated input verification after a water-start command; Python 3.4."""
import math
import time

from .cooling_safety import decode_publications, runtime_publications
from .acquisition_procedures import ProcedureCancelled
from .card_observation import source_age


def wait_for_cooling(read_sample, cancel, observe, timeout=30.0,
                     clock=None, stable_seconds=2.0):
    if (type(timeout) not in (int, float) or not math.isfinite(timeout)
            or not 2 <= timeout <= 120 or not 0 < stable_seconds <= timeout):
        raise ValueError("Bounded cooling startup timeout required")
    clock = clock or time.monotonic
    deadline, normal_since, count = clock() + timeout, None, 0
    while clock() < deadline:
        if cancel.is_set():
            raise ProcedureCancelled("Cooling startup interrupted; ownership retained")
        sample = read_sample(cancel)
        if sample.get("source") != "python_daqmx_acquisition" or sample.get("simulated") is not False:
            raise RuntimeError("Real Python input snapshot required for circulation verification")
        if source_age(sample) >= 2 or (sample.get("input_health") or {}).get("all_current") is False:
            raise RuntimeError("Current per-card cooling input images required")
        circuits, unused = decode_publications(runtime_publications(sample))
        observe(sample, circuits)
        now = clock()
        normal = (set(circuits) == {"CANON", "SECTION"} and all(
            item.get("quality") == "FRESH" and item.get("fault") is False
            for item in circuits.values()))
        if normal:
            if normal_since is None:
                normal_since, count = now, 0
            count += 1
            if count >= 2 and now - normal_since >= stable_seconds and now < deadline:
                return dict(circuits=["CANON", "SECTION"], repeated_samples=count,
                            stable_seconds=now - normal_since,
                            interpretation="Fresh cooling indications, not full machine acknowledgement")
        else:
            normal_since, count = None, 0
        if cancel.wait(min(.2, max(0, deadline - clock()))):
            raise ProcedureCancelled("Cooling startup interrupted; ownership retained")
    raise RuntimeError("COOLING_START_TIMEOUT: Canon/Section circulation not confirmed; later starts blocked")

