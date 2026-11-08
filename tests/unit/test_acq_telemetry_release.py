"""Release assembly checks; no hardware or native VI execution."""

from __future__ import annotations

import hashlib
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "tools/build_acq_telemetry_release.py"
SPEC = importlib.util.spec_from_file_location("acq_release_builder", SCRIPT)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def test_project_has_native_relative_paths_and_separate_owners():
    root = ET.fromstring(
        release.project_xml(
            ["ACQ_SharedState_Transport.vi", "ACQ_SharedState_Collect_Local.vi"]
        )
    )
    urls = [item.get("URL") for item in root.iter("Item") if item.get("URL")]
    assert len(urls) == 3
    assert all(url.startswith("../") for url in urls)
    assert (
        root.find(".//Item[@Name='OPERATOR ONLY - owns NI cards']/Item").get("Name")
        == "0_ACQ_ELYSE.vi"
    )
    assert (
        root.find(
            ".//Item[@Name='My Computer']/Item[@Name='ACQ_SharedState_Transport.vi']"
        )
        is not None
    )
    assert all("Probe" not in url and "Soak" not in url for url in urls)


@pytest.mark.skipif(not release.GOOD.exists(), reason="native evidence not present")
def test_sixteen_hardware_members_are_exact_baseline_bytes():
    members = release.check_members()
    assert len(members) == 17
    assert members["1_ACQ_WRITE_NI6703.vi"] == (
        "5437FD979E7D5AB2F50257DF0F75B73D7C800684EFF0A45D28D6E51931893C3D"
    )


def test_existing_candidate_is_never_overwritten(tmp_path):
    (tmp_path / release.RELEASE_NAME).mkdir()
    with pytest.raises(FileExistsError, match="preserve existing"):
        release.build(tmp_path)


def test_changed_main_refuses_build(tmp_path, monkeypatch):
    good = tmp_path / "good"
    before = tmp_path / "before"
    (good / "members").mkdir(parents=True)
    (before / "members").mkdir(parents=True)
    for index in range(17):
        name = "0_ACQ_ELYSE.vi" if index == 0 else "sub%d.vi" % index
        (good / "members" / name).write_bytes(b"unreviewed")
        (before / "members" / name).write_bytes(b"unreviewed")
    with pytest.raises(ValueError, match="main hash changed"):
        release.check_members(good, before)


PROBE_EXPORT = release.EVIDENCE / "2026-10-14/release_probe_export"


@pytest.mark.skipif(not PROBE_EXPORT.exists(), reason="native probe not exported")
def test_saved_native_probe_is_finite_and_never_invokes_main():
    pins = {
        "ACQ_SharedState_Release_Probe.xml": (
            "A23E968ECA8444FD2F126B7A62CFD2659A5B0F8AA8B19D553D76C0ABBF94086A"
        ),
        "ACQ_SharedState_Release_Probe_BDHb.xml": (
            "E3545CF07522D2CF97C266FA48E444899B5B1CC3EA221A24683F0A1F7827F619"
        ),
        "ACQ_SharedState_Release_Probe_FPHb.xml": (
            "FD8338CEA41ABF702BB2E5FBE973BA6114AAA402F6ACAD8B11328E670B899E48"
        ),
    }
    for name, expected in pins.items():
        assert (
            hashlib.sha256((PROBE_EXPORT / name).read_bytes()).hexdigest().upper()
            == expected
        )
    meta = ET.parse(PROBE_EXPORT / "ACQ_SharedState_Release_Probe.xml").getroot()
    bd = ET.parse(PROBE_EXPORT / "ACQ_SharedState_Release_Probe_BDHb.xml").getroot()
    execution = meta.find("LVSR/Section/Execution")
    assert execution.get("RunOnOpen") == "0"
    assert execution.get("BadCompile") == "0"
    assert len([n for n in bd.iter() if n.get("class") == "forLoop"]) == 1
    assert sorted(
        n.findtext("primResID") for n in bd.iter() if n.get("class") == "prim"
    ) == ["1302", "8010", "8011"]
    constants = {
        n.get("uid"): bytes.fromhex(n.findtext("ConstValue"))
        for n in bd.iter()
        if n.get("class") == "bDConstDCO"
    }
    assert int.from_bytes(constants["484"], "big") == 1000
    assert int.from_bytes(constants["654"], "big") == 20
    assert b"ELYSE_ACQ_TELEMETRY_RELEASE_20261017" in constants["149"]
    assert [
        n.findtext("LinkSaveQualName/String")
        for n in meta.findall("LIvi/Section/LVIN/VIVI")
    ] == ["ACQ_SharedState_Collect_Local.vi"]
