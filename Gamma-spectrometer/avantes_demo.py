"""Generate a reproducible synthetic Avantes run with independent sample, fiber and lamp signals."""

import argparse
from pathlib import Path

import h5py
import numpy as np

from avantes_analysis import fit_mcr
from avantes_h5 import field, nx
from avantes_run import AvantesRun, optical_density


def generate_demo(path):
    wavelength = np.linspace(250, 800, 551)
    wavelengths = wavelength, wavelength.copy()
    elapsed = np.arange(0, 3601, 15, dtype=float)
    anchor_times = {0, 600, 1500, 2700, 3600}
    epoch = 1767225600.0
    rng = np.random.default_rng(42)

    def band(center, width):
        return np.exp(-0.5 * ((wavelength - center) / width) ** 2)

    sample_spectra = np.stack((0.6 * band(342, 22), 0.35 * band(423, 30)))
    sample_amplitudes = np.stack((1 - np.exp(-elapsed / 700), (elapsed / elapsed[-1]) ** 1.65), axis=1)
    sample_od = sample_amplitudes @ sample_spectra
    fiber_od = ((1 - np.exp(-elapsed[:, None] / 420)) * 0.32 * band(320, 52)
                + (elapsed[:, None] / elapsed[-1]) ** 1.3 * 0.20 * band(388, 66))
    lamp_base = 25000 * (0.38 + 0.52 * band(440, 145) + 0.25 * band(640, 190))
    lamp_relative = 1 + elapsed[:, None] / elapsed[-1] * (0.12 * band(375, 62) - 0.08 * band(520, 94))
    dark = 46 + 0.02 * (wavelength - 250), 54 + 0.018 * (wavelength - 250)
    cuvette = 0.25 * band(255, 21)
    static_sample = 0.03 * band(360, 45)
    metadata = dict(collection_interval_s=15, channel_ok=[True, True], channels=[
        dict(serial=serial, integration_ms=1, trigger_mode=1, averages=40) for serial in ("DEMO-SAMPLE", "DEMO-MONITOR")
    ])

    def measure(time_s, role, lamp, absorption, *, noise=True):
        signals = (0.93 * lamp * 10 ** (-absorption), lamp)
        ch1, ch2 = (dark[i] + signal + (
            rng.normal(0, np.sqrt(signal / 40)) if noise else 0
        ) for i, signal in enumerate(signals))
        return dict(ch1=ch1, ch2=ch2, metadata=dict(metadata, utc_s=epoch + time_s, role=role))

    reference = measure(-60, "reference", lamp_base, np.zeros_like(wavelength), noise=False)
    background = measure(-75, "background", np.zeros_like(wavelength), np.zeros_like(wavelength), noise=False)
    initial_blank = measure(-30, "initial_blank", lamp_base, cuvette)
    sample_zero = measure(-15, "sample_t0", lamp_base, cuvette + static_sample)

    def od(block):
        return optical_density(block["ch1"], block["ch2"], (reference["ch1"], reference["ch2"]), dark, wavelengths)

    settings = dict(
        spectrometers={str(i + 1): channel for i, channel in enumerate(metadata["channels"])},
        exposure=dict(dose_rate_gy_h=72, irradiating_at_start=True, window_diameter_mm=8, path_length_mm=10),
        synthetic=True,
    )
    calibration = {key: [block] for key, block in (
        ("background", background), ("reference", reference), ("initial_blank", initial_blank), ("sample_t0", sample_zero)
    )}
    run = AvantesRun.create(path, wavelengths, [channel["serial"] for channel in metadata["channels"]],
                            epoch, settings, calibration)
    run.add_blank(0, [initial_blank], od(initial_blank), initial=True)
    live = []
    measured_blank_od = [od(initial_blank)]
    kinetic_zero = od(sample_zero)
    for i, time_s in enumerate(elapsed):
        lamp = lamp_base * lamp_relative[i]
        block = measure(time_s, "collection", lamp, cuvette + static_sample + sample_od[i] + fiber_od[i])
        measured_od = od(block)
        live.append(measured_od - kinetic_zero)
        run.append(time_s, epoch + time_s, block["ch1"], block["ch2"], measured_od, live[-1], block["metadata"])
        if time_s > 0 and time_s in anchor_times:
            blank = measure(time_s, "blank", lamp, cuvette + fiber_od[i])
            measured_blank_od.append(od(blank))
            run.add_blank(time_s, [blank], measured_blank_od[-1])
    run.mark_irradiation(False, epoch + elapsed[-1])

    _, corrected, _ = run.view("od_corrected", limit=len(elapsed))
    endpoints_only = np.asarray(live) - elapsed[:, None] / elapsed[-1] * (measured_blank_od[-1] - measured_blank_od[0])
    endpoint_rmse = np.sqrt(np.mean((endpoints_only - sample_od) ** 2))
    all_blanks_rmse = np.sqrt(np.mean((corrected - sample_od) ** 2))
    with h5py.File(run.path, "r+") as file:
        truth = nx(file["entry"], "simulation_truth", "NXcollection")
        truth.attrs["note"] = "Synthetic truth for checking the correction; it is not used by MCR-ALS"
        field(truth, "sample_od", sample_od, "1")
        field(truth, "fiber_od", fiber_od, "1")
        field(truth, "lamp_relative", lamp_relative, "1")
        field(truth, "endpoints_only_rmse", endpoint_rmse, "1")
        field(truth, "all_blanks_rmse", all_blanks_rmse, "1")
        recovery_days = np.arange(8.0)
        field(truth, "recovery_time", recovery_days, "day")
        field(truth, "fiber_recovery_od", fiber_od[-1] * np.exp(-recovery_days[:, None] / 3), "1")
        field(truth, "recovery_time_constant", 3, "day")
    return run, endpoint_rmse, all_blanks_rmse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--fit", action="store_true", help="Save a two-component MCR-ALS fit")
    options = parser.parse_args()
    run, endpoints, all_blanks = generate_demo(options.file)
    print(f"{run.path}\nOD RMSE: {endpoints:.5f} with 2 blanks, {all_blanks:.5f} with 5 blanks")
    if options.fit:
        print(fit_mcr(run, 2))


if __name__ == "__main__":
    main()
