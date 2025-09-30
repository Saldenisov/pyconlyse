from typing import Optional, Union

from tango import AttrWriteType, DevState
from tango.server import attribute, command, device_property

try:
    from DeviceServers.base.DS_general import DS_General
except ModuleNotFoundError:
    # Fallback for when launched from a subdirectory without PYTHONPATH set
    import sys
    from pathlib import Path

    app_folder = Path(__file__).resolve().parents[3]  # Go to pyconlyse root
    if str(app_folder) not in sys.path:
        sys.path.append(str(app_folder))
    from DeviceServers.base.DS_general import DS_General


class DS_KEYSIGHT_33509B(DS_General):
    """Device Server for Keysight 33509B Trueform Waveform Generator.

    Provides basic SCPI control via PyVISA: IDN, output state, waveform, frequency,
    amplitude (Vpp), and DC offset. Discovery is by VISA resource string or
    by USB serial number (e.g. 'MY59000717').
    """

    # Versioning/metadata shown in the UI
    _version_ = "0.1"
    _model_ = "KEYSIGHT 33509B"

    # Tango device properties
    serial_number = device_property(dtype=str, default_value="")  # e.g. MY59000717
    resource = device_property(dtype=str, default_value="")  # e.g. USB0::0x0957::0x2C07::MY59000717::INSTR
    channel = device_property(dtype=int, default_value=1)  # Output channel (1 or 2)

    # Internal state/cache
    _rm = None  # type: ignore
    _inst = None  # type: ignore
    _idn_cache: str = ""

    # Defaults applied on turn_on
    _default_waveform = "SIN"
    _default_frequency_hz = 1000.0
    _default_amplitude_vpp = 1.0
    _default_offset_v = 0.0

    def init_device(self):
        # Initialize local defaults before base init (which calls find_device)
        self._rm = None
        self._inst = None
        self._idn_cache = ""
        super().init_device()

    # ---------------- Base overrides -----------------
    def register_variables_for_archive(self):
        super().register_variables_for_archive()

    def find_device(self):
        """Find and open the VISA session. Sets _device_id_internal and _uri."""
        self._device_id_internal, self._uri = -1, b""
        try:
            import pyvisa  # lazy import

            self.info("Searching for Keysight 33509B via VISA", True)
            rm = pyvisa.ResourceManager()

            chosen = None
            if self.resource:
                chosen = self.resource
            else:
                # Try to locate by serial number inside USB VISA resource string
                # Typical format: USB0::0x0957::0x2C07::MY59000717::INSTR
                if self.serial_number:
                    for r in rm.list_resources("?*INSTR"):
                        if self.serial_number in r:
                            chosen = r
                            break
                # Fallback: pick the first Keysight USB generator-looking resource
                if not chosen:
                    for r in rm.list_resources("USB?*INSTR"):
                        if "USB" in r and "::INSTR" in r:
                            chosen = r
                            break

            if not chosen:
                self.info("No matching VISA resource found for Keysight 33509B", True)
                return

            inst = rm.open_resource(chosen)
            # Configure common IO parameters
            try:
                inst.read_termination = "\n"
                inst.write_termination = "\n"
                inst.timeout = 2000  # ms
            except Exception:
                pass

            # Verify identity
            try:
                idn = inst.query("*IDN?").strip()
                self._idn_cache = idn
                if "33509" not in idn and "33500" not in idn and "KEYSIGHT" not in idn.upper():
                    self.info(f"VISA resource selected but does not look like 33509B: {idn}", True)
            except Exception as e:
                self.info(f"Warning: could not query *IDN?: {e}", True)

            # Success
            self._rm = rm
            self._inst = inst
            self._device_id_internal, self._uri = 1, chosen.encode("utf-8")
            self.info(f"Found instrument at {chosen}", True)
        except Exception as e:
            self.error(f"VISA discovery failed: {e}")
            self._device_id_internal, self._uri = -1, b""

    def get_controller_status_local(self) -> Union[int, str]:
        # If we have a session, consider the controller OK
        if self._inst is not None:
            self.set_state(DevState.ON)
            return 0
        self.set_state(DevState.FAULT)
        return -1

    def turn_on_local(self) -> Union[int, str]:
        """Put device in a known state. For safety, keep output OFF by default."""
        try:
            self._ensure_session()
            if self._inst is None:
                return "No VISA session open"
            # Clear, set defaults; keep outputs off
            self._safe_write("*CLS")
            # Configure channel defaults
            ch = max(1, min(int(self.channel), 2))
            self._safe_write(f"SOUR{ch}:FUNC {self._default_waveform}")
            self._safe_write(f"SOUR{ch}:FREQ {self._default_frequency_hz}")
            self._safe_write(f"SOUR{ch}:VOLT:UNIT VPP")
            self._safe_write(f"SOUR{ch}:VOLT {self._default_amplitude_vpp}")
            self._safe_write(f"SOUR{ch}:VOLT:OFFS {self._default_offset_v}")
            self._safe_write(f"OUTP{ch}:STAT OFF")
            self.set_state(DevState.ON)
            return 0
        except Exception as e:
            self.set_state(DevState.FAULT)
            return str(e)

    def turn_off_local(self) -> Union[int, str]:
        try:
            if self._inst is not None:
                ch = max(1, min(int(self.channel), 2))
                self._safe_write(f"OUTP{ch}:STAT OFF")
                try:
                    self._inst.close()
                except Exception:
                    pass
            if self._rm is not None:
                try:
                    self._rm.close()
                except Exception:
                    pass
            self._inst = None
            self._rm = None
            self.set_state(DevState.OFF)
            return 0
        except Exception as e:
            self.set_state(DevState.FAULT)
            return str(e)

    # ---------------- Attributes -----------------
    @attribute(label="IDN", dtype=str, access=AttrWriteType.READ)
    def idn(self) -> str:
        try:
            self._ensure_session()
            if self._inst is None:
                return self._idn_cache or ""
            idn = self._inst.query("*IDN?").strip()
            self._idn_cache = idn
            return idn
        except Exception as e:
            self.error(f"IDN error: {e}")
            return self._idn_cache or ""

    @attribute(label="Output enabled", dtype=int, access=AttrWriteType.READ_WRITE)
    def output_enabled(self) -> int:
        try:
            self._ensure_session()
            if self._inst is None:
                return 0
            ch = max(1, min(int(self.channel), 2))
            val = self._inst.query(f"OUTP{ch}:STAT?").strip()
            return 1 if val in ("1", "ON") else 0
        except Exception:
            return 0

    def write_output_enabled(self, value: int):
        try:
            self._ensure_session()
            if self._inst is None:
                return
            ch = max(1, min(int(self.channel), 2))
            state = "ON" if int(value) else "OFF"
            self._safe_write(f"OUTP{ch}:STAT {state}")
        except Exception as e:
            self.error(f"Failed to set output: {e}")

    @attribute(label="Burst enabled", dtype=int, access=AttrWriteType.READ_WRITE)
    def burst_enabled(self) -> int:
        try:
            self._ensure_session()
            if self._inst is None:
                return 0
            ch = max(1, min(int(self.channel), 2))
            val = self._inst.query(f"SOUR{ch}:BURS:STAT?").strip()
            return 1 if val in ("1", "ON") else 0
        except Exception:
            return 0

    def write_burst_enabled(self, value: int):
        try:
            self._ensure_session()
            if self._inst is None:
                return
            ch = max(1, min(int(self.channel), 2))
            state = "ON" if int(value) else "OFF"
            self._safe_write(f"SOUR{ch}:BURS:STAT {state}")
        except Exception as e:
            self.error(f"Failed to set burst: {e}")

    @attribute(label="Waveform", dtype=str, access=AttrWriteType.READ_WRITE)
    def waveform(self) -> str:
        try:
            self._ensure_session()
            if self._inst is None:
                return self._default_waveform
            ch = max(1, min(int(self.channel), 2))
            return self._inst.query(f"SOUR{ch}:FUNC?").strip()
        except Exception:
            return self._default_waveform

    def write_waveform(self, value: str):
        try:
            self._ensure_session()
            if self._inst is None:
                return
            ch = max(1, min(int(self.channel), 2))
            v = str(value).strip().upper()
            # Common: SIN,SQU,RAMP,NOIS,DC,USER
            self._safe_write(f"SOUR{ch}:FUNC {v}")
        except Exception as e:
            self.error(f"Failed to set waveform: {e}")

    @attribute(label="Frequency (Hz)", dtype=float, access=AttrWriteType.READ_WRITE)
    def frequency_hz(self) -> float:
        try:
            self._ensure_session()
            if self._inst is None:
                return self._default_frequency_hz
            ch = max(1, min(int(self.channel), 2))
            return float(self._inst.query(f"SOUR{ch}:FREQ?").strip())
        except Exception:
            return self._default_frequency_hz

    def write_frequency_hz(self, value: float):
        try:
            self._ensure_session()
            if self._inst is None:
                return
            ch = max(1, min(int(self.channel), 2))
            self._safe_write(f"SOUR{ch}:FREQ {float(value)}")
        except Exception as e:
            self.error(f"Failed to set frequency: {e}")

    @attribute(label="Amplitude (Vpp)", dtype=float, access=AttrWriteType.READ_WRITE)
    def amplitude_vpp(self) -> float:
        try:
            self._ensure_session()
            if self._inst is None:
                return self._default_amplitude_vpp
            ch = max(1, min(int(self.channel), 2))
            # Ensure units are VPP for a consistent reading
            self._safe_write(f"SOUR{ch}:VOLT:UNIT VPP")
            return float(self._inst.query(f"SOUR{ch}:VOLT?").strip())
        except Exception:
            return self._default_amplitude_vpp

    def write_amplitude_vpp(self, value: float):
        try:
            self._ensure_session()
            if self._inst is None:
                return
            ch = max(1, min(int(self.channel), 2))
            self._safe_write(f"SOUR{ch}:VOLT:UNIT VPP")
            self._safe_write(f"SOUR{ch}:VOLT {float(value)}")
        except Exception as e:
            self.error(f"Failed to set amplitude: {e}")

    @attribute(label="DC Offset (V)", dtype=float, access=AttrWriteType.READ_WRITE)
    def offset_v(self) -> float:
        try:
            self._ensure_session()
            if self._inst is None:
                return self._default_offset_v
            ch = max(1, min(int(self.channel), 2))
            return float(self._inst.query(f"SOUR{ch}:VOLT:OFFS?").strip())
        except Exception:
            return self._default_offset_v

    def write_offset_v(self, value: float):
        try:
            self._ensure_session()
            if self._inst is None:
                return
            ch = max(1, min(int(self.channel), 2))
            self._safe_write(f"SOUR{ch}:VOLT:OFFS {float(value)}")
        except Exception as e:
            self.error(f"Failed to set offset: {e}")

    # ---------------- Commands -----------------
    @command(dtype_in=str, dtype_out=str, doc_in="SCPI command (write)", doc_out="'OK' or error")
    def scpi_write(self, cmd: str) -> str:
        try:
            self._ensure_session()
            if self._inst is None:
                return "ERROR: No session"
            self._safe_write(cmd)
            return "OK"
        except Exception as e:
            return f"ERROR: {e}"

    @command(dtype_in=str, dtype_out=str, doc_in="SCPI query (read)", doc_out="Response string")
    def scpi_query(self, q: str) -> str:
        try:
            self._ensure_session()
            if self._inst is None:
                return ""
            return str(self._inst.query(q)).strip()
        except Exception as e:
            return f"ERROR: {e}"

    # ---------------- Helpers -----------------
    def _ensure_session(self):
        if self._inst is None:
            self.find_device()

    def _safe_write(self, cmd: str):
        if self._inst is None:
            raise RuntimeError("No VISA session")
        self._inst.write(cmd)


if __name__ == "__main__":
    DS_KEYSIGHT_33509B.run_server()
