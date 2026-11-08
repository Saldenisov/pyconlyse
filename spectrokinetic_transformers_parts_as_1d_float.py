"""Implementation for _as_1d_float and related operations."""

from __future__ import annotations


def _bind_spectrokinetic_transformers_parts_as_1d_float(api):
    """Bind implementation to the owning module and its runtime state."""

    def _as_1d_float(arr: ArrayLike, name: str) -> np.ndarray:
        out = api.np.asarray(arr, dtype=float)
        if out.ndim != 1:
            raise ValueError(f"{name} must be a 1D array, got shape {out.shape}.")
        return out

    _as_1d_float.__module__ = api.__name__
    _as_1d_float.__qualname__ = "_as_1d_float"

    def _as_2d_float(arr: ArrayLike, name: str) -> np.ndarray:
        out = api.np.asarray(arr, dtype=float)
        if out.ndim != 2:
            raise ValueError(f"{name} must be a 2D array, got shape {out.shape}.")
        return out

    _as_2d_float.__module__ = api.__name__
    _as_2d_float.__qualname__ = "_as_2d_float"

    def _normalize_nonneg_vector(nonneg: Union[bool, Sequence[bool]], n_cols: int) -> np.ndarray:
        if isinstance(nonneg, (bool, api.np.bool_)):
            return api.np.full(n_cols, bool(nonneg), dtype=bool)
        vec = api.np.asarray(nonneg, dtype=bool)
        if vec.ndim != 1 or vec.size != n_cols:
            raise ValueError(
                f"nonneg_s must have length {n_cols}; got shape {vec.shape}."
            )
        return vec

    _normalize_nonneg_vector.__module__ = api.__name__
    _normalize_nonneg_vector.__qualname__ = "_normalize_nonneg_vector"

    def _normalize_bool_vector(flag: Union[bool, Sequence[bool]], n_cols: int) -> np.ndarray:
        if isinstance(flag, (bool, api.np.bool_)):
            return api.np.full(n_cols, bool(flag), dtype=bool)
        vec = api.np.asarray(flag, dtype=bool)
        if vec.ndim != 1 or vec.size != n_cols:
            raise ValueError(f"Boolean vector must have length {n_cols}, got {vec.shape}.")
        return vec

    _normalize_bool_vector.__module__ = api.__name__
    _normalize_bool_vector.__qualname__ = "_normalize_bool_vector"

    def _mask_to_bool(mask: Optional[ArrayLike], n: int) -> np.ndarray:
        if mask is None:
            return api.np.ones(n, dtype=bool)
        m = api.np.asarray(mask)
        if m.ndim != 1 or m.size != n:
            raise ValueError(f"Mask must have length {n}; got shape {m.shape}.")
        if m.dtype == bool:
            return m.copy()
        if api.np.issubdtype(m.dtype, api.np.floating):
            return ~api.np.isnan(m)
        return m.astype(bool)

    _mask_to_bool.__module__ = api.__name__
    _mask_to_bool.__qualname__ = "_mask_to_bool"

    def compute_lof(model: np.ndarray, data: np.ndarray) -> float:
        """Compute lack-of-fit percentage, matching SK-Ana convention."""
        model = api._as_2d_float(model, "model")
        data = api._as_2d_float(data, "data")
        denom = float(api.np.sum(data**2))
        if denom <= 0:
            return 100.0
        return float(100.0 * api.np.sqrt(api.np.sum((data - model) ** 2) / denom))

    compute_lof.__module__ = api.__name__
    compute_lof.__qualname__ = "compute_lof"

    def convolve_spectrum(spectrum: np.ndarray, sigma: float) -> np.ndarray:
        """Apply Gaussian convolution to a 1D spectrum."""
        spectrum = api._as_1d_float(spectrum, "spectrum")
        if not api.np.isfinite(sigma) or sigma <= 0:
            return spectrum.copy()

        kernel_size = max(3, int(api.np.ceil(3 * sigma)))
        x = api.np.arange(-kernel_size, kernel_size + 1, dtype=float)
        kernel = api.np.exp(-(x**2) / (2 * sigma**2))
        kernel_sum = float(kernel.sum())
        if kernel_sum <= 0:
            return spectrum.copy()
        kernel /= kernel_sum

        padded = api.np.pad(spectrum, (kernel_size, kernel_size), mode="edge")
        conv = api.np.convolve(padded, kernel, mode="same")
        return conv[kernel_size : kernel_size + spectrum.size]

    convolve_spectrum.__module__ = api.__name__
    convolve_spectrum.__qualname__ = "convolve_spectrum"

    def _safe_lstsq(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        try:
            sol, *_ = api.np.linalg.lstsq(a, b, rcond=None)
        except api.np.linalg.LinAlgError:
            sol = api.np.zeros(a.shape[1], dtype=float)
        return api.np.asarray(sol, dtype=float)

    _safe_lstsq.__module__ = api.__name__
    _safe_lstsq.__qualname__ = "_safe_lstsq"

    def _safe_solve(a: np.ndarray, b: np.ndarray, nonneg: bool) -> np.ndarray:
        if nonneg:
            try:
                sol, _ = api.nnls(a, b)
            except Exception:
                sol = api.np.zeros(a.shape[1], dtype=float)
        else:
            sol = api._safe_lstsq(a, b)
        return api.np.asarray(sol, dtype=float)

    _safe_solve.__module__ = api.__name__
    _safe_solve.__qualname__ = "_safe_solve"

    def _moving_average(y: np.ndarray, span: float) -> np.ndarray:
        if span <= 0:
            return y.copy()
        n = y.size
        if n <= 2:
            return y.copy()
        w = max(3, int(round(span * n)))
        if w % 2 == 0:
            w += 1
        if w > n:
            w = n if n % 2 == 1 else n - 1
        if w <= 1:
            return y.copy()
        pad = w // 2
        y_pad = api.np.pad(y, (pad, pad), mode="reflect")
        kernel = api.np.ones(w, dtype=float) / float(w)
        return api.np.convolve(y_pad, kernel, mode="valid")

    _moving_average.__module__ = api.__name__
    _moving_average.__qualname__ = "_moving_average"

    def enforce_unimodal(y: np.ndarray) -> np.ndarray:
        """Project a vector onto a unimodal shape via isotonic segments."""
        y = api._as_1d_float(y, "y")
        if y.size <= 2:
            return y.copy()

        mode_idx = int(api.np.nanargmax(y))
        left_x = api.np.arange(mode_idx + 1, dtype=float)
        right_x = api.np.arange(y.size - mode_idx, dtype=float)

        iso_inc = api.IsotonicRegression(increasing=True, out_of_bounds="clip")
        left = iso_inc.fit_transform(left_x, y[: mode_idx + 1])

        # Decreasing constraint on right by fitting increasing on reversed sequence.
        right_rev = iso_inc.fit_transform(right_x, y[mode_idx:][::-1])
        right = right_rev[::-1]

        out = y.copy()
        out[: mode_idx + 1] = left
        out[mode_idx:] = right
        out[mode_idx] = 0.5 * (left[-1] + right[0])
        return out

    enforce_unimodal.__module__ = api.__name__
    enforce_unimodal.__qualname__ = "enforce_unimodal"

    def _normalize_column(col: np.ndarray, sum_norm: bool, norm_mode: str) -> np.ndarray:
        if sum_norm or norm_mode == "l1":
            denom = float(api.np.sum(api.np.abs(col)))
        else:
            denom = float(api.np.max(api.np.abs(col)))
        if denom <= 0:
            return col
        return col / denom

    _normalize_column.__module__ = api.__name__
    _normalize_column.__qualname__ = "_normalize_column"

    def optimize_broadening_single(
        data_row: np.ndarray,
        c_row: np.ndarray,
        s: np.ndarray,
        g_init: np.ndarray,
        sigma_max: Optional[float] = None,
        broadening_vec: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Three-stage grid refinement for broadening sigmas."""
        data_row = api._as_1d_float(data_row, "data_row")
        c_row = api._as_1d_float(c_row, "c_row")
        s = api._as_2d_float(s, "s")
        g_init = api._as_1d_float(g_init, "g_init")

        n_components = s.shape[1]
        if c_row.size != n_components:
            raise ValueError("c_row length must match number of components.")
        if g_init.size != n_components:
            raise ValueError("g_init length must match number of components.")

        sigma_min = 0.0
        if sigma_max is None:
            sigma_max = 0.10 * s.shape[0]
        sigma_max = float(max(sigma_max, 1e-12))

        if broadening_vec is None:
            broadening_vec = api.np.ones(n_components, dtype=bool)
        else:
            broadening_vec = api._normalize_bool_vector(broadening_vec, n_components)

        def eval_error(g_vec: np.ndarray) -> float:
            recon = api.np.zeros_like(data_row, dtype=float)
            for j in range(n_components):
                recon += c_row[j] * api.convolve_spectrum(s[:, j], float(g_vec[j]))
            return float(api.np.sum((data_row - recon) ** 2))

        g_opt = g_init.copy()

        for k in range(n_components):
            if not broadening_vec[k]:
                continue

            best_sigma = float(g_opt[k])
            best_error = api.np.inf

            grid_coarse = api.np.linspace(sigma_min, sigma_max, num=10)
            for sigma_test in grid_coarse:
                g_tmp = g_opt.copy()
                g_tmp[k] = sigma_test
                err = eval_error(g_tmp)
                if err < best_error:
                    best_error = err
                    best_sigma = float(sigma_test)

            range_medium = (sigma_max - sigma_min) * 0.1
            grid_medium = api.np.linspace(
                max(sigma_min, best_sigma - range_medium),
                min(sigma_max, best_sigma + range_medium),
                num=10,
            )
            for sigma_test in grid_medium:
                g_tmp = g_opt.copy()
                g_tmp[k] = sigma_test
                err = eval_error(g_tmp)
                if err < best_error:
                    best_error = err
                    best_sigma = float(sigma_test)

            range_fine = (sigma_max - sigma_min) * 0.02
            grid_fine = api.np.linspace(
                max(sigma_min, best_sigma - range_fine),
                min(sigma_max, best_sigma + range_fine),
                num=10,
            )
            for sigma_test in grid_fine:
                g_tmp = g_opt.copy()
                g_tmp[k] = sigma_test
                err = eval_error(g_tmp)
                if err < best_error:
                    best_error = err
                    best_sigma = float(sigma_test)

            g_opt[k] = best_sigma

        return g_opt

    optimize_broadening_single.__module__ = api.__name__
    optimize_broadening_single.__qualname__ = "optimize_broadening_single"

    def solve_C(
        s: np.ndarray,
        data: np.ndarray,
        c: np.ndarray,
        nonneg_c: bool = True,
        null_c: Optional[np.ndarray] = None,
        close_c: bool = False,
        w_close_c: float = 0.0,
        g: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Solve for C given S and data, row-wise."""
        s = api._as_2d_float(s, "s")
        data = api._as_2d_float(data, "data")
        c = api._as_2d_float(c, "c")

        if data.shape[0] != c.shape[0]:
            raise ValueError("C row count must match data row count.")
        if s.shape[1] != c.shape[1]:
            raise ValueError("S component count must match C columns.")
        if data.shape[1] != s.shape[0]:
            raise ValueError("Data wavelength dimension must match S rows.")

        c_out = c.copy()
        use_broadening = g is not None and api.np.asarray(g).shape == c.shape
        if use_broadening:
            g = api._as_2d_float(g, "g")

        for i in range(data.shape[0]):
            s_work = s.copy()
            if use_broadening:
                for k in range(s.shape[1]):
                    s_work[:, k] = api.convolve_spectrum(s[:, k], float(g[i, k]))

            b = data[i, :]
            if close_c and w_close_c != 0:
                s_aug = api.np.vstack([s_work, api.np.full((1, s_work.shape[1]), w_close_c)])
                b_aug = api.np.concatenate([b, api.np.array([w_close_c], dtype=float)])
            else:
                s_aug = s_work
                b_aug = b

            c_out[i, :] = api._safe_solve(s_aug, b_aug, nonneg=nonneg_c)

        if null_c is not None:
            null_c = api._as_2d_float(null_c, "null_c")
            if null_c.shape == c_out.shape:
                c_out = c_out * null_c

        return c_out

    solve_C.__module__ = api.__name__
    solve_C.__qualname__ = "solve_C"

    def solve_S(
        c: np.ndarray,
        data: np.ndarray,
        s: np.ndarray,
        x_s: np.ndarray,
        nonneg_s: Union[bool, Sequence[bool]] = True,
        uni_s: bool = False,
        s0: Optional[np.ndarray] = None,
        norm_s: bool = True,
        smooth: float = 0.0,
        sum_s: bool = False,
        hard_s0: bool = True,
        w_hard_s0: float = 1.0,
        norm_mode: str = "intensity",
        g: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Solve for S given C and data, column-wise."""
        c = api._as_2d_float(c, "c")
        data = api._as_2d_float(data, "data")
        s = api._as_2d_float(s, "s")
        _ = api._as_1d_float(x_s, "x_s")

        if data.shape[0] != c.shape[0]:
            raise ValueError("C row count must match data rows.")
        if s.shape[1] != c.shape[1]:
            raise ValueError("S components must match C columns.")
        if data.shape[1] != s.shape[0]:
            raise ValueError("Data wavelength dimension must match S rows.")

        c_work = c.copy()
        data_work = data.copy()
        s_work = s.copy()
        nonneg_vec = api._normalize_nonneg_vector(nonneg_s, c_work.shape[1])

        c0 = None
        if s0 is not None:
            s0 = api._as_2d_float(s0, "s0")
            if s0.shape[0] != s.shape[0]:
                raise ValueError("s0 must have same wavelength length as S.")
            n_s0 = s0.shape[1]

            if hard_s0:
                if c_work.shape[1] == n_s0:
                    return s0.copy()

                c0 = c_work[:, :n_s0]
                c_work = c_work[:, n_s0:]
                s_work = s_work[:, n_s0:]
                nonneg_vec = nonneg_vec[n_s0:]

                contrib = c0 @ s0.T
                data_work = data_work - contrib
                data_work[~api.np.isfinite(data_work)] = 0.0
            else:
                c_aug = api.np.vstack([c_work, api.np.zeros((n_s0, c_work.shape[1]))])
                for i in range(n_s0):
                    c_aug[c_work.shape[0] + i, i] = w_hard_s0
                data_aug = api.np.vstack([data_work, w_hard_s0 * s0.T])
                c_work = c_aug
                data_work = data_aug

        all_same = bool(api.np.all(nonneg_vec == nonneg_vec[0]))
        use_broadening = g is not None and api.np.asarray(g).shape[0] == c_work.shape[0]

        if all_same:
            for j in range(data_work.shape[1]):
                if use_broadening:
                    # Keep SK-Ana behavior path for broadening-enabled S updates.
                    a = c_work
                    b = data_work[:, j]
                else:
                    a = c_work
                    b = data_work[:, j]
                s_work[j, :] = api._safe_solve(a, b, nonneg=bool(nonneg_vec[0]))
        else:
            idx_pos = api.np.where(nonneg_vec)[0]
            idx_free = api.np.where(~nonneg_vec)[0]
            for j in range(data_work.shape[1]):
                sol = api.np.zeros(c_work.shape[1], dtype=float)

                if idx_free.size > 0:
                    a_free = c_work[:, idx_free]
                    sol[idx_free] = api._safe_lstsq(a_free, data_work[:, j])
                    resid = data_work[:, j] - a_free @ sol[idx_free]
                else:
                    resid = data_work[:, j]

                if idx_pos.size > 0:
                    a_pos = c_work[:, idx_pos]
                    sol[idx_pos] = api._safe_solve(a_pos, resid, nonneg=True)

                s_work[j, :] = sol

        if uni_s:
            for i in range(s_work.shape[1]):
                s_work[:, i] = api.enforce_unimodal(s_work[:, i])

        if smooth and smooth > 0:
            for i in range(s_work.shape[1]):
                y = api._moving_average(s_work[:, i], float(smooth))
                if nonneg_vec[i]:
                    y = api.np.clip(y, 0.0, None)
                s_work[:, i] = y

        if norm_s:
            for i in range(s_work.shape[1]):
                s_work[:, i] = api._normalize_column(
                    s_work[:, i], sum_norm=bool(sum_s), norm_mode=norm_mode
                )

        if s0 is not None and hard_s0:
            s_work = api.np.hstack([s0, s_work])
            _ = c0  # kept for parity with R flow

        return s_work

    solve_S.__module__ = api.__name__
    solve_S.__qualname__ = "solve_S"

    def solve_C_coupled(
        s: np.ndarray,
        data: np.ndarray,
        c: np.ndarray,
        nonneg_c: bool = True,
        null_c: Optional[np.ndarray] = None,
        close_c: bool = False,
        w_close_c: float = 0.0,
        n_fixed: int = 0,
    ) -> np.ndarray:
        """Solve for C then enforce correction/fixed pairwise coupling."""
        c_out = api.solve_C(
            s=s,
            data=data,
            c=c,
            nonneg_c=nonneg_c,
            null_c=null_c,
            close_c=close_c,
            w_close_c=w_close_c,
            g=None,
        )

        if n_fixed > 0:
            for i in range(n_fixed):
                corr_idx = n_fixed + i
                if corr_idx >= c_out.shape[1]:
                    break
                c_fix = c_out[:, i]
                c_corr = c_out[:, corr_idx]
                norm_sq = float(api.np.sum(c_fix**2))
                if norm_sq <= 1e-12:
                    c_out[:, corr_idx] = 0.0
                else:
                    alpha = float(api.np.sum(c_corr * c_fix) / norm_sq)
                    c_out[:, corr_idx] = alpha * c_fix

        return c_out

    solve_C_coupled.__module__ = api.__name__
    solve_C_coupled.__qualname__ = "solve_C_coupled"

    def solve_S_coupled(
        c: np.ndarray,
        data: np.ndarray,
        s: np.ndarray,
        x_s: np.ndarray,
        nonneg_s: Union[bool, Sequence[bool]] = True,
        uni_s: bool = False,
        s0: Optional[np.ndarray] = None,
        norm_s: bool = True,
        smooth: float = 0.0,
        sum_s: bool = False,
        hard_s0: bool = True,
        w_hard_s0: float = 1.0,
        n_fixed: int = 0,
        lambda_corr: float = 0.0,
        norm_mode: str = "intensity",
    ) -> np.ndarray:
        """Solve for S with correction-spectra orthogonality/coupling constraints."""
        s_out = api.solve_S(
            c=c,
            data=data,
            s=s,
            x_s=x_s,
            nonneg_s=nonneg_s,
            uni_s=uni_s,
            s0=s0,
            norm_s=False,
            smooth=0.0,
            sum_s=sum_s,
            hard_s0=hard_s0,
            w_hard_s0=w_hard_s0,
            norm_mode=norm_mode,
            g=None,
        )

        nonneg_vec = api._normalize_nonneg_vector(nonneg_s, s_out.shape[1])

        if n_fixed > 0:
            for i in range(n_fixed):
                corr_idx = n_fixed + i
                if corr_idx >= s_out.shape[1]:
                    break

                s_fix = s_out[:, i]
                s_corr = s_out[:, corr_idx]

                norm_sq = float(api.np.sum(s_fix**2))
                if norm_sq > 1e-12:
                    proj = float(api.np.sum(s_corr * s_fix) / norm_sq)
                    s_corr = s_corr - proj * s_fix

                s_corr = s_corr - float(api.np.mean(s_corr))

                if lambda_corr > 0:
                    penalty = 1.0 / (1.0 + lambda_corr * api.np.sqrt(float(api.np.sum(s_corr**2))))
                    s_corr = s_corr * penalty

                s_out[:, corr_idx] = s_corr

        if smooth and smooth > 0:
            for i in range(s_out.shape[1]):
                if n_fixed > 0 and n_fixed <= i < (2 * n_fixed):
                    continue
                sm = api._moving_average(s_out[:, i], float(smooth))
                if nonneg_vec[i]:
                    sm = api.np.clip(sm, 0.0, None)
                s_out[:, i] = sm

        if norm_s:
            if n_fixed > 0:
                # Normalize fixed spectra.
                for i in range(min(n_fixed, s_out.shape[1])):
                    s_out[:, i] = api._normalize_column(
                        s_out[:, i], sum_norm=bool(sum_s), norm_mode=norm_mode
                    )

                # Keep correction spectra as-is; normalize free spectra.
                start_free = 2 * n_fixed
                if s_out.shape[1] > start_free:
                    for i in range(start_free, s_out.shape[1]):
                        s_out[:, i] = api._normalize_column(
                            s_out[:, i], sum_norm=bool(sum_s), norm_mode=norm_mode
                        )
            else:
                for i in range(s_out.shape[1]):
                    s_out[:, i] = api._normalize_column(
                        s_out[:, i], sum_norm=bool(sum_s), norm_mode=norm_mode
                    )

        return s_out

    solve_S_coupled.__module__ = api.__name__
    solve_S_coupled.__qualname__ = "solve_S_coupled"

    def _reconstruct_with_broadening(
        c: np.ndarray,
        s: np.ndarray,
        g: Optional[np.ndarray],
        broadening_vec: np.ndarray,
    ) -> np.ndarray:
        c = api._as_2d_float(c, "c")
        s = api._as_2d_float(s, "s")
        model = api.np.zeros((c.shape[0], s.shape[0]), dtype=float)

        if g is None or not api.np.any(broadening_vec):
            return c @ s.T

        g = api._as_2d_float(g, "g")
        for i in range(c.shape[0]):
            s_broad = s.copy()
            for k in range(s.shape[1]):
                if broadening_vec[k]:
                    s_broad[:, k] = api.convolve_spectrum(s[:, k], float(g[i, k]))
            model[i, :] = c[i, :] @ s_broad.T
        return model

    _reconstruct_with_broadening.__module__ = api.__name__
    _reconstruct_with_broadening.__qualname__ = "_reconstruct_with_broadening"

    class ALSConfig:
        n_components: int = 2
        n_start: Optional[int] = None
        maxiter: int = 100
        thresh: float = 1e-3
        init_method: str = "svd"
        opt_s_first: bool = True
        nonneg_c: bool = True
        nonneg_s: Union[bool, Sequence[bool]] = True
        uni_s: bool = False
        norm_s: bool = True
        sum_norm: bool = False
        norm_mode: str = "intensity"
        smooth: float = 0.0
        close_c: bool = False
        w_close_c: float = 0.0
        hard_s0: bool = True
        w_hard_s0: float = 1.0
        broadening: Union[bool, Sequence[bool]] = False
        broadening_max_pct: float = 10.0
        correction_spectra: bool = False
        correction_lambda: float = 0.0
        random_state: int = 42

    ALSConfig.__module__ = api.__name__
    ALSConfig.__qualname__ = "ALSConfig"

    class ALSResult:
        c: np.ndarray
        s: np.ndarray
        model: np.ndarray
        resid: np.ndarray
        rss: float
        iter: int
        lof: float
        converged: bool
        msg: str
        g: Optional[np.ndarray] = None
        broadening_vec: Optional[np.ndarray] = None
        n_fixed: int = 0
        lambda_corr: float = 0.0
        meta: Dict[str, Any] = api.field(default_factory=dict)

    ALSResult.__module__ = api.__name__
    ALSResult.__qualname__ = "ALSResult"

    return {
        "_as_1d_float": _as_1d_float,
        "_as_2d_float": _as_2d_float,
        "_normalize_nonneg_vector": _normalize_nonneg_vector,
        "_normalize_bool_vector": _normalize_bool_vector,
        "_mask_to_bool": _mask_to_bool,
        "compute_lof": compute_lof,
        "convolve_spectrum": convolve_spectrum,
        "_safe_lstsq": _safe_lstsq,
        "_safe_solve": _safe_solve,
        "_moving_average": _moving_average,
        "enforce_unimodal": enforce_unimodal,
        "_normalize_column": _normalize_column,
        "optimize_broadening_single": optimize_broadening_single,
        "solve_C": solve_C,
        "solve_S": solve_S,
        "solve_C_coupled": solve_C_coupled,
        "solve_S_coupled": solve_S_coupled,
        "_reconstruct_with_broadening": _reconstruct_with_broadening,
        "ALSConfig": ALSConfig,
        "ALSResult": ALSResult,
    }
