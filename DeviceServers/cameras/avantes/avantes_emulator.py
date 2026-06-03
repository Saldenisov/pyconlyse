"""
Avantes and Arduino emulator for local standalone development.

The emulator keeps the same small API surface used by avantes_dual_viewer:
prepare_measure(), measure(), poll_scan(), get_data(), get_lambda(), and the
Arduino trigger controller methods.
"""

import os
import sys
import time
import zlib
from dataclasses import dataclass
from typing import Tuple

import numpy as np


ARDUINO_TRIGGER_HZ = 40.0
N_PIXELS = 2048


def should_use_avantes_emulator() -> bool:
    """Return True when Avantes hardware should be emulated."""
    value = os.environ.get("AVANTES_EMULATOR")
    if value is not None:
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return sys.platform != "win32"


@dataclass
class _EmulatedArduinoState:
    lamp_enabled: bool = False
    avantes_enabled: bool = False
    mode: str = "OFF"
    frequency_hz: float = ARDUINO_TRIGGER_HZ


EMULATED_ARDUINO_STATE = _EmulatedArduinoState()


class EmulatedArduinoTriggerController:
    """In-memory Arduino TTL trigger controller."""

    def __init__(self, ip: str = "emulated", port: int = 80, timeout: float = 0.01):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.base_url = f"emulated://{ip}:{port}"
        self._last_mode = "OFF"

    def set_mode(self, mode: str) -> bool:
        if mode == "LAMP AND AVANTES":
            EMULATED_ARDUINO_STATE.lamp_enabled = True
            EMULATED_ARDUINO_STATE.avantes_enabled = True
        elif mode == "ONLY AVANTES":
            EMULATED_ARDUINO_STATE.lamp_enabled = False
            EMULATED_ARDUINO_STATE.avantes_enabled = True
        elif mode == "OFF":
            EMULATED_ARDUINO_STATE.lamp_enabled = False
            EMULATED_ARDUINO_STATE.avantes_enabled = False
        else:
            return False

        EMULATED_ARDUINO_STATE.mode = mode
        self._last_mode = mode
        return True

    def get_state(self) -> Tuple[bool, bool]:
        return EMULATED_ARDUINO_STATE.lamp_enabled, EMULATED_ARDUINO_STATE.avantes_enabled

    def set_frequency_hz(self, frequency_hz: float) -> bool:
        EMULATED_ARDUINO_STATE.frequency_hz = min(max(float(frequency_hz), 1.0), 100.0)
        return True

    def get_frequency_hz(self) -> float:
        return EMULATED_ARDUINO_STATE.frequency_hz

    def start_lamp_and_spectrometers(self) -> bool:
        return self.set_mode("LAMP AND AVANTES")

    def start_spectrometers_only(self) -> bool:
        return self.set_mode("ONLY AVANTES")

    def stop_all(self) -> bool:
        return self.set_mode("OFF")

    def is_connected(self) -> bool:
        return True

    def get_status_string(self) -> str:
        lamp, avantes = self.get_state()
        if lamp and avantes:
            return "EMULATED LAMP AND AVANTES"
        if avantes and not lamp:
            return "EMULATED ONLY AVANTES"
        return "EMULATED OFF"

    @property
    def lamp_enabled(self) -> bool:
        return EMULATED_ARDUINO_STATE.lamp_enabled

    @property
    def avantes_enabled(self) -> bool:
        return EMULATED_ARDUINO_STATE.avantes_enabled


class EmulatedAvantesSpectrometer:
    """Synthetic Avantes spectrometer with Xe flash and fiber drift."""

    class TriggerType:
        def __init__(self):
            self.m_Mode = 1
            self.m_Source = 0
            self.m_SourceType = 0

    class MeasConfigType:
        def __init__(self):
            self.m_StartPixel = 0
            self.m_StopPixel = N_PIXELS - 1
            self.m_IntegrationTime = 1.0
            self.m_NrAverages = 1
            self.m_Trigger = EmulatedAvantesSpectrometer.TriggerType()

    def __init__(self, serial: str, channel_index: int):
        self.serial = serial
        self.channel_index = channel_index
        self._rng = np.random.default_rng(self._seed(serial, channel_index))
        self._wavelengths = np.linspace(200.0, 1100.0, N_PIXELS)
        self._config = self.MeasConfigType()
        self._ready_at = 0.0
        self._measuring = False
        self._measurement_index = 0
        self._shape_drift = self._rng.normal(0.0, [0.002, 0.0015, 0.001])
        self._phase = self._rng.uniform(0.0, 2.0 * np.pi)
        self._fiber_transfer = self._make_fiber_transfer()

    @staticmethod
    def _seed(serial: str, channel_index: int) -> int:
        payload = f"{serial}:{channel_index}:avantes-emulator".encode("utf-8")
        return zlib.crc32(payload) or 1

    def use_high_res_adc(self, enabled: bool):
        return None

    def get_lambda(self) -> np.ndarray:
        return self._wavelengths.copy()

    def get_num_pixels(self) -> int:
        return N_PIXELS

    def prepare_measure(self, config):
        self._config = config

    def measure(self, num_measurements: int = 1, wh=None):
        averages = max(1, int(getattr(self._config, "m_NrAverages", 1)))
        trigger = getattr(self._config, "m_Trigger", None)
        trigger_mode = int(getattr(trigger, "m_Mode", 0)) if trigger is not None else 0
        integration_s = max(0.0001, float(getattr(self._config, "m_IntegrationTime", 1.0)) / 1000.0)

        if trigger_mode in {1, 2}:
            duration_s = averages / max(EMULATED_ARDUINO_STATE.frequency_hz, 1.0)
        else:
            duration_s = averages * integration_s

        self._ready_at = time.time() + duration_s
        self._measuring = True

    def poll_scan(self) -> bool:
        return self._measuring and time.time() >= self._ready_at

    def get_data(self):
        if not self.poll_scan():
            raise RuntimeError("ERR_INVALID_MEAS_DATA")

        averages = max(1, int(getattr(self._config, "m_NrAverages", 1)))
        data = np.mean([self._single_flash_spectrum() for _ in range(averages)], axis=0)
        self._measurement_index += 1
        self._measuring = False
        return int(time.time() * 1000), data.astype(float)

    def stop_measure(self):
        self._measuring = False

    def disconnect(self):
        self._measuring = False

    def _single_flash_spectrum(self) -> np.ndarray:
        wavelengths = self._wavelengths
        integration_ms = max(0.1, float(getattr(self._config, "m_IntegrationTime", 1.0)))

        if not EMULATED_ARDUINO_STATE.avantes_enabled:
            return self._dark_spectrum()

        if EMULATED_ARDUINO_STATE.lamp_enabled:
            lamp = self._xe_lamp_shape()
        else:
            return self._dark_spectrum()

        amplitude_jitter = self._rng.normal(1.0, 0.015)
        spectral_drift = self._next_spectral_drift()
        intensity = lamp * self._fiber_transfer * spectral_drift * amplitude_jitter
        intensity = self._apply_intensity_dependent_fiber_transport(intensity)

        intensity *= 23000.0 * min(integration_ms, 20.0)
        intensity = self._apply_detector_nonlinearity(intensity)
        intensity += self._dark_spectrum()
        intensity += self._rng.normal(0.0, np.sqrt(np.maximum(intensity, 1.0)) * 0.35)
        return np.clip(intensity, 0.0, 65000.0)

    def _xe_lamp_shape(self) -> np.ndarray:
        wavelengths = self._wavelengths
        continuum = (
            0.16
            + 0.95 * np.exp(-0.5 * ((wavelengths - 420.0) / 150.0) ** 2)
            + 0.55 * np.exp(-0.5 * ((wavelengths - 760.0) / 260.0) ** 2)
        )
        uv_rolloff = 1.0 / (1.0 + np.exp(-(wavelengths - 230.0) / 10.0))
        ir_rolloff = 1.0 / (1.0 + np.exp((wavelengths - 1080.0) / 18.0))
        line_centers = np.array([248.0, 308.0, 365.0, 405.0, 467.0, 529.0, 823.0, 882.0, 980.0])
        line_heights = np.array([0.22, 0.18, 0.28, 0.20, 0.16, 0.10, 0.13, 0.10, 0.08])
        lines = np.zeros_like(wavelengths)
        for center, height in zip(line_centers, line_heights):
            lines += height * np.exp(-0.5 * ((wavelengths - center) / 2.8) ** 2)
        return np.maximum((continuum + lines) * uv_rolloff * ir_rolloff, 0.0)

    def _make_fiber_transfer(self) -> np.ndarray:
        wavelengths = self._wavelengths
        x = (wavelengths - wavelengths.mean()) / (np.ptp(wavelengths) / 2.0)
        channel_shift = 0.09 * (self.channel_index - 0.5)
        transfer = (
            0.76
            + channel_shift
            + 0.08 * np.sin(wavelengths / 115.0 + self._phase)
            + 0.035 * x
            - 0.04 * np.exp(-0.5 * ((wavelengths - (610.0 + 25.0 * self.channel_index)) / 55.0) ** 2)
        )
        return np.clip(transfer, 0.30, 1.15)

    def _next_spectral_drift(self) -> np.ndarray:
        self._shape_drift = 0.985 * self._shape_drift + self._rng.normal(0.0, [0.0006, 0.0004, 0.00025])
        wavelengths = self._wavelengths
        x = (wavelengths - wavelengths.mean()) / (np.ptp(wavelengths) / 2.0)
        c0, c1, c2 = self._shape_drift
        drift = 1.0 + c0 + c1 * x + c2 * (x * x - 0.33)
        ripple = 1.0 + 0.003 * np.sin(wavelengths / 85.0 + self._phase + 0.01 * self._measurement_index)
        return np.clip(drift * ripple, 0.94, 1.06)

    def _apply_intensity_dependent_fiber_transport(self, intensity: np.ndarray) -> np.ndarray:
        wavelengths = self._wavelengths
        x = (wavelengths - wavelengths.mean()) / (np.ptp(wavelengths) / 2.0)
        normalized_shape = intensity / max(float(np.max(intensity)), 1.0)
        channel_sign = -1.0 if self.channel_index == 0 else 1.0
        coupling = 1.0 + channel_sign * 0.008 * normalized_shape * x
        coupling += 0.004 * np.sin(wavelengths / 170.0 + self._phase) * (normalized_shape - normalized_shape.mean())
        return intensity * np.clip(coupling, 0.97, 1.03)

    def _apply_detector_nonlinearity(self, intensity: np.ndarray) -> np.ndarray:
        normalized = intensity / 65000.0
        nonlinearity = 1.0 - 0.035 * normalized + 0.012 * normalized * normalized
        return intensity * nonlinearity

    def _dark_spectrum(self) -> np.ndarray:
        wavelengths = self._wavelengths
        baseline = 70.0 + 0.025 * (wavelengths - 200.0) + 8.0 * self.channel_index
        thermal = self._rng.normal(0.0, 2.5, size=wavelengths.shape)
        return np.clip(baseline + thermal, 0.0, None)
