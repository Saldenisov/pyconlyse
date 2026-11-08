"""Spectrokinetic transformers and numerical kernels.

This module ports core SK-Ana SVD + MCR-ALS behavior into sklearn-compatible
DataFrame transformers for use in xrd-analysis pipelines.
"""

from __future__ import annotations

from sys import modules as _refactor_modules

if __package__:
    from .spectrokinetic_transformers_parts_as_1d_float import _bind_spectrokinetic_transformers_parts_as_1d_float
else:
    from spectrokinetic_transformers_parts_as_1d_float import _bind_spectrokinetic_transformers_parts_as_1d_float

if __package__:
    from .spectrokinetic_transformers_parts_run_als_iteration import _bind_spectrokinetic_transformers_parts_run_als_iteration
else:
    from spectrokinetic_transformers_parts_run_als_iteration import _bind_spectrokinetic_transformers_parts_run_als_iteration

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import NMF
from sklearn.isotonic import IsotonicRegression


ArrayLike = Union[np.ndarray, Sequence[float], Sequence[Sequence[float]]]


_spectrokinetic_transformers_parts_as_1d_float = _bind_spectrokinetic_transformers_parts_as_1d_float(_refactor_modules[__name__])
_as_1d_float = _spectrokinetic_transformers_parts_as_1d_float["_as_1d_float"]


_as_2d_float = _spectrokinetic_transformers_parts_as_1d_float["_as_2d_float"]


_normalize_nonneg_vector = _spectrokinetic_transformers_parts_as_1d_float["_normalize_nonneg_vector"]


_normalize_bool_vector = _spectrokinetic_transformers_parts_as_1d_float["_normalize_bool_vector"]


_mask_to_bool = _spectrokinetic_transformers_parts_as_1d_float["_mask_to_bool"]


compute_lof = _spectrokinetic_transformers_parts_as_1d_float["compute_lof"]


convolve_spectrum = _spectrokinetic_transformers_parts_as_1d_float["convolve_spectrum"]


_safe_lstsq = _spectrokinetic_transformers_parts_as_1d_float["_safe_lstsq"]


_safe_solve = _spectrokinetic_transformers_parts_as_1d_float["_safe_solve"]


_moving_average = _spectrokinetic_transformers_parts_as_1d_float["_moving_average"]


enforce_unimodal = _spectrokinetic_transformers_parts_as_1d_float["enforce_unimodal"]


_normalize_column = _spectrokinetic_transformers_parts_as_1d_float["_normalize_column"]


optimize_broadening_single = _spectrokinetic_transformers_parts_as_1d_float["optimize_broadening_single"]


solve_C = _spectrokinetic_transformers_parts_as_1d_float["solve_C"]


solve_S = _spectrokinetic_transformers_parts_as_1d_float["solve_S"]


solve_C_coupled = _spectrokinetic_transformers_parts_as_1d_float["solve_C_coupled"]


solve_S_coupled = _spectrokinetic_transformers_parts_as_1d_float["solve_S_coupled"]


_reconstruct_with_broadening = _spectrokinetic_transformers_parts_as_1d_float["_reconstruct_with_broadening"]


ALSConfig = (dataclass)(_spectrokinetic_transformers_parts_as_1d_float["ALSConfig"])


ALSResult = (dataclass)(_spectrokinetic_transformers_parts_as_1d_float["ALSResult"])
del _spectrokinetic_transformers_parts_as_1d_float


_spectrokinetic_transformers_parts_run_als_iteration = _bind_spectrokinetic_transformers_parts_run_als_iteration(_refactor_modules[__name__])
run_als_iteration = _spectrokinetic_transformers_parts_run_als_iteration["run_als_iteration"]


SpectroSVDTransformer = _spectrokinetic_transformers_parts_run_als_iteration["SpectroSVDTransformer"]
del _spectrokinetic_transformers_parts_run_als_iteration


class MCRALSTransformer(TransformerMixin, BaseEstimator):
    """MCR-ALS transformer for matrix-per-row spectrokinetic data."""

    def __init__(
        self,
        matrix_col: str = "spectro_matrix",
        delay_col: str = "delay_axis",
        wavelength_col: str = "wavelength_axis",
        delay_mask_col: Optional[str] = None,
        wavelength_mask_col: Optional[str] = None,
        decomposition_mode: str = "row",
        group_col: Optional[str] = None,
        group_strategy: str = "tile_delay",
        allow_group_wavelength_interpolation: bool = False,
        n_components: int = 2,
        n_start: Optional[int] = None,
        init_method: str = "svd",
        maxiter: int = 100,
        thresh: float = 1e-3,
        opt_s_first: bool = True,
        nonneg_c: bool = True,
        nonneg_s: Union[bool, Sequence[bool]] = True,
        uni_s: bool = False,
        norm_s: bool = True,
        sum_norm: bool = False,
        norm_mode: str = "intensity",
        smooth: float = 0.0,
        close_c: bool = False,
        w_close_c: float = 0.0,
        presence_mask_col: Optional[str] = None,
        fixed_spectra: Optional[np.ndarray] = None,
        fixed_spectra_col: Optional[str] = None,
        fixed_wavelength_axis: Optional[np.ndarray] = None,
        interpolate_fixed: bool = False,
        hard_s0: bool = True,
        w_hard_s0: float = 1.0,
        correction_spectra: bool = False,
        correction_lambda: float = 0.0,
        broadening: Union[bool, Sequence[bool]] = False,
        broadening_max_pct: float = 10.0,
        random_state: int = 42,
        restart_result: Optional[ALSResult] = None,
    ):
        self.matrix_col = matrix_col
        self.delay_col = delay_col
        self.wavelength_col = wavelength_col
        self.delay_mask_col = delay_mask_col
        self.wavelength_mask_col = wavelength_mask_col

        self.decomposition_mode = decomposition_mode
        self.group_col = group_col
        self.group_strategy = group_strategy
        self.allow_group_wavelength_interpolation = allow_group_wavelength_interpolation

        self.n_components = int(n_components)
        self.n_start = n_start
        self.init_method = init_method
        self.maxiter = int(maxiter)
        self.thresh = float(thresh)
        self.opt_s_first = bool(opt_s_first)

        self.nonneg_c = bool(nonneg_c)
        self.nonneg_s = nonneg_s
        self.uni_s = bool(uni_s)
        self.norm_s = bool(norm_s)
        self.sum_norm = bool(sum_norm)
        self.norm_mode = norm_mode
        self.smooth = float(smooth)

        self.close_c = bool(close_c)
        self.w_close_c = float(w_close_c)
        self.presence_mask_col = presence_mask_col

        self.fixed_spectra = fixed_spectra
        self.fixed_spectra_col = fixed_spectra_col
        self.fixed_wavelength_axis = fixed_wavelength_axis
        self.interpolate_fixed = bool(interpolate_fixed)
        self.hard_s0 = bool(hard_s0)
        self.w_hard_s0 = float(w_hard_s0)

        self.correction_spectra = bool(correction_spectra)
        self.correction_lambda = float(correction_lambda)

        self.broadening = broadening
        self.broadening_max_pct = float(broadening_max_pct)

        self.random_state = int(random_state)
        self.restart_result = restart_result
        self._last_result: Optional[ALSResult] = restart_result

    def fit(self, x: pd.DataFrame, y=None):
        _ = x
        _ = y
        # Mark as fitted for sklearn>=1.6 Pipeline fitted-state checks.
        self.is_fitted_ = True
        return self

    def _extract_masked_matrix(self, row: pd.Series) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        mat = _as_2d_float(row[self.matrix_col], self.matrix_col)
        delay = _as_1d_float(row[self.delay_col], self.delay_col)
        wav = _as_1d_float(row[self.wavelength_col], self.wavelength_col)

        if mat.shape != (delay.size, wav.size):
            raise ValueError(
                f"Matrix shape {mat.shape} must equal (len(delay), len(wavelength)) "
                f"= ({delay.size}, {wav.size})."
            )

        dmask = _mask_to_bool(
            row[self.delay_mask_col] if self.delay_mask_col and self.delay_mask_col in row else None,
            delay.size,
        )
        wmask = _mask_to_bool(
            row[self.wavelength_mask_col]
            if self.wavelength_mask_col and self.wavelength_mask_col in row
            else None,
            wav.size,
        )

        return mat[np.ix_(dmask, wmask)], delay[dmask], wav[wmask]

    def _extract_presence_mask(self, row: pd.Series, n_delay: int, n_components: int) -> Optional[np.ndarray]:
        if self.presence_mask_col is None or self.presence_mask_col not in row:
            return None
        mask = row[self.presence_mask_col]
        if mask is None:
            return None
        arr = np.asarray(mask, dtype=float)
        if arr.ndim == 1:
            if arr.size != n_components:
                raise ValueError(
                    f"Presence mask vector must have length {n_components}, got {arr.size}."
                )
            arr = np.tile(arr[None, :], (n_delay, 1))
        if arr.shape != (n_delay, n_components):
            raise ValueError(
                f"Presence mask must have shape {(n_delay, n_components)}, got {arr.shape}."
            )
        return arr

    def _extract_fixed_spectra(self, row: pd.Series, wav: np.ndarray) -> Optional[np.ndarray]:
        s0 = None
        src_wav = None

        if self.fixed_spectra is not None:
            s0 = np.asarray(self.fixed_spectra, dtype=float)
            if self.fixed_wavelength_axis is not None:
                src_wav = _as_1d_float(self.fixed_wavelength_axis, "fixed_wavelength_axis")
        elif self.fixed_spectra_col is not None and self.fixed_spectra_col in row:
            value = row[self.fixed_spectra_col]
            if isinstance(value, dict):
                s0 = np.asarray(value.get("spectra"), dtype=float)
                wav_dict = value.get("wavelength")
                if wav_dict is not None:
                    src_wav = _as_1d_float(wav_dict, "fixed_spectra wavelength")
            elif value is not None:
                s0 = np.asarray(value, dtype=float)

        if s0 is None:
            return None

        if s0.ndim == 1:
            s0 = s0.reshape(-1, 1)
        if s0.ndim != 2:
            raise ValueError("Fixed spectra must be 1D or 2D.")

        if s0.shape[0] == wav.size:
            return s0

        if not self.interpolate_fixed:
            raise ValueError(
                "Fixed spectra wavelength length mismatch. "
                "Enable interpolate_fixed=True to interpolate onto data wavelength grid."
            )

        if src_wav is None:
            raise ValueError(
                "fixed_wavelength_axis (or per-row wavelength) is required for interpolation."
            )
        if src_wav.size != s0.shape[0]:
            raise ValueError("fixed_wavelength_axis length must match fixed spectra rows.")

        s0_interp = np.zeros((wav.size, s0.shape[1]), dtype=float)
        for j in range(s0.shape[1]):
            s0_interp[:, j] = np.interp(wav, src_wav, s0[:, j])
        return s0_interp

    def _initialize_cs(
        self,
        mat: np.ndarray,
        n_start: int,
        rng: np.random.RandomState,
    ) -> Tuple[np.ndarray, np.ndarray]:
        method = self.init_method.lower()

        if method in {"svd", "seq"}:
            u, _, vt = np.linalg.svd(mat, full_matrices=False)
            c_init = np.abs(u[:, :n_start])
            s_init = np.abs(vt[:n_start, :].T)
            return c_init, s_init

        if method == "pca":
            mat_centered = mat - np.mean(mat, axis=0, keepdims=True)
            u, d, vt = np.linalg.svd(mat_centered, full_matrices=False)
            c_init = np.abs(u[:, :n_start])
            s_init = np.abs(vt[:n_start, :].T)
            for i in range(n_start):
                denom = float(np.max(np.abs(s_init[:, i])))
                if denom > 0:
                    s_init[:, i] = s_init[:, i] * float(d[i]) / denom
            return c_init, s_init

        if method == "nmf":
            u, d, vt = np.linalg.svd(mat, full_matrices=False)
            fmat = np.zeros_like(mat)
            for i in range(min(n_start, d.size)):
                fmat += d[i] * np.outer(u[:, i], vt[i, :])
            nmf = NMF(
                n_components=n_start,
                init="nndsvda",
                random_state=rng.randint(0, 1_000_000),
                max_iter=500,
            )
            w = nmf.fit_transform(np.abs(fmat))
            h = nmf.components_
            return w, h.T

        if method == "restart":
            ref = self._last_result
            if ref is None:
                raise ValueError("init_method='restart' requires restart_result or previous run.")
            if ref.c.shape[0] != mat.shape[0] or ref.s.shape[0] != mat.shape[1]:
                raise ValueError("restart_result shape is incompatible with current matrix.")
            if ref.c.shape[1] < n_start or ref.s.shape[1] < n_start:
                raise ValueError("restart_result has fewer components than requested n_start.")
            return ref.c[:, :n_start].copy(), ref.s[:, :n_start].copy()

        raise ValueError(f"Unsupported init_method '{self.init_method}'.")

    def _build_config(self, n_components: int) -> ALSConfig:
        return ALSConfig(
            n_components=n_components,
            n_start=self.n_start,
            maxiter=self.maxiter,
            thresh=self.thresh,
            init_method=self.init_method,
            opt_s_first=self.opt_s_first,
            nonneg_c=self.nonneg_c,
            nonneg_s=self.nonneg_s,
            uni_s=self.uni_s,
            norm_s=self.norm_s,
            sum_norm=self.sum_norm,
            norm_mode=self.norm_mode,
            smooth=self.smooth,
            close_c=self.close_c,
            w_close_c=self.w_close_c,
            hard_s0=self.hard_s0,
            w_hard_s0=self.w_hard_s0,
            broadening=self.broadening,
            broadening_max_pct=self.broadening_max_pct,
            correction_spectra=self.correction_spectra,
            correction_lambda=self.correction_lambda,
            random_state=self.random_state,
        )

    def _run_single(self,
        mat: np.ndarray,
        delay: np.ndarray,
        wav: np.ndarray,
        row: pd.Series,
    ) -> ALSResult:
        rng = np.random.RandomState(self.random_state)
        n_target = int(self.n_components)
        if n_target < 1:
            raise ValueError("n_components must be >= 1.")

        n_start = self.n_start
        if n_start is None:
            n_start = 2 if self.init_method.lower() == "seq" and n_target > 1 else n_target
        n_start = int(max(1, min(n_start, n_target)))

        s0 = self._extract_fixed_spectra(row, wav)
        n_fixed = 0 if s0 is None else int(s0.shape[1])

        if self.correction_spectra and n_fixed > 0 and n_target < 2 * n_fixed:
            raise ValueError(
                f"n_components={n_target} must be >= 2*n_fixed={2 * n_fixed} for correction mode."
            )

        c_init, s_init = self._initialize_cs(mat, n_start=n_start, rng=rng)

        result: Optional[ALSResult] = None
        c_cur = c_init
        s_cur = s_init
        g_cur = None

        for n in range(n_start, n_target + 1):
            if n > c_cur.shape[1]:
                c_cur = np.hstack([c_cur, np.ones((c_cur.shape[0], 1), dtype=float)])
                s_cur = np.hstack([s_cur, np.ones((s_cur.shape[0], 1), dtype=float)])

            cfg = self._build_config(n_components=n)

            nonneg_s_eff: Union[bool, Sequence[bool]]
            if isinstance(self.nonneg_s, (bool, np.bool_)):
                nonneg_s_eff = bool(self.nonneg_s)
            else:
                vec = np.asarray(self.nonneg_s, dtype=bool)
                if vec.size < n:
                    raise ValueError(
                        f"nonneg_s vector length {vec.size} is smaller than required components {n}."
                    )
                nonneg_s_eff = vec[:n]
            cfg.nonneg_s = nonneg_s_eff

            if isinstance(self.broadening, (bool, np.bool_)):
                cfg.broadening = bool(self.broadening)
            else:
                bvec = np.asarray(self.broadening, dtype=bool)
                if bvec.size < n:
                    raise ValueError(
                        f"broadening vector length {bvec.size} is smaller than required components {n}."
                    )
                cfg.broadening = bvec[:n]

            null_c = self._extract_presence_mask(row, n_delay=mat.shape[0], n_components=n)

            result = run_als_iteration(
                c=c_cur[:, :n],
                psi=mat,
                s=s_cur[:, :n],
                x_c=delay,
                x_s=wav,
                config=cfg,
                null_c=null_c,
                s0=s0,
                g=g_cur[:, :n] if g_cur is not None and g_cur.shape[1] >= n else None,
                n_fixed=n_fixed,
            )

            c_cur = result.c
            s_cur = result.s
            g_cur = result.g

        if result is None:
            raise RuntimeError("ALS run produced no result.")

        self._last_result = result
        return result

    def _align_group_to_wavelength(
        self,
        mat: np.ndarray,
        wav: np.ndarray,
        base_wav: np.ndarray,
    ) -> np.ndarray:
        if np.array_equal(wav, base_wav):
            return mat
        if not self.allow_group_wavelength_interpolation:
            raise ValueError(
                "Group mode requires identical wavelength grids unless "
                "allow_group_wavelength_interpolation=True."
            )
        aligned = np.zeros((mat.shape[0], base_wav.size), dtype=float)
        for i in range(mat.shape[0]):
            aligned[i, :] = np.interp(base_wav, wav, mat[i, :])
        return aligned

    def _run_group(self, gdf: pd.DataFrame) -> Dict[int, Dict[str, Any]]:
        prepared: List[Tuple[int, np.ndarray, np.ndarray, np.ndarray, pd.Series]] = []
        for ridx, row in gdf.iterrows():
            mat, delay, wav = self._extract_masked_matrix(row)
            prepared.append((ridx, mat, delay, wav, row))

        if not prepared:
            return {}

        out_map: Dict[int, Dict[str, Any]] = {}

        if self.group_strategy == "mean":
            base_wav = prepared[0][3]
            base_delay = prepared[0][2]
            mats = []
            for _, mat, delay, wav, _ in prepared:
                if delay.size != base_delay.size or not np.allclose(delay, base_delay):
                    raise ValueError("group_strategy='mean' requires identical delay axes.")
                mats.append(self._align_group_to_wavelength(mat, wav, base_wav))
            mean_mat = np.mean(np.stack(mats, axis=0), axis=0)
            ref_row = prepared[0][4]
            result = self._run_single(mean_mat, base_delay, base_wav, ref_row)

            for ridx, _, _, _, _ in prepared:
                out_map[ridx] = {
                    "als_C": result.c,
                    "als_S": result.s,
                    "als_model": result.model,
                    "als_residual": result.resid,
                    "als_lof_pct": result.lof,
                    "als_rss": result.rss,
                    "als_iter": result.iter,
                    "als_converged": result.converged,
                    "als_G": result.g,
                    "als_broadening_enabled": bool(
                        result.broadening_vec is not None and np.any(result.broadening_vec)
                    ),
                    "als_meta": {
                        "decomposition_mode": "group",
                        "group_strategy": "mean",
                        "group_size": len(prepared),
                        "n_components": result.s.shape[1],
                        "n_fixed": result.n_fixed,
                        "init_method": self.init_method,
                        "constraints": {
                            "nonneg_c": self.nonneg_c,
                            "nonneg_s": (
                                np.asarray(self.nonneg_s, dtype=bool).tolist()
                                if not isinstance(self.nonneg_s, (bool, np.bool_))
                                else bool(self.nonneg_s)
                            ),
                            "uni_s": self.uni_s,
                            "norm_s": self.norm_s,
                            "sum_norm": self.sum_norm,
                            "norm_mode": self.norm_mode,
                            "smooth": self.smooth,
                            "close_c": self.close_c,
                            "w_close_c": self.w_close_c,
                        },
                        "correction_spectra": self.correction_spectra,
                        "broadening": self.broadening,
                    },
                }
            return out_map

        if self.group_strategy != "tile_delay":
            raise ValueError(
                f"Unsupported group_strategy '{self.group_strategy}'. "
                "Expected 'tile_delay' or 'mean'."
            )

        base_wav = prepared[0][3]
        mats: List[np.ndarray] = []
        delays: List[np.ndarray] = []
        slices: List[Tuple[int, int, int, pd.Series]] = []

        start = 0
        for ridx, mat, delay, wav, row in prepared:
            mat_aligned = self._align_group_to_wavelength(mat, wav, base_wav)
            mats.append(mat_aligned)
            delays.append(delay)
            end = start + mat_aligned.shape[0]
            slices.append((ridx, start, end, row))
            start = end

        tile_mat = np.vstack(mats)
        tile_delay = np.concatenate(delays)
        ref_row = prepared[0][4]
        result = self._run_single(tile_mat, tile_delay, base_wav, ref_row)

        for ridx, s0, s1, _row in slices:
            c_slice = result.c[s0:s1, :]
            model_slice = result.model[s0:s1, :]
            resid_slice = result.resid[s0:s1, :]
            g_slice = result.g[s0:s1, :] if result.g is not None else None

            out_map[ridx] = {
                "als_C": c_slice,
                "als_S": result.s,
                "als_model": model_slice,
                "als_residual": resid_slice,
                "als_lof_pct": result.lof,
                "als_rss": result.rss,
                "als_iter": result.iter,
                "als_converged": result.converged,
                "als_G": g_slice,
                "als_broadening_enabled": bool(
                    result.broadening_vec is not None and np.any(result.broadening_vec)
                ),
                "als_meta": {
                    "decomposition_mode": "group",
                    "group_strategy": "tile_delay",
                    "group_size": len(prepared),
                    "n_components": result.s.shape[1],
                    "n_fixed": result.n_fixed,
                    "init_method": self.init_method,
                    "constraints": {
                        "nonneg_c": self.nonneg_c,
                        "nonneg_s": (
                            np.asarray(self.nonneg_s, dtype=bool).tolist()
                            if not isinstance(self.nonneg_s, (bool, np.bool_))
                            else bool(self.nonneg_s)
                        ),
                        "uni_s": self.uni_s,
                        "norm_s": self.norm_s,
                        "sum_norm": self.sum_norm,
                        "norm_mode": self.norm_mode,
                        "smooth": self.smooth,
                        "close_c": self.close_c,
                        "w_close_c": self.w_close_c,
                    },
                    "correction_spectra": self.correction_spectra,
                    "broadening": self.broadening,
                    "tile_slice": (s0, s1),
                },
            }

        return out_map

    def transform(self, x: pd.DataFrame) -> pd.DataFrame:
        out = x.copy()

        for col in [
            "als_C",
            "als_S",
            "als_model",
            "als_residual",
            "als_lof_pct",
            "als_rss",
            "als_iter",
            "als_converged",
            "als_G",
            "als_broadening_enabled",
            "als_meta",
        ]:
            out[col] = None

        if self.decomposition_mode == "row":
            for idx, row in out.iterrows():
                mat, delay, wav = self._extract_masked_matrix(row)
                result = self._run_single(mat, delay, wav, row)

                out.at[idx, "als_C"] = result.c
                out.at[idx, "als_S"] = result.s
                out.at[idx, "als_model"] = result.model
                out.at[idx, "als_residual"] = result.resid
                out.at[idx, "als_lof_pct"] = result.lof
                out.at[idx, "als_rss"] = result.rss
                out.at[idx, "als_iter"] = result.iter
                out.at[idx, "als_converged"] = result.converged
                out.at[idx, "als_G"] = result.g
                out.at[idx, "als_broadening_enabled"] = bool(
                    result.broadening_vec is not None and np.any(result.broadening_vec)
                )
                out.at[idx, "als_meta"] = {
                    "decomposition_mode": "row",
                    "n_components": result.s.shape[1],
                    "n_fixed": result.n_fixed,
                    "init_method": self.init_method,
                    "constraints": {
                        "nonneg_c": self.nonneg_c,
                        "nonneg_s": (
                            np.asarray(self.nonneg_s, dtype=bool).tolist()
                            if not isinstance(self.nonneg_s, (bool, np.bool_))
                            else bool(self.nonneg_s)
                        ),
                        "uni_s": self.uni_s,
                        "norm_s": self.norm_s,
                        "sum_norm": self.sum_norm,
                        "norm_mode": self.norm_mode,
                        "smooth": self.smooth,
                        "close_c": self.close_c,
                        "w_close_c": self.w_close_c,
                    },
                    "correction_spectra": self.correction_spectra,
                    "broadening": self.broadening,
                }

            return out

        if self.decomposition_mode != "group":
            raise ValueError(
                f"Unsupported decomposition_mode '{self.decomposition_mode}'. "
                "Expected 'row' or 'group'."
            )

        if self.group_col is None or self.group_col not in out.columns:
            raise ValueError("group_col must be provided and present when decomposition_mode='group'.")

        for _g, gdf in out.groupby(self.group_col, sort=False):
            mapping = self._run_group(gdf)
            for ridx, payload in mapping.items():
                for col, val in payload.items():
                    out.at[ridx, col] = val

        return out


__all__ = [
    "ALSConfig",
    "ALSResult",
    "SpectroSVDTransformer",
    "MCRALSTransformer",
    "compute_lof",
    "convolve_spectrum",
    "optimize_broadening_single",
    "solve_C",
    "solve_S",
    "solve_C_coupled",
    "solve_S_coupled",
    "run_als_iteration",
    "enforce_unimodal",
]
