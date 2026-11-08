"""Treatment adapter for the existing SK-Ana Python branch, not a new solver.

The vendored ``skana`` package and ``spectrokinetic_transformers.py`` are copied
unchanged from SKAna-Python commit ad7bba876715f052869cd9bacc52e21ca43aa5d4.
This boundary validates Treatment orientation, preserves physical axes/units,
bounds requests, and translates existing results into a shared Web/Qt format.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import inspect
import math
from threading import RLock

import numpy as np

UPSTREAM_COMMIT = "ad7bba876715f052869cd9bacc52e21ca43aa5d4"
MAX_MATRIX_CELLS = 2_000_000
MAX_COMPONENTS = 32
MAX_ITERATIONS = 5000
TIME_UNITS = frozenset({"fs", "ps", "ns", "us", "µs", "μs", "ms", "s"})
_TARGET_LOCK = RLock()  # Existing SciPy LSODA cannot run concurrently in threads.


class AnalysisCancelled(RuntimeError):
    """Cancellation discards a result; it does not interrupt the upstream solver."""


def _check_cancel(cancel):
    if cancel is not None and cancel():
        raise AnalysisCancelled("SK-Ana analysis cancelled; result discarded")


def _real_array(value, name, ndim):
    array = np.asarray(value)
    if array.dtype.kind not in "biuf" or array.ndim != ndim:
        raise ValueError(f"{name} must be a real numeric {ndim}D array")
    array = np.array(array, dtype=np.float64, copy=True)
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains nonfinite values; mask or repair them explicitly")
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class Dataset:
    """Immutable Treatment snapshot with canonical ``matrix[time,wavelength]``."""

    matrix: np.ndarray
    times: np.ndarray
    wavelengths: np.ndarray
    time_unit: str = "??"
    signal_unit: str = "OD"
    source: str = "Treatment"
    delay_ids: np.ndarray | None = None

    def __post_init__(self):
        raw = np.asarray(self.matrix)
        if raw.ndim != 2 or raw.size > MAX_MATRIX_CELLS:
            raise ValueError(f"SK-Ana requires a 2D matrix of at most {MAX_MATRIX_CELLS} cells")
        matrix = _real_array(raw, "matrix", 2)
        times = _real_array(self.times, "times", 1)
        wavelengths = _real_array(self.wavelengths, "wavelengths", 1)
        if matrix.shape != (times.size, wavelengths.size) or min(matrix.shape) < 2:
            raise ValueError("Canonical matrix shape must be (number of times, number of wavelengths), at least 2×2")
        ids = np.ones(times.size, dtype=int) if self.delay_ids is None else np.asarray(self.delay_ids)
        if (ids.shape != times.shape or ids.dtype.kind not in "iu" or np.any(ids < 1)
                or not np.array_equal(np.unique(ids), np.arange(1, np.unique(ids).size + 1))):
            raise ValueError("delay_ids must contain consecutive positive integer experiment IDs matching times")
        ids = np.array(ids, dtype=int, copy=True)
        ids.setflags(write=False)
        for name, value in (("matrix", matrix), ("times", times), ("wavelengths", wavelengths), ("delay_ids", ids)):
            object.__setattr__(self, name, value)
        for name in ("time_unit", "signal_unit", "source"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) > (2048 if name == "source" else 64):
                raise ValueError(f"{name} must be a bounded text label")
        object.__setattr__(self, "time_unit", self.time_unit.strip() or "??")

    def to_upstream(self):
        """Give upstream code its own arrays; never expose mutable caller data."""
        from skana import MatrixData
        return MatrixData(self.matrix, self.times, self.wavelengths, name=self.source,
                          delay_id=self.delay_ids, time=self.times)


def from_measurement(measurement, *, source=None, signal_unit=None):
    """Copy a Treatment Measurement with its documented wavelength × time layout.

    The transpose is unconditional after exact shape validation, including for
    square matrices. No shape guessing, data-file opening, unit conversion or
    replacement of NaN by fabricated zeros takes place.
    """
    wavelengths = np.asarray(measurement.wavelengths)
    times = np.asarray(measurement.timedelays)
    matrix = np.asarray(measurement.data)
    if wavelengths.ndim != 1 or times.ndim != 1 or matrix.shape != (wavelengths.size, times.size):
        raise ValueError("Treatment Measurement must be wavelength × time and match both axes")
    return Dataset(matrix.T, times, wavelengths,
                   time_unit=getattr(measurement, "time_scale", "??") or "??",
                   signal_unit=signal_unit if signal_unit is not None else getattr(measurement, "signal_unit", "a.u."),
                   source=source if source is not None else str(getattr(measurement, "source", "Treatment measurement")))


def _integer(value, name, low, high):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    value = int(value)
    if not low <= value <= high:
        raise ValueError(f"{name} must be in {low}..{high}")
    return value


def _number(value, name, low, high, *, positive=False):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high or (positive and value == 0):
        raise ValueError(f"{name} is outside its numerical limits")
    return value


def _boolean(value, name):
    if not isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a boolean")
    return bool(value)


def _bool_vector(value, name, size):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if not isinstance(value, (list, tuple, np.ndarray)) or len(value) != size:
        raise ValueError(f"{name} must be a boolean or one boolean per component")
    return [_boolean(item, name) for item in value]


def _interval(value, name):
    if not isinstance(value, (list, tuple, np.ndarray)) or len(value) != 2:
        raise ValueError(f"{name} requires [minimum, maximum]")
    low = _number(value[0], name, -1e100, 1e100)
    high = _number(value[1], name, -1e100, 1e100)
    if low > high:
        raise ValueError(f"{name} minimum exceeds maximum")
    return low, high


def _selection(data, options):
    from skana import select
    kwargs = {}
    for name in ("delay_range", "wavelength_range", "intensity_range"):
        if name in options:
            kwargs[name] = _interval(options.pop(name), name)
    for name in ("excluded_delays", "excluded_wavelengths"):
        if name in options:
            values = options.pop(name)
            if not isinstance(values, (list, tuple)) or len(values) > 100:
                raise ValueError(f"{name} requires at most 100 intervals")
            kwargs[name] = [_interval(item, name) for item in values]
    for name, size in (("delay_keep", data.delay.size), ("wavelength_keep", data.wavelength.size)):
        if name in options:
            values = options.pop(name)
            if not isinstance(values, (list, tuple, np.ndarray)) or len(values) != size:
                raise ValueError(f"{name} must match its full axis")
            kwargs[name] = np.array([_boolean(item, name) for item in values])
    return select(data, **kwargs) if kwargs else data


def _aliases(options, mapping):
    for old, new in mapping.items():
        if old in options:
            if new in options:
                raise ValueError(f"Use only one of {old} and {new}")
            options[new] = options.pop(old)


def _allowed(options, function, excluded=("data",)):
    unknown = set(options) - (set(inspect.signature(function).parameters) - set(excluded))
    if unknown:
        raise ValueError("Unsupported SK-Ana options: " + ", ".join(sorted(unknown)))


def _als_options(options, data):
    _aliases(options, {"max_iterations": "maxiter", "tolerance": "thresh",
                      "nonnegative_concentrations": "nonneg_c", "nonnegative_spectra": "nonneg_s",
                      "initialization": "init_method"})
    if "normalize_spectra" in options:
        mode = options.pop("normalize_spectra")
        if "norm_s" in options or "norm_mode" in options or mode not in ("max", "l1", "none"):
            raise ValueError("Use either normalize_spectra=max/l1/none or upstream norm_s/norm_mode")
        options.update(norm_s=mode != "none", norm_mode="l1" if mode == "l1" else "intensity")
    count = _integer(options.get("n_components", 2), "n_components", 1, min(MAX_COMPONENTS, *data.matrix.shape))
    options["n_components"] = count
    for name, low, high in (("maxiter", 1, MAX_ITERATIONS), ("random_state", 0, 2**32 - 1),
                             ("filtered_rank", 1, min(MAX_COMPONENTS, *data.matrix.shape))):
        if name in options and options[name] is not None:
            options[name] = _integer(options[name], name, low, high)
    for name in ("opt_s_first", "nonneg_c", "uni_s", "norm_s", "sum_norm", "close_c", "hard_s0", "correction_spectra"):
        if name in options:
            options[name] = _boolean(options[name], name)
    for name in ("nonneg_s", "broadening"):
        if name in options:
            options[name] = _bool_vector(options[name], name, count)
    for name in ("thresh", "smooth"):
        if name in options:
            options[name] = _number(options[name], name, 0, 1)
    for name in ("w_close_c", "w_hard_s0", "correction_lambda"):
        if name in options:
            options[name] = _number(options[name], name, 0, 1e6)
    if "broadening_max_pct" in options:
        options["broadening_max_pct"] = _number(options["broadening_max_pct"], "broadening_max_pct", 0.1, 50)
    if options.get("init_method", "svd") not in ("svd", "pca", "nmf", "seq", "restart"):
        raise ValueError("init_method must be svd, pca, nmf, seq or restart")
    if options.get("norm_mode", "intensity") not in ("intensity", "l1"):
        raise ValueError("norm_mode must be intensity or l1")
    if options.get("presence_mask") is not None:
        presence = _real_array(options["presence_mask"], "presence_mask", 2)
        if presence.shape != (data.delay.size, count) or not np.isin(presence, [0, 1]).all():
            raise ValueError("presence_mask must be selected time × component with 0/1 values")
        options["presence_mask"] = presence.copy()
    if options.get("fixed_spectra") is not None:
        fixed = np.asarray(options["fixed_spectra"])
        if fixed.ndim == 1:
            fixed = fixed[:, None]
        fixed = _real_array(fixed, "fixed_spectra", 2)
        if fixed.shape[0] != data.wavelength.size or not 1 <= fixed.shape[1] <= count:
            raise ValueError("fixed_spectra must be selected wavelength × fixed component")
        options["fixed_spectra"] = fixed.copy()


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None  # Optional uncertainty/diagnostics only; fitted arrays are checked separately.
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def analyze(dataset, method="svd", options=None, cancel=None):
    """Run an existing upstream solver and return JSON-safe shared Web/Qt data.

    No R subprocess or Streamlit application is launched. Cancellation is
    checked before and after the upstream call; in-flight LAPACK/ALS/ODE work
    cannot be interrupted by this adapter and its result is discarded instead.
    Time-unit overrides change labels only; no numerical axis/rate conversion
    is performed. Target kinetics requires explicit physical time units.
    """
    import skana
    if not isinstance(dataset, Dataset):
        raise ValueError("SK-Ana analyze requires an explicit Dataset snapshot")
    if options is not None and not isinstance(options, Mapping):
        raise ValueError("SK-Ana options must be a mapping")
    options = dict(options or {})
    if any(not isinstance(key, str) for key in options):
        raise ValueError("SK-Ana option names must be strings")
    if method not in ("svd", "mcr_als", "target"):
        raise ValueError("SK-Ana method must be svd, mcr_als or target")
    _check_cancel(cancel)
    unit = options.pop("time_unit", dataset.time_unit)
    if not isinstance(unit, str) or len(unit) > 64:
        raise ValueError("time_unit must be a bounded text label")
    unit = unit.strip() or "??"
    data = _selection(dataset.to_upstream(), options)
    if not np.any(data.matrix):
        raise ValueError("Selected SK-Ana matrix has no nonzero signal")
    metadata = {"schema_version": 1, "method": method, "source": dataset.source,
                "times": data.time, "wavelengths": data.wavelength, "time_unit": unit,
                "signal_unit": dataset.signal_unit, "delay_ids": data.delay_id,
                "input_shape": list(data.matrix.shape), "original_shape": list(dataset.matrix.shape),
                "data": data.matrix}
    diagnostics = {"upstream_commit": UPSTREAM_COMMIT, "engine": "existing SK-Ana Python port",
                   "residual_definition": "data - model", "cancellation": "result discard after upstream solver returns",
                   "time_conversion_applied": False, "physical_species_count_established": False}
    if method == "svd":
        _aliases(options, {"n_components": "rank"})
        options["rank"] = _integer(options.get("rank", 2), "rank", 1, min(MAX_COMPONENTS, *data.matrix.shape))
        if "max_rank" in options:
            options["max_rank"] = _integer(options["max_rank"], "max_rank", 1, MAX_COMPONENTS)
        _allowed(options, skana.svd)
        fitted = skana.svd(data, **options)
        c = fitted.u[:, :fitted.rank] * fitted.singular_values[:fitted.rank]
        s = fitted.vt[:fitted.rank].T
        model, residual = fitted.model, fitted.residual
        details = {"singular_values": fitted.singular_values, "statistics": fitted.statistics.to_dict("records")}
        diagnostics.update(centred=False, termination_reason="direct_svd")
        converged, iterations = True, 1
        from spectrokinetic_transformers import compute_lof
        lof = compute_lof(model, data.matrix)
    elif method == "mcr_als":
        _als_options(options, data)
        _allowed(options, skana.als)
        fitted = skana.als(data, **options)
        c, s, model, residual = fitted.c, fitted.s, fitted.model, fitted.resid
        details = {"broadening": fitted.g, "broadening_components": fitted.broadening_vec,
                   "normalized_rss": fitted.rss, "fixed_components": fitted.n_fixed,
                   "correction_lambda": fitted.lambda_corr}
        diagnostics.update(message=fitted.msg, upstream_metadata=fitted.meta,
                           iteration_history_available=False)
        converged, iterations, lof = fitted.converged, fitted.iter, fitted.lof
    else:
        if unit not in TIME_UNITS:
            raise ValueError("Target kinetics requires a known time_unit: fs, ps, ns, us, µs, ms or s; numeric times are not converted")
        scheme_text = options.pop("scheme", None)
        if not isinstance(scheme_text, str) or not scheme_text.strip() or len(scheme_text) > 32768:
            raise ValueError("Target kinetics requires a chemical scheme (up to 32 KiB)")
        scheme = skana.parse_scheme(scheme_text, n_experiments=np.unique(data.delay_id).size)
        if len(scheme.species) > MAX_COMPONENTS or len(scheme.reactions) > 64:
            raise ValueError("Target scheme exceeds species/reaction limits")
        if len(skana.variable_parameters(scheme)) > 32:
            raise ValueError("Target scheme exceeds 32 variable parameters")
        _aliases(options, {"nonnegative_spectra": "nonnegative_s", "tolerance": "tol"})
        for name in ("nonnegative_s", "weighted"):
            if name in options:
                options[name] = _boolean(options[name], name)
        for name, low, high in (("global_generations", 0, 50), ("population_factor", 5, 100)):
            if name in options:
                options[name] = _integer(options[name], name, low, high)
        for name, low, high, positive in (("sigma", 0, 1e100, True), ("tol", 0, 1, True),
                                          ("spectral_smooth", 0, 1, False)):
            if name in options:
                options[name] = _number(options[name], name, low, high, positive=positive)
        if options.get("start") is not None:
            start = _real_array(options["start"], "start", 1)
            if start.size != len(skana.variable_parameters(scheme)):
                raise ValueError("start must match the number of variable target parameters")
            options["start"] = start.copy()
        if options.get("fixed_spectra") is not None:
            fixed = options["fixed_spectra"]
            if not isinstance(fixed, Mapping) or set(fixed) - set(scheme.species):
                raise ValueError("Target fixed_spectra must map known species names to spectra")
            converted = {}
            for species, vector in fixed.items():
                array = _real_array(vector, "fixed_spectra", 1)
                if array.size != data.wavelength.size:
                    raise ValueError("Target fixed spectra must match selected wavelengths")
                converted[species] = array.copy()
            options["fixed_spectra"] = converted
        _allowed(options, skana.fit_kinetics, excluded=("data", "scheme"))
        fixed_names = set(options.get("fixed_spectra") or {})
        free_active = [name for name, active in zip(scheme.species, scheme.active)
                       if active and name not in fixed_names]
        if len(free_active) == 1 and not options.get("nonnegative_s", False):
            diagnostics["warnings"] = [
                "Existing SK-Ana enforces a nonnegative slope for one free active kinetic spectrum, "
                "even when signed spectra are requested. This option is not effective for this configuration."
            ]
        # Do not modify the upstream LSODA or optimiser to implement cancellation.
        while not _TARGET_LOCK.acquire(timeout=0.1):
            _check_cancel(cancel)
        try:
            _check_cancel(cancel)
            fitted = skana.fit_kinetics(data, scheme, **options)
        finally:
            _TARGET_LOCK.release()
        c, s, model, residual = fitted.c, fitted.s, fitted.model, fitted.residual
        details = {"parameters": fitted.parameters, "all_concentrations": fitted.c_all,
                   "active_species": fitted.active_species, "species": scheme.species,
                   "contracted_parameters": fitted.contracted, "covariance": fitted.covariance,
                   "normalized_rss": fitted.rss, "scheme": skana.format_scheme(scheme)}
        diagnostics.update(message=fitted.message, parameter_time_basis=unit,
                           parameter_unit_note="Concentration-order factors follow the supplied model units; no implicit seconds conversion.",
                           covariance_basis="normalized log-parameter z space",
                           solver_note="Existing MAP optimiser; a small-residual success override may be reported in its message.",
                           iterations_available=False)
        converged, iterations, lof = fitted.success, None, fitted.lof
    _check_cancel(cancel)
    for name, array in (("concentrations", c), ("spectra", s), ("model", model), ("residuals", residual)):
        if not np.isfinite(array).all():
            raise ValueError(f"Upstream SK-Ana returned nonfinite {name}; no valid result is available")
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    if not math.isfinite(rmse) or not math.isfinite(float(lof)):
        raise ValueError("Upstream SK-Ana returned nonfinite fit statistics")
    return _json_safe({**metadata, "components": int(s.shape[1]), "concentrations": c, "spectra": s,
                       "reconstruction": model, "residuals": residual, "lof_percent": float(lof),
                       "rmse": rmse, "converged": bool(converged), "iterations": iterations,
                       "diagnostics": diagnostics, "warnings": diagnostics.get("warnings", []), **details})


__all__ = ["AnalysisCancelled", "Dataset", "TIME_UNITS", "UPSTREAM_COMMIT", "analyze", "from_measurement"]
