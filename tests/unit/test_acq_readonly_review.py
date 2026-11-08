"""Review-copy identity, not native-load or original behavioral qualification."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = Path("C:/dev/ELYSE-ACQ-analysis/review_20261015")
SOURCE = Path("C:/dev/ELYSE-ACQ-analysis/offline/extracted/ACQUISITION_VIs")


@pytest.mark.skipif(
    not (REVIEW / "safeopen_receipt.json").exists(),
    reason="native review clone not generated",
)
def test_rejected_autorun_artifact_diff_is_not_a_native_load_qualification():
    report = json.loads((REVIEW / "safeopen_receipt.json").read_text("utf-8"))
    before = (SOURCE / "0_ACQ_ELYSE.vi").read_bytes()
    after = (REVIEW / "original_safeopen/0_ACQ_ELYSE.vi").read_bytes()
    assert len(before) == len(after)
    changes = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert changes == report["changed_byte_offsets"] == [42]
    assert before[42] ^ after[42] == 0x40
    assert hashlib.sha256(before).hexdigest().upper() == report["source_sha256"]
    assert hashlib.sha256(after).hexdigest().upper() == report["clone_sha256"]
    execution = ET.parse(REVIEW / "safeopen_export/0_ACQ_ELYSE.xml").find(
        "LVSR/Section/Execution"
    )
    assert execution.get("RunOnOpen") == "0"
    assert not report["hardware_execution_permitted"]


@pytest.mark.skipif(
    not (REVIEW / "original_safeopen").exists(),
    reason="native review clone not generated",
)
def test_all_seventeen_original_members_still_match_registered_hashes():
    manifest = json.loads(
        (ROOT / "docs/ELYSE_ACQ_ORIGINAL_DIAGRAM_CENSUS_2026-10-01.json").read_text(
            "utf-8"
        )
    )
    assert len(manifest["members"]) == 17
    for member in manifest["members"]:
        data = (SOURCE / member["vi"]).read_bytes()
        assert hashlib.sha256(data).hexdigest().upper() == member["source_vi_sha256"]
        if member["vi"] != "0_ACQ_ELYSE.vi":
            assert data == (REVIEW / "original_safeopen" / member["vi"]).read_bytes()


@pytest.mark.skipif(
    not (REVIEW / "native_subvi_originals").exists(),
    reason="byte-exact native subVI review copy not generated",
)
def test_native_subvi_review_copy_preserves_all_original_execution_flags_and_bytes():
    from tools.prepare_acq_readonly_review import audit_copy

    report = audit_copy()
    assert len(report["members"]) == 17
    assert report["all_17_byte_identical"]
    assert not report["run_on_open_modified"]
    assert not report["open_main_directly_permitted"]
    assert not report["hardware_execution_permitted"]
    assert not report["native_loaded"]
    assert report["native_load_claim_requires_separate_observation"]
