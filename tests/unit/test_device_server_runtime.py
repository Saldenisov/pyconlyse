"""Software-only contracts for direct Windows device-server Python launch."""

import subprocess
import sys
from pathlib import Path

from DeviceServers.python_runtime import direct_python_candidates, resolve_direct_python


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_NAMES = (
    "DS_ANDOR_CCD.bat",
    "DS_ANDOR_SPECTROGRAPH.bat",
    "DS_Basler_camera.bat",
    "DS_DAQmx.bat",
    "DS_DG645.bat",
    "DS_HAMAMATSU_STREAK.bat",
    "DS_KEYSIGHT_33509B.bat",
    "DS_LaserPointing.bat",
    "DS_ML_Stability.bat",
    "DS_Netio_pdu.bat",
    "DS_OWIS_Aggregator.bat",
    "DS_OWIS_PS90.bat",
    "DS_PSP.bat",
    "DS_Standa_Motor.bat",
    "DS_iTest_PSU.bat",
)


def test_configured_absolute_python_wins_over_discovered_environments():
    configured = r"D:\runtime\pyconlyse39\python.exe"
    resolution = resolve_direct_python(
        {
            "PYCONLYSE_PYTHON": configured,
            "PYCONLYSE_ENV": "pyconlyse39",
            "ANACONDA": r"C:\Users\operator\miniconda3",
        },
        lambda path: path == configured,
    )

    assert resolution is not None
    assert resolution.executable == configured
    assert resolution.source == "PYCONLYSE_PYTHON"


def test_resolver_rejects_relative_config_and_uses_common_user_environment():
    candidates = direct_python_candidates(
        {
            "PYCONLYSE_PYTHON": r"envs\pyconlyse39\python.exe",
            "PYCONLYSE_ENV": "pyconlyse39",
            "USERPROFILE": r"C:\Users\operator",
        }
    )
    expected = r"C:\Users\operator\miniconda3\envs\pyconlyse39\python.exe"
    resolution = resolve_direct_python({}, lambda _path: False)

    assert all(candidate.source != "PYCONLYSE_PYTHON" for candidate in candidates)
    assert expected in [candidate.executable for candidate in candidates]
    assert resolution is None


def test_resolver_skips_a_different_active_conda_environment():
    candidates = direct_python_candidates(
        {
            "PYCONLYSE_ENV": "pyconlyse39",
            "CONDA_PREFIX": r"C:\Users\operator\miniconda3\envs\other",
            "CONDA_DEFAULT_ENV": "other",
        }
    )

    assert all(candidate.source != "CONDA_PREFIX" for candidate in candidates)


def test_all_device_server_wrappers_use_shared_launcher_without_conda_activation():
    device_servers = PROJECT_ROOT / "DeviceServers"
    for wrapper_name in WRAPPER_NAMES:
        wrapper = (device_servers / wrapper_name).read_text(encoding="utf-8")
        assert "activate.bat" not in wrapper
        assert "launch_device_server.cmd" in wrapper


def test_shared_launcher_preserves_terminal_tabs_without_conda_activation():
    device_servers = PROJECT_ROOT / "DeviceServers"
    launcher = (device_servers / "launch_device_server.cmd").read_text(encoding="utf-8")
    logged = (device_servers / "run_logged_server.cmd").read_text(encoding="utf-8")
    tailer = (device_servers / "tail_device_server_log.cmd").read_text(encoding="utf-8")
    resolver = (device_servers / "resolve_python.cmd").read_text(encoding="utf-8")
    preparer = (device_servers / "prepare_python_runtime.cmd").read_text(encoding="utf-8")

    assert 'PYCONLYSE_WT_WINDOW=PyconlyseTango' in launcher
    assert 'wt -w "%PYCONLYSE_WT_WINDOW%" nt' in launcher
    assert 'start "" /b cmd.exe /d /c call "%LOGGED_LAUNCHER%"' in launcher
    assert 'cmd /k call "%TAIL_LAUNCHER%"' in launcher
    assert launcher.index('start "" /b cmd.exe') < launcher.index("where wt")
    assert "Get-Content" in tailer
    assert "-Wait" in tailer
    assert "prepare_python_runtime.cmd" in logged
    assert "PYTHONUNBUFFERED=1" in logged
    assert '"%PYCONLYSE_PYTHON%" %PYCONLYSE_DS_SCRIPT% %PYCONLYSE_DS_INSTANCE%' in logged
    assert '"%PYCONLYSE_DS_SCRIPT%"' not in logged
    assert "powershell.exe" not in logged.lower()
    assert "resolve_python.cmd" in preparer
    assert "activate.bat" not in preparer
    assert "conda-activate" not in preparer
    assert "PYCONLYSE_PYTHON" in resolver


def test_astor_executable_contract_requires_the_batch_wrappers():
    device_servers = PROJECT_ROOT / "DeviceServers"
    compiler = (device_servers / "compile_wrapper.bat").read_text(encoding="utf-8")
    laser = (device_servers / "DS_LaserPointing.bat").read_text(encoding="utf-8")

    assert "Building DS_*.exe wrappers is disabled" in compiler
    assert "Astor must resolve DS_*.bat" in compiler
    assert all(not (device_servers / wrapper_name.replace(".bat", ".exe")).exists() for wrapper_name in WRAPPER_NAMES)
    assert "taskkill" not in laser.lower()


def test_legacy_netio_restart_is_explicit_nonzero_dry_run():
    completed = subprocess.run(
        [sys.executable, "scripts/restart_netio_servers.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "DEPRECATED_DRY_RUN" in completed.stdout
