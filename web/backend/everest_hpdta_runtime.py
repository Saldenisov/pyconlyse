"""Controlled HPD-TA/RemoteEx process lifecycle on the Everest host."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable, Sequence


class EverestRuntimeError(RuntimeError):
    """Everest could not report or change the HPD-TA runtime state."""


class EverestHpdtaRuntime:
    """Use the existing Windows scheduled task only to launch TaRemoteEx."""

    def __init__(
        self,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ):
        self._runner = runner
        self.host = os.environ.get("PYCONLYSE_EVERST_SSH_HOST", "10.20.30.202")
        self.user = os.environ.get("PYCONLYSE_EVERST_SSH_USER", "elyse")
        self.key_path = Path(
            os.environ.get(
                "PYCONLYSE_EVERST_SSH_KEY",
                str(Path.home() / ".ssh" / "pyconlyse_win_daqmx"),
            )
        )

    def state(self) -> dict[str, bool]:
        payload = self._run_powershell(
            "[pscustomobject]@{"
            "remoteex_running=[bool](Get-Process TaRemoteEx -ErrorAction SilentlyContinue);"
            "hpdta_running=[bool](Get-Process HPDTA95 -ErrorAction SilentlyContinue)"
            "}|ConvertTo-Json -Compress"
        )
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise EverestRuntimeError(f"Invalid Everest runtime response: {payload}") from exc
        return {
            "remoteex_running": bool(decoded.get("remoteex_running", False)),
            "hpdta_running": bool(decoded.get("hpdta_running", False)),
        }

    def start_remoteex(self) -> dict[str, bool]:
        self._run_powershell(
            'Start-ScheduledTask -TaskName "Pyconlyse-TaRemoteEx"; Start-Sleep -Seconds 2'
        )
        state = self.state()
        if not state["remoteex_running"]:
            raise EverestRuntimeError("TaRemoteEx did not start on Everest")
        return state

    def stop_remoteex(self) -> dict[str, bool]:
        self._run_powershell(
            "Get-Process TaRemoteEx -ErrorAction SilentlyContinue|Stop-Process -Force"
        )
        return self.state()

    def _run_powershell(self, command: str) -> str:
        if not self.key_path.is_file():
            raise EverestRuntimeError(f"Everest SSH key is missing: {self.key_path}")
        completed = self._runner(
            [
                "ssh",
                "-i",
                str(self.key_path),
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                f"{self.user}@{self.host}",
                command,
            ],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "Everest SSH command failed").strip()
            raise EverestRuntimeError(message)
        return completed.stdout.strip()
