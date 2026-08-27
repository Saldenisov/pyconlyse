"""Folder-local DAT provenance manifest contracts."""

import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from treatment_manifest import (
    TREATMENT_MANIFEST_FILE_NAME,
    TREATMENT_MANIFEST_FORMAT,
    TREATMENT_MANIFEST_VERSION,
    record_treatment_manifest,
)


def _session_state(folder: Path) -> dict:
    return {
        "save_folder": str(folder),
        "save_file_name": "sample.dat",
        "folder_path": str(folder / "sample"),
        "exp_type": "ABS+BASE+NOISE",
        "calc_mode": "averaged",
        "first_map_with_electrons": True,
        "paths": {"ABS": str(folder / "sample" / "ABS1.h5")},
        "path_sources": {"ABS": str(folder / "sample" / "ABS1.h5")},
    }


def test_manifest_creates_atomic_dat_record_and_upserts_by_file_name(tmp_path):
    state = _session_state(tmp_path)
    first_saved = {"save_path": str(tmp_path / "sample.dat"), "bytes": 12}
    first_receipt = record_treatment_manifest(
        first_saved,
        session_state=state,
        workflow={"kind": "immediate"},
    )
    second_saved = {"save_path": str(tmp_path / "sample.dat"), "bytes": 34}
    second_receipt = record_treatment_manifest(
        second_saved,
        session_state=state,
        workflow={"kind": "queue_recipe", "label": "rerun", "queue_job_id": "job-7"},
    )

    manifest_path = tmp_path / TREATMENT_MANIFEST_FILE_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert first_receipt["manifest_path"] == str(manifest_path)
    assert second_receipt["manifest_path"] == str(manifest_path)
    assert manifest["format"] == TREATMENT_MANIFEST_FORMAT
    assert manifest["format_version"] == TREATMENT_MANIFEST_VERSION
    assert len(manifest["dat_files"]) == 1
    assert manifest["dat_files"][0]["dat_file"] == "sample.dat"
    assert manifest["dat_files"][0]["workflow"]["kind"] == "queue_recipe"
    assert manifest["dat_files"][0]["result"]["bytes"] == 34
    assert not list(tmp_path.glob(f".{TREATMENT_MANIFEST_FILE_NAME}.*"))


@pytest.mark.parametrize(
    "content, error",
    [
        ("not-json", "not valid JSON"),
        ("[]", "must be a JSON object"),
        ("{}", "unsupported format"),
        (
            json.dumps(
                {
                    "format": TREATMENT_MANIFEST_FORMAT,
                    "format_version": TREATMENT_MANIFEST_VERSION,
                    "dat_files": ["not-an-object"],
                }
            ),
            "list of objects",
        ),
    ],
)
def test_manifest_never_overwrites_invalid_existing_document(tmp_path, content, error):
    manifest_path = tmp_path / TREATMENT_MANIFEST_FILE_NAME
    manifest_path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        record_treatment_manifest(
            {"save_path": str(tmp_path / "sample.dat")},
            session_state=_session_state(tmp_path),
            workflow={"kind": "immediate"},
        )

    assert manifest_path.read_text(encoding="utf-8") == content
