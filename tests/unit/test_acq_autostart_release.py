"""Operator-entry and release inventory tests; no VI execution."""

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import build_acq_autostart_release as release  # noqa: E402
import validate_acq_autostart as lifecycle  # noqa: E402
import validate_acq_legacy_hook_retirement as retirement  # noqa: E402


def test_only_start_is_exposed_as_operator_entry():
    root = ET.fromstring(
        release.project_xml(
            [
                lifecycle.START + ".vi",
                lifecycle.WORKER + ".vi",
            ]
        )
    )
    entry = root.find(".//Item[@Name='OPERATOR ONLY - START owns NI cards']")
    assert [n.get("Name") for n in entry] == [lifecycle.START + ".vi"]
    assert all(n.get("URL", "../").startswith("../") for n in root.iter("Item"))


@pytest.mark.skipif(not release.PARENT.exists(), reason="release artifact required")
def test_archive_is_pinned_without_tests_or_secrets():
    directory = release.PARENT / lifecycle.FOLDER
    manifest = json.loads((directory / "auto_launch_manifest.json").read_text("utf-8"))
    assert manifest["main_retains_original_hardware_initialization_and_writes"]
    assert not manifest["hardware_main_executed_during_preparation"]
    assert not manifest["test_fixtures_included"]
    assert not manifest["secrets_included"]
    assert manifest["obsolete_init_hook_retirement"]["legacy_queue_body_disabled"]
    assert manifest["files"][retirement.NAME + ".vi"] == retirement.SOURCE_SHA256
    with ZipFile(release.PARENT / (lifecycle.FOLDER + ".zip")) as archive:
        names = archive.namelist()
        assert len(names) == len(manifest["files"]) + 1
        assert not any(
            any(word in n for word in ("Probe", "Soak", "Fixture", "TEST"))
            for n in names
        )
        assert not any(n.endswith(".key") for n in names)
        for name, expected in manifest["files"].items():
            data = archive.read(lifecycle.FOLDER + "/" + name)
            assert hashlib.sha256(data).hexdigest().upper() == expected


def test_existing_candidate_not_overwritten(tmp_path):
    (tmp_path / lifecycle.FOLDER).mkdir()
    with pytest.raises(FileExistsError, match="preserve existing"):
        release.build(tmp_path)


def test_retirement_audit_failure_blocks_packaging(tmp_path, monkeypatch):
    def fail():
        raise AssertionError("retired native helper is not verified")

    monkeypatch.setattr(retirement, "audit", fail)
    with pytest.raises(AssertionError, match="not verified"):
        release.build(tmp_path)
    assert not (tmp_path / lifecycle.FOLDER).exists()
