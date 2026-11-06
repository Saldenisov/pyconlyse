"""Compute window-specific VD2 readouts from the shared Web preview, without camera I/O."""

import base64
from collections import deque
from dataclasses import dataclass
from functools import cached_property
import json
import math
from statistics import mean, stdev
from threading import Lock
import time

import numpy as np


READOUT_VERSION = 1
FRESH_SECONDS = 1.5
REGION_FIELDS = ("wavelengthMin", "wavelengthMax", "topPercent", "bottomPercent")


def _number(value):
    return type(value) in (int, float) and abs(value) <= 1e12


def parse_selection(raw):
    if len(raw) > 1024:
        raise ValueError("Selection is too long.")
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Invalid Alignment selection.") from exc
    if not isinstance(value, dict) or set(value) != {"region", "windows"}:
        raise ValueError("Expected an ROI and time windows.")
    region, windows = value["region"], value["windows"]
    if (not isinstance(region, dict) or set(region) != set(REGION_FIELDS)
            or not all(_number(v) for v in region.values())):
        raise ValueError("Invalid Alignment ROI.")
    lo, hi, top, bottom = (region[key] for key in REGION_FIELDS)
    if not (0 <= lo < hi and 0 <= top < bottom <= 100):
        raise ValueError("Choose increasing wavelength and vertical limits (0–100%).")
    if windows is not None and (
        not isinstance(windows, dict) or set(windows) != {"baseline", "signal"}
        or any(not isinstance(v, list) or len(v) != 2 or not all(_number(x) for x in v)
               for v in windows.values())
    ):
        raise ValueError("Invalid Alignment time windows.")
    return (float(lo), float(hi), float(top), float(bottom)), windows


def _profile(observation, region):
    frame = observation.payload
    axes = frame.get("calibration")
    if not axes:
        raise ValueError("Waiting for calibrated axes from the Live image.")
    width, height = frame["width"], frame["height"]
    wavelengths = np.asarray(axes["wavelengths"], dtype=float)
    timedelays = np.asarray(axes["timedelays"], dtype=float)
    if (axes["width"], axes["height"], wavelengths.size, timedelays.size) != (width, height, width, height):
        raise ValueError("Image size differs from calibration. Updating calibrated axes…")
    lo, hi, top, bottom = region
    columns = np.flatnonzero((wavelengths >= lo) & (wavelengths <= hi))
    if not columns.size:
        raise ValueError("Selected wavelengths are outside the calibrated camera image.")
    first = min(height - 1, math.floor(height * top / 100 + 1e-9))
    end = min(height, max(first + 1, math.ceil(height * bottom / 100 - 1e-9)))
    pixels = observation.pixels
    if pixels.size != width * height:
        raise ValueError("Incomplete image frame.")
    x = timedelays[first:end]
    y = pixels.reshape(height, width)[first:end, columns].mean(axis=1)
    if not np.all(np.isfinite(x)) or np.unique(x).size != x.size:
        raise ValueError("Invalid time/intensity samples.")
    selected = wavelengths[columns]
    available_min, available_max = float(wavelengths.min()), float(wavelengths.max())
    info = {
        "timeUnit": axes["time_unit"], "frameId": frame["received_at"],
        "bounds": {"x0": int(columns[0]), "x1": int(columns[-1]), "y0": first, "y1": end - 1},
        "wavelengthMin": float(selected.min()), "wavelengthMax": float(selected.max()),
        "clipped": lo < available_min or hi > available_max,
        "availableMin": available_min, "availableMax": available_max,
    }
    return x, y, info


def _auto_windows(x, y):
    order = np.argsort(x)
    x, y = x[order], y[order]
    if x.size < 6:
        return None

    def mad(values, axis=None):
        centre = np.median(values, axis=axis, keepdims=True)
        return np.median(np.abs(values - centre), axis=axis) * 1.4826

    # Same robust pre-edge trend and five-point foot as the previous Live view.
    # Fit candidate windows together to keep frame processing inexpensive.
    edges = np.flatnonzero(np.diff(y) < 0) + 1
    edges = edges[(edges >= 10) & (edges <= x.size - 5)]
    if edges.size:
        idx = edges[:, None] + np.arange(-10, 0)
        bx, by = x[idx], y[idx]
        i, j = np.triu_indices(10, 1)
        slope = np.median((by[:, j] - by[:, i]) / (bx[:, j] - bx[:, i]), axis=1)
        origin = bx[:, -1]
        intercept = np.median(by - slope[:, None] * (bx - origin[:, None]), axis=1)
        noise_floor = max(mad(np.diff(y)) / math.sqrt(2), 1e-9 * max(1, np.max(np.abs(y))))
        noise = np.maximum(noise_floor, mad(by - intercept[:, None] - slope[:, None] * (bx - origin[:, None]), axis=1))
        sharpness = y[edges - 1] + slope * (x[edges] - x[edges - 1]) - y[edges]
        best = None
        for k in np.flatnonzero(sharpness >= 3 * math.sqrt(2) * noise):
            edge = int(edges[k])
            deficit = intercept[k] + slope[k] * (x - origin[k]) - y
            foot = edge
            for r in range(edge + 1, min(x.size - 5, edge + 4) + 1):
                if deficit[r] > deficit[foot] + noise[k] * 0.5:
                    foot = r
            after = deficit[foot:foot + 5]
            drop = after.mean()
            if (y[foot:foot + 5].mean() + drop > 0 and drop >= 3 * noise[k]
                    and sharpness[k] >= drop * 0.25 and np.count_nonzero(after >= drop * 0.5) >= 4
                    and (best is None or drop > best[0])):
                best = drop, edge, foot
        if best is not None:
            _, edge, foot = best
            return {"baseline": x[[edge - 10, edge - 1]].tolist(), "signal": x[[foot, foot + 4]].tolist()}
    last = x.size - 1
    before = max(2, min(last - 3, math.floor(last * 0.35)))
    after = max(before + 1, min(last - 2, math.floor(last * 0.65)))
    return {"baseline": x[[max(0, before - max(2, math.floor(last * 0.2))), before]].tolist(),
            "signal": x[[after, min(last, max(after + 2, math.floor(last * 0.85)))]].tolist()}


def _compare(x, y, windows):
    if windows is None or x.size < 6:
        raise ValueError("Choose baseline and signal windows with at least 3 points each.")
    (a, b), (c, d) = windows["baseline"], windows["signal"]
    if not a < b < c < d:
        raise ValueError("Baseline window must end before the signal window.")
    before = (x >= a) & (x <= b)
    after = (x >= c) & (x <= d)
    n_before, n_after = int(before.sum()), int(after.sum())
    if min(n_before, n_after) < 3:
        raise ValueError("Each window needs at least 3 points.")
    origin, intercept = x[before].mean(), y[before].mean()
    centered = x[before] - origin
    denom = np.dot(centered, centered)
    if denom <= 0:
        raise ValueError("Baseline window has no time span.")
    slope = np.dot(centered, y[before] - intercept) / denom
    baseline_at = lambda t: intercept + slope * (t - origin)
    at, intensity = float(x[after].mean()), float(y[after].mean())
    base = float(baseline_at(at))
    if not math.isfinite(base) or base <= 0:
        raise ValueError("I₀ must be positive in the selected windows.")
    drop = base - intensity
    return {"found": True, "base": base, "y": intensity, "drop": drop,
            "optical_density": math.log10(base) - math.log10(intensity) if intensity > 0 else None,
            "percent": 100 * (drop / base), "x": at,
            "windowStart": c, "windowEnd": d, "baselinePoints": n_before, "signalPoints": n_after,
            "baseline": [{"x": t, "y": float(baseline_at(t))} for t in (a, d)]}


@dataclass(frozen=True)
class _Frame:
    payload: dict
    captured: float
    generation: int
    context: tuple

    @cached_property
    def pixels(self):
        return np.frombuffer(base64.b64decode(self.payload["pixels_b64"], validate=True), dtype=np.uint8)


class AlignmentReadout:
    def __init__(self):
        self._lock = Lock()
        self._frames = deque(maxlen=24)
        self._generation = 0
        self._available = False

    def unavailable(self):
        with self._lock:
            if self._available:
                self._generation += 1
                self._available = False

    def observe(self, payload, captured):
        # Payload bytes/axes are shared by reference with preview; never copied
        # or decoded under the native camera lock.
        encoded = payload.get("pixels_b64")
        if not payload.get("calibration") or not encoded or len(encoded) > 6_000_000:
            self.unavailable()
            return
        context = (payload.get("calibration_key"), payload.get("measurement_key"),
                   payload["stream_state"])
        with self._lock:
            last = self._frames[-1] if self._frames else None
            if last and payload["received_at"] == last.payload["received_at"]:
                return
            if last and (last.context != context or captured - last.captured >= FRESH_SECONDS):
                self._generation += 1
            self._frames.append(_Frame(payload, captured, self._generation, context))
            self._available = True

    def read(self, frame_id, region, windows):
        with self._lock:
            frames = tuple(self._frames)
        anchor = next((f for f in reversed(frames) if f.payload["received_at"] == frame_id), None)
        if anchor is None:
            raise LookupError("Waiting for the next calibrated preview frame.")
        x, y, profile = _profile(anchor, region)
        profile["points"] = [{"x": t, "y": v} for t, v in zip(x.tolist(), y.tolist())]
        if windows is None:
            windows = _auto_windows(x, y)
        try:
            comparison = _compare(x, y, windows)
        except ValueError as exc:
            comparison = {"found": False, "error": str(exc)}
        summary = None
        measured = anchor.captured
        if comparison["found"]:
            values = []
            # Use completed server-clock seconds. Clients requesting the same
            # anchor get the same bucket even if their network delays differ.
            end = math.floor(anchor.captured)
            if anchor.context[2] == "acquiring":
                for frame in frames:
                    if frame.generation == anchor.generation and end - 1 <= frame.captured < end:
                        try:
                            sx, sy, _ = _profile(frame, region)
                            values.append((_compare(sx, sy, windows)["percent"], frame.captured))
                        except ValueError:
                            values.clear()
            if values:
                percentages, timestamps = zip(*values)
                summary = {"kind": "mean", "mean": mean(percentages),
                           "sd": stdev(percentages) if len(values) > 1 else None, "n": len(values)}
                measured = timestamps[-1]
            else:
                summary = {"kind": "frame", "mean": comparison["percent"], "sd": None, "n": 1}
        now = time.monotonic()
        age = max(0, now - anchor.captured)
        with self._lock:
            current = self._available and self._generation == anchor.generation
        return {"version": READOUT_VERSION, "profile": profile, "windows": windows, "comparison": comparison,
                "summary": summary, "fresh": current and anchor.context[2] == "acquiring" and age < FRESH_SECONDS,
                "frame_age_ms": age * 1000, "summary_age_ms": max(0, now - measured) * 1000,
                "signal_key": json.dumps([anchor.generation, *anchor.context, region, windows],
                                         sort_keys=True, separators=(",", ":"))}
