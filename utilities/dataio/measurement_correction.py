"""RAW rejection, finite paired-slot rejection, and audited neighbor repair."""

from dataclasses import dataclass

import numpy as np

if __package__:
    from .laser_shot_correction import (
        correct_block,
        correct_scan,
        detect_paired_od_outliers,
        load_legacy_zip,
        write_dat,
    )
    from .temporal_outlier_correction import (
        correct_temporal_outliers,
        detect_unstable_repeats,
        fill_missing_neighbors,
    )
else:
    from laser_shot_correction import (
        correct_block,
        correct_scan,
        detect_paired_od_outliers,
        load_legacy_zip,
        write_dat,
    )
    from temporal_outlier_correction import (
        correct_temporal_outliers,
        detect_unstable_repeats,
        fill_missing_neighbors,
    )


@dataclass
class MeasurementCorrection:
    raw_correction: object
    cleaned_blocks: tuple
    finite_paired_outliers: tuple
    repeat_quality: object
    missing_correction: object
    temporal_correction: object

    @property
    def od(self):
        return self.temporal_correction.od

    @property
    def valid_shot_counts(self):
        return np.asarray([b.valid_shot_count for b in self.cleaned_blocks])

    def to_payload(self):
        payload = self.raw_correction.to_payload()
        values = self.od.astype(object)
        values[~np.isfinite(self.od)] = None
        payload["od"] = values.tolist()
        payload["valid_shot_counts"] = self.valid_shot_counts.tolist()
        payload["pixel_counts"] = np.stack(
            [b.pixel_counts for b in self.cleaned_blocks], axis=1
        ).tolist()
        payload["filled_missing_mask"] = self.missing_correction.filled_mask.tolist()
        payload["missing_fill_method"] = self.missing_correction.method.tolist()
        payload["temporal_corrected_mask"] = (
            self.temporal_correction.corrected_mask.tolist()
        )
        payload["finite_paired_outliers_one_based"] = [
            (np.flatnonzero(b.excluded_shots) + 1).tolist()
            for b in self.finite_paired_outliers
        ]
        payload["audit"]["raw_valid_counts_before_finite_rejection"] = (
            self.raw_correction.valid_shot_counts.tolist()
        )
        payload["audit"]["temporal_correction"] = self.temporal_correction.audit()
        payload["audit"]["missing_values_filled"] = int(
            self.missing_correction.filled_mask.sum()
        )
        payload["audit"]["estimated_values_are_measurements"] = False
        for j, record in enumerate(payload["audit"]["delays"]):
            block = self.cleaned_blocks[j]
            record["valid_shots_before_finite_rejection"] = record["valid_shots"]
            record["valid_shots"] = block.valid_shot_count
            record["rejected_shots_one_based"] = (
                np.flatnonzero(~block.valid_shots) + 1
            ).tolist()
            record["rejection_reasons"] = [list(x) for x in block.reasons]
            record["estimated_missing_pixels"] = int(
                self.missing_correction.filled_mask[:, j].sum()
            )
            record["temporal_replacement_pixels"] = int(
                self.temporal_correction.corrected_mask[:, j].sum()
            )
            record["status"] = (
                "estimated_from_neighbors"
                if block.valid_shot_count == 0 and record["estimated_missing_pixels"]
                else "unrecoverable"
                if block.valid_shot_count == 0
                else "reduced_shot_count"
                if not block.valid_shots.all()
                else "complete"
            )
        return payload

    def write_dat(self, path):
        write_dat(
            path,
            self.raw_correction.wavelengths_nm,
            self.raw_correction.delays_ps,
            self.od,
        )


def correct_measurement(
    scan,
    shot_config=None,
    paired_config=None,
    temporal_config=None,
    edge_policy="two_nearest_mean",
    pulse_present=None,
):
    """Return corrected map and separate evidence/estimation masks; no mutation.

    Supports a parsed legacy RAW scan or an equivalent acquisition array adapter.
    Pulse-monitor flags remain the preferred evidence for missing pump pulses.
    Neighbor estimates retain zero measured-shot counts in the web payload.
    """
    first = correct_scan(scan, shot_config, pulse_present)
    quality = detect_unstable_repeats(
        [b.shot_od for b in first.blocks], scan.wavelengths_nm
    )
    detections = tuple(
        detect_paired_od_outliers(b, scan.wavelengths_nm, paired_config)
        for b in first.blocks
    )
    blocks = tuple(
        correct_block(
            scan.blocks[i],
            scan.wavelengths_nm,
            first.config,
            None if pulse_present is None else pulse_present[i],
            detection.excluded_shots,
            "paired_od_outlier",
        )
        if detection.excluded_shots.any()
        else first.blocks[i]
        for i, detection in enumerate(detections)
    )
    raw_od = np.stack([b.od for b in blocks], axis=1)
    missing = fill_missing_neighbors(scan.delays_ps, raw_od, edge_policy)
    temporal = correct_temporal_outliers(
        scan.delays_ps, missing.od, temporal_config, quality.unstable_delay_mask
    )
    return MeasurementCorrection(first, blocks, detections, quality, missing, temporal)


def correct_legacy_zip(source, **kwargs):
    """Accept ZIP path, uploaded bytes, or binary stream for future web reuse."""
    return correct_measurement(load_legacy_zip(source), **kwargs)
