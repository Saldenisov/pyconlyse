"""Online OD and block uncertainty for the operator's fixed detector ROI."""
from dataclasses import dataclass
import math

import numpy as np


BLOCK_PAIRS = 20
MIN_BLOCKS = 8
ERROR_CONFIRMATIONS = 2


@dataclass(frozen=True)
class DetectorROI:
    x0: int
    x1: int
    y0: int
    y1: int
    width: int
    height: int

    @classmethod
    def from_payload(cls, payload):
        fields = cls.__dataclass_fields__
        if not isinstance(payload, dict) or payload.keys() != fields.keys() or any(
            type(payload[key]) is not int for key in fields
        ):
            raise ValueError("Select an Acquisition ROI on the camera image")
        roi = cls(**payload)
        if not (0 <= roi.x0 <= roi.x1 < roi.width <= 8192 and 0 <= roi.y0 <= roi.y1 < roi.height <= 8192):
            raise ValueError("Selected ROI falls outside the camera image")
        return roi

    @property
    def slices(self):
        # H5 and analysis orientation is wavelength by time.
        return slice(self.x0, self.x1 + 1), slice(self.y0, self.y1 + 1)


class PairedAnalysis:
    def __init__(self, background, roi, dark_blocks=()):
        self.background = background
        self.roi = roi
        self.dark_blocks = dark_blocks
        self.od_sum = np.zeros_like(background, dtype=np.float64)
        self.valid_count = np.zeros_like(background, dtype=np.int32)
        self.estimate_mod = self.error_mod = None
        self.block_mean = []
        self._block = []
        self._block_valid = True
        self._roi_sum = self._roi_count = 0
        self._gradient = np.zeros_like(background[roi.slices]) if roi else None

    def add(self, absorption, base):
        abs_counts = absorption.astype(np.float64) - self.background
        base_counts = base.astype(np.float64) - self.background
        valid = (abs_counts > 0) & (base_counts > 0) & np.isfinite(abs_counts) & np.isfinite(base_counts)
        od = np.zeros_like(self.background)
        od[valid] = np.log10(base_counts[valid]) - np.log10(abs_counts[valid])
        self.od_sum += od
        self.valid_count += valid
        if self.roi is None:
            return False

        region = self.roi.slices
        if valid[region].all():
            value = float(1000 * od[region].mean())
            self._roi_sum += value
            self._roi_count += 1
            self.estimate_mod = self._roi_sum / self._roi_count
            self._block.append(value)
            self._gradient += (1000 / math.log(10) / self._gradient.size) * (
                1.0 / abs_counts[region] - 1.0 / base_counts[region]
            )
        else:
            self._block_valid = False
            self.error_mod = None

        if len(self._block) == BLOCK_PAIRS and self._block_valid:
            self.block_mean.append(float(np.mean(self._block)))
            self._block.clear()
            self.error_mod = self._block_error()
            return True
        if not self._block_valid:
            # An invalid ROI breaks the independent contiguous blocks used for
            # stopping. Preserve the frames and map, and start a new estimate.
            self.block_mean.clear()
            self._block.clear()
            self._block_valid = True
            self._roi_sum = self._roi_count = 0
            self._gradient.fill(0)
            self.estimate_mod = None
        return False

    @property
    def roi_pair_count(self):
        return self._roi_count

    def _block_error(self):
        count = len(self.block_mean)
        if count < MIN_BLOCKS or len(self.dark_blocks) < 4:
            return None
        means = np.asarray(self.block_mean)
        short_error = np.std(means, ddof=1) / math.sqrt(count)
        merged = means[:2 * (count // 2)].reshape(-1, 2).mean(axis=1)
        long_error = np.std(merged, ddof=1) / math.sqrt(merged.size)
        dark_projection = [
            float(np.sum(dark * self._gradient / self._roi_count)) for dark in self.dark_blocks
        ]
        dark_error = np.std(dark_projection, ddof=1) / math.sqrt(len(dark_projection))
        return float(math.hypot(max(short_error, long_error), dark_error))

    def map(self):
        return np.divide(self.od_sum, self.valid_count, out=np.full_like(self.od_sum, np.nan),
                         where=self.valid_count > 0)
