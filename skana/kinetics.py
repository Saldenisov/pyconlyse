"""Chemical-scheme kinetic modeling and Bayesian MAP fitting, without R.

The reaction syntax and normalized log-parameter priors follow SK-Ana's
``kinetParsers.R`` / ``kinetHypercubeTransfo.R``. Integration uses SciPy LSODA;
MAP search uses SciPy optimizers in place of the R optimizer packages.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Mapping

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import differential_evolution, minimize, nnls

from .matrix import MatrixData
from spectrokinetic_transformers import compute_lof


@dataclass(frozen=True)
class Reaction:
    reactants: tuple[str, ...]
    products: tuple[str, ...]
    rate: float
    factor: float = 1.0


@dataclass(frozen=True)
class Scheme:
    species: tuple[str, ...]
    reactions: tuple[Reaction, ...]
    initial: np.ndarray  # experiments x species
    initial_factors: np.ndarray
    extinction: np.ndarray  # species
    extinction_factors: np.ndarray
    source: str

    def __post_init__(self) -> None:
        n = len(self.species)
        if not self.reactions or not n:
            raise ValueError("A kinetic scheme needs reactions and species.")
        if any(not np.isfinite(r.rate) or r.rate < 0 or
               not np.isfinite(r.factor) or r.factor < 1 for r in self.reactions):
            raise ValueError("Reaction rates must be nonnegative and uncertainty factors at least one.")
        if self.initial.ndim != 2 or self.initial.shape[1] != n:
            raise ValueError("Initial concentrations must be experiments × species.")
        if self.initial_factors.shape != self.initial.shape:
            raise ValueError("Initial factors must match initial concentrations.")
        if self.extinction.shape != (n,) or self.extinction_factors.shape != (n,):
            raise ValueError("Extinction vectors must match species.")
        for array in (self.initial, self.initial_factors, self.extinction, self.extinction_factors):
            if not np.isfinite(array).all():
                raise ValueError("Scheme values must be finite.")
        if (self.initial < 0).any() or (self.extinction < 0).any():
            raise ValueError("Initial concentrations and extinction coefficients cannot be negative.")
        if (self.initial_factors < 1).any() or (self.extinction_factors < 1).any():
            raise ValueError("Uncertainty factors must be at least one.")

    @property
    def active(self) -> np.ndarray:
        return self.extinction > 0

    def with_values(self, *, rates: np.ndarray | None = None,
                    rate_factors: np.ndarray | None = None,
                    initial: np.ndarray | None = None,
                    initial_factors: np.ndarray | None = None,
                    extinction: np.ndarray | None = None,
                    extinction_factors: np.ndarray | None = None) -> "Scheme":
        rate_values = np.asarray(rates if rates is not None else [r.rate for r in self.reactions])
        factors = np.asarray(rate_factors if rate_factors is not None else
                             [r.factor for r in self.reactions])
        if rate_values.shape != (len(self.reactions),) or factors.shape != rate_values.shape:
            raise ValueError("Rate values and factors must match the reaction count.")
        reactions = tuple(replace(r, rate=float(rate), factor=float(factor))
                          for r, rate, factor in zip(self.reactions, rate_values, factors))
        return Scheme(self.species, reactions,
                      np.asarray(initial if initial is not None else self.initial, dtype=float).copy(),
                      np.asarray(initial_factors if initial_factors is not None else self.initial_factors, dtype=float).copy(),
                      np.asarray(extinction if extinction is not None else self.extinction, dtype=float).copy(),
                      np.asarray(extinction_factors if extinction_factors is not None else self.extinction_factors, dtype=float).copy(),
                      self.source)


def _value_factor(text: str) -> tuple[float, float]:
    pieces = [piece.strip() for piece in text.split("/")]
    if len(pieces) not in (1, 2):
        raise ValueError(f"Invalid value/factor: {text}")
    value = float(pieces[0])
    factor = float(pieces[1]) if len(pieces) == 2 else 1.0
    if not np.isfinite(value) or not np.isfinite(factor) or factor < 1:
        raise ValueError(f"Invalid value or uncertainty factor: {text}")
    return value, factor


def parse_scheme(text: str, n_experiments: int | None = None) -> Scheme:
    """Parse reactions, ``c0_SPEC_EXP`` and ``eps_SPEC`` from R-style text.

    Literal ``0`` is a sink and is excluded from modeled species.
    """
    reactions: list[Reaction] = []
    initial_records: dict[tuple[str, int], tuple[float, float]] = {}
    extinction_records: dict[str, tuple[float, float]] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "->" in line:
            match = re.fullmatch(r"(.+?)\s*->\s*(.+?)\s*;\s*(.+)", line)
            if not match:
                raise ValueError(f"Invalid reaction: {line}")
            left = tuple(x.strip() for x in match.group(1).split("+"))
            right = tuple(x.strip() for x in match.group(2).split("+"))
            if not all(left + right):
                raise ValueError(f"Invalid reaction species: {line}")
            rate, factor = _value_factor(match.group(3))
            if rate < 0:
                raise ValueError("Reaction rates cannot be negative.")
            reactions.append(Reaction(left, right, rate, factor))
        elif match := re.fullmatch(r"c0_(.+)_(\d+)\s*=\s*(.+)", line):
            exp = int(match.group(2))
            if exp < 1:
                raise ValueError("Experiment indices start at 1.")
            initial_records[(match.group(1), exp)] = _value_factor(match.group(3))
        elif match := re.fullmatch(r"eps_(\S+)\s*=\s*(.+)", line):
            extinction_records[match.group(1)] = _value_factor(match.group(2))
        else:
            raise ValueError(f"Unrecognized scheme line: {line}")
    if not reactions:
        raise ValueError("Scheme contains no reactions.")
    species = tuple(sorted({name for reaction in reactions
                            for name in reaction.reactants + reaction.products if name != "0"}))
    if not species:
        raise ValueError("Scheme contains no modeled species.")
    unknown = ({name for name, _ in initial_records} | set(extinction_records)) - set(species)
    if unknown:
        raise ValueError(f"Parameters refer to unknown species: {', '.join(sorted(unknown))}")
    declared_experiments = max((exp for _, exp in initial_records), default=1)
    n_exp = declared_experiments if n_experiments is None else int(n_experiments)
    if n_exp < declared_experiments or n_exp < 1:
        raise ValueError("Scheme declares more experiments than the selected data.")
    initial = np.zeros((n_exp, len(species)))
    initial_factors = np.ones_like(initial)
    extinction = np.zeros(len(species))
    extinction_factors = np.ones(len(species))
    for (name, exp), (value, factor) in initial_records.items():
        initial[exp - 1, species.index(name)] = value
        initial_factors[exp - 1, species.index(name)] = factor
    for name, (value, factor) in extinction_records.items():
        extinction[species.index(name)] = value
        extinction_factors[species.index(name)] = factor
    return Scheme(species, tuple(reactions), initial, initial_factors,
                  extinction, extinction_factors, text)


def format_scheme(scheme: Scheme) -> str:
    lines = [f"{' + '.join(r.reactants)} -> {' + '.join(r.products)} ; {r.rate:.12g} / {r.factor:.12g}"
             for r in scheme.reactions]
    lines.append("")
    for j, name in enumerate(scheme.species):
        if scheme.extinction[j] != 0:
            lines.append(f"eps_{name} = {scheme.extinction[j]:.12g} / {scheme.extinction_factors[j]:.12g}")
    for exp in range(scheme.initial.shape[0]):
        lines.append("")
        for j, name in enumerate(scheme.species):
            if scheme.initial[exp, j] != 0:
                lines.append(f"c0_{name}_{exp + 1} = {scheme.initial[exp, j]:.12g} / {scheme.initial_factors[exp, j]:.12g}")
    return "\n".join(lines) + "\n"


def stoichiometry(scheme: Scheme) -> tuple[np.ndarray, np.ndarray]:
    """Return reaction reactant powers L and net changes D."""
    left = np.zeros((len(scheme.reactions), len(scheme.species)), dtype=int)
    right = np.zeros_like(left)
    for i, reaction in enumerate(scheme.reactions):
        for name in reaction.reactants:
            if name != "0":
                left[i, scheme.species.index(name)] += 1
        for name in reaction.products:
            if name != "0":
                right[i, scheme.species.index(name)] += 1
    return left, right - left


@dataclass(frozen=True)
class Parameter:
    name: str
    nominal: float
    factor: float
    kind: str
    index: tuple[int, ...]


def variable_parameters(scheme: Scheme) -> tuple[Parameter, ...]:
    params = []
    # Match the R setOptPars() sequence: extinction, initial state, rates.
    for j, name in enumerate(scheme.species):
        if scheme.active[j] and scheme.extinction_factors[j] > 1:
            params.append(Parameter(f"eps_{name}", scheme.extinction[j],
                                    scheme.extinction_factors[j], "extinction", (j,)))
    for exp in range(scheme.initial.shape[0]):
        for j, name in enumerate(scheme.species):
            if scheme.initial_factors[exp, j] > 1:
                params.append(Parameter(f"c0_{name}_{exp + 1}", scheme.initial[exp, j],
                                        scheme.initial_factors[exp, j], "initial", (exp, j)))
    for i, reaction in enumerate(scheme.reactions):
        if reaction.factor > 1:
            params.append(Parameter(f"k_{i + 1}", reaction.rate, reaction.factor, "rate", (i,)))
    if any(p.nominal <= 0 for p in params):
        raise ValueError("Variable rate, concentration and extinction values must be positive.")
    return tuple(params)


def _expanded(scheme: Scheme, parameters: tuple[Parameter, ...], z: np.ndarray):
    rates = np.array([r.rate for r in scheme.reactions], dtype=float)
    initial = scheme.initial.copy()
    extinction = scheme.extinction.copy()
    for p, value in zip(parameters, z):
        val = p.nominal * np.exp(value * np.log(p.factor))
        if p.kind == "rate":
            rates[p.index[0]] = val
        elif p.kind == "initial":
            initial[p.index] = val
        else:
            extinction[p.index[0]] = val
    return rates, initial, extinction


def concentrations(data: MatrixData, scheme: Scheme, *, rates: np.ndarray | None = None,
                   initial: np.ndarray | None = None) -> np.ndarray:
    """Integrate mass-action ODE separately for each experiment."""
    ids = np.unique(data.delay_id)
    if ids.size != scheme.initial.shape[0]:
        raise ValueError("Scheme experiment count must match selected matrix.")
    rates = np.asarray(rates if rates is not None else [r.rate for r in scheme.reactions], dtype=float)
    initial = np.asarray(initial if initial is not None else scheme.initial, dtype=float)
    left, net = stoichiometry(scheme)
    result = np.zeros((data.time.size, len(scheme.species)))
    for exp, exp_id in enumerate(ids):
        rows = np.flatnonzero(data.delay_id == exp_id)
        times = data.time[rows]
        if (times < 0).any():
            raise ValueError("Kinetic time points must be nonnegative.")
        unique_times, inverse = np.unique(times, return_inverse=True)
        if unique_times[-1] == 0:
            result[rows] = initial[exp]
            continue

        def rhs(_time, y):
            rate_values = rates * np.prod(np.maximum(y, 0)[None, :] ** left, axis=1)
            return net.T @ rate_values

        solution = solve_ivp(rhs, (0, float(unique_times[-1])), initial[exp],
                             t_eval=unique_times[unique_times > 0], method="LSODA",
                             rtol=1e-6, atol=1e-8)
        if not solution.success:
            raise RuntimeError(f"ODE integration failed: {solution.message}")
        values = np.vstack([initial[exp], solution.y.T]) if unique_times[0] == 0 else solution.y.T
        result[rows] = values[inverse]
    return result


def solve_spectra(data: MatrixData, concentrations_matrix: np.ndarray,
                  scheme: Scheme, extinction: np.ndarray, *, nonnegative: bool = False,
                  fixed_spectra: Mapping[str, np.ndarray] | None = None,
                  smooth: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Solve variable-projection spectra and return active C and S."""
    active = np.flatnonzero(scheme.active)
    if not active.size:
        raise ValueError("Set at least one nonzero extinction coefficient.")
    c = concentrations_matrix[:, active]
    spectra = np.zeros((data.wavelength.size, active.size))
    residual_data = data.matrix.copy()
    free = np.ones(active.size, dtype=bool)
    fixed_spectra = fixed_spectra or {}
    for col, idx in enumerate(active):
        name = scheme.species[idx]
        if name in fixed_spectra:
            shape = np.asarray(fixed_spectra[name], dtype=float)
            if shape.shape != data.wavelength.shape or not np.isfinite(shape).all():
                raise ValueError(f"Fixed spectrum {name} must match wavelength axis.")
            spectra[:, col] = extinction[idx] * shape
            residual_data -= np.outer(c[:, col], spectra[:, col])
            free[col] = False
    if free.sum() == 1:
        col = np.flatnonzero(free)[0]
        x = c[:, col]
        denom = float(np.sum((x - x.mean()) ** 2))
        if denom > 0:
            spectra[:, col] = np.maximum(0, (x - x.mean()) @
                                              (residual_data - residual_data.mean(axis=0)) / denom)
    elif free.sum() > 1:
        for wav in range(data.wavelength.size):
            spectra[wav, free] = (nnls(c[:, free], residual_data[:, wav])[0]
                                   if nonnegative else np.linalg.lstsq(c[:, free], residual_data[:, wav], rcond=None)[0])
    if smooth:
        if not 0 < smooth <= 1:
            raise ValueError("Spectral smoothing span must be in (0, 1].")
        n = spectra.shape[0]
        if n >= 4:
            x = np.arange(n, dtype=float)
            neighborhood = max(4, min(n, int(np.ceil(smooth * n))))
            fitted = np.empty_like(spectra)
            for i in range(n):
                distance = np.abs(x - i)
                bandwidth = np.partition(distance, neighborhood - 1)[neighborhood - 1]
                if bandwidth <= 0:
                    bandwidth = 1.0
                weight = np.maximum(0, 1 - (distance / (bandwidth + 1e-12))**3)**3
                design = np.column_stack((np.ones(n), x - i, (x - i)**2))
                weighted = design * np.sqrt(weight)[:, None]
                fitted[i] = np.linalg.lstsq(weighted, spectra * np.sqrt(weight)[:, None],
                                            rcond=None)[0][0]
            spectra = np.maximum(fitted, 0) if nonnegative else fitted
    for col, idx in enumerate(active):
        scale = np.max(np.abs(spectra[:, col]))
        if scale > 0:
            spectra[:, col] *= extinction[idx] / scale
    return c, spectra


@dataclass(frozen=True)
class KineticResult:
    c_all: np.ndarray
    c: np.ndarray
    s: np.ndarray
    model: np.ndarray
    residual: np.ndarray
    lof: float
    rss: float
    parameters: dict[str, float]
    contracted: np.ndarray
    covariance: np.ndarray | None
    success: bool
    message: str
    active_species: tuple[str, ...]


def _hessian(function, point: np.ndarray, step: float = 1e-3) -> np.ndarray:
    n = point.size
    out = np.zeros((n, n))
    f0 = function(point)
    for i in range(n):
        ei = np.eye(n)[i] * step
        out[i, i] = (function(point + ei) - 2 * f0 + function(point - ei)) / step**2
        for j in range(i):
            ej = np.eye(n)[j] * step
            out[i, j] = out[j, i] = (function(point + ei + ej) - function(point + ei - ej)
                                     - function(point - ei + ej) + function(point - ei - ej)) / (4 * step**2)
    return out


def fit_kinetics(data: MatrixData, scheme: Scheme, *, nonnegative_s: bool = False,
                 weighted: bool = False, sigma: float = 1.0, global_generations: int = 0,
                 population_factor: int = 30, tol: float = 1e-8,
                 spectral_smooth: float = 0.0,
                 fixed_spectra: Mapping[str, np.ndarray] | None = None,
                 start: np.ndarray | None = None) -> KineticResult:
    """MAP fit with variable-projection spectra and truncated-normal log priors."""
    if sigma <= 0 or not np.isfinite(sigma):
        raise ValueError("sigma must be positive.")
    params = variable_parameters(scheme)
    if np.unique(data.delay_id).size != scheme.initial.shape[0]:
        raise ValueError("Scheme experiment count must match selected matrix.")

    def evaluate(z):
        rates, initial, extinction = _expanded(scheme, params, z)
        c_all = concentrations(data, scheme, rates=rates, initial=initial)
        c, s = solve_spectra(data, c_all, scheme, extinction,
                             nonnegative=nonnegative_s, fixed_spectra=fixed_spectra,
                             smooth=spectral_smooth)
        model = c @ s.T
        residual = data.matrix - model
        return c_all, c, s, model, residual

    def objective(z):
        try:
            residual = evaluate(z)[-1]
            sse = float(np.sum(residual**2))
            likelihood = 0.5 * sse / sigma**2 if weighted else 0.5 * residual.size * np.log(max(sse, 1e-30))
            return likelihood + 0.5 * float(np.sum(np.asarray(z) ** 2))
        except (ValueError, RuntimeError, np.linalg.LinAlgError, FloatingPointError):
            return 1e30

    if params:
        x0 = np.zeros(len(params)) if start is None else np.asarray(start, dtype=float)
        if x0.shape != (len(params),):
            raise ValueError("Restart vector length does not match variable parameters.")
        bounds = [(-3., 3.)] * len(params)
        if global_generations > 0:
            global_result = differential_evolution(
                objective, bounds, maxiter=global_generations,
                popsize=max(5, population_factor), polish=False, seed=42)
            x0 = global_result.x
        local = minimize(objective, x0, method="L-BFGS-B", bounds=bounds,
                         options={"ftol": tol, "maxiter": 1000})
        z = local.x
        success, message = bool(local.success), str(local.message)
        if np.any(np.abs(z) >= 2.999):
            covariance = None  # centered local curvature is invalid at a bound
        else:
            try:
                hessian = _hessian(objective, z)
                covariance = np.linalg.inv(hessian) if np.all(np.linalg.eigvalsh(hessian) > 0) else None
            except np.linalg.LinAlgError:
                covariance = None
    else:
        z = np.array([])
        covariance, success, message = None, True, "All scheme parameters fixed."
    c_all, c, s, model, residual = evaluate(z)
    if not success and np.linalg.norm(residual) <= 1e-6 * max(np.linalg.norm(data.matrix), 1e-30):
        success = True
        message = f"Residual below 1e-6 relative norm; optimizer reported: {message}"
    rates, initial, extinction = _expanded(scheme, params, z)
    values = {f"k_{i + 1}": float(rate) for i, rate in enumerate(rates)}
    values.update({f"c0_{name}_{exp + 1}": float(initial[exp, j])
                   for exp in range(initial.shape[0]) for j, name in enumerate(scheme.species)})
    values.update({f"eps_{name}": float(extinction[j]) for j, name in enumerate(scheme.species)})
    rss = float(np.sum(residual**2) / max(np.sum(data.matrix**2), 1e-30))
    return KineticResult(c_all, c, s, model, residual, compute_lof(model, data.matrix), rss,
                         values, z, covariance, success, message,
                         tuple(name for name, active in zip(scheme.species, scheme.active) if active))
