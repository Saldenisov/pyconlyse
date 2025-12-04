"""Tests for data orientation and consistency of Hamamatsu, H5 and ASCII openers.

These tests are meant to catch missing/extra transposes by checking that
Measurement.data always has shape (len(wavelengths), len(timedelays)) and that
HIS- and H5-derived measurements for the same run agree on axes.

The tests are written to be robust on a developer machine:
- They will be skipped if the expected data directories or files do not exist.
- They only import the openers and core datastructures, so they avoid
  device-server DLL dependencies that affect other tests.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gui.controllers.openers import HamamatsuFileOpener, H5Opener, ASCIIOpener


# Base data directories as provided by the developer
DATA_VD2 = Path(r"E:\\DATA_VD2")
DATA_VD = Path(r"E:\\DATA_VD")


@pytest.mark.skipif(not DATA_VD2.exists(), reason="DATA_VD2 directory not available on this machine")
def test_his_and_h5_axes_agree_for_same_run():
    """Check that a HIS/H5 pair for the same run has consistent axes and shapes.

    We look for a folder that contains both ABSxxxx.his and ABSxxxx.h5 and
    compare the resulting Measurement objects from HamamatsuFileOpener and
    H5Opener for that pair.
    """

    # Find a folder with both ABS*.his and ABS*.h5 present
    candidate_pairs: list[tuple[Path, Path]] = []
    for his_path in DATA_VD2.rglob("ABS*.his"):
        h5_path = his_path.with_suffix(".h5")
        if h5_path.exists():
            candidate_pairs.append((his_path, h5_path))
            break

    if not candidate_pairs:
        pytest.skip("No ABSxxx.his / ABSxxx.h5 pair found under DATA_VD2")

    his_path, h5_path = candidate_pairs[0]

    ham = HamamatsuFileOpener()
    h5o = H5Opener()

    his_meas, _ = ham.read_map(his_path, 0)
    h5_meas, _ = h5o.read_map(h5_path, 0)

    # Basic shape invariants: data always (wavelengths, timedelays)
    assert his_meas.data.shape == (
        len(his_meas.wavelengths),
        len(his_meas.timedelays),
    ), f"HIS data shape {his_meas.data.shape} not (len(waves), len(times))"

    assert h5_meas.data.shape == (
        len(h5_meas.wavelengths),
        len(h5_meas.timedelays),
    ), f"H5 data shape {h5_meas.data.shape} not (len(waves), len(times))"

    # Axes should match between HIS and H5 for same run
    assert np.allclose(his_meas.wavelengths, h5_meas.wavelengths), (
        f"Wavelength axes differ for pair: {his_path} vs {h5_path}"
    )
    assert np.allclose(his_meas.timedelays, h5_meas.timedelays), (
        f"Timedelay axes differ for pair: {his_path} vs {h5_path}"
    )

    # If the H5 file is truly built from the HIS file, the data should at least
    # be the same up to floating tolerance. If this is too strict we can
    # relax it later, but it will catch transpose mistakes immediately.
    assert his_meas.data.shape == h5_meas.data.shape
    # either equal or equal after a transpose; enforce one of them
    same_direct = np.allclose(his_meas.data, h5_meas.data)
    same_transposed = np.allclose(his_meas.data, h5_meas.data.T)
    assert same_direct or same_transposed, (
        "HIS/H5 data for same run differ more than a transpose would explain; "
        f"his_shape={his_meas.data.shape}, h5_shape={h5_meas.data.shape}"
    )


@pytest.mark.skipif(not DATA_VD2.exists(), reason="DATA_VD2 directory not available on this machine")
def test_h5_data_orientation_is_wavelengths_by_timedelays():
    """Validate orientation of H5Opener alone using the first ABS*.h5 file found."""

    h5_files = sorted(DATA_VD2.rglob("ABS*.h5"))
    if not h5_files:
        pytest.skip("No ABS*.h5 files found under DATA_VD2")

    h5_path = h5_files[0]
    h5o = H5Opener()
    meas, _ = h5o.read_map(h5_path, 0)

    assert meas.data.shape == (
        len(meas.wavelengths),
        len(meas.timedelays),
    ), f"H5 data shape {meas.data.shape} not (len(waves), len(times))"


@pytest.mark.skipif(not DATA_VD2.exists(), reason="DATA_VD2 directory not available on this machine")
def test_his_data_orientation_is_wavelengths_by_timedelays():
    """Validate orientation of HamamatsuFileOpener using the first ABS*.his file."""

    his_files = sorted(DATA_VD2.rglob("ABS*.his"))
    if not his_files:
        pytest.skip("No ABS*.his files found under DATA_VD2")

    his_path = his_files[0]
    ham = HamamatsuFileOpener()
    meas, _ = ham.read_map(his_path, 0)

    assert meas.data.shape == (
        len(meas.wavelengths),
        len(meas.timedelays),
    ), f"HIS data shape {meas.data.shape} not (len(waves), len(times))"


@pytest.mark.skipif(not DATA_VD.exists(), reason="DATA_VD directory not available on this machine")
def test_dat_data_orientation_matches_docstring():
    """Check ASCIIOpener orientation matches its documented table layout.

    Docstring:
        0 wave1 wave2   wave3   ...   waveN
        timedelay1  X11   X12   X13 ... X1N
        timedelay2  X21   X22   X23 ... X2N
        ...

    ASCIIOpener.read_map transposes data[1:, 1:], so the resulting
    Measurement.data should again be (wavelengths, timedelays).
    """

    dat_files = sorted(DATA_VD.rglob("*.dat"))
    if not dat_files:
        pytest.skip("No .dat files found under DATA_VD")

    dat_path = dat_files[0]
    ascii_opener = ASCIIOpener()
    meas, _ = ascii_opener.read_map(dat_path, 0)

    assert meas.data.shape == (
        len(meas.wavelengths),
        len(meas.timedelays),
    ), f"DAT data shape {meas.data.shape} not (len(waves), len(times))"
