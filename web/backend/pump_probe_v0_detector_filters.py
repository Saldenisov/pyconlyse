"""Pure, ordered admission of canonical TRANCON detector-cycle batches.

The input layout is [cycle, BGI/BGII/IeI/IeII/I0I/I0II, wavelength].
This module neither changes RAW nor supplies a missing monitor/calibration.
Whole-cycle rejection is an explicit Web coherence policy. Legacy OpenG NaN
matching, external ML prediction, and raw counter-to-repump alignment are not
asserted equivalent by this implementation.
"""

import math

import numpy as np


FILTER_VERSION = "trancon-detector-filters-v1"
REPUMP_VERSION = "external-aligned-values-v1"
SIMILARITY_VERSION = "trancon-python-batch-distance-v1"


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _section(filters, name):
    section = filters.get(name)
    if not isinstance(section, dict) or not isinstance(section.get("enabled"), bool):
        raise ValueError(f"filters.{name}.enabled must be an explicit boolean")
    return dict(section)


def validate_detector_filter_settings(settings):
    """Validate explicit profile choices without RAW, state changes, or I/O.

    Saved LabVIEW globals are evidence, not defaults for a different camera.
    Disabled stages therefore also require an explicit profile declaration.
    """
    if not isinstance(settings, dict) or not isinstance(settings.get("all_cycles"), bool):
        raise ValueError("all_cycles must be an explicit boolean")
    filters = settings.get("filters")
    if not isinstance(filters, dict) or filters.get("version") != FILTER_VERSION:
        raise ValueError(f"filters.version must be {FILTER_VERSION}")
    if set(filters) - {"version", "repump", "nonfinite", "similarity"}:
        raise ValueError("Unknown detector filter parameter")
    repump = _section(filters, "repump")
    nonfinite = _section(filters, "nonfinite")
    similarity = _section(filters, "similarity")
    if set(repump) - {"enabled", "version", "repump_min", "repump_max"}:
        raise ValueError("Unknown repump filter parameter")
    if set(nonfinite) - {"enabled", "max_percent"}:
        raise ValueError("Unknown nonfinite filter parameter")
    if set(similarity) - {"enabled", "version", "threshold_ref_channel", "mode", "metric",
                          "diff", "min_distance", "from_pixel", "to_pixel"}:
        raise ValueError("Unknown similarity filter parameter")
    if repump["enabled"]:
        if repump.get("version") != REPUMP_VERSION:
            raise ValueError("Repump requires the external-aligned-values-v1 contract")
        lo = _number(repump.get("repump_min"), "repump_min")
        hi = _number(repump.get("repump_max"), "repump_max")
        if lo >= hi:
            raise ValueError("repump_min must be below repump_max")
        repump.update(repump_min=lo, repump_max=hi)
    if nonfinite["enabled"]:
        percent = _integer(nonfinite.get("max_percent"), "max_percent")
        if not 0 <= percent <= 100:
            raise ValueError("max_percent must be in 0..100")
    if similarity["enabled"]:
        threshold = _number(similarity.get("threshold_ref_channel"), "threshold_ref_channel")
        similarity["threshold_ref_channel"] = threshold
        # Source similiraty_cleaning113 bypasses the Python/ML helper at <=0.
        if threshold > 0:
            if similarity.get("version") != SIMILARITY_VERSION:
                raise ValueError("Similarity requires trancon-python-batch-distance-v1")
            if similarity.get("mode") != "python":
                raise ValueError("External ML similarity is not an available profile capability")
            if similarity.get("metric") not in {"euclidean", "cosine"}:
                raise ValueError("Similarity metric must be euclidean or cosine")
            similarity["diff"] = _number(similarity.get("diff"), "similarity diff")
            similarity["min_distance"] = _number(similarity.get("min_distance"), "min_distance")
            start = _integer(similarity.get("from_pixel"), "from_pixel")
            stop = _integer(similarity.get("to_pixel"), "to_pixel")
            if start < 0 or stop <= start:
                raise ValueError("Similarity requires a nonempty [from_pixel,to_pixel) interval")
    return {"version": FILTER_VERSION, "all_cycles": settings["all_cycles"],
            "repump": repump, "nonfinite": nonfinite, "similarity": similarity}


def _od(groups):
    bg_i, bg_ii, ie_i, ie_ii, i0_i, i0_ii = np.moveaxis(groups, 1, 0)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        return np.log10(((i0_i - bg_i) / (ie_i - bg_i))
                        / ((i0_ii - bg_ii) / (ie_ii - bg_ii)))


def apply_detector_filters(six_groups, settings, *, repump=None):
    """Return positional acceptance and diagnostics for an ordered batch.

    ``repump`` must be an independently measured, already aligned object:
    {"version": "external-aligned-values-v1", "values": [one per cycle]}.
    Raw legacy monitor/counter alignment is intentionally not reconstructed
    from one camera packet. Missing enabled monitor rejects every cycle.

    Nonfinite counting uses an explicit NumPy finite mask. Source OpenG NaN
    lookup has not been numerically qualified. Similarity matches the inspected
    local Python formula on finite defined distances; its legacy broad-except
    fail-open is replaced by an identified fail-closed Web guard.
    """
    config = validate_detector_filter_settings(settings)
    original = np.asarray(six_groups)
    if original.ndim == 2:
        original = original[np.newaxis, ...]
    if (original.ndim != 3 or original.shape[1] != 6 or original.shape[2] == 0
            or original.dtype.kind not in "iuf" or not np.isfinite(original).all()):
        raise ValueError("Detector filters require finite cycles x six groups x wavelengths")
    data = np.asarray(original, dtype=np.float64)
    count, _, width = data.shape
    keep = np.ones(count, dtype=bool)
    reasons = [[] for _ in range(count)]
    stages = []

    def reject(indices, reason):
        for index in indices:
            keep[index] = False
            reasons[index].append(reason)

    stage = {"stage": "repump", "enabled": config["repump"]["enabled"]}
    if stage["enabled"]:
        r = config["repump"]
        valid = (isinstance(repump, dict) and repump.get("version") == REPUMP_VERSION
                 and isinstance(repump.get("values"), (list, tuple, np.ndarray)))
        try:
            values = np.asarray(repump["values"]) if valid else None
        except (TypeError, ValueError):
            values, valid = None, False
        valid = (valid and values.ndim == 1 and len(values) == count
                 and values.dtype.kind in "iuf" and np.isfinite(values).all())
        if not valid:
            reject(range(count), "repump_monitor_missing_or_unaligned")
            stage.update(status="rejected_missing_capability", monitor_fabricated=False)
        else:
            accepted = (values > r["repump_min"]) & (values < r["repump_max"])
            reject(np.flatnonzero(~accepted), "repump_outside_strict_limits")
            stage.update(status="applied", values=values.tolist(),
                         bounds=[r["repump_min"], r["repump_max"]],
                         alignment="supplied_external_alignment_not_reconstructed")
    else:
        stage["status"] = "disabled_explicitly"
    stages.append(stage)

    stage = {"stage": "nonfinite", "enabled": config["nonfinite"]["enabled"]}
    if not stage["enabled"]:
        stage["status"] = "disabled_explicitly"
    elif config["all_cycles"]:
        stage["status"] = "bypassed_source_All_true"
    else:
        active = np.flatnonzero(keep)
        counts = (~np.isfinite(_od(data[active]))).sum(axis=1)
        percent = config["nonfinite"]["max_percent"]
        limit = width * (percent / 100.0)
        reject(active[counts >= limit], "nonfinite_OD_quota")
        stage.update(status="applied", source_indices=active.tolist(),
                     nonfinite_counts=counts.tolist(), reject_at_or_above=limit,
                     max_percent=percent, nan_search="explicit_finite_mask_OpenG_equivalence_pending")
    stages.append(stage)

    sim = config["similarity"]
    stage = {"stage": "similarity", "enabled": sim["enabled"]}
    if not stage["enabled"]:
        stage["status"] = "disabled_explicitly"
    elif sim["threshold_ref_channel"] <= 0:
        stage["status"] = "bypassed_source_threshold_not_positive"
    else:
        if sim["to_pixel"] > width:
            raise ValueError("Similarity pixel interval exceeds the wavelength axis")
        active = np.flatnonzero(keep)
        if not len(active):
            stage["status"] = "no_remaining_cycles"
        else:
            # similiraty_cleaning384/437/488/504: I-track Ie and I0 only;
            # calc_similarity798 returns indexes applied to both tracks.
            a = data[active, 2, sim["from_pixel"]:sim["to_pixel"]]
            b = data[active, 4, sim["from_pixel"]:sim["to_pixel"]]
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                if sim["metric"] == "euclidean":
                    distances = np.sqrt(np.sum((a - b) ** 2, axis=1))
                else:
                    distances = np.clip(1.0 - np.sum(a * b, axis=1)
                                        / np.sqrt(np.sum(a * a, axis=1) * np.sum(b * b, axis=1)),
                                        0.0, 2.0)
            if not np.isfinite(distances).all():
                reject(active, "similarity_distance_undefined")
                stage.update(status="rejected_undefined_metric",
                             legacy_difference="legacy_Python_except_or_NaN_path_not_reproduced")
            else:
                minimum = float(np.min(distances))
                relative_limit = minimum * sim["diff"]
                accepted = distances <= relative_limit
                if sim["min_distance"] > 0:
                    accepted &= distances <= sim["min_distance"]
                reject(active[~accepted], "similarity_distance")
                stage.update(status="applied", source_indices=active.tolist(),
                             metric=sim["metric"], distances=distances.tolist(), minimum=minimum,
                             relative_limit=relative_limit,
                             absolute_limit=sim["min_distance"] if sim["min_distance"] > 0 else None,
                             track="detector_I", pixel_interval=[sim["from_pixel"], sim["to_pixel"]])
    stages.append(stage)
    accepted = np.flatnonzero(keep).tolist()
    return {"accepted": bool(accepted), "accepted_indices": accepted,
            "rejected_indices": np.flatnonzero(~keep).tolist(), "reasons": reasons,
            "details": {"version": FILTER_VERSION, "order": [s["stage"] for s in stages],
                        "stages": stages, "input_cycles": count,
                        "coherence_policy": "reject_whole_paired_physical_cycle",
                        "RAW_mutated": False, "native_whole_equivalence": False}}
