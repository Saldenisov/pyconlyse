"""Discriminating vectors for the TRANCON client audit.

Native expectations come from static VI wires, not LabVIEW execution.
Run from any directory. This reads no experimental files and calls no devices.
"""

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

from utilities.dataio.laser_shot_correction import (
    CorrectionConfig,
    DISK_TO_CANONICAL,
    _corrected_signals,
    _optical_density,
    correct_block,
)
from treatment_service import TreatmentDataService


def _od_from_means(means):
    """Frozen pre-2026-10-04 V0 behavior for historical discriminating vectors.

    Current V0 uses a mean of per-shot logs and explicit pulse-state semantics.
    Keep the earlier audit comparator independent of production changes.
    """
    bg1, ir1, is1, bg2, ir2, is2 = means
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log10(((is1-bg1)/(ir1-bg1))/((is2-bg2)/(ir2-bg2)))


def native_raw_od(disk):
    """Raw_data_to_data.vi: [BGI, BGII, IeI, IeII, I0I, I0II]."""
    bg_i, bg_ii, ie_i, ie_ii, i0_i, i0_ii = disk
    with np.errstate(divide="ignore", invalid="ignore"):
        per_shot = np.log10(
            ((i0_i - bg_i) / (ie_i - bg_i))
            / ((i0_ii - bg_ii) / (ie_ii - bg_ii))
        )
    return per_shot.mean(axis=0)


def block(values):
    return np.repeat(np.asarray(values, dtype=float)[:, :, None], 3, axis=2)


def web_vd2(abs_value, base_value, noise_value):
    """Execute current separate-role calculation with in-memory map readers."""
    maps = {"ABS": abs_value, "BASE": base_value, "NOISE": noise_value}
    service = TreatmentDataService()
    service._require_path = lambda state, role: Path(role + ".his")
    service._get_opener_and_info = lambda path: (
        SimpleNamespace(average_map=lambda ignored: np.full((2, 3), maps[path.stem])),
        None,
    )
    result, _, _ = service._calc_abs_base_noise({})
    return float(result[0, 0])


def verify():
    wavelengths = np.array([500.0, 600.0, 700.0])
    config = CorrectionConfig(min_signal_counts=0.0, ratio_policy="positive")
    records = []

    disk = block([[0, 0], [0, 0], [1, 1], [1, 1], [1, 4], [1, 1]])
    canonical = disk[list(DISK_TO_CANONICAL)]
    native = float(native_raw_od(disk)[0])
    corrected = float(correct_block(canonical, wavelengths, config).od[0])
    emulator = float(_od_from_means(canonical.mean(axis=1))[0])
    np.testing.assert_allclose(native, 0.3010299956639812, atol=1e-12)
    np.testing.assert_allclose(corrected, native, atol=1e-12)
    assert abs(emulator - native) > 0.09
    records.append(dict(
        case="average_order", disk_group_values=disk[:, :, 0].tolist(),
        native_static_expected_od=native, correction_utility_od=corrected,
        current_v0_emulator_od=emulator, difference_od=emulator-native,
    ))

    disk = block([[10], [90], [110], [190], [210], [140]])
    canonical = disk[list(DISK_TO_CANONICAL)]
    native = float(native_raw_od(disk)[0])
    corrected = float(correct_block(canonical, wavelengths, config).od[0])
    emulator = float(_od_from_means(canonical.mean(axis=1))[0])
    np.testing.assert_allclose(native, np.log10(4.0), atol=1e-12)
    np.testing.assert_allclose(corrected, native, atol=1e-12)
    assert abs(emulator - native) > 0.03
    records.append(dict(
        case="detector_background_pairing", disk_group_values=disk[:, :, 0].tolist(),
        native_static_expected_od=native, correction_utility_od=corrected,
        current_v0_emulator_od=emulator, difference_od=emulator-native,
    ))

    abs_value, base_value, noise_value, ceren_value = 6.0, 10.0, 1.0, 2.0
    native = float(np.log10((base_value-noise_value)/(abs_value-noise_value-ceren_value)))
    current = web_vd2(abs_value, base_value, noise_value)
    without_ceren = float(np.log10((base_value-noise_value)/(abs_value-noise_value)))
    np.testing.assert_allclose(current, without_ceren, atol=1e-12)
    assert abs(native-current) > 0.22
    records.append(dict(
        case="vd2_cerenkov_role", ABS=abs_value, BASE=base_value,
        BRUIT=noise_value, CEREN=ceren_value, native_static_expected_od=native,
        current_web_od=current, native_ceren_zero_od=without_ceren,
        omitted_correction_difference_od=current-native,
    ))

    disk = block([[0], [0], [100], [100], [-100], [100]])
    canonical = disk[list(DISK_TO_CANONICAL)]
    assert np.isnan(native_raw_od(disk)).all()
    signals = _corrected_signals(canonical, "detector")
    absolute = _optical_density(signals, "legacy_absolute")
    positive = _optical_density(signals, "positive")
    np.testing.assert_allclose(absolute, 0.0, atol=1e-12)
    assert np.isnan(positive).all()
    records.append(dict(
        case="negative_ratio_low_level_policy",
        disk_group_values=disk[:, :, 0].tolist(), native_static_result="NaN",
        utility_legacy_absolute_od=float(absolute[0, 0]),
        utility_positive_result="NaN",
        boundary="Low-level OD policy only; whole-shot rejection is tested separately.",
    ))

    rejected = correct_block(canonical, wavelengths, config)
    assert rejected.valid_shot_count == 0
    assert np.isnan(rejected.od).all()
    records.append(dict(
        case="negative_signal_whole_shot_rejection", valid_shots=0,
        output="NaN", reasons=[list(x) for x in rejected.reasons],
    ))
    return {
        "format": "pyconlyse.trancon-client-discriminating-vectors",
        "format_version": 1,
        "native_execution": False,
        "native_basis": "Static lvkit wires in Raw_data_to_data.vi and VD2_TRABS_Calc.vi",
        "python_version": sys.version.split()[0], "numpy_version": np.__version__,
        "verified_cases": len(records), "cases": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify()
    rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
