"""Millimetre-only control of the VD2 Zaber A-MCA / LSM050A-T4 stage.

The controller speaks Zaber Binary at COM1/9600 on Elysium 2. Opening a
connection only reads identity and limits; it never homes or moves the stage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Optional


CONTROLLER_ID = 30111
PERIPHERAL_ID = 43021
TRAVEL_MM = 50.8
LEAD_MM_PER_REVOLUTION = 0.6096
MOTOR_STEPS_PER_REVOLUTION = 200


@dataclass(frozen=True)
class StageSnapshot:
    position_mm: float
    minimum_mm: float
    maximum_mm: float
    status_code: int
    resolution: int


class ZaberStage:
    """One validated binary-protocol axis with an exclusively owned port."""

    def __init__(
        self,
        port: str = "COM1",
        baud_rate: int = 9600,
        address: int = 1,
        *,
        connection_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.port = str(port)
        self.baud_rate = int(baud_rate)
        self.address = int(address)
        self._connection_factory = connection_factory
        self._connection = None
        self._device = None
        self._resolution = 0
        self._step_mm = 0.0
        self._minimum_native = 0
        self._maximum_native = 0

    @property
    def connected(self) -> bool:
        return self._device is not None

    @property
    def minimum_mm(self) -> float:
        return self._minimum_native * self._step_mm

    @property
    def maximum_mm(self) -> float:
        return min(TRAVEL_MM, self._maximum_native * self._step_mm)

    def _api(self):
        from zaber_motion import Units
        from zaber_motion.binary import CommandCode, Connection

        return Units, CommandCode, Connection

    def _require_device(self):
        if self._device is None:
            raise RuntimeError("Zaber stage is not connected")
        return self._device

    def _read(self, command, data: int = 0) -> int:
        reply = self._require_device().generic_command(command, data)
        if int(reply.device_address) != self.address:
            raise RuntimeError("Zaber response came from an unexpected address")
        return int(reply.data)

    def connect(self) -> StageSnapshot:
        """Open COM1 and reject any unexpected controller, stage, or scale."""
        if self.connected:
            return self.snapshot()
        Units, CommandCode, Connection = self._api()
        del Units
        factory = self._connection_factory or Connection.open_serial_port
        connection = factory(self.port, baud_rate=self.baud_rate)
        self._connection = connection
        self._device = connection.get_device(self.address)
        try:
            controller_id = self._read(CommandCode.RETURN_DEVICE_ID)
            peripheral_id = self._read(CommandCode.RETURN_SETTING, 66)
            resolution = self._read(CommandCode.RETURN_SETTING, 37)
            minimum_native = self._read(CommandCode.RETURN_SETTING, 106)
            maximum_native = self._read(CommandCode.RETURN_SETTING, 44)
            if controller_id != CONTROLLER_ID or peripheral_id != PERIPHERAL_ID:
                raise RuntimeError(
                    "Unexpected Zaber hardware: controller {} / peripheral {}".format(
                        controller_id, peripheral_id
                    )
                )
            if resolution <= 0 or minimum_native < 0 or maximum_native <= minimum_native:
                raise RuntimeError("Invalid Zaber resolution or travel limits")
            step_mm = LEAD_MM_PER_REVOLUTION / (
                MOTOR_STEPS_PER_REVOLUTION * resolution
            )
            travel_mm = maximum_native * step_mm
            if not 50.7 <= travel_mm <= 50.9:
                raise RuntimeError(
                    "Zaber travel does not match the 50.8 mm stage: {:.6f} mm".format(
                        travel_mm
                    )
                )
            self._resolution = resolution
            self._step_mm = step_mm
            self._minimum_native = minimum_native
            self._maximum_native = maximum_native
            return self.snapshot()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        self._device = None
        if connection is not None:
            connection.close()

    def snapshot(self) -> StageSnapshot:
        _, CommandCode, _ = self._api()
        position_native = self._read(CommandCode.RETURN_CURRENT_POSITION)
        status_code = self._read(CommandCode.RETURN_STATUS)
        return StageSnapshot(
            position_mm=position_native * self._step_mm,
            minimum_mm=self.minimum_mm,
            maximum_mm=self.maximum_mm,
            status_code=status_code,
            resolution=self._resolution,
        )

    def _target_native(self, target_mm: float) -> int:
        self._require_device()
        requested = float(target_mm)
        if not math.isfinite(requested):
            raise ValueError("Zaber target must be a finite number of millimetres")
        if not self.minimum_mm <= requested <= self.maximum_mm:
            raise ValueError(
                "Zaber target {:.6f} mm is outside {:.6f}–{:.6f} mm".format(
                    requested, self.minimum_mm, self.maximum_mm
                )
            )
        target_native = round(requested / self._step_mm)
        if not self._minimum_native <= target_native <= self._maximum_native:
            raise ValueError("Rounded Zaber target is outside controller limits")
        return target_native

    def move_absolute_mm(self, target_mm: float, *, timeout_s: float = 120.0) -> float:
        Units, CommandCode, _ = self._api()
        target_native = self._target_native(target_mm)
        if self._read(CommandCode.RETURN_STATUS) != 0:
            raise RuntimeError("Zaber stage must be idle before a new move")
        final_native = self._require_device().move_absolute(
            target_native, unit=Units.NATIVE, timeout=float(timeout_s)
        )
        return float(final_native) * self._step_mm

    def move_relative_mm(self, delta_mm: float, *, timeout_s: float = 120.0) -> float:
        delta = float(delta_mm)
        if not math.isfinite(delta):
            raise ValueError("Zaber displacement must be finite millimetres")
        return self.move_absolute_mm(
            self.snapshot().position_mm + delta, timeout_s=timeout_s
        )

    def home(self, *, timeout_s: float = 120.0) -> float:
        """Move to the home switch only after an explicit Tango Home command."""
        Units, CommandCode, _ = self._api()
        if self._read(CommandCode.RETURN_STATUS) != 0:
            raise RuntimeError("Zaber stage must be idle before homing")
        final_native = self._require_device().home(
            unit=Units.NATIVE, timeout=float(timeout_s)
        )
        return float(final_native) * self._step_mm

    def stop(self, *, timeout_s: float = 10.0) -> float:
        Units, _, _ = self._api()
        final_native = self._require_device().stop(
            unit=Units.NATIVE, timeout=float(timeout_s)
        )
        return float(final_native) * self._step_mm
