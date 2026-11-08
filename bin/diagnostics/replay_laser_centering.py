"""Replay archived camera bursts only. No Tango/network/device imports.

Usage: python bin/diagnostics/replay_laser_centering.py --input-dir DIR --output-dir DIR
Saved bursts verify temporal image repeatability, not hardware return accuracy.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from DeviceServers.control.laser_pointing.alignment_quality import centering_verification, confirm_improvement
from DeviceServers.control.laser_pointing.beam_metrics import beam_contour_symmetry, camera_contour_profile


def replay(input_dir, output_dir, tolerance_px=1.0):
    records = {}
    for path in sorted(input_dir.glob("*.npz")):
        metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        settings = metadata["camera"]
        with np.load(path, allow_pickle=False) as saved:
            frames = saved["frames"]
            if len(frames) < 3:
                raise ValueError(f"{path.name}: fewer than three independent frames")
            hashes = [hashlib.sha256(f.tobytes()).hexdigest() for f in frames]
            if len(set(hashes)) != len(hashes):
                raise ValueError(f"{path.name}: duplicated frames cannot establish repeatability")
            arguments = {**camera_contour_profile("Cam2", settings["center_gravity_threshold"]),
                         "width": settings["width"], "height": settings["height"]}
            groups = np.array_split(np.arange(len(frames)), 3)
            measured = [beam_contour_symmetry(frames[index], **arguments) for index in groups]
            quality = centering_verification(measured, tolerance_px)
            whole = beam_contour_symmetry(frames, **arguments)
            records[path.stem] = {
                "camera": settings, "point": metadata["active_point"],
                "disjoint_frame_indices": [g.tolist() for g in groups],
                "frame_hashes": hashes,
                "whole_burst": {k: whole[k] for k in ("centering_error_px", "ellipticity_error_pct", "roundness_error_pct")},
                "within_frame_verification": quality,
                "alignment_verified": False, "aperture_pair_checked": False,
                "hardware_return_tested": False,
            }

    comparisons = {}
    for before, after in (("p4-before-coarse", "p4-after-coarse"),
                          ("p6-exposure100ms", "resumed-light-check")):
        if before not in records or after not in records:
            continue
        ref, candidate = records[before], records[after]
        if ref["camera"] != candidate["camera"] or ref["point"] != candidate["point"]:
            raise ValueError("comparison is confounded by camera settings or optical point")
        if set(ref["frame_hashes"]).intersection(candidate["frame_hashes"]):
            raise ValueError("comparison reuses camera frames")
        decision = confirm_improvement(ref["within_frame_verification"]["centering_repeatability"]["scores"],
                                       candidate["within_frame_verification"]["centering_repeatability"]["scores"])
        comparisons[before + " -> " + after] = decision

    output_dir.mkdir(parents=True, exist_ok=True)
    report = {"mode": "offline_only", "centering_tolerance_px": tolerance_px,
              "ellipticity_tolerance_pct": 7.0, "records": records, "comparisons": comparisons,
              "limitations": ["Saved bursts cannot validate motor response, backlash, or return accuracy.",
                              "No complete matched open/closed aperture-pair dataset is present.",
                              "Independent batches use disjoint archived frames; each batch has 2 or 3 frames.",
                              "No live hardware commands, deployment, server restart, or calibration changes."]}
    (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    selected = [k for k in ("p4-before-coarse", "p4-after-coarse", "p3-after-coarse", "p6-exposure100ms", "resumed-light-check") if k in records]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    for ax, field, label, limit in ((axes[0], "centering_error_px", "Center spread / px", tolerance_px),
                                     (axes[1], "ellipticity_error_pct", "Ellipticity / % (diagnostic only)", 7.0)):
        values = [records[k]["within_frame_verification"][field] for k in selected]
        ax.bar(np.arange(len(selected)), values, color="#2077a5")
        ax.axhline(limit, color="#b94f35", linestyle="--", label=f"separate tolerance: {limit:g}")
        ax.set_xticks(np.arange(len(selected)), selected, rotation=25, ha="right")
        ax.set_ylabel(label)
        ax.legend()
    fig.suptitle("Archived Cam2 frames | separate centering and shape; no hardware verification")
    fig.savefig(output_dir / "centering-vs-ellipticity.png", dpi=150)
    plt.close(fig)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--tolerance-px", type=float, default=1.0)
    args = parser.parse_args()
    if args.input_dir.resolve() == args.output_dir.resolve():
        parser.error("output directory must differ from the source archive")
    result = replay(args.input_dir, args.output_dir, args.tolerance_px)
    print(json.dumps({"records": len(result["records"]), "comparisons": result["comparisons"],
                      "report": str(args.output_dir / "report.json")}, indent=2))
