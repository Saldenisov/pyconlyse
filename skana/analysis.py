"""Single-matrix analysis API over the transferred numerical kernels."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from spectrokinetic_transformers import ALSResult, MCRALSTransformer, compute_lof, convolve_spectrum

from .matrix import MatrixData


@dataclass(frozen=True)
class SVDResult:
    u: np.ndarray
    singular_values: np.ndarray
    vt: np.ndarray
    rank: int
    model: np.ndarray
    residual: np.ndarray
    statistics: pd.DataFrame


def svd(data: MatrixData, rank: int = 2, max_rank: int = 10) -> SVDResult:
    """SVD of canonical delay × wavelength matrix, without centering."""
    matrix = data.matrix
    max_rank = min(int(max_rank), *matrix.shape)
    if not (1 <= rank <= max_rank):
        raise ValueError(f"rank must be between 1 and {max_rank}.")
    u, values, vt = np.linalg.svd(matrix, full_matrices=False)
    u, values, vt = u[:, :max_rank], values[:max_rank], vt[:max_rank, :]
    rows = []
    for k in range(1, max_rank + 1):
        model = (u[:, :k] * values[:k]) @ vt[:k, :]
        residual = matrix - model
        rows.append({"rank": k, "singular_value": values[k - 1],
                     "lof_pct": compute_lof(model, matrix),
                     "residual_sd": float(np.std(residual, ddof=1))})
    model = (u[:, :rank] * values[:rank]) @ vt[:rank, :]
    return SVDResult(u, values, vt, rank, model, matrix - model, pd.DataFrame(rows))


def als(data: MatrixData, *, n_components: int = 2,
        init_method: str = "svd", maxiter: int = 1000, thresh: float = 1e-6,
        opt_s_first: bool = False, nonneg_c: bool = True,
        nonneg_s: bool | list[bool] = True, uni_s: bool = False,
        norm_s: bool = True, sum_norm: bool = False, norm_mode: str = "intensity",
        smooth: float = 0.0, close_c: bool = False, w_close_c: float = 0.0,
        filtered_rank: int | None = None, presence_mask: np.ndarray | None = None,
        fixed_spectra: np.ndarray | None = None, hard_s0: bool = True,
        w_hard_s0: float = 1.0, correction_spectra: bool = False,
        correction_lambda: float = 0.0, broadening: bool | list[bool] = False,
        broadening_max_pct: float = 10.0, restart_result: ALSResult | None = None,
        random_state: int = 42) -> ALSResult:
    """Run transferred MCR-ALS core on one matrix, with R-style defaults.

    ``thresh`` and ``w_close_c`` are linear values; the UI converts R's log10
    sliders. Results retain the source module's ``ALSResult`` type.
    """
    if not 1 <= n_components <= min(data.matrix.shape):
        raise ValueError("n_components must fit matrix dimensions.")
    matrix = svd(data, filtered_rank).model if filtered_rank is not None else data.matrix
    if fixed_spectra is not None:
        fixed_spectra = np.asarray(fixed_spectra, dtype=float).copy()
        if fixed_spectra.ndim == 1:
            fixed_spectra = fixed_spectra[:, None]
        if fixed_spectra.ndim != 2 or fixed_spectra.shape[0] != data.wavelength.size:
            raise ValueError("Fixed spectra must have one row per wavelength.")
        if not np.isfinite(fixed_spectra).all():
            raise ValueError("Fixed spectra must be finite.")
        if norm_s:
            if sum_norm or norm_mode == "l1":
                scale = np.sum(np.abs(fixed_spectra), axis=0)
            else:
                scale = np.max(np.abs(fixed_spectra), axis=0)
            fixed_spectra /= np.where(scale > 0, scale, 1)[None, :]
    payload = pd.DataFrame([{
        "spectro_matrix": matrix,
        "delay_axis": data.delay,
        "wavelength_axis": data.wavelength,
        "presence": presence_mask,
    }])
    transformer = MCRALSTransformer(
        n_components=n_components, init_method=init_method, maxiter=maxiter,
        thresh=thresh, opt_s_first=opt_s_first, nonneg_c=nonneg_c,
        nonneg_s=nonneg_s, uni_s=uni_s, norm_s=norm_s, sum_norm=sum_norm,
        norm_mode=norm_mode, smooth=smooth, close_c=close_c, w_close_c=w_close_c,
        presence_mask_col="presence", fixed_spectra=fixed_spectra,
        hard_s0=hard_s0, w_hard_s0=w_hard_s0,
        correction_spectra=correction_spectra, correction_lambda=correction_lambda,
        broadening=broadening, broadening_max_pct=broadening_max_pct,
        restart_result=restart_result, random_state=random_state,
    )
    transformer.transform(payload)
    result = transformer._last_result
    if result is None:
        raise RuntimeError("ALS did not return a result.")
    return result


def als_contributions(result: ALSResult) -> list[np.ndarray]:
    """Return one delay × wavelength model matrix per ALS component."""
    if result.g is None or result.broadening_vec is None or not np.any(result.broadening_vec):
        return [np.outer(result.c[:, i], result.s[:, i])
                for i in range(result.s.shape[1])]
    matrices = []
    for i in range(result.s.shape[1]):
        if result.broadening_vec[i]:
            rows = [result.c[j, i] * convolve_spectrum(result.s[:, i], result.g[j, i])
                    for j in range(result.c.shape[0])]
            matrices.append(np.vstack(rows))
        else:
            matrices.append(np.outer(result.c[:, i], result.s[:, i]))
    return matrices
