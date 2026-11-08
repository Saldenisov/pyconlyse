"""Prepare byte-exact ACQ copies for NI's static subVI inspection workflow.

NEVER open Main directly: its original RunOnOpen flag is True. Select it as
a subVI on a NEW BLANK VI's block diagram, then open that subVI for review.
Do not Run or Save either VI. No flags, checksums or protection are changed.

The earlier one-bit autorun patch was rejected by native LabVIEW with0x59;
it is retained only as a failed artifact, not a supported loading workflow.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path("C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs")
DESTINATION = Path("C:/dev/ELYSE-ACQ-analysis/review_20261015/native_subvi_originals")
CENSUS = REPO / "docs/ELYSE_ACQ_ORIGINAL_DIAGRAM_CENSUS_2026-10-01.json"
NI_WORKFLOW = (
    "https://www.ni.com/docs/en-AS/bundle/labview-api-ref/page/"
    "dialog-boxes/execution-page-vi-properties-dialog-box.html"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def audit_copy(source=SOURCE, destination=DESTINATION, census=CENSUS):
    """Read-only audit; reject changed, missing or additional VI members."""
    members = json.loads(census.read_text("utf-8"))["members"]
    expected = {member["vi"] for member in members}
    if len(expected) != 17 or {p.name for p in destination.glob("*.vi")} != expected:
        raise ValueError("exactly seventeen original review members required")
    identities = []
    for member in members:
        name, expected_hash = member["vi"], member["source_vi_sha256"]
        if digest(source / name) != expected_hash:
            raise ValueError(f"original member changed: {name}")
        if digest(destination / name) != expected_hash:
            raise ValueError(f"review member differs: {name}")
        identities.append({"vi": name, "sha256": expected_hash})
    return {
        "source": str(source),
        "review_directory": str(destination),
        "members": identities,
        "all_17_byte_identical": True,
        "run_on_open_modified": False,
        "native_loaded": False,
        "native_load_claim_requires_separate_observation": True,
        "open_main_directly_permitted": False,
        "hardware_execution_permitted": False,
        "workflow": "Select Main onto a NEW BLANK VI diagram; open as a subVI only",
        "workflow_reference": NI_WORKFLOW,
        "rejected_one_bit_patch_native_error": (
            "(Hex 0x59) Another user tampered with the VI password"
        ),
    }


def build():
    """Copy to a new directory, or verify an existing copy without rewriting it."""
    members = json.loads(CENSUS.read_text("utf-8"))["members"]
    for member in members:
        if digest(SOURCE / member["vi"]) != member["source_vi_sha256"]:
            raise ValueError("original member changed; nothing copied")
    if not DESTINATION.exists():
        DESTINATION.mkdir(parents=True)
        for member in members:
            shutil.copy2(SOURCE / member["vi"], DESTINATION / member["vi"])
    return audit_copy()


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
