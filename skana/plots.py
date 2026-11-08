"""Diagnostic figures shared by Streamlit and notebook."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from .matrix import MatrixData


def image(data: MatrixData, matrix: np.ndarray, title: str,
          color_limits: tuple[float, float] | None = None):
    fig, ax = plt.subplots(figsize=(7, 4))
    limits = {} if color_limits is None else {"vmin": color_limits[0], "vmax": color_limits[1]}
    mesh = ax.pcolormesh(data.delay, data.wavelength, np.asarray(matrix).T,
                         shading="auto", cmap="RdBu_r", **limits)
    fig.colorbar(mesh, ax=ax, label="O.D.")
    ax.set(xlabel="Delay", ylabel="Wavelength", title=title)
    fig.tight_layout()
    return fig


def profiles(data: MatrixData, c: np.ndarray, s: np.ndarray, title: str):
    fig, (ax_s, ax_c) = plt.subplots(1, 2, figsize=(11, 4))
    for j in range(s.shape[1]):
        ax_s.plot(data.wavelength, s[:, j], label=f"{j + 1}")
        ax_c.plot(data.delay, c[:, j], label=f"{j + 1}")
    ax_s.set(xlabel="Wavelength", ylabel="Signal", title=f"{title}: spectra")
    ax_c.set(xlabel="Delay", ylabel="Amplitude", title=f"{title}: kinetics")
    ax_s.legend(title="Component")
    ax_c.legend(title="Component")
    fig.tight_layout()
    return fig


def diagnostics(data: MatrixData, model: np.ndarray, residual: np.ndarray, title: str):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, array, label in zip(axes, (data.matrix, model, residual),
                                ("Data", "Model", "Residual")):
        mesh = ax.pcolormesh(data.delay, data.wavelength, array.T,
                             shading="auto", cmap="RdBu_r")
        fig.colorbar(mesh, ax=ax)
        ax.set(xlabel="Delay", ylabel="Wavelength", title=label)
    fig.suptitle(title)
    fig.tight_layout()
    return fig


def ambiguity_ensemble(data: MatrixData, solutions, *, max_lines: int = 200):
    """Show spectra and kinetics across accepted rotations."""
    fig, (ax_s, ax_c) = plt.subplots(1, 2, figsize=(11, 4))
    indices = np.linspace(0, len(solutions) - 1,
                          min(max_lines, len(solutions))).astype(int)
    for index in indices:
        solution = solutions[index]
        ax_s.plot(data.wavelength, solution.s, color="steelblue", alpha=0.08)
        ax_c.plot(data.delay, solution.c, color="darkorange", alpha=0.08)
    ax_s.set(xlabel="Wavelength", ylabel="Signal", title="Accepted spectra")
    ax_c.set(xlabel="Delay", ylabel="Amplitude", title="Accepted kinetics")
    fig.tight_layout()
    return fig
