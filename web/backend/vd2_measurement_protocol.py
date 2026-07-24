"""One-phase HIS acquisition protocol for the VD2 streak-camera experiment."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PureWindowsPath
from typing import Any, Callable, Mapping


PHASES: Mapping[str, dict[str, str]] = {
    "BRUIT": {"label": "Bruit", "file_stem": "BRUIT"},
    "BASE": {"label": "Base", "file_stem": "BASE"},
    "ABSORPTION": {"label": "Absorption", "file_stem": "ABS"},
}
DEFAULT_OUTPUT_ROOT = r"E:\DATA_VD2"


class Vd2ProtocolError(RuntimeError):
    """A protocol request cannot be performed safely."""


@dataclass(frozen=True)
class PhaseRequest:
    phase: str
    frames_per_his: int
    output_root: str
    run_name: str
    his_path: str


class Vd2MeasurementProtocol:
    """Serializes one prepared Bruit/Base/Absorption HIS acquisition at a time."""

    def __init__(self, proxy_factory: Callable[[], Any]):
        self._proxy_factory = proxy_factory
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._state: dict[str, Any] = {
            "status": "idle",
            "phase": None,
            "frames_per_his": None,
            "his_path": None,
            "started_at": None,
            "completed_at": None,
            "error": "",
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def start(
        self,
        *,
        phase: str,
        frames_per_his: object,
        output_root: object = DEFAULT_OUTPUT_ROOT,
        run_name: object,
    ) -> dict[str, Any]:
        request = self._build_request(phase, frames_per_his, output_root, run_name)
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise Vd2ProtocolError("A VD2 HIS acquisition is already running")
            self._state = {
                "status": "acquiring",
                "phase": request.phase,
                "phase_label": PHASES[request.phase]["label"],
                "frames_per_his": request.frames_per_his,
                "his_path": request.his_path,
                "started_at": _utc_now(),
                "completed_at": None,
                "error": "",
            }
            self._thread = threading.Thread(
                target=self._acquire,
                args=(request,),
                daemon=True,
                name=f"vd2-{request.phase.lower()}-his",
            )
            self._thread.start()
            return dict(self._state)

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _acquire(self, request: PhaseRequest) -> None:
        try:
            proxy = self._proxy_factory()
            proxy.set_timeout_millis(300_000)
            if not bool(proxy.read_attribute("connected").value):
                raise Vd2ProtocolError("Hamamatsu Tango device is not connected")
            if not bool(proxy.read_attribute("application_running").value):
                raise Vd2ProtocolError("HPD-TA is not running")

            proxy.write_attribute("sequence_loops", str(request.frames_per_his))
            proxy.command_inout("StartSequence")
            proxy.command_inout("WaitForIdle")
            proxy.command_inout("SaveCurrentSequence", request.his_path)
            self._finish("completed")
        except Exception as exc:
            self._finish("failed", str(exc))

    def _finish(self, status: str, error: str = "") -> None:
        with self._lock:
            self._state["status"] = status
            self._state["error"] = error
            self._state["completed_at"] = _utc_now()

    @staticmethod
    def _build_request(
        phase: object,
        frames_per_his: object,
        output_root: object,
        run_name: object,
    ) -> PhaseRequest:
        phase_name = str(phase).strip().upper()
        # Keep the early UI spelling accepted for clients not yet upgraded.
        if phase_name == "BREW":
            phase_name = "BRUIT"
        if phase_name not in PHASES:
            raise Vd2ProtocolError(f"Unsupported VD2 phase: {phase}")
        try:
            frames = int(frames_per_his)
        except (TypeError, ValueError) as exc:
            raise Vd2ProtocolError("HIS frames must be an integer") from exc
        if not 1 <= frames <= 100_000:
            raise Vd2ProtocolError("HIS frames must be between 1 and 100000")

        name = str(run_name).strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            raise Vd2ProtocolError("Run name may use only letters, digits, '.', '_' and '-'")

        root = PureWindowsPath(str(output_root).strip() or DEFAULT_OUTPUT_ROOT)
        if not root.drive or any(part == ".." for part in root.parts):
            raise Vd2ProtocolError("Output folder must be an absolute Windows path")
        his_path = root / name / f"{PHASES[phase_name]['file_stem']}.his"
        return PhaseRequest(
            phase=phase_name,
            frames_per_his=frames,
            output_root=str(root),
            run_name=name,
            his_path=str(his_path),
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
