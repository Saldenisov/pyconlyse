"""Implementation for run_als_iteration and related operations."""

from __future__ import annotations


def _bind_spectrokinetic_transformers_parts_run_als_iteration(api):
    """Bind implementation to the owning module and its runtime state."""

    def run_als_iteration(
        c: np.ndarray,
        psi: np.ndarray,
        s: np.ndarray,
        x_c: np.ndarray,
        x_s: np.ndarray,
        config: ALSConfig,
        null_c: Optional[np.ndarray] = None,
        s0: Optional[np.ndarray] = None,
        g: Optional[np.ndarray] = None,
        n_fixed: int = 0,
    ) -> ALSResult:
        """Main ALS iterative loop (standard, broadening, or coupled mode)."""
        c = api._as_2d_float(c, "c")
        psi = api._as_2d_float(psi, "psi")
        s = api._as_2d_float(s, "s")
        _ = api._as_1d_float(x_c, "x_c")
        _ = api._as_1d_float(x_s, "x_s")

        n_components = c.shape[1]
        if n_components != s.shape[1]:
            raise ValueError("C and S must have identical component count.")

        broadening_vec = api._normalize_bool_vector(config.broadening, n_components)
        broadening_enabled = bool(api.np.any(broadening_vec))

        if config.correction_spectra and broadening_enabled:
            raise ValueError(
                "Correction-spectra and broadening modes are mutually exclusive in v1."
            )

        if broadening_enabled:
            if g is None:
                sigma_init = 0.001 * s.shape[0]
                g = api.np.zeros_like(c)
                for k in range(n_components):
                    if broadening_vec[k]:
                        g[:, k] = sigma_init
            else:
                g = api._as_2d_float(g, "g")
                if g.shape != c.shape:
                    raise ValueError("G must have same shape as C when broadening is enabled.")

        model = api._reconstruct_with_broadening(c, s, g, broadening_vec)
        resid = psi - model

        denom = max(float(api.np.sum(psi**2)), 1e-30)
        oldrss = float(api.np.sum(resid**2) / denom)
        rd = 1e20

        b = 1 if config.opt_s_first else 0
        iter_idx = 0
        min_steps = 3 if broadening_enabled else 2

        while iter_idx < config.maxiter and (iter_idx < min_steps or abs(rd) > config.thresh):
            iter_idx += 1

            if config.correction_spectra and n_fixed > 0:
                if iter_idx % 2 == b:
                    s = api.solve_S_coupled(
                        c=c,
                        data=psi,
                        s=s,
                        x_s=x_s,
                        nonneg_s=config.nonneg_s,
                        uni_s=config.uni_s,
                        s0=s0,
                        norm_s=config.norm_s,
                        smooth=config.smooth,
                        sum_s=config.sum_norm,
                        hard_s0=config.hard_s0,
                        w_hard_s0=config.w_hard_s0,
                        n_fixed=n_fixed,
                        lambda_corr=config.correction_lambda,
                        norm_mode=config.norm_mode,
                    )
                else:
                    c = api.solve_C_coupled(
                        s=s,
                        data=psi,
                        c=c,
                        nonneg_c=config.nonneg_c,
                        null_c=null_c,
                        close_c=config.close_c,
                        w_close_c=config.w_close_c,
                        n_fixed=n_fixed,
                    )
            elif broadening_enabled:
                step = iter_idx % 3
                if step == (b % 3):
                    s = api.solve_S(
                        c=c,
                        data=psi,
                        s=s,
                        x_s=x_s,
                        nonneg_s=config.nonneg_s,
                        uni_s=config.uni_s,
                        s0=s0,
                        norm_s=config.norm_s,
                        smooth=config.smooth,
                        sum_s=config.sum_norm,
                        hard_s0=config.hard_s0,
                        w_hard_s0=config.w_hard_s0,
                        norm_mode=config.norm_mode,
                        g=g,
                    )
                elif step == ((b + 1) % 3):
                    c = api.solve_C(
                        s=s,
                        data=psi,
                        c=c,
                        nonneg_c=config.nonneg_c,
                        null_c=null_c,
                        close_c=config.close_c,
                        w_close_c=config.w_close_c,
                        g=g,
                    )
                else:
                    sigma_max = (config.broadening_max_pct / 100.0) * s.shape[0]
                    for i in range(psi.shape[0]):
                        g_opt = api.optimize_broadening_single(
                            data_row=psi[i, :],
                            c_row=c[i, :],
                            s=s,
                            g_init=g[i, :],
                            sigma_max=sigma_max,
                            broadening_vec=broadening_vec,
                        )
                        for k in range(n_components):
                            if broadening_vec[k]:
                                g[i, k] = g_opt[k]
            else:
                if iter_idx % 2 == b:
                    s = api.solve_S(
                        c=c,
                        data=psi,
                        s=s,
                        x_s=x_s,
                        nonneg_s=config.nonneg_s,
                        uni_s=config.uni_s,
                        s0=s0,
                        norm_s=config.norm_s,
                        smooth=config.smooth,
                        sum_s=config.sum_norm,
                        hard_s0=config.hard_s0,
                        w_hard_s0=config.w_hard_s0,
                        norm_mode=config.norm_mode,
                        g=None,
                    )
                else:
                    c = api.solve_C(
                        s=s,
                        data=psi,
                        c=c,
                        nonneg_c=config.nonneg_c,
                        null_c=null_c,
                        close_c=config.close_c,
                        w_close_c=config.w_close_c,
                        g=None,
                    )

            model = api._reconstruct_with_broadening(c, s, g, broadening_vec)
            resid = psi - model

            rss = float(api.np.sum(resid**2) / denom)
            if oldrss <= 0:
                rd = 0.0
            else:
                rd = (oldrss - rss) / oldrss
            oldrss = rss

            if not api.np.isfinite(rd):
                raise RuntimeError("ALS diverged: non-finite relative difference.")

        lof = api.compute_lof(model, psi)
        converged = bool(abs(rd) <= config.thresh)
        msg = (
            f"Dimension: {s.shape[1]}, |RD|={abs(rd):.3g}, "
            f"threshold={config.thresh:g}, LOF={lof:.3g}%"
        )

        return api.ALSResult(
            c=c,
            s=s,
            model=model,
            resid=resid,
            rss=float(oldrss),
            iter=iter_idx,
            lof=float(lof),
            converged=converged,
            msg=msg,
            g=g,
            broadening_vec=broadening_vec,
            n_fixed=int(n_fixed),
            lambda_corr=float(config.correction_lambda),
        )

    run_als_iteration.__module__ = api.__name__
    run_als_iteration.__qualname__ = "run_als_iteration"

    class SpectroSVDTransformer(api.TransformerMixin, api.BaseEstimator):
        """SVD transformer for matrix-per-row spectrokinetic data."""

        def __init__(
            self,
            matrix_col: str = "spectro_matrix",
            delay_col: str = "delay_axis",
            wavelength_col: str = "wavelength_axis",
            delay_mask_col: Optional[str] = None,
            wavelength_mask_col: Optional[str] = None,
            max_rank: int = 10,
            model_rank: Optional[int] = None,
        ):
            self.matrix_col = matrix_col
            self.delay_col = delay_col
            self.wavelength_col = wavelength_col
            self.delay_mask_col = delay_mask_col
            self.wavelength_mask_col = wavelength_mask_col
            self.max_rank = int(max_rank)
            self.model_rank = model_rank

        def fit(self, x: pd.DataFrame, y=None):
            _ = x
            _ = y
            # Mark as fitted for sklearn>=1.6 Pipeline fitted-state checks.
            self.is_fitted_ = True
            return self

        def _extract_masked_matrix(self, row: pd.Series) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
            mat = api._as_2d_float(row[self.matrix_col], self.matrix_col)
            delay = api._as_1d_float(row[self.delay_col], self.delay_col)
            wav = api._as_1d_float(row[self.wavelength_col], self.wavelength_col)

            if mat.shape != (delay.size, wav.size):
                raise ValueError(
                    f"Matrix shape {mat.shape} must equal (len(delay), len(wavelength)) "
                    f"= ({delay.size}, {wav.size})."
                )

            dmask = api._mask_to_bool(
                row[self.delay_mask_col] if self.delay_mask_col and self.delay_mask_col in row else None,
                delay.size,
            )
            wmask = api._mask_to_bool(
                row[self.wavelength_mask_col]
                if self.wavelength_mask_col and self.wavelength_mask_col in row
                else None,
                wav.size,
            )

            return mat[api.np.ix_(dmask, wmask)], delay[dmask], wav[wmask]

        @staticmethod
        def _recommended_rank(svals: np.ndarray) -> int:
            if svals.size == 0:
                return 1
            if svals.size < 4:
                return int(min(1, svals.size))
            tail_start = max(1, int(api.np.floor(2 * svals.size / 3)))
            baseline = float(api.np.mean(svals[tail_start:]))
            if baseline <= 0:
                return 1
            idx = api.np.where(svals > 1.5 * baseline)[0]
            if idx.size == 0:
                return 1
            return int(idx[-1] + 1)

        def transform(self, x: pd.DataFrame) -> pd.DataFrame:
            out = x.copy()

            for col in [
                "svd_u",
                "svd_s",
                "svd_vt",
                "svd_lof_curve",
                "svd_sd_resid_curve",
                "svd_model_rank_matrix",
                "svd_residual_rank_matrix",
                "svd_recommended_rank",
            ]:
                out[col] = None

            for idx, row in out.iterrows():
                mat, _, _ = self._extract_masked_matrix(row)
                n_rank = min(self.max_rank, min(mat.shape))
                u, svals, vt = api.np.linalg.svd(mat, full_matrices=False)

                u = u[:, :n_rank]
                svals = svals[:n_rank]
                vt = vt[:n_rank, :]

                lof_curve: List[float] = []
                sd_curve: List[float] = []

                model = api.np.zeros_like(mat)
                for r in range(n_rank):
                    model = model + svals[r] * api.np.outer(u[:, r], vt[r, :])
                    resid = mat - model
                    lof_curve.append(api.compute_lof(model, mat))
                    sd_curve.append(float(api.np.std(resid)))

                rec_rank = self._recommended_rank(svals)
                rank_for_model = int(self.model_rank) if self.model_rank is not None else rec_rank
                rank_for_model = max(1, min(rank_for_model, n_rank))

                model_rank = api.np.zeros_like(mat)
                for r in range(rank_for_model):
                    model_rank += svals[r] * api.np.outer(u[:, r], vt[r, :])

                out.at[idx, "svd_u"] = u
                out.at[idx, "svd_s"] = svals
                out.at[idx, "svd_vt"] = vt
                out.at[idx, "svd_lof_curve"] = lof_curve
                out.at[idx, "svd_sd_resid_curve"] = sd_curve
                out.at[idx, "svd_model_rank_matrix"] = model_rank
                out.at[idx, "svd_residual_rank_matrix"] = mat - model_rank
                out.at[idx, "svd_recommended_rank"] = rec_rank

            return out

    SpectroSVDTransformer.__module__ = api.__name__
    SpectroSVDTransformer.__qualname__ = "SpectroSVDTransformer"

    return {
        "run_als_iteration": run_als_iteration,
        "SpectroSVDTransformer": SpectroSVDTransformer,
    }
