"""General-only commissioning: no network or hardware writes in this suite."""
from legacy.xp_acq_agent.tests.test_acquisition_general_only import (
    GeneralOnlyTests, GeneralOnlyConfigurationTests,
)


def test_package_profile_is_explicit_and_manifest_hashes_match(tmp_path):
    import hashlib
    import json
    from tools.package_acquisition_runtime import build

    folder = tmp_path / "general_only"
    result = build(folder, control_profile="general_only_test")
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    config = json.loads((folder / "config.acquisition.json").read_text("utf-8"))
    assert manifest["control_profile"] == config["control_profile"] == "general_only_test"
    assert manifest["general_stop_scope"] == "source_event_6_frames_13_to_16"
    assert result["auto_initialize"] is False
    assert manifest["secret_files_included"] is False
    for record in manifest["files"]:
        assert hashlib.sha256((folder / record["path"]).read_bytes()).hexdigest() == record["sha256"]
    assert not any(".key" in record["path"] for record in manifest["files"])

    legacy = tmp_path / "legacy"
    build(legacy)
    assert json.loads((legacy / "config.acquisition.json").read_text("utf-8"))["control_profile"] == "legacy_full"
    full_manifest = json.loads((legacy / "manifest.json").read_text("utf-8"))
    assert full_manifest["control_profile"] == "legacy_full"
    assert full_manifest["general_stop_scope"] == "source_event_6_all_17_frames"
    assert full_manifest["general_stop_includes_ht_supply_stop"] is False
    for record in full_manifest["files"]:
        assert hashlib.sha256((legacy / record["path"]).read_bytes()).hexdigest() == record["sha256"]


def test_full_package_cannot_silently_inherit_general_only_source_configuration(tmp_path):
    import json
    from pathlib import Path
    from tools.package_acquisition_runtime import build, MODULES, DATA

    real_source = Path(__file__).resolve().parents[2] / "legacy/xp_acq_agent"
    fake_root = tmp_path / "synthetic_source_root"
    source = fake_root / "legacy/xp_acq_agent"
    paths = [Path("acquisition_server.pyw"), Path("config.acquisition.json")]
    paths += [Path("elyse_agent") / name for name in MODULES]
    paths += [Path("data") / name for name in DATA]
    for relative in paths:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((real_source / relative).read_bytes())
    config = json.loads((source / "config.acquisition.json").read_text("utf-8"))
    config["control_profile"] = "general_only_test"
    (source / "config.acquisition.json").write_text(json.dumps(config), encoding="utf-8")
    full = tmp_path / "full_candidate"
    build(full, root=fake_root, control_profile="legacy_full")
    candidate = json.loads((full / "config.acquisition.json").read_text("utf-8"))
    assert candidate["control_profile"] == "legacy_full"
    assert candidate["focal_stop"]["resources_verified"] is False


def test_invalid_package_profile_creates_no_output(tmp_path):
    import pytest
    from tools.package_acquisition_runtime import build
    folder = tmp_path / "invalid"
    with pytest.raises(ValueError, match="Unknown acquisition control profile"):
        build(folder, control_profile="skip_checks")
    assert not folder.exists()
