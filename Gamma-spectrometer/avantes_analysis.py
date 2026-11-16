"""Reprocess and fit archived Gamma runs using their stored blank measurements."""

import argparse
from importlib.metadata import version
from pathlib import Path
import time

import h5py
import numpy as np

from avantes_h5 import axes, field, nx, process_revision, published_processes, utc_iso
from avantes_run import AvantesRun


def initial_spectra(matrix, components):
    """Use successive projections to choose independent starting spectra from observed rows."""
    residual = matrix.copy()
    indices = []
    threshold = np.linalg.norm(matrix) * np.finfo(matrix.dtype).eps * max(matrix.shape)
    for _ in range(components):
        row = int(np.argmax(np.einsum("ij,ij->i", residual, residual)))
        direction = residual[row]
        length = np.linalg.norm(direction)
        if length <= threshold:
            raise ValueError("The requested number of components exceeds the numerical rank of corrected OD")
        indices.append(row)
        unit = direction / length
        residual -= np.outer(residual @ unit, unit)
    spectra = matrix[indices]
    return spectra / np.linalg.norm(spectra, axis=1)[:, None], np.asarray(indices)


def fit_mcr(run, components, max_iter=50, wavelength_range=None, *, signed_spectra=False, signed_amplitudes=False):
    """Fit the sample matrix after removing the independently measured blank drift."""
    if components < 1 or max_iter < 1:
        raise ValueError("Components and iteration limit must be positive")
    try:
        from pymcr.mcr import McrAR
    except ImportError as exc:
        raise ValueError("MCR-ALS requires pyMCR. Install it with: python -m pip install pyMCR==0.3.2") from exc

    with h5py.File(run.path, "r") as file:
        entry = run._writable_entry(file)
        correction = next(reversed(list(published_processes(entry, "blank_correction"))), None)
        if correction is None:
            raise ValueError("MCR-ALS requires a blank correction made from at least two measured blanks")
        source_path = correction["data/od"].name
        all_wavelengths = correction["data/wavelength"][:]
        all_times = correction["data/time"][:]
        all_dose = correction["data/dose"][:] if "dose" in correction["data"] else None
        wavelength_mask = np.ones(all_wavelengths.shape, dtype=bool)
        if wavelength_range is not None:
            lo, hi = wavelength_range
            if not lo < hi:
                raise ValueError("Minimum wavelength must be below maximum wavelength")
            wavelength_mask = (all_wavelengths >= lo) & (all_wavelengths <= hi)
        wavelengths = np.flatnonzero(wavelength_mask)
        measured = correction["data/od"][:, wavelengths]

    time_rows = np.flatnonzero(np.any(np.isfinite(measured), axis=1))
    if len(time_rows) <= components:
        raise ValueError("Too few valid time points between measured blanks for this component count")
    finite_columns = np.all(np.isfinite(measured[time_rows]), axis=0)
    indices = wavelengths[finite_columns]
    if min(len(time_rows), len(indices)) <= components:
        raise ValueError("Too few valid time points or wavelengths. Reduce the component count or choose a wavelength range")
    od = measured[np.ix_(time_rows, np.flatnonzero(finite_columns))]
    seed = od if signed_spectra else np.abs(od) if signed_amplitudes else np.maximum(od, 0)
    try:
        starting_spectra, starting_rows = initial_spectra(seed, components)
    except ValueError as exc:
        if not signed_spectra and not signed_amplitudes:
            raise ValueError(f"{exc}. For bleaching bands, enable signed spectra or amplitudes.") from exc
        raise
    fit = McrAR(c_regr="OLS" if signed_amplitudes else "NNLS", st_regr="OLS" if signed_spectra else "NNLS",
                c_constraints=[], st_constraints=[],
                max_iter=max_iter, tol_increase=None, tol_err_change=1e-12)
    fit.fit(od, ST=starting_spectra)
    if fit.C_opt_ is None or fit.ST_opt_ is None:
        raise ValueError("MCR-ALS failed to find a finite solution")
    norms = np.linalg.norm(fit.ST_opt_, axis=1)
    if np.any(norms == 0) or not np.isfinite(norms).all():
        raise ValueError("An MCR-ALS component collapsed. Try a smaller component count")
    amplitudes = fit.C_opt_ * norms
    spectra = fit.ST_opt_ / norms[:, None]
    reconstructed = amplitudes @ spectra
    residual = od - reconstructed
    rmse = np.linalg.norm(residual) / np.sqrt(residual.size)
    relative_residual = np.linalg.norm(residual) / np.linalg.norm(od)
    stop_flags = [name for name in (
        "exit_max_iter_reached", "exit_tol_increase", "exit_tol_n_increase",
        "exit_tol_err_change", "exit_tol_n_above_min",
    ) if getattr(fit, name, False)]

    with h5py.File(run.path, "r+") as file:
        entry = run._writable_entry(file)
        if source_path not in file:
            raise ValueError("The source correction no longer exists")
        inputs = dict(source=source_path, components=components, max_iterations=max_iter,
                      signed_amplitudes=signed_amplitudes, signed_spectra=signed_spectra,
                      amplitudes_constraint="OLS" if signed_amplitudes else "NNLS",
                      spectra_constraint="OLS" if signed_spectra else "NNLS",
                      initialization="Successive projections of measured spectra")
        if wavelength_range is not None:
            inputs["requested_wavelength_range_nm"] = wavelength_range
        with process_revision(entry, "mcr_als", "pyMCR", version("pyMCR"), utc_iso(time.time()), inputs) as (result, path):
            field(result, "source_time_index", time_rows)
            field(result, "source_wavelength_index", indices)
            field(result, "initialization_time_index", time_rows[starting_rows])
            field(result, "initial_spectra", starting_spectra, "1")
            field(result, "rmse", rmse, "1")
            field(result, "relative_residual", relative_residual, "1")
            field(result, "iterations", fit.n_iter)
            field(result, "best_iteration", fit.n_iter_opt)
            field(result, "stop_flags", ", ".join(stop_flags))
            field(result, "objective_history", fit.err, "1")
            field(result, "components", np.arange(1, components + 1))

            data = nx(result, "data", "NXdata")
            field(data, "time", all_times[time_rows], "s")
            if all_dose is not None and np.isfinite(all_dose[time_rows]).any():
                field(data, "dose", all_dose[time_rows], "Gy")
                data.attrs["dose_indices"] = 0
            field(data, "wavelength", all_wavelengths[indices], "nm")
            for name, values in (("fitted_od", reconstructed), ("residual_od", residual)):
                data.create_dataset(name, data=values, compression="gzip", compression_opts=1).attrs["units"] = "1"
            axes(data, "fitted_od", ("time", "wavelength"), ("residual_od",))
            result.attrs["default"] = "data"

            spectral = nx(result, "spectra", "NXdata")
            spectral["component"] = result["components"]
            spectral["wavelength"] = data["wavelength"]
            field(spectral, "loadings", spectra, "1", "Spectra normalized to unit L2 norm")
            axes(spectral, "loadings", ("component", "wavelength"))

            kinetic = nx(result, "kinetics", "NXdata")
            kinetic["time"] = data["time"]
            if "dose" in data:
                kinetic["dose"] = data["dose"]
                kinetic.attrs["dose_indices"] = 0
            kinetic["component"] = result["components"]
            field(kinetic, "amplitudes", amplitudes, "1", "Relative component amplitudes")
            axes(kinetic, "amplitudes", ("time", "component"))
    return path


def read_mcr(run, path=None):
    with h5py.File(run.path, "r") as file:
        entry = run._writable_entry(file)
        result = file[path] if path else next(reversed(list(published_processes(entry, "mcr_als"))), None)
        if result is None:
            return None
        source = result["parameters/source"].asstr()[()]
        correction = file[source].parent.parent
        anchor_od = correction["anchor_od"][:, result["source_wavelength_index"][:]]
        latest_correction = next(reversed(list(published_processes(entry, "blank_correction"))))
        return dict(path=result.name, source=source, stale=latest_correction.name != correction.name,
                    anchor_time=correction["anchor_time"][:], anchor_drift=anchor_od - anchor_od[0],
                    anchor_dose=correction["anchor_dose"][:] if "anchor_dose" in correction else None,
                    signed_spectra=bool(result["parameters/signed_spectra"][()]) if "signed_spectra" in result["parameters"] else True,
                    signed_amplitudes=bool(result["parameters/signed_amplitudes"][()]) if "signed_amplitudes" in result["parameters"] else False,
                    dose=result["kinetics/dose"][:] if "dose" in result["kinetics"] else None,
                    spectra=result["spectra/loadings"][:], wavelength=result["spectra/wavelength"][:],
                    amplitudes=result["kinetics/amplitudes"][:], time=result["kinetics/time"][:],
                    rmse=float(result["rmse"][()]), relative_residual=float(result["relative_residual"][()]),
                    iterations=int(result["iterations"][()]), stop_flags=result["stop_flags"].asstr()[()])


def validate_schema(run):
    """Verify the Gamma v2 acquisition schema and the dimensions of the committed records."""
    with h5py.File(run.path, "r") as file:
        entry = run._writable_entry(file)
        required_groups = {
            "entry": "NXentry", "entry/instrument": "NXinstrument", "entry/acquisition": "NXcollection",
            "entry/instrument/detector_1": "NXdetector", "entry/instrument/detector_2": "NXdetector",
            "entry/raw_ch1": "NXdata", "entry/raw_ch2": "NXdata", "entry/od_live": "NXdata",
            "entry/blanks": "NXcollection", "entry/processing": "NXcollection", "entry/calibration": "NXcollection",
        }
        for path, cls in required_groups.items():
            if file[path].attrs.get("NX_class") != cls:
                raise ValueError(f"/{path} should be {cls}")
        count = int(entry["acquisition"].attrs["committed_rows"])
        for _, dataset in run._row_fields(entry):
            if len(dataset) != count:
                raise ValueError(f"{dataset.name} has {len(dataset)} rows, expected {count}")
        groups = [entry[name] for name in ("raw_ch1", "raw_ch2", "od_live")]
        for kind in ("blank_correction", "mcr_als"):
            for process in published_processes(entry, kind):
                if process.attrs.get("NX_class") != "NXprocess" or process["parameters/source"].asstr()[()] not in file:
                    raise ValueError(f"Invalid processing provenance in {process.name}")
                groups.extend(group for group in process.values() if group.attrs.get("NX_class") == "NXdata")
        for group in groups:
            names = tuple(group.attrs["axes"])
            shape = tuple(len(group[name]) for name in names)
            for name in (group.attrs["signal"], *group.attrs.get("auxiliary_signals", ())):
                if group[name].shape != shape:
                    raise ValueError(f"Signal and axes differ in {group[name].name}")
        return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "upgrade", "recalculate", "mcr"):
        subparser = commands.add_parser(command)
        subparser.add_argument("file", type=Path)
        if command == "upgrade":
            subparser.add_argument("destination", type=Path)
        if command == "mcr":
            subparser.add_argument("--components", type=int, required=True)
            subparser.add_argument("--iterations", type=int, default=50)
            subparser.add_argument("--wavelength", type=float, nargs=2, metavar=("MIN_NM", "MAX_NM"))
            subparser.add_argument("--signed-spectra", action="store_true")
            subparser.add_argument("--signed-amplitudes", action="store_true")
    args = parser.parse_args()
    run = AvantesRun(args.file)
    try:
        if args.command == "validate":
            print(f"Gamma HDF5 v2 validated: {validate_schema(run)} committed rows")
        elif args.command == "upgrade":
            print(run.upgrade(args.destination).path)
        elif args.command == "recalculate":
            print(run.recalculate())
        else:
            print(fit_mcr(run, args.components, args.iterations, args.wavelength,
                          signed_spectra=args.signed_spectra, signed_amplitudes=args.signed_amplitudes))
    except (KeyError, ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
