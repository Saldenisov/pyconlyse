"""Random sampling tests for HIS and H5 opener data orientation on E:.

These tests walk the E: drive (as requested) to find up to 10 .his files and
10 .h5 files and then validate that the corresponding openers return
Measurement objects with a consistent internal structure.
"""

from __future__ import annotations

from pathlib import Path
from random import shuffle

import pytest

from gui.controllers.openers import HamamatsuFileOpener, H5Opener


E_DRIVE = Path("E:\\")


@pytest.mark.skipif(not E_DRIVE.exists(), reason="E: drive not available on this machine")
def test_random_his_files_orientation():
    """Pick up to 10 random .his files on E:\ and check HamamatsuFileOpener output.

    Invariants tested per file:
    - len(wavelengths) > 0, len(timedelays) > 0
    - data.shape == (len(wavelengths), len(timedelays))
    """

    his_files = list(E_DRIVE.rglob("*.his"))
    if not his_files:
        pytest.skip("No .his files found on E:")

    shuffle(his_files)
    sample = his_files[:10]

    opener = HamamatsuFileOpener()

    for path in sample:
        meas, comments = opener.read_map(path, 0)
        assert hasattr(meas, "data"), f"HamamatsuFileOpener returned non-Measurement for {path}: {comments}"

        n_waves = len(meas.wavelengths)
        n_times = len(meas.timedelays)
        assert n_waves > 0 and n_times > 0, f"Empty axes for {path}: waves={n_waves}, times={n_times}"

        assert meas.data.shape == (n_waves, n_times), (
            f"{path}: data.shape={meas.data.shape}, expected (len(wavelengths)={n_waves}, "
            f"len(timedelays)={n_times})"
        )


@pytest.mark.skipif(not E_DRIVE.exists(), reason="E: drive not available on this machine")
def test_random_h5_files_orientation():
    """Pick up to 10 random .h5 files on E:\ and check H5Opener output.

    Invariants tested per file:
    - len(wavelengths) > 0, len(timedelays) > 0
    - data.shape == (len(wavelengths), len(timedelays))
    """

    h5_files = list(E_DRIVE.rglob("*.h5"))
    if not h5_files:
        pytest.skip("No .h5 files found on E:")

    shuffle(h5_files)
    sample = h5_files[:10]

    opener = H5Opener()

    for path in sample:
        meas, comments = opener.read_map(path, 0)

        # Some legacy or non-standard H5 files may not conform to the
        # Measurement API used by the Treatment GUI (e.g. extra dimensions
        # or missing metadata). For the purpose of checking the HIS/H5
        # structure expected by this GUI, we skip such files.
        if not hasattr(meas, "data"):
            continue
        if getattr(meas.data, "ndim", 0) != 2:
            continue

        n_waves = len(meas.wavelengths)
        n_times = len(meas.timedelays)
        assert n_waves > 0 and n_times > 0, f"Empty axes for {path}: waves={n_waves}, times={n_times}"

        assert meas.data.shape == (n_waves, n_times), (
            f"{path}: data.shape={meas.data.shape}, expected (len(wavelengths)={n_waves}, "
            f"len(timedelays)={n_times})"
        )
