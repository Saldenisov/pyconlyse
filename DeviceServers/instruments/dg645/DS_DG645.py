from __future__ import annotations

import socket
from typing import Optional, Union

from tango import AttrWriteType, DevState
from tango.server import attribute, command, device_property

try:
    from DeviceServers.base.DS_general import DS_General
except ModuleNotFoundError:
    import sys
    from pathlib import Path

    app_folder = Path(__file__).resolve().parents[3]
    if str(app_folder) not in sys.path:
        sys.path.append(str(app_folder))
    from DeviceServers.base.DS_general import DS_General


class _Dg645SocketSession:
    def __init__(self, host: str, port: int, timeout_s: float):
        self.host = host
        self.port = int(port)
        self.timeout_s = float(timeout_s)
        self._sock: Optional[socket.socket] = None

    def open(self):
        if self._sock is not None:
            return
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
        sock.settimeout(self.timeout_s)
        self._sock = sock

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def write(self, cmd: str):
        self.open()
        assert self._sock is not None
        self._sock.sendall((cmd.strip() + "\n").encode("ascii"))

    def query(self, cmd: str) -> str:
        self.write(cmd)
        assert self._sock is not None
        chunks = []
        while True:
            data = self._sock.recv(4096)
            if not data:
                break
            chunks.append(data)
            if b"\n" in data or b"\r" in data:
                break
        return b"".join(chunks).decode("ascii", errors="replace").strip()


class _Dg645SrsinstSession:
    def __init__(self, interface_type: str, args):
        from srsinst.dg645 import DG645

        self._driver = DG645(interface_type, *args)

    def close(self):
        disconnect = getattr(self._driver, "disconnect", None)
        if disconnect is not None:
            disconnect()

    def write(self, cmd: str):
        if hasattr(self._driver, "send"):
            self._driver.send(cmd.strip())
            return
        self._driver.comm.send(cmd.strip())

    def query(self, cmd: str) -> str:
        if hasattr(self._driver, "query_text"):
            return str(self._driver.query_text(cmd.strip())).strip()
        return str(self._driver.comm.query_text(cmd.strip())).strip()


class DS_DG645(DS_General):
    """Tango device server for Stanford Research Systems DG645.

    PyConlyse wrapper around the official SRS ``srsinst.dg645`` driver.
    Falls back to raw SCPI only when the Python driver is not installed.

    Minimal Tango surface for pump-probe operation:
    identity, trigger source/rate, burst mode/count/period, and delay commands.
    """

    _version_ = "0.1"
    _model_ = "SRS DG645"

    resource = device_property(dtype=str, default_value="")
    host = device_property(dtype=str, default_value="")
    port = device_property(dtype=int, default_value=5025)
    interface_type = device_property(dtype=str, default_value="")
    serial_baud_rate = device_property(dtype=int, default_value=9600)
    driver_backend = device_property(dtype=str, default_value="auto")
    timeout_ms = device_property(dtype=int, default_value=2000)

    _rm = None
    _session = None
    _idn_cache = ""
    _active_backend = ""

    def init_device(self):
        self._rm = None
        self._session = None
        self._idn_cache = ""
        self._active_backend = ""
        super().init_device()

    def find_device(self):
        self._device_id_internal, self._uri = -1, ""
        self._close_session()
        try:
            backend = str(self.driver_backend or "auto").strip().lower()
            if backend not in {"auto", "srsinst", "scpi"}:
                raise ValueError("driver_backend must be auto, srsinst, or scpi")

            candidates = []
            if backend in {"auto", "srsinst"}:
                candidates.append(("srsinst.dg645", self._open_srsinst_session))
            if backend in {"auto", "scpi"}:
                candidates.append(("raw-scpi", self._open_scpi_session))

            errors = []
            for backend_name, opener in candidates:
                try:
                    session, uri = opener()
                    self._session = session
                    self._active_backend = backend_name
                    # Opening a driver object alone is not a connection test.
                    # Verify the transport before accepting it as the active one.
                    idn = str(session.query("*IDN?")).strip()
                    if not idn:
                        raise RuntimeError("DG645 returned an empty *IDN? response")
                    self._idn_cache = idn
                    self._device_id_internal, self._uri = 1, uri
                    # Discovery verifies transport only.  The generator remains
                    # in STANDBY until an explicit Tango turn_on command.
                    self.set_state(DevState.STANDBY)
                    self.info(f"Found DG645 via {backend_name}: {idn}", True)
                    return
                except Exception as exc:
                    errors.append(f"{backend_name}: {exc}")
                    self._close_session()

            raise RuntimeError("; ".join(errors) or "No DG645 backend is configured")
        except Exception as exc:
            self._close_session()
            self.set_state(DevState.FAULT)
            self.error(f"DG645 discovery failed: {exc}")

    def get_controller_status_local(self) -> Union[int, str]:
        try:
            self._ensure_session()
            self._query("*IDN?")
            self.set_state(DevState.ON)
            return 0
        except Exception as exc:
            self.set_state(DevState.FAULT)
            return str(exc)

    def turn_on_local(self) -> Union[int, str]:
        try:
            self._ensure_session()
            self.set_state(DevState.ON)
            return 0
        except Exception as exc:
            self.set_state(DevState.FAULT)
            return str(exc)

    def turn_off_local(self) -> Union[int, str]:
        try:
            self._close_session()
            self.set_state(DevState.OFF)
            return 0
        except Exception as exc:
            self.set_state(DevState.FAULT)
            return str(exc)

    def release_power_dependency_local(self) -> None:
        """Close the local TCP/driver session after an external PDU power loss."""
        self._close_session()

    @attribute(label="IDN", dtype=str, access=AttrWriteType.READ)
    def idn(self) -> str:
        try:
            self._ensure_session()
            self._idn_cache = self._query("*IDN?")
        except Exception as exc:
            self.error(f"IDN error: {exc}")
        return self._idn_cache

    @attribute(label="Driver backend", dtype=str, access=AttrWriteType.READ)
    def active_backend(self) -> str:
        return self._active_backend

    @attribute(label="Trigger source", dtype=int, access=AttrWriteType.READ_WRITE)
    def trigger_source(self) -> int:
        try:
            return int(float(self._query("TSRC?")))
        except Exception:
            return -1

    def write_trigger_source(self, value: int):
        self._write(f"TSRC {int(value)}")

    @attribute(label="Trigger rate, Hz", dtype=float, access=AttrWriteType.READ_WRITE)
    def trigger_rate_hz(self) -> float:
        try:
            return float(self._query("TRAT?"))
        except Exception:
            return 0.0

    def write_trigger_rate_hz(self, value: float):
        self._write(f"TRAT {float(value):.12g}")

    @attribute(label="Burst enabled", dtype=int, access=AttrWriteType.READ_WRITE)
    def burst_enabled(self) -> int:
        try:
            return int(float(self._query("BURM?")))
        except Exception:
            return 0

    def write_burst_enabled(self, value: int):
        self._write(f"BURM {1 if int(value) else 0}")

    @attribute(label="Burst count", dtype=int, access=AttrWriteType.READ_WRITE)
    def burst_count(self) -> int:
        try:
            return int(float(self._query("BURC?")))
        except Exception:
            return 0

    def write_burst_count(self, value: int):
        self._write(f"BURC {max(1, int(value))}")

    @attribute(label="Burst period, s", dtype=float, access=AttrWriteType.READ_WRITE)
    def burst_period_s(self) -> float:
        try:
            return float(self._query("BURP?"))
        except Exception:
            return 0.0

    def write_burst_period_s(self, value: float):
        self._write(f"BURP {float(value):.12g}")

    @command(dtype_in=str, dtype_out=str, doc_in="SCPI write command")
    def scpi_write(self, cmd: str) -> str:
        # Arbitrary SCPI may contain a non-idempotent action such as *TRG.
        # Reconnect it, but never replay it automatically.
        self._write(cmd, retry=False)
        return "OK"

    @command(dtype_in=str, dtype_out=str, doc_in="SCPI query command")
    def scpi_query(self, cmd: str) -> str:
        return self._query(cmd)

    @command(dtype_in=str, dtype_out=str, doc_in="channel,reference,seconds. Example: A,T0,10e-6")
    def set_delay(self, spec: str) -> str:
        channel, reference, seconds = self._parse_delay_spec(spec)
        self._write(f"DLAY {channel},{reference},{seconds:.12g}")
        return self._query(f"DLAY?{channel}")

    @command(dtype_in=str, dtype_out=str, doc_in="Delay channel name or index. Example: B")
    def get_delay(self, channel: str) -> str:
        channel_id = self._channel_id(channel)
        return self._query(f"DLAY?{channel_id}")

    def _ensure_session(self):
        if self._session is None:
            self.find_device()
        if self._session is None:
            raise RuntimeError("No DG645 session")

    def _close_session(self):
        session, rm = self._session, self._rm
        self._session = None
        self._rm = None
        self._active_backend = ""
        if session is not None and hasattr(session, "close"):
            try:
                session.close()
            except Exception:
                pass
        if rm is not None:
            try:
                rm.close()
            except Exception:
                pass

    def _execute_with_reconnect(self, operation: str, command: str, retry: bool = True):
        """Execute a command, reconnecting once only when replay is safe."""
        self._ensure_session()
        try:
            return getattr(self._session, operation)(command)
        except Exception as first_error:
            # Power cycling a DG645 invalidates the driver socket without
            # invalidating the Python object. Discard it before trying again.
            self.warn(f"DG645 transport failed for {command!r}; reconnecting.", True)
            self._close_session()
            self.find_device()
            if self._session is None:
                raise RuntimeError(f"DG645 reconnect failed after {first_error}") from first_error
            if not retry:
                raise RuntimeError(
                    f"DG645 transport reconnected; {command!r} was not replayed"
                ) from first_error
            try:
                return getattr(self._session, operation)(command)
            except Exception:
                self._close_session()
                raise

    def _open_srsinst_session(self):
        if self.resource:
            interface_type = (self.interface_type or "visa").strip().lower()
            if interface_type == "serial":
                args = [self.resource, int(self.serial_baud_rate)]
            else:
                args = [self.resource]
            return _Dg645SrsinstSession(interface_type, args), f"{interface_type}:{self.resource}"
        if self.host:
            interface_type = (self.interface_type or "tcpip").strip().lower()
            args = [self.host] if interface_type == "vxi11" else [self.host, int(self.port)]
            return _Dg645SrsinstSession(interface_type, args), f"{interface_type}://{self.host}:{self.port}"
        raise RuntimeError("DG645 resource or host property is required")

    def _open_scpi_session(self):
        if self.resource:
            import pyvisa

            self._rm = pyvisa.ResourceManager()
            session = self._rm.open_resource(self.resource)
            session.timeout = int(self.timeout_ms)
            try:
                session.read_termination = "\n"
                session.write_termination = "\n"
            except Exception:
                pass
            return session, self.resource
        if self.host:
            return (
                _Dg645SocketSession(self.host, int(self.port), int(self.timeout_ms) / 1000),
                f"tcp://{self.host}:{self.port}",
            )
        raise RuntimeError("DG645 resource or host property is required")

    def _write(self, cmd: str, retry: bool = True):
        self._execute_with_reconnect("write", cmd, retry=retry)

    def _query(self, cmd: str) -> str:
        return str(self._execute_with_reconnect("query", cmd)).strip()

    @staticmethod
    def _channel_id(value: str) -> int:
        mapping = {
            "T0": 0,
            "T1": 1,
            "A": 2,
            "B": 3,
            "C": 4,
            "D": 5,
            "E": 6,
            "F": 7,
            "G": 8,
            "H": 9,
        }
        text = str(value).strip().upper()
        if text in mapping:
            return mapping[text]
        return int(text)

    @classmethod
    def _parse_delay_spec(cls, spec: str):
        parts = [part.strip() for part in str(spec).split(",")]
        if len(parts) != 3:
            raise ValueError("Delay spec must be channel,reference,seconds")
        return cls._channel_id(parts[0]), cls._channel_id(parts[1]), float(parts[2])


if __name__ == "__main__":
    DS_DG645.run_server()
