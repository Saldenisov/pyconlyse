"""
ML Stability model retraining module.

Extracted from ELYSE_stability.ipynb.  Trains an XGBoost regressor that
predicts optical-density variance from the ratio of two spectra (i02 / ie2),
after background subtraction, outlier cleaning and binning.

Usage from Python
-----------------
>>> from DeviceServers.data.ml.ml_retrain import retrain_model
>>> result = retrain_model(
...     data_path="E:/spectra_raw.h5",
...     model_dir="C:/dev/pyconlyse/DeviceServers/data/ml/models",
... )
>>> print(result)  # {'r2_train': …, 'r2_test': …}
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

import h5py
import joblib
import numpy as np
from scipy.spatial.distance import pdist
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor


# ---------------------------------------------------------------------------
# Helper: bin a 2-D array along axis-1 by sub-sampling every *step* columns
# ---------------------------------------------------------------------------

def _split_array(array_1d: np.ndarray, n_bins: int) -> np.ndarray:
    step = round(len(array_1d) / n_bins)
    return array_1d[::step][:n_bins]


def _bin_2d(array_2d: np.ndarray, n_bins: int) -> np.ndarray:
    if n_bins <= 0:
        return array_2d
    return np.array([_split_array(row, n_bins) for row in array_2d])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrain_model(
    data_path: str,
    model_dir: str,
    scaler_filename: str = "UV1_scaler.joblib",
    model_filename: str = "UV1_xgb.joblib",
    n_bins: int = 100,
    test_size: float = 0.3,
    seed: int = 18,
    from_pixel: int = 200,
    to_pixel: int = 800,
    bg_multiplier: float = 2.0,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> dict:
    """Train an XGBoost regressor and persist model + scaler as *joblib* files.

    Parameters
    ----------
    data_path : str
        Path to the HDF5 file that contains the raw spectra datasets
        (``bg1``, ``bg2``, ``i01``, ``ie1``, ``i02``, ``ie2``, ``timestamp``).
    model_dir : str
        Directory where the trained model and scaler will be saved.
    scaler_filename / model_filename : str
        File names for the saved artefacts (default ``UV1_*.joblib``).
    n_bins : int
        Number of spectral bins used to down-sample the ratio feature.
    test_size : float
        Fraction of data kept for the test split.
    seed : int
        Random state for reproducibility.
    from_pixel / to_pixel : int
        Pixel range to select from the raw spectra.
    bg_multiplier : float
        Outlier threshold – spectra whose pixel-sum is below
        ``bg_multiplier × sum_bg`` are dropped.
    progress_callback : callable, optional
        ``(message, percent) -> None`` called at key stages so a GUI can
        report progress.

    Returns
    -------
    dict
        ``{'r2_train': float, 'r2_test': float}``
    """

    def _report(msg: str, pct: int) -> None:
        if progress_callback is not None:
            progress_callback(msg, pct)

    # ------------------------------------------------------------------
    # 1. Load raw data
    # ------------------------------------------------------------------
    _report("Loading data…", 0)
    with h5py.File(data_path, "r") as f:
        bg1 = f["bg1"][1:]
        bg2 = f["bg2"][1:]
        i01 = f["i01"][1:]
        ie1 = f["ie1"][1:]
        i02 = f["i02"][1:]
        ie2 = f["ie2"][1:]
    _report("Data loaded", 10)

    # ------------------------------------------------------------------
    # 2. Background subtraction & OD calculation
    # ------------------------------------------------------------------
    _report("Computing optical density…", 15)
    dem1 = ie1 - bg1
    dem2 = ie2 - bg2
    dem1[dem1 == 0] = 1
    dem2[dem2 == 0] = 1

    bot = (i02 - bg2) / dem2
    bot[bot == 0] = 0.0001

    res = np.abs(((i01 - bg1) / dem1) / bot)
    res[res == 0] = 0.00001
    od = np.log10(res)

    # ------------------------------------------------------------------
    # 3. Pixel range selection
    # ------------------------------------------------------------------
    od_sel = od[:, from_pixel:to_pixel]
    i02_sel = i02[:, from_pixel:to_pixel]
    ie2_sel = ie2[:, from_pixel:to_pixel]
    _report("OD computed and pixel range selected", 25)

    # ------------------------------------------------------------------
    # 4. Compute target: OD variance per spectrum
    # ------------------------------------------------------------------
    od_var = np.std(od_sel, axis=1)

    # ------------------------------------------------------------------
    # 5. Compute reference distances (euclidean) for outlier filtering
    # ------------------------------------------------------------------
    _report("Computing distances…", 30)
    ref_distances = np.array([
        pdist([i02j, ie2j], "euclidean")[0]
        for i02j, ie2j in zip(i02_sel, ie2_sel)
    ])

    sum_bg = np.sum(
        (np.average(bg1[:, from_pixel:to_pixel], axis=0)
         + np.average(bg2[:, from_pixel:to_pixel], axis=0)) / 2
    )
    _report("Distances computed", 40)

    # ------------------------------------------------------------------
    # 6. Clean outliers
    # ------------------------------------------------------------------
    _report("Cleaning outliers…", 45)
    ref_median = np.median(ref_distances)
    good_idx = np.where(
        (ref_distances < 5 * ref_median)
        & (np.sum(i02_sel, axis=1) > bg_multiplier * sum_bg)
        & (np.sum(ie2_sel, axis=1) > bg_multiplier * sum_bg)
    )[0]

    i02_clean = i02_sel[good_idx]
    ie2_clean = ie2_sel[good_idx]
    od_var_clean = od_var[good_idx]
    ref_dist_clean = ref_distances[good_idx]
    _report(f"Outliers removed: {len(od_var)} → {len(od_var_clean)} spectra", 50)

    # ------------------------------------------------------------------
    # 7. Prepare features (ratio, binned, scaled)
    # ------------------------------------------------------------------
    _report("Preparing features…", 55)
    I02_binned = _bin_2d(i02_clean, n_bins)
    Ie2_binned = _bin_2d(ie2_clean, n_bins)
    I_ratio = I02_binned / Ie2_binned

    scaler = StandardScaler()
    I_ratio_norm = scaler.fit_transform(I_ratio)

    # Insert euclidean distance as first feature (as in notebook cell 41)
    X = np.insert(I_ratio_norm, 0, ref_dist_clean, axis=1)

    x_train, x_test, y_train, y_test = train_test_split(
        X, od_var_clean, test_size=test_size, random_state=seed,
    )
    _report(f"Features ready – train {x_train.shape[0]}, test {x_test.shape[0]}", 65)

    # ------------------------------------------------------------------
    # 8. Train XGBoost regressor
    # ------------------------------------------------------------------
    _report("Training XGBoost model…", 70)
    params = {
        "n_estimators": 400,
        "learning_rate": 0.08,
        "max_depth": 6,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "gamma": 0,
        "reg_alpha": 0,
        "reg_lambda": 1,
        "min_child_weight": 1,
        "objective": "reg:squarederror",
    }
    model = XGBRegressor(**params)
    model.fit(x_train, y_train)
    _report("Training complete", 85)

    # ------------------------------------------------------------------
    # 9. Evaluate
    # ------------------------------------------------------------------
    r2_train = float(r2_score(y_train, model.predict(x_train)))
    r2_test = float(r2_score(y_test, model.predict(x_test)))
    _report(f"R² train={r2_train:.3f}  test={r2_test:.3f}", 90)

    # ------------------------------------------------------------------
    # 10. Save artefacts
    # ------------------------------------------------------------------
    _report("Saving model…", 92)
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(model, os.path.join(model_dir, model_filename))
    joblib.dump(scaler, os.path.join(model_dir, scaler_filename))
    _report("Model saved", 100)

    return {"r2_train": r2_train, "r2_test": r2_test}
