"""Streamlit interface. Run with ``python -m streamlit run skana/app.py``."""

from __future__ import annotations

from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.signal import savgol_filter

from skana.analysis import als, als_contributions, svd
from skana.ambiguity import rotate_three, rotate_two
from skana.matrix import (MatrixData, baseline_correct, combine, export_matrix,
                          postprocess_compress,
                          read_matrix, select, suggest_baseline_intervals,
                          suggest_signal_mask)
from skana.kinetics import fit_kinetics, format_scheme, parse_scheme, variable_parameters
from skana.plots import ambiguity_ensemble, diagnostics, image, profiles
from skana.r_project import read_r_project, read_r_selection
from skana.report import build_report


def _csv(axis: np.ndarray, values: np.ndarray, axis_name: str, prefix: str) -> bytes:
    frame = pd.DataFrame(values, columns=[f"{prefix}_{i + 1}" for i in range(values.shape[1])])
    frame.insert(0, axis_name, axis)
    return frame.to_csv(index=False).encode("utf-8")


def _project_bytes(data: MatrixData) -> bytes:
    buffer = BytesIO()
    np.savez_compressed(buffer, matrix=data.matrix, delay=data.delay, time=data.time,
                        wavelength=data.wavelength, delay_id=data.delay_id,
                        metadata=json.dumps({"version": 1, "name": data.name,
                                             "orientation": data.orientation}))
    return buffer.getvalue()


def _read_project(upload) -> MatrixData:
    with np.load(BytesIO(upload.getvalue()), allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata"]))
        if metadata.get("version") != 1:
            raise ValueError("Unsupported Python project version.")
        time = archive["time"] if "time" in archive else archive["delay"]
        return MatrixData(archive["matrix"], archive["delay"], archive["wavelength"],
                          metadata["name"], metadata["orientation"], archive["delay_id"], time)


def _fixed_spectra(upload, wavelength: np.ndarray) -> np.ndarray:
    frame = pd.read_csv(BytesIO(upload.getvalue()), sep=None, engine="python")
    if frame.shape[1] < 2:
        raise ValueError("Fixed spectra CSV needs wavelength and at least one spectrum column.")
    source_axis = pd.to_numeric(frame.iloc[:, 0], errors="raise").to_numpy(dtype=float)
    spectra = frame.iloc[:, 1:].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    if not np.isfinite(source_axis).all() or not np.isfinite(spectra).all():
        raise ValueError("Fixed spectra must be finite.")
    order = np.argsort(source_axis)
    source_axis, spectra = source_axis[order], spectra[order]
    if np.any(np.diff(source_axis) <= 0):
        raise ValueError("Fixed spectra wavelength axis must be unique.")
    if wavelength.min() < source_axis.min() or wavelength.max() > source_axis.max():
        raise ValueError("Fixed spectra must span selected wavelength range.")
    return np.column_stack([np.interp(wavelength, source_axis, spectra[:, j])
                            for j in range(spectra.shape[1])])


def _zip_als(data: MatrixData, result) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("kinetics.csv", _csv(data.delay, result.c, "delay", "C"))
        archive.writestr("spectra.csv", _csv(data.wavelength, result.s, "wavelength", "S"))
        for name, matrix in (("model.csv", result.model), ("residual.csv", result.resid)):
            archive.writestr(name, export_matrix(MatrixData(matrix, data.delay, data.wavelength)))
        if result.g is not None:
            archive.writestr("broadening.csv", _csv(data.delay, result.g, "delay", "G"))
        archive.writestr("summary.json", json.dumps({"lof_pct": result.lof, "rss": result.rss,
                                                       "iterations": result.iter,
                                                       "converged": result.converged}))
    return buffer.getvalue()


def _zip_rotation(data: MatrixData, rotation) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("kinetics.csv", _csv(data.delay, rotation.c, "delay", "C"))
        archive.writestr("spectra.csv", _csv(data.wavelength, rotation.s, "wavelength", "S"))
        parameters = {name: getattr(rotation, name) for name in
                      ("t12", "t21", "t23", "t32", "t13", "t31") if hasattr(rotation, name)}
        archive.writestr("rotation.json", json.dumps(parameters))
    return buffer.getvalue()


def _all_rotations_bytes(solutions) -> bytes:
    buffer = BytesIO()
    parameters = np.array([[getattr(sol, name, np.nan) for name in
                            ("t12", "t21", "t23", "t32", "t13", "t31")]
                           for sol in solutions])
    np.savez_compressed(buffer, c=np.stack([sol.c for sol in solutions]),
                        s=np.stack([sol.s for sol in solutions]), parameters=parameters)
    return buffer.getvalue()


def _show_plot(fig) -> None:
    st.pyplot(fig)
    plt.close(fig)


def _smoothed_profiles(values: np.ndarray, axis: np.ndarray, label: str, key: str) -> None:
    with st.expander("Savitzky–Golay display smoothing"):
        windows = list(range(3, values.shape[0] + 1, 2))
        if not windows:
            st.info("At least three time points are needed.")
            return
        window = st.selectbox("Window length", windows, index=min(2, len(windows) - 1),
                              key=f"{key}_sg_window")
        order = st.number_input("Polynomial order", 1, window - 1,
                                min(2, window - 1), key=f"{key}_sg_order")
        display = st.radio("Display", ["Raw and smoothed", "Smoothed only"],
                           horizontal=True, key=f"{key}_sg_display")
        smoothed = savgol_filter(values, window_length=window, polyorder=order, axis=0)
        columns = [f"{label}_{i + 1}" for i in range(values.shape[1])]
        frame = pd.DataFrame(smoothed, index=axis, columns=columns)
        if display == "Raw and smoothed":
            for j, name in enumerate(columns):
                frame[f"raw_{name}"] = values[:, j]
        st.line_chart(frame)


def _cut_indices(axis: np.ndarray, position: float, min_points: int = 50) -> np.ndarray:
    """R indxCuts-style local averaging for dense coordinate axes."""
    if position <= axis[0]:
        return np.array([0])
    if position >= axis[-1]:
        return np.array([axis.size - 1])
    if axis.size > 2 * min_points:
        half_width = (axis[-1] - axis[0]) / (2 * min_points)
        indices = np.flatnonzero((axis > position - half_width) &
                                 (axis < position + half_width))
        if indices.size:
            return indices
    return np.array([int(np.argmin(np.abs(axis - position)))])


def _demo_matrix() -> MatrixData:
    """Reproducible synthetic A → B example for exploring the interface."""
    time = np.linspace(0, 5, 40)
    wavelength = np.linspace(400, 680, 65)
    a = np.exp(-0.7 * time)
    c = np.column_stack((a, 1 - a))
    spectra = np.column_stack((np.exp(-((wavelength - 470) / 36) ** 2),
                               0.8 * np.exp(-((wavelength - 560) / 42) ** 2)))
    spectra /= spectra.max(axis=0)
    spectra[:, 1] *= 0.8
    return MatrixData(c @ spectra.T, time, wavelength, "synthetic_A_to_B")


def _zip_kinetics(data: MatrixData, result, scheme_text: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("scheme.txt", scheme_text)
        archive.writestr("concentrations_all.csv", _csv(data.time, result.c_all, "time", "species"))
        archive.writestr("kinetics_active.csv", _csv(data.time, result.c, "time", "C"))
        archive.writestr("spectra.csv", _csv(data.wavelength, result.s, "wavelength", "S"))
        archive.writestr("model.csv", export_matrix(MatrixData(result.model, data.delay, data.wavelength)))
        archive.writestr("residual.csv", export_matrix(MatrixData(result.residual, data.delay, data.wavelength)))
        archive.writestr("parameters.json", json.dumps(result.parameters, indent=2))
        scheme = parse_scheme(scheme_text, n_experiments=np.unique(data.delay_id).size)
        parameters = variable_parameters(scheme)
        if parameters:
            sd = (np.sqrt(np.maximum(np.diag(result.covariance), 0))
                  if result.covariance is not None else np.full(len(parameters), np.nan))
            uncertainty = pd.DataFrame({
                "parameter": [p.name for p in parameters],
                "nominal": [p.nominal for p in parameters],
                "factor": [p.factor for p in parameters],
                "fitted": [result.parameters[p.name] for p in parameters],
                "z": result.contracted,
                "sd_z": sd,
            })
            archive.writestr("local_uncertainty.csv", uncertainty.to_csv(index=False))
        archive.writestr("summary.json", json.dumps({"lof_pct": result.lof, "relative_rss": result.rss,
                                                      "success": result.success, "message": result.message}))
    return buffer.getvalue()


def _workspace_zip(project_data: MatrixData, selected: MatrixData, selection_state: dict,
                   als_result=None, kinetic_result=None, scheme_text: str = "") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("project.npz", _project_bytes(project_data))
        archive.writestr("selected_matrix.csv", export_matrix(selected))
        archive.writestr("selections.json", json.dumps(selection_state, indent=2))
        archive.writestr("svd_statistics.csv", svd(selected, 1).statistics.to_csv(index=False))
        if als_result is not None:
            archive.writestr("als_results.zip", _zip_als(selected, als_result))
        if kinetic_result is not None:
            archive.writestr("kinetic_results.zip",
                             _zip_kinetics(selected, kinetic_result, scheme_text))
    return buffer.getvalue()


def main() -> None:
    st.set_page_config(page_title="SK-Ana Python", layout="wide")
    st.markdown("""<style>
        .block-container {max-width: 100%; padding: 0.8rem 1rem 3rem;}
        h1 {font-size: 1.55rem !important; margin: 0 0 0.15rem !important;}
        [data-testid="stToolbar"] {display: none;}
        [role="tablist"] {background: #f1f1f1; padding: 0 0.5rem;}
    </style>""", unsafe_allow_html=True)
    st.title("SK-Ana · Python")
    st.caption("Independent Streamlit implementation · spectrokinetic matrix = delay × wavelength")
    project_tab, selection_tab, svd_tab, als_tab, kinet_tab, export_tab, about_tab, debug_tab = st.tabs(
        ["Project", "Data Selection", "SVD", "ALS", "Kinet", "Downloads", "About", "Debug Console"])
    selection_state = None

    with project_tab:
        project_controls, project_results = st.columns([1, 2], gap="large")
        with project_controls:
            st.subheader("Import matrix")
            demo = st.checkbox("Use synthetic A → B demo data")
            if demo:
                project_upload = r_project_upload = r_selection_upload = python_selection_upload = None
                uploads = []
                preset, orientation, sep, decimal = "Auto", "wxd", None, None
                cd = cw = 1
                transform = "None"
            else:
                project_upload = st.file_uploader("Open Python project (.npz)", type="npz")
                r_project_upload = st.file_uploader("Import R/Shiny project (.Rda)",
                                                    type=["rda", "Rda", "RData"])
                r_selection_upload = st.file_uploader("Import R selections (.Rda)",
                                                      type=["rda", "Rda", "RData"],
                                                      key="r_selections")
                python_selection_upload = st.file_uploader("Open Python selections (.json)",
                                                           type="json", key="python_selections")
                uploads = st.file_uploader("Matrix files", type=["csv", "tsv", "txt", "dat"],
                                           accept_multiple_files=True)
                preset = st.selectbox("Input format", ["Auto", "ELYSE (TSV)", "CSV", "Fluo", "Streak", "Other"])
                if preset in {"Auto", "Other"}:
                    orientation = st.radio("Coordinates", ["wxd: first row wavelength", "dxw: first row delay"],
                                           horizontal=True)
                    orientation = orientation[:3]
                else:
                    orientation = None
                sep = decimal = None
                if preset == "Other":
                    sep_label = st.selectbox("Separator", ["Tab", "Comma", "Semicolon", "Space"])
                    sep = {"Tab": "\t", "Comma": ",", "Semicolon": ";", "Space": " "}[sep_label]
                    decimal = st.selectbox("Decimal mark", [".", ","])
                cd = st.number_input("Load compression: delay", 1, 20, 1)
                cw = st.number_input("Load compression: wavelength", 1, 20, 1)
                post_cd = st.number_input("Post-process compression: delay", 1, 20, 1)
                post_cw = st.number_input("Post-process compression: wavelength", 1, 20, 1)
                transform = st.selectbox("Delay transform", ["None", "Index", "Log10"])
            data = None
            try:
                if demo:
                    data = _demo_matrix()
                elif project_upload is not None:
                    data = _read_project(project_upload)
                elif r_project_upload is not None:
                    data = read_r_project(r_project_upload.getvalue(),
                                          prefer_original=(r_selection_upload is not None or
                                                           python_selection_upload is not None))
                elif uploads:
                    items = [read_matrix(upload.getvalue(), name=upload.name, preset=preset,
                                         sep=sep, decimal=decimal, orientation=orientation,
                                         compress_delay=cd, compress_wavelength=cw) for upload in uploads]
                    if len(items) == 1:
                        mode = "single"
                    else:
                        mode = st.selectbox("Combine", ["average", "tile_delay", "tile_wavelength"])
                    data = combine(items, mode, transform)
                    if post_cd > 1 or post_cw > 1:
                        data = postprocess_compress(data, post_cd, post_cw)
            except (ValueError, KeyError, pd.errors.ParserError) as exc:
                st.error(str(exc))
        with project_results:
            if data is not None:
                st.success(f"{data.name}: {data.matrix.shape[0]} delays × {data.matrix.shape[1]} wavelengths")
                _show_plot(image(data, data.matrix, "Imported data"))
                st.download_button("Save Python project (.npz)", _project_bytes(data),
                                   file_name="skana_project.npz")

    with selection_tab:
        if data is None:
            st.info("Import a matrix on the Project tab.")
            selected = None
        else:
            selection_controls, selection_results = st.columns([1, 2], gap="large")
            with selection_controls:
                dmin, dmax = float(data.delay.min()), float(data.delay.max())
                wmin, wmax = float(data.wavelength.min()), float(data.wavelength.max())
                selection_config = None
                if python_selection_upload is not None:
                    try:
                        selection_config = json.loads(python_selection_upload.getvalue())
                    except (ValueError, UnicodeDecodeError) as exc:
                        st.error(f"Invalid selection JSON: {exc}")
                elif r_selection_upload is not None:
                    try:
                        selection_config = read_r_selection(r_selection_upload.getvalue())
                    except ValueError as exc:
                        st.error(str(exc))
                if selection_config is not None:
                    required = {"matrix_dimensions", "delay_range", "wavelength_range",
                                "baseline_ranges", "excluded_delays", "excluded_wavelengths"}
                    if (not isinstance(selection_config, dict) or
                            not required.issubset(selection_config) or
                            not isinstance(selection_config.get("matrix_dimensions"), (list, tuple)) or
                            tuple(selection_config.get("matrix_dimensions") or ()) != data.matrix.shape):
                        st.warning("Saved selection fields or dimensions do not match imported matrix; ignored.")
                        selection_config = None
                use_imported_selections = (st.checkbox("Apply imported selections", True)
                                           if selection_config is not None else False)
                d_range = st.slider("Delay range", dmin, dmax, (dmin, dmax)) if dmin < dmax else (dmin, dmax)
                w_range = st.slider("Wavelength range", wmin, wmax, (wmin, wmax)) if wmin < wmax else (wmin, wmax)
                n_bl = st.number_input("Baseline intervals", 0, 10, 0)
                baseline_ranges = [st.slider(f"Baseline delay {i + 1}", dmin, dmax,
                                             (dmin, dmin), key=f"bl_{i}") for i in range(n_bl)]
                n_dm = st.number_input("Excluded delay intervals", 0, 10, 0)
                d_masks = [st.slider(f"Delay mask {i + 1}", dmin, dmax, (dmin, dmin),
                                     key=f"dmask_{i}") for i in range(n_dm)]
                n_wm = st.number_input("Excluded wavelength intervals", 0, 10, 0)
                w_masks = [st.slider(f"Wavelength mask {i + 1}", wmin, wmax, (wmin, wmin),
                                     key=f"wmask_{i}") for i in range(n_wm)]
                if use_imported_selections:
                    d_range = selection_config["delay_range"] or d_range
                    w_range = selection_config["wavelength_range"] or w_range
                    baseline_ranges = selection_config["baseline_ranges"]
                    d_masks = selection_config["excluded_delays"]
                    w_masks = selection_config["excluded_wavelengths"]
                    st.caption("Imported R ranges and masks are applied; disable to use manual controls.")
                with st.expander("Automatic signal masks"):
                    st.caption("Python estimates signal regions from RMS intensity. "
                               "R uses variance changepoints; inspect the suggested ranges before fitting.")
                    auto_delay = st.checkbox("Apply automatic delay mask")
                    auto_wavelength = st.checkbox("Apply automatic wavelength mask")
                    auto_baseline = st.checkbox("Use leading quiet rows for baseline")
                    auto_fraction = st.slider("Signal threshold fraction", 0.01, 0.5, 0.05, 0.01)
                delay_keep = (suggest_signal_mask(data, "delay", auto_fraction)
                              if auto_delay else None)
                wavelength_keep = (suggest_signal_mask(data, "wavelength", auto_fraction)
                                   if auto_wavelength else None)
                if delay_keep is not None:
                    st.caption(f"Automatic delay mask keeps {int(delay_keep.sum())}/{delay_keep.size} rows.")
                if wavelength_keep is not None:
                    st.caption(f"Automatic wavelength mask keeps {int(wavelength_keep.sum())}/{wavelength_keep.size} columns.")
                if auto_baseline:
                    suggested = suggest_baseline_intervals(data, auto_fraction)
                    baseline_ranges.extend(suggested)
                    st.caption(f"Automatic baseline intervals: {suggested or 'none found'}")
                if st.checkbox("Remove largest SVD kinetic glitch"):
                    level = st.number_input("SVD vector", 1, min(data.matrix.shape), 1)
                    vector = np.linalg.svd(data.matrix, full_matrices=False)[0][:, level - 1]
                    glitch = int(np.argmax(np.abs(vector)))
                    st.write(f"Excluded delay index {glitch + 1}: {data.delay[glitch]:g}")
                    d_masks.append((float(data.delay[glitch]), float(data.delay[glitch])))
            with selection_results:
                try:
                    corrected = baseline_correct(data, baseline_ranges)
                    selected = select(corrected, delay_range=d_range, wavelength_range=w_range,
                                      excluded_delays=d_masks, excluded_wavelengths=w_masks,
                                      delay_keep=delay_keep, wavelength_keep=wavelength_keep)
                    selection_state = {
                        "matrix_dimensions": list(data.matrix.shape),
                        "delay_range": list(d_range), "wavelength_range": list(w_range),
                        "baseline_ranges": [list(x) for x in baseline_ranges],
                        "excluded_delays": [list(x) for x in d_masks],
                        "excluded_wavelengths": [list(x) for x in w_masks],
                    }
                    st.download_button("Save selection settings JSON",
                                       json.dumps(selection_state, indent=2),
                                       file_name="skana_selections.json", mime="application/json")
                    st.write(f"Selected: {selected.matrix.shape[0]} × {selected.matrix.shape[1]}")
                    signal_min, signal_max = float(selected.matrix.min()), float(selected.matrix.max())
                    if signal_min < signal_max:
                        color_limits = st.slider("Displayed O.D. color range", signal_min, signal_max,
                                                 (signal_min, signal_max))
                    else:
                        color_limits = None
                    _show_plot(image(selected, selected.matrix, "Selected data", color_limits))
                    c1, c2 = st.columns(2)
                    with c1:
                        cut_delay = st.slider("Spectrum at delay", float(selected.delay.min()),
                                              float(selected.delay.max()))
                        rows = _cut_indices(selected.delay, cut_delay)
                        spectrum = selected.matrix[rows].mean(axis=0)
                        st.line_chart(pd.DataFrame({"O.D.": spectrum},
                                               index=selected.wavelength))
                        st.download_button("Download spectrum cut CSV",
                                           _csv(selected.wavelength, spectrum[:, None],
                                                "wavelength", "OD"),
                                           file_name="skana_spectrum_cut.csv")
                    with c2:
                        cut_wavelength = st.slider("Kinetics at wavelength",
                                                   float(selected.wavelength.min()),
                                                   float(selected.wavelength.max()))
                        cols = _cut_indices(selected.wavelength, cut_wavelength)
                        kinetic_trace = selected.matrix[:, cols].mean(axis=1)
                        st.line_chart(pd.DataFrame({"O.D.": kinetic_trace},
                                               index=selected.delay))
                        st.download_button("Download kinetic cut CSV",
                                           _csv(selected.delay, kinetic_trace[:, None],
                                                "delay", "OD"),
                                           file_name="skana_kinetic_cut.csv")
                    with st.expander("Families of spectra and kinetics cuts"):
                        delay_step = st.number_input("Delay cut step (rows)", 1, selected.delay.size,
                                                     max(1, selected.delay.size // 5))
                        wavelength_step = st.number_input("Wavelength cut step (columns)",
                                                          1, selected.wavelength.size,
                                                          max(1, selected.wavelength.size // 5))
                        row_indices = np.arange(0, selected.delay.size, delay_step)
                        col_indices = np.arange(0, selected.wavelength.size, wavelength_step)
                        st.write("Spectra at selected delays")
                        st.line_chart(pd.DataFrame(selected.matrix[row_indices].T,
                                                   index=selected.wavelength,
                                                   columns=[f"t={selected.delay[i]:.4g}" for i in row_indices]))
                        st.download_button("Download spectra family CSV",
                                           _csv(selected.wavelength, selected.matrix[row_indices].T,
                                                "wavelength", "spectrum"),
                                           file_name="skana_spectra_family.csv")
                        st.write("Kinetics at selected wavelengths")
                        st.line_chart(pd.DataFrame(selected.matrix[:, col_indices],
                                                   index=selected.delay,
                                                   columns=[f"λ={selected.wavelength[j]:.4g}"
                                                            for j in col_indices]))
                        st.download_button("Download kinetics family CSV",
                                           _csv(selected.delay, selected.matrix[:, col_indices],
                                                "delay", "kinetic"),
                                           file_name="skana_kinetics_family.csv")
                except ValueError as exc:
                    st.error(str(exc))
                    selected = None

    with svd_tab:
        if selected is None:
            st.info("Import and select a valid matrix first.")
        else:
            svd_controls, svd_results = st.columns([1, 2], gap="large")
            with svd_controls:
                st.subheader("SVD options")
                rank = st.number_input("Model rank", 1, min(10, *selected.matrix.shape),
                                       min(2, *selected.matrix.shape))
            with svd_results:
                svd_result = svd(selected, rank)
                st.dataframe(svd_result.statistics, hide_index=True)
                st.line_chart(svd_result.statistics.set_index("rank")[["singular_value", "lof_pct"]])
                with st.expander("Singular-value noise trend"):
                    all_values = np.linalg.svd(selected.matrix, compute_uv=False)
                    fig, ax = plt.subplots(figsize=(6, 3))
                    indices = np.arange(1, all_values.size + 1)
                    ax.semilogy(indices, all_values, "o-", label="Singular values")
                    if all_values.size >= 11:
                        tail = np.arange(10, min(20, all_values.size) + 1)
                        slope, intercept = np.polyfit(tail, all_values[tail - 1], 1)
                        predicted = intercept + slope * indices
                        ax.semilogy(indices[predicted > 0], predicted[predicted > 0], "--",
                                    label="Linear tail trend (R method)")
                    ax.set(xlabel="Rank", ylabel="Singular value", title="Noise trend")
                    ax.legend()
                    _show_plot(fig)
                _show_plot(profiles(selected, svd_result.u[:, :rank], svd_result.vt[:rank, :].T, "SVD"))
                _show_plot(diagnostics(selected, svd_result.model, svd_result.residual, f"SVD rank {rank}"))
                with st.expander("SVD component contributions"):
                    for i in range(rank):
                        contribution = svd_result.singular_values[i] * np.outer(
                            svd_result.u[:, i], svd_result.vt[i, :])
                        _show_plot(image(selected, contribution, f"SVD component {i + 1}"))
                st.download_button("Download SVD statistics", svd_result.statistics.to_csv(index=False),
                                   file_name="svd_statistics.csv")

    with als_tab:
        if selected is None:
            st.info("Import and select a valid matrix first.")
        else:
            als_controls, als_results = st.columns([1, 2], gap="large")
            with als_controls:
                st.subheader("ALS options")
                n = st.number_input("Components", 1, min(10, *selected.matrix.shape),
                                    min(2, *selected.matrix.shape))
                method = st.selectbox("Initialization", ["svd", "pca", "nmf", "seq", "restart"])
                maxiter = st.number_input("Maximum iterations", 20, 9999, 1000, step=20)
                log_threshold = st.slider("Log10 convergence threshold", -10, -2, -6)
                filtered = st.checkbox("Use SVD-filtered matrix")
                filtered_rank = st.number_input("SVD filter rank", 1, min(selected.matrix.shape),
                                                min(n, *selected.matrix.shape)) if filtered else None
                opt_s_first = st.checkbox("Optimize spectra first", False)
                col_c, col_s = st.columns(2)
                with col_c:
                    nonneg_c = st.checkbox("C ≥ 0", True)
                    closure = st.checkbox("Soft closure: sum(C) ≈ 1")
                    log_closure = st.slider("Log10 closure weight", -3.0, 3.0, 1.0, 0.5) if closure else 0.0
                with col_s:
                    per_component = st.checkbox("Per-component S ≥ 0")
                    nonneg_s = [st.checkbox(f"S_{i + 1} ≥ 0", True, key=f"nonneg_s_{i}")
                                for i in range(n)] if per_component else st.checkbox("S ≥ 0", True)
                    uni_s = st.checkbox("Unimodal spectra")
                    norm_s = st.checkbox("Normalize spectra", True)
                    norm_mode = st.radio("Norm", ["intensity", "l1"], horizontal=True)
                    sum_norm = st.checkbox("SUM(|S|)=1")
                    smooth = st.number_input("Spectral smoothing span", 0.0, 1.0, 0.0, 0.1)
                fixed_file = st.file_uploader("Fixed spectra CSV: wavelength, S_1, ...", type="csv", key="fixed")
                soft_fixed = st.checkbox("Soft fixed-spectra constraint") if fixed_file else False
                soft_weight = st.slider("Log10 fixed-spectra weight", -3.0, 3.0, 1.0, 0.5) if soft_fixed else 0.0
                correction = st.checkbox("Correction spectra") if fixed_file else False
                correction_lambda = (10.0 ** st.slider("Log10 correction penalty", -4.0, 0.0,
                                                       -2.0, 0.5)) if correction else 0.0
                broaden = st.checkbox("Gaussian broadening")
                if broaden:
                    broadening = [st.checkbox(f"Broaden component {i + 1}", True,
                                              key=f"broad_{i}") for i in range(n)]
                    broadening_pct = st.number_input("Maximum broadening (%)", 0.1, 50.0, 10.0, 0.5)
                else:
                    broadening, broadening_pct = False, 10.0
                presence = None
                if np.unique(selected.delay_id).size > 1:
                    st.write("Component presence by imported experiment")
                    ids = np.unique(selected.delay_id)
                    flags = pd.DataFrame(np.ones((ids.size, n), dtype=int),
                                         index=[f"Experiment {i}" for i in ids],
                                         columns=[f"C_{i + 1}" for i in range(n)])
                    edited = st.data_editor(flags)
                    presence = np.vstack([edited.loc[f"Experiment {i}"].to_numpy(dtype=float)
                                          for i in selected.delay_id])
                if st.button("Run MCR-ALS", type="primary"):
                    try:
                        fixed = _fixed_spectra(fixed_file, selected.wavelength) if fixed_file else None
                        if correction and broaden:
                            raise ValueError("Correction spectra and broadening cannot be combined.")
                        if correction and fixed is not None and n < 2 * fixed.shape[1]:
                            raise ValueError("Correction mode needs at least two components per fixed spectrum.")
                        prior = st.session_state.get("als_result") if method == "restart" else None
                        prior_selection = st.session_state.get("als_selection")
                        same_selection = prior_selection is not None and (
                            np.array_equal(prior_selection.matrix, selected.matrix)
                            and np.array_equal(prior_selection.delay, selected.delay)
                            and np.array_equal(prior_selection.wavelength, selected.wavelength))
                        if method == "restart" and (prior is None or not same_selection):
                            raise ValueError("Restart requires an ALS result from the current matrix selection.")
                        result = als(selected, n_components=n, init_method=method,
                                     maxiter=maxiter, thresh=10.0 ** log_threshold,
                                     opt_s_first=opt_s_first, nonneg_c=nonneg_c,
                                     nonneg_s=nonneg_s, uni_s=uni_s, norm_s=norm_s,
                                     norm_mode=norm_mode, sum_norm=sum_norm, smooth=smooth,
                                     close_c=closure, w_close_c=10.0 ** log_closure if closure else 0.0,
                                     filtered_rank=filtered_rank, presence_mask=presence,
                                     fixed_spectra=fixed, hard_s0=not soft_fixed,
                                     w_hard_s0=10.0 ** soft_weight if soft_fixed else 1.0,
                                     correction_spectra=correction, correction_lambda=correction_lambda,
                                     broadening=broadening, broadening_max_pct=broadening_pct,
                                     restart_result=prior)
                        st.session_state["als_result"] = result
                        st.session_state["als_selection"] = selected
                        st.session_state.pop("ambiguity_solutions", None)
                        st.session_state["als_data"] = MatrixData(
                            svd(selected, filtered_rank).model if filtered_rank else selected.matrix,
                            selected.delay, selected.wavelength, selected.name,
                            selected.orientation, selected.delay_id, selected.time)
                    except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
                        st.error(str(exc))
            with als_results:
                result = st.session_state.get("als_result")
                result_data = st.session_state.get("als_data")
                original_selection = st.session_state.get("als_selection")
                if result is not None and result_data is not None:
                    if original_selection is None or not (
                        np.array_equal(original_selection.matrix, selected.matrix)
                        and np.array_equal(original_selection.delay, selected.delay)
                        and np.array_equal(original_selection.wavelength, selected.wavelength)):
                        st.warning("Displayed ALS result belongs to previous matrix selection. Run again.")
                    else:
                        if not np.array_equal(result_data.matrix, selected.matrix):
                            st.caption("ALS fit and residuals refer to the SVD-filtered matrix.")
                        st.write({"LOF (%)": result.lof, "relative RSS": result.rss,
                                  "iterations": result.iter, "converged": result.converged})
                        _show_plot(profiles(result_data, result.c, result.s, "MCR-ALS"))
                        _smoothed_profiles(result.c, result_data.delay, "C", "als")
                        _show_plot(diagnostics(result_data, result.model, result.resid, "MCR-ALS"))
                        fig, ax = plt.subplots(figsize=(6, 3))
                        ax.hist(result_data.matrix.ravel(), bins=30, alpha=0.5, label="Data")
                        ax.hist(result.resid.ravel(), bins=30, alpha=0.5, label="Residual")
                        ax.set(xlabel="O.D.", ylabel="Count", title="Residual distribution")
                        ax.legend()
                        _show_plot(fig)
                        st.write("Component contributions")
                        for i, component in enumerate(als_contributions(result)):
                            _show_plot(image(result_data, component, f"Component {i + 1}"))
                        residual_sv = np.linalg.svd(result.resid, compute_uv=False)
                        st.line_chart(pd.DataFrame({"residual singular value": residual_sv}))
                        st.download_button("Download ALS result ZIP", _zip_als(result_data, result),
                                           file_name="skana_als.zip")
                        with st.expander("Rotational ambiguity (2 or 3 components)"):
                            free_components = list(range(result.n_fixed, result.s.shape[1]))
                            if len(free_components) < 2:
                                st.info("Two nonfixed components are required.")
                            else:
                                choices = st.multiselect("Components to rotate",
                                                         free_components,
                                                         default=free_components[:min(3, len(free_components))],
                                                         format_func=lambda i: f"Component {i + 1}")
                                density = st.slider("Exploration step", 0.01, 0.1, 0.05, 0.01)
                                epsilon = st.slider("Relative positivity threshold", -0.1, 0.1,
                                                    -0.01, 0.01)
                                radius = st.selectbox("Three-component search radius (grid steps)", [1, 2])
                                if st.button("Explore ambiguity"):
                                    if len(choices) not in (2, 3):
                                        st.error("Choose two or three components.")
                                    else:
                                        try:
                                            with st.spinner("Exploring rotations"):
                                                if len(choices) == 2:
                                                    solutions = rotate_two(result.c, result.s,
                                                                           components=tuple(choices),
                                                                           step=density, positivity=epsilon)
                                                else:
                                                    solutions = rotate_three(result.c, result.s,
                                                                             components=tuple(choices),
                                                                             step=density, positivity=epsilon,
                                                                             radius=radius)
                                                st.session_state["ambiguity_solutions"] = solutions
                                        except ValueError as exc:
                                            st.error(str(exc))
                                solutions = st.session_state.get("ambiguity_solutions")
                                if solutions is not None:
                                    st.write(f"Accepted rotations: {len(solutions)}")
                                    if solutions:
                                        if st.checkbox("Show all accepted rotations"):
                                            _show_plot(ambiguity_ensemble(result_data, solutions))
                                        st.download_button("Download all rotations (.npz)",
                                                           _all_rotations_bytes(solutions),
                                                           file_name="skana_ambiguity_all.npz")
                                        index = st.slider("Rotation", 0, len(solutions) - 1, 0)
                                        rotation = solutions[index]
                                        st.write({name: getattr(rotation, name) for name in
                                                  ("t12", "t21", "t23", "t32", "t13", "t31")
                                                  if hasattr(rotation, name)})
                                        _show_plot(profiles(result_data, rotation.c, rotation.s,
                                                            "Rotated factors"))
                                        st.download_button("Download rotated factors ZIP",
                                                           _zip_rotation(result_data, rotation),
                                                           file_name="skana_rotation.zip")

    with kinet_tab:
        if selected is None:
            st.info("Import and select a valid matrix first.")
        else:
            kinet_controls, kinet_results = st.columns([1, 2], gap="large")
            with kinet_controls:
                st.subheader("Reaction scheme and kinetic fit")
                st.caption("Mass-action ODE with LSODA; spectra solved by variable projection. "
                           "Use uncertainty factors > 1 to fit a parameter.")
                scheme_upload = st.file_uploader("Reaction scheme (.txt or .in)",
                                                 type=["txt", "in"], key="scheme_upload")
                default_scheme = ("A -> B ; 0.7 / 1.5\n\n"
                                  "c0_A_1 = 1\n\n"
                                  "eps_A = 1\neps_B = 0.8\n")
                if scheme_upload is not None:
                    uploaded_scheme = scheme_upload.getvalue().decode("utf-8-sig")
                    if st.session_state.get("scheme_upload_name") != scheme_upload.name:
                        st.session_state["scheme_text"] = uploaded_scheme
                        st.session_state["scheme_upload_name"] = scheme_upload.name
                scheme_text = st.text_area("Scheme: reactions; c0_species_experiment; eps_species",
                                           value=default_scheme, height=190, key="scheme_text")
                try:
                    scheme = parse_scheme(scheme_text, n_experiments=np.unique(selected.delay_id).size)
                    if np.any(selected.time < 0):
                        raise ValueError("Kinetic fitting needs nonnegative physical times.")
                    st.write("Modeled species:", ", ".join(scheme.species))
                    parameters = variable_parameters(scheme)
                    st.write("Variable parameters:", ", ".join(p.name for p in parameters) or "none")
                    with st.expander("Fit settings"):
                        nonnegative_s = st.checkbox("Nonnegative kinetic spectra", False)
                        spectral_smooth = st.slider("Spectral local-quadratic smoothing span",
                                                    0.0, 1.0, 0.0, 0.05)
                        weighted = st.checkbox("Weighted residual likelihood", False)
                        sigma = st.number_input("Signal standard deviation σ", min_value=1e-12,
                                                value=0.01, format="%.6g", disabled=not weighted)
                        sigma_rank = st.number_input("Estimate σ from SVD residual rank (0 = manual)",
                                                     0, min(10, *selected.matrix.shape), 0,
                                                     disabled=not weighted)
                        if weighted and sigma_rank:
                            sigma = max(float(np.std(svd(selected, sigma_rank).residual, ddof=1)), 1e-12)
                            st.caption(f"Estimated σ = {sigma:.6g}")
                        global_generations = st.number_input("Global generations (0 = local only)",
                                                              0, 1000, 0)
                        population_factor = st.number_input("Global population factor", 5, 200, 15)
                        convergence = st.number_input("Local tolerance", min_value=1e-12,
                                                       value=1e-8, format="%.1e")
                        restart = st.checkbox("Restart from previous kinetic fit")
                    fixed_upload = st.file_uploader("Fixed spectra CSV (wavelength, species columns)",
                                                    type="csv", key="kinet_fixed")
                    if st.button("Run kinetic fit", type="primary"):
                        try:
                            fixed_spectra = None
                            if fixed_upload is not None:
                                fixed_frame = pd.read_csv(BytesIO(fixed_upload.getvalue()),
                                                          sep=None, engine="python")
                                fixed_values = _fixed_spectra(fixed_upload, selected.wavelength)
                                names = list(fixed_frame.columns[1:])
                                unknown = set(names) - set(scheme.species)
                                if unknown:
                                    raise ValueError(f"Unknown fixed-spectrum species: {sorted(unknown)}")
                                fixed_spectra = dict(zip(names, fixed_values.T))
                            previous = st.session_state.get("kinetic_result")
                            previous_data = st.session_state.get("kinetic_selection")
                            same_data = previous_data is not None and np.array_equal(
                                previous_data.matrix, selected.matrix) and np.array_equal(
                                previous_data.time, selected.time) and np.array_equal(
                                previous_data.wavelength, selected.wavelength)
                            if restart and (previous is None or not same_data or
                                            previous.contracted.size != len(parameters)):
                                raise ValueError("Restart requires a compatible fit on the current selection.")
                            with st.spinner("Integrating and fitting kinetic model"):
                                result = fit_kinetics(
                                    selected, scheme, nonnegative_s=nonnegative_s,
                                    weighted=weighted, sigma=sigma,
                                    global_generations=global_generations,
                                    population_factor=population_factor, tol=convergence,
                                    spectral_smooth=spectral_smooth,
                                    fixed_spectra=fixed_spectra,
                                    start=previous.contracted if restart else None)
                            st.session_state["kinetic_result"] = result
                            st.session_state["kinetic_selection"] = selected
                            st.session_state["kinetic_scheme"] = format_scheme(scheme)
                        except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
                            st.error(str(exc))
                    with kinet_results:
                        result = st.session_state.get("kinetic_result")
                        previous_data = st.session_state.get("kinetic_selection")
                        if result is not None and previous_data is not None:
                            if not (np.array_equal(previous_data.matrix, selected.matrix) and
                                    np.array_equal(previous_data.time, selected.time) and
                                    np.array_equal(previous_data.wavelength, selected.wavelength) and
                                    st.session_state.get("kinetic_scheme") == format_scheme(scheme)):
                                st.warning("Kinetic result belongs to a previous selection or scheme. Run again.")
                            else:
                                st.write({"LOF (%)": result.lof, "relative RSS": result.rss,
                                          "optimizer success": result.success, "message": result.message})
                                st.dataframe(pd.DataFrame({"parameter": list(result.parameters),
                                                           "value": list(result.parameters.values())}),
                                             hide_index=True)
                                if parameters:
                                    uncertainty = (np.sqrt(np.maximum(np.diag(result.covariance), 0))
                                                   if result.covariance is not None else
                                                   np.full(len(parameters), np.nan))
                                    posterior = pd.DataFrame({
                                        "parameter": [p.name for p in parameters],
                                        "nominal": [p.nominal for p in parameters],
                                        "fitted": [result.parameters[p.name] for p in parameters],
                                        "factor": [p.factor for p in parameters],
                                        "contracted z": result.contracted,
                                        "approx. SD(z)": uncertainty,
                                        "approx. 95% low": [p.nominal * p.factor ** np.clip(z - 1.96 * sd, -3, 3)
                                                            for p, z, sd in zip(parameters, result.contracted,
                                                                                uncertainty)],
                                        "approx. 95% high": [p.nominal * p.factor ** np.clip(z + 1.96 * sd, -3, 3)
                                                             for p, z, sd in zip(parameters, result.contracted,
                                                                                 uncertainty)],
                                    })
                                    with st.expander("Prior and local posterior approximation"):
                                        st.dataframe(posterior, hide_index=True)
                                        st.caption("z = log(fitted / nominal) / log(factor); "
                                                   "prior z ~ standard normal on [-3, 3]. "
                                                   "Posterior SD uses inverse finite-difference Hessian.")
                                        if result.covariance is not None:
                                            covariance = result.covariance
                                            scale = np.sqrt(np.maximum(np.diag(covariance), 1e-30))
                                            correlation = covariance / np.outer(scale, scale)
                                            st.dataframe(pd.DataFrame(correlation,
                                                                      index=[p.name for p in parameters],
                                                                      columns=[p.name for p in parameters]))
                                            grid = np.linspace(-3, 3, 121)
                                            curves = {"prior": np.exp(-0.5 * grid**2)}
                                            for j, p in enumerate(parameters):
                                                sd = scale[j]
                                                curves[f"posterior_{p.name}"] = np.exp(
                                                    -0.5 * ((grid - result.contracted[j]) / sd)**2)
                                            st.line_chart(pd.DataFrame(curves, index=grid))
                                st.line_chart(pd.DataFrame(result.c_all, index=selected.time,
                                                           columns=scheme.species))
                                _smoothed_profiles(result.c_all, selected.time, "species", "kinetic")
                                _show_plot(profiles(selected, result.c, result.s, "Kinetic fit"))
                                _show_plot(diagnostics(selected, result.model, result.residual,
                                                       "Kinetic fit"))
                                st.download_button("Download kinetic result ZIP",
                                                   _zip_kinetics(selected, result,
                                                                 st.session_state["kinetic_scheme"]),
                                                   file_name="skana_kinetics.zip")
                except ValueError as exc:
                    st.error(str(exc))

    with export_tab:
        if selected is not None:
            st.download_button("Download selected matrix CSV", export_matrix(selected),
                               file_name="skana_matrix.csv")
            bundle_als = st.session_state.get("als_result")
            bundle_kinetic = st.session_state.get("kinetic_result")
            for key, item in (("als_selection", bundle_als),
                              ("kinetic_selection", bundle_kinetic)):
                previous = st.session_state.get(key)
                if item is not None and (previous is None or
                                         not np.array_equal(previous.matrix, selected.matrix) or
                                         not np.array_equal(previous.delay, selected.delay) or
                                         not np.array_equal(previous.wavelength, selected.wavelength)):
                    if key == "als_selection":
                        bundle_als = None
                    else:
                        bundle_kinetic = None
            st.download_button("Download complete workspace ZIP",
                               _workspace_zip(data, selected, selection_state or {},
                                              bundle_als, bundle_kinetic,
                                              st.session_state.get("kinetic_scheme", "")),
                               file_name="skana_workspace.zip")
            if st.checkbox("Prepare HTML report"):
                if st.checkbox("Include SVD in HTML report", True):
                    report_rank = st.number_input("Report SVD rank", 1,
                                                  min(10, *selected.matrix.shape),
                                                  min(2, *selected.matrix.shape))
                    report_svd = svd(selected, report_rank)
                else:
                    report_svd = None
                st.download_button("Download HTML analysis report",
                                   build_report(selected, svd_result=report_svd,
                                                als_result=bundle_als,
                                                kinetic_result=bundle_kinetic,
                                                scheme_text=st.session_state.get("kinetic_scheme")
                                                if bundle_kinetic is not None else None,
                                                ambiguity_solutions=st.session_state.get(
                                                    "ambiguity_solutions") if bundle_als is not None else None),
                                   file_name="skana_report.html", mime="text/html")
        st.write("Python runs matrix import, SVD, MCR-ALS, kinetic fitting, ambiguity search, "
                 "R project migration and reporting without an R runtime. "
                 "See python/README.md for validated modes and known numerical differences.")

    with about_tab:
        st.subheader("About SK-Ana Python")
        st.write("Independent Python implementation of the SK-Ana spectrokinetic workflow. "
                 "The Project, Data Selection, SVD, ALS, Kinet and Downloads pages follow "
                 "the R/Shiny navigation. Numerical differences and unvalidated modes are "
                 "listed in python/R_PORT_INVENTORY.md.")
        st.write("Matrix convention: delay × wavelength. The Python app does not call R.")

    with debug_tab:
        st.subheader("Debug Console")
        if data is None:
            st.info("No matrix loaded.")
        else:
            st.json({"matrix": data.name, "shape": list(data.matrix.shape),
                     "selected_shape": list(selected.matrix.shape) if selected is not None else None,
                     "als_available": "als_result" in st.session_state,
                     "kinetic_available": "kinetic_result" in st.session_state})


if __name__ == "__main__":
    main()
