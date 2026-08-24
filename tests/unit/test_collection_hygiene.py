import configparser
import ntpath
import runpy
import subprocess
import sys
import types
from fnmatch import fnmatchcase
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _configured_python_file_patterns():
    config = configparser.ConfigParser()
    config.read(PROJECT_ROOT / "pytest.ini", encoding="utf-8")
    return config["pytest"]["python_files"].split()


def _matches_on_windows(filename, pattern):
    return fnmatchcase(ntpath.normcase(filename), ntpath.normcase(pattern))


def test_windows_casefold_does_not_collect_device_registration_scripts():
    patterns = _configured_python_file_patterns()

    for filename in ("DS_Test.py", "add_ds_Test.py"):
        assert not any(
            _matches_on_windows(filename, pattern) for pattern in patterns
        )


def test_registration_probe_lives_in_manual_lane_and_is_not_default_collected():
    old_path = PROJECT_ROOT / "tests/device_servers/testing/add_ds_Test.py"
    manual_path = PROJECT_ROOT / (
        "tests/manual/device_servers/testing/add_ds_test_probe.py"
    )

    assert not old_path.exists()
    assert manual_path.is_file()

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr

    assert completed.returncode == 0, output
    assert "DS_Test.py" not in output
    assert "add_ds_Test.py" not in output
    assert "add_ds_test_probe.py" not in output


def test_registration_probe_import_does_not_construct_database(monkeypatch):
    manual_path = PROJECT_ROOT / (
        "tests/manual/device_servers/testing/add_ds_test_probe.py"
    )
    fake_tango = types.ModuleType("tango")

    def fail_database_construction():
        raise AssertionError("Database construction must stay inside main()")

    fake_tango.Database = fail_database_construction
    fake_tango.DbDevInfo = object
    monkeypatch.setitem(sys.modules, "tango", fake_tango)

    runpy.run_path(str(manual_path), run_name="add_ds_test_probe")
