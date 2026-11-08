"""Bind manual visits to all45 original controlled-stop diagrams.

The validator checks source identity, graph coverage and retained images.
It does not interpret pixels or execute the controller/standard DAQmx VIs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from validate_acq_controlled_stop import WRAPPERS, validate_stop
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_native_static_observations import (
    MAIN_SHA,
    REPO,
    STOP_RECORD,
    validate_stop_observations,
)
from validate_acq_vam_status import checked_vam

RECORD = REPO / "docs/ELYSE_ACQ_NATIVE_NESTED_STOP_2026-10-15.json"


def validate(record=None):
    if record is None:
        record = json.loads(RECORD.read_text("utf-8"))
    require(
        record["source_vi_sha256"] == MAIN_SHA
        and record["native_executable_file_version"] == "20.0f1"
        and record["no_native_run_or_save"] is True
        and record["hardware_or_psp_executed"] is False
        and record["original_lv2012_runtime_equivalence"] is False
        and record["whole_acquisition_closed"] is False
        and record["all_45_stop_diagrams_visually_reviewed"] is True
        and record["case_display_is_not_runtime_case_entry"] is True
        and record["source_sequence_uid"] == "51954"
        and record["prior_selected_view_record"] == STOP_RECORD.name,
        "nested stop observation scope changed",
    )
    rows = record["nested_sequences"]
    require(
        len(rows) == 5 and [row["phase"] for row in rows] == list(range(1, 6)),
        "nested sequence population changed",
    )
    links, expected_images = {}, set()
    for row, (wrapper, (sequence, frames, _)) in zip(rows, WRAPPERS.items()):
        require(
            row["wrapper"] == wrapper
            and row["sequence"] == sequence
            and row["visited_frames"] == list(frames),
            "manual visited frame population or order changed",
        )
        for index, uid in enumerate(frames):
            name = f"STOP-phase{row['phase']}-frame{index:02d}-{uid}.png"
            links[uid] = name
            expected_images.add(name)
        links[wrapper] = links[frames[0]]
    require(
        record["poll_body_views"]
        == [
            {"diagram": "47770", "image": links["47671"]},
            {"diagram": "48062", "image": links["47989"]},
        ],
        "counter poll body view mapping changed",
    )
    links.update({r["diagram"]: r["image"] for r in record["poll_body_views"]})
    require(
        record["prior_image_views"]
        == [
            {
                "image": "MAIN-stop-phase0-ht-decrement.png",
                "diagrams": ["60323", "42212", "47573"],
            },
            {
                "image": "MAIN-stop-phase0-ht-exit.png",
                "diagrams": ["60323", "42212", "47580"],
            },
            {
                "image": "MAIN-stop-phase6-completion-flags.png",
                "diagrams": ["64826"],
            },
        ],
        "prior HT/completion view mapping changed",
    )
    base = json.loads(STOP_RECORD.read_text("utf-8"))
    validate_stop_observations(base)
    prior_names = set()
    for row in record["prior_image_views"]:
        name = row["image"]
        require(name in base["image_sha256"], "prior stop image is unqualified")
        prior_names.add(name)
        links.update({uid: name for uid in row["diagrams"]})
    images = record["image_sha256"]
    require(
        len(images) == 33 and set(images) == expected_images,
        "nested stop image population changed",
    )
    for name, expected in images.items():
        require(Path(name).name == name, "nested stop image must be a basename")
        actual = hashlib.sha256((Path(record["image_directory"]) / name).read_bytes())
        require(actual.hexdigest().upper() == expected, "nested stop image changed")
    root, metadata = checked_vam(
        REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
    )
    sequence = unique(root, "sequence", "51954")
    source_diagrams = [
        n.get("uid") for n in sequence.iter() if n.get("class") == "diag"
    ]
    require(
        len(source_diagrams) == 45
        and len(set(source_diagrams)) == 45
        and set(links) == set(source_diagrams),
        "manual diagram views do not exhaust source stop diagram census",
    )
    proof = validate_stop(root, metadata)
    return {
        "source_sequence_uid": "51954",
        "source_stop_diagrams": proof["diagrams"],
        "source_stop_nets": proof["nets"],
        "manually_viewed_stop_diagrams": len(links),
        "nested_sequence_frames": len(expected_images),
        "retained_nested_images": len(images),
        "retained_prior_images_used": len(prior_names),
        "diagram_image_links": links,
        "native_original_lv2012_runtime_equivalence": False,
        "whole_acquisition_closed": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
