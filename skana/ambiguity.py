"""Two/three-component rotational ambiguity search from the active R workflow."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np


@dataclass(frozen=True)
class Rotation:
    t12: float
    t21: float
    c: np.ndarray
    s: np.ndarray


@dataclass(frozen=True)
class Rotation3:
    t12: float
    t21: float
    t23: float
    t32: float
    t13: float
    t31: float
    c: np.ndarray
    s: np.ndarray


def rotate_two(c: np.ndarray, s: np.ndarray, *, components: tuple[int, int] = (0, 1),
               step: float = 0.05, positivity: float = -0.01,
               presence_mask: np.ndarray | None = None, max_steps: int = 100) -> list[Rotation]:
    """Search R ``rotAmb2``'s three directional branches per coefficient.

    The R search is unbounded. ``max_steps`` prevents an infinite branch for
    degenerate factors; if the cap is reached, the result is incomplete.
    """
    c, s = np.asarray(c, dtype=float), np.asarray(s, dtype=float)
    if c.ndim != 2 or s.ndim != 2 or c.shape[1] != s.shape[1]:
        raise ValueError("C and S must be 2D with equal component counts.")
    if len(components) != 2 or len(set(components)) != 2 or any(i < 0 or i >= c.shape[1] for i in components):
        raise ValueError("Select two distinct component indices.")
    if step <= 0 or max_steps < 1:
        raise ValueError("step and max_steps must be positive.")
    c0, s0 = c[:, components], s[:, components]
    if presence_mask is not None:
        presence_mask = np.asarray(presence_mask, dtype=float)
        if presence_mask.shape != c.shape:
            raise ValueError("presence_mask shape must match C.")
    solutions: list[Rotation] = []
    for direction_12 in (0, -1, 1):
        for index_12 in range(1, max_steps + 1):
            t12 = step * index_12 * direction_12
            outer_ok = False
            for direction_21 in (0, -1, 1):
                for index_21 in range(1, max_steps + 1):
                    t21 = step * index_21 * direction_21
                    rotation = np.array([[1., t12], [t21, 1.]])
                    if abs(np.linalg.det(rotation)) <= 1e-12:
                        break
                    s1 = s0 @ rotation.T
                    c1 = c0 @ np.linalg.inv(rotation)
                    norms = np.max(s1, axis=0)
                    if np.any(norms <= 0) or not np.isfinite(norms).all():
                        break
                    s1 = s1 / norms
                    c1 = c1 * norms
                    if presence_mask is not None:
                        c1 = c1 * presence_mask[:, components]
                    valid = (np.min(s1) >= positivity * np.max(s1)
                             and np.min(c1) >= positivity * np.max(c1))
                    if not valid:
                        break
                    solutions.append(Rotation(t12, t21, c1, s1))
                    outer_ok = True
                    if direction_21 == 0:
                        break
            if direction_12 == 0 or not outer_ok:
                break
    return solutions


def rotate_three(c: np.ndarray, s: np.ndarray, *, components: tuple[int, int, int] = (0, 1, 2),
                 step: float = 0.05, positivity: float = -0.01,
                 radius: int = 1, presence_mask: np.ndarray | None = None) -> list[Rotation3]:
    """Explore a bounded six-parameter subset of R ``rotAmb3`` transformations.

    ``radius=1`` evaluates 3**6 transformations; larger radii increase the
    grid combinatorially. Reconstruction is exact absent a presence mask.
    """
    c, s = np.asarray(c, dtype=float), np.asarray(s, dtype=float)
    if c.ndim != 2 or s.ndim != 2 or c.shape[1] != s.shape[1]:
        raise ValueError("C and S must be 2D with equal component counts.")
    if len(components) != 3 or len(set(components)) != 3 or any(i < 0 or i >= c.shape[1] for i in components):
        raise ValueError("Select three distinct component indices.")
    if step <= 0 or radius not in (1, 2):
        raise ValueError("step must be positive and radius must be 1 or 2.")
    if presence_mask is not None:
        presence_mask = np.asarray(presence_mask, dtype=float)
        if presence_mask.shape != c.shape:
            raise ValueError("presence_mask shape must match C.")
    c0, s0 = c[:, components], s[:, components]
    values = range(-radius, radius + 1)
    solutions = []
    for integers in product(values, repeat=6):
        t12, t21, t23, t32, t13, t31 = (step * x for x in integers)
        rotation = np.array([[1., t12, t13], [t21, 1., t23], [t31, t32, 1.]])
        if abs(np.linalg.det(rotation)) <= 1e-12:
            continue
        s1 = s0 @ rotation.T
        c1 = c0 @ np.linalg.inv(rotation)
        norms = np.max(s1, axis=0)
        if np.any(norms <= 0) or not np.isfinite(norms).all():
            continue
        s1 = s1 / norms
        c1 = c1 * norms
        if presence_mask is not None:
            c1 = c1 * presence_mask[:, components]
        if np.min(s1) < positivity * np.max(s1) or np.min(c1) < positivity * np.max(c1):
            continue
        solutions.append(Rotation3(t12, t21, t23, t32, t13, t31, c1, s1))
    return solutions
