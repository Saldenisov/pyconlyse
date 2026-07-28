import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_collection_does_not_leak_tango_or_taurus_stubs(tmp_path):
    (tmp_path / "conftest.py").write_text(
        "pytest_plugins = ('scripts.refactor.pytest_module_isolation',)\n",
        encoding="utf-8",
    )
    (tmp_path / "test_a_stub.py").write_text(
        textwrap.dedent(
            """
            import sys
            import types

            sys.modules['tango'] = types.ModuleType('tango')
            sys.modules['taurus'] = types.ModuleType('taurus')

            def test_stub_file_is_collected():
                assert True
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_b_clean.py").write_text(
        textwrap.dedent(
            """
            import sys

            def test_next_file_has_no_stub_from_test_a():
                assert 'tango' not in sys.modules
                assert 'taurus' not in sys.modules
            """
        ),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    project_root = str(Path(__file__).resolve().parents[2])
    environment["PYTHONPATH"] = project_root + os.pathsep + environment.get(
        "PYTHONPATH", ""
    )

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "2 passed" in completed.stdout


def test_runtime_imports_do_not_leak_tango_bound_device_modules(tmp_path):
    (tmp_path / "conftest.py").write_text(
        textwrap.dedent(
            """
            import pytest

            from scripts.refactor.pytest_module_isolation import isolated_test_modules
            from tests._tango_stub import install_tango_stub

            pytest_plugins = ('scripts.refactor.pytest_module_isolation',)

            @pytest.fixture(autouse=True)
            def isolated_tango_stub(monkeypatch):
                with isolated_test_modules():
                    install_tango_stub(monkeypatch)
                    yield
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_a_runtime_import.py").write_text(
        textwrap.dedent(
            """
            def test_imports_a_tango_bound_module_at_runtime():
                from DeviceServers.base import general
                assert general.DevState.ON == 'ON'
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_b_clean.py").write_text(
        textwrap.dedent(
            """
            import sys

            def test_next_test_has_no_tango_bound_device_module():
                assert 'DeviceServers.base.general' not in sys.modules
            """
        ),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    project_root = str(Path(__file__).resolve().parents[2])
    environment["PYTHONPATH"] = project_root + os.pathsep + environment.get(
        "PYTHONPATH", ""
    )

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "2 passed" in completed.stdout
