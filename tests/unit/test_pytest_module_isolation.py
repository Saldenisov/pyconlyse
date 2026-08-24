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
    environment = _subprocess_environment()

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "2 passed" in completed.stdout


def test_collection_uses_inert_stubs_and_restores_real_modules_and_environment(tmp_path):
    (tmp_path / "conftest.py").write_text(
        textwrap.dedent(
            """
            import os
            import sys
            import types

            original_tango = types.ModuleType('real_tango_sentinel')
            original_taurus = types.ModuleType('real_taurus_sentinel')
            sys.modules['tango'] = original_tango
            sys.modules['taurus'] = original_taurus
            os.environ['TANGO_HOST'] = 'remote-sentinel:10000'
            os.environ['PYCONLYSE_TANGO_HOST'] = 'remote-sentinel:10000'

            pytest_plugins = ('scripts.refactor.pytest_module_isolation',)
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_a_collection.py").write_text(
        textwrap.dedent(
            """
            import os
            import sys

            collection_tango_is_inert = sys.modules['tango'].__name__ == 'tango'
            collection_taurus_is_inert = sys.modules['taurus'].__name__ == 'taurus'
            collection_hosts_are_local = (
                os.environ['TANGO_HOST'] == '127.0.0.1:1'
                and os.environ['PYCONLYSE_TANGO_HOST'] == '127.0.0.1:1'
            )
            from tango import AttrWriteType, DevFloat, DevState, DeviceProxy, DispLevel
            from tango.server import Device, attribute, command, device_property, pipe
            collection_tango_surface_is_sufficient = all((
                AttrWriteType.READ == 0,
                DevFloat is float,
                DevState.ON == 'ON',
                DeviceProxy('test/device').name == 'test/device',
                DispLevel.OPERATOR == 0,
                Device().get_state() == DevState.OFF,
                attribute(lambda: None) is not None,
                command(lambda: None) is not None,
                pipe(lambda: None) is not None,
                device_property(default_value='test') == 'test',
                hasattr(sys.modules['taurus'], 'Device'),
            ))
            try:
                sys.modules['tango'].Database().get_device_exported('*')
            except RuntimeError as error:
                collection_database_is_inert = 'unavailable while collecting' in str(error)
            else:
                collection_database_is_inert = False

            def test_collection_was_isolated():
                assert collection_tango_is_inert
                assert collection_taurus_is_inert
                assert collection_hosts_are_local
                assert collection_tango_surface_is_sufficient
                assert collection_database_is_inert
                assert sys.modules['tango'].__name__ == 'real_tango_sentinel'
                assert sys.modules['taurus'].__name__ == 'real_taurus_sentinel'
                assert os.environ['TANGO_HOST'] == 'remote-sentinel:10000'
                assert os.environ['PYCONLYSE_TANGO_HOST'] == 'remote-sentinel:10000'
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_b_no_leak.py").write_text(
        textwrap.dedent(
            """
            import os
            import sys

            collection_tango_is_inert = sys.modules['tango'].__name__ == 'tango'
            collection_hosts_are_local = os.environ['TANGO_HOST'] == '127.0.0.1:1'

            def test_stubs_are_replaced_for_each_collected_file():
                assert collection_tango_is_inert
                assert collection_hosts_are_local
                assert sys.modules['tango'].__name__ == 'real_tango_sentinel'
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "test_c_runtime_default.py").write_text(
        textwrap.dedent(
            """
            import os
            import sys
            import types

            from scripts.refactor.pytest_module_isolation import isolated_test_modules

            def test_runtime_context_does_not_replace_existing_protocol_modules():
                runtime_tango = types.ModuleType('runtime_tango_sentinel')
                runtime_taurus = types.ModuleType('runtime_taurus_sentinel')
                sys.modules['tango'] = runtime_tango
                sys.modules['taurus'] = runtime_taurus
                os.environ['TANGO_HOST'] = 'runtime-remote:10000'
                os.environ['PYCONLYSE_TANGO_HOST'] = 'runtime-remote:10000'

                with isolated_test_modules():
                    assert sys.modules['tango'] is runtime_tango
                    assert sys.modules['taurus'] is runtime_taurus
                    assert os.environ['TANGO_HOST'] == 'runtime-remote:10000'
                    assert os.environ['PYCONLYSE_TANGO_HOST'] == 'runtime-remote:10000'
            """
        ),
        encoding="utf-8",
    )
    environment = _subprocess_environment()

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "3 passed" in completed.stdout


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
    environment = _subprocess_environment()

    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "2 passed" in completed.stdout


def _subprocess_environment():
    environment = os.environ.copy()
    project_root = str(Path(__file__).resolve().parents[2])
    environment["PYTHONPATH"] = project_root + os.pathsep + environment.get(
        "PYTHONPATH", ""
    )
    return environment
