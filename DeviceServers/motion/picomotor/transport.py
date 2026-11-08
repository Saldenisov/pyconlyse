"""Synchronous 8742 TCP transport; construction performs no I/O.

Protocol: Newport 8742 User Manual, sections 5.5 and 6.1.1/6.2.1.
Commands end in CR, replies in CRLF; RS-485 slaves use matching ``n>``
command/reply prefixes. TCP framing also matches the published newfocus8742
TCP implementation. Telnet option negotiation is refused rather than treating
its initial bytes as a fixed-length banner.

This transport reports controller step counts, not measured physical position.
No discovery, initialization motion, reset, automatic reconnect or command
replay is performed. A TE? read consumes one queued controller error.
"""

from __future__ import annotations

import math
import re
import socket
import time
from threading import RLock


class PicomotorError(RuntimeError):
    """Base class for controller and communication failures."""


class PicomotorTransportError(PicomotorError):
    """Connection failed or response did not arrive before the deadline."""


class PicomotorProtocolError(PicomotorError):
    """Malformed response; session closed to prevent response misalignment."""


class PicomotorDeviceError(PicomotorError):
    """Controller returned a nonzero error after a command."""

    def __init__(self, code: int, command: str):
        self.code = code
        self.command = command
        super().__init__(f"Controller error {code} after {command!r}")


def _integer(value, low: int, high: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not low <= value <= high:
        raise ValueError(f"{name} must be in [{low}, {high}]")
    return value


class Picomotor8742:
    """One explicitly configured TCP controller, with serialized transactions.

    ``controller_address=0`` selects the directly connected master. Addresses
    1..31 select a controller through the master's RS-485 link. An injected
    ``connection_factory`` has the socket.create_connection call signature:
    ``factory((host, port), timeout=timeout_s)`` and returns a socket-like object.
    """

    _MAX_REPLY_BYTES = 4096
    _MAX_WIRE_BYTES = 8192
    _RECV_CHUNK = 1024
    _STARTUP_IDLE_S = 0.05
    _MIN_STEPS = -(2**31)
    _MAX_STEPS = 2**31 - 1
    _IAC, _WILL, _WONT, _DO, _DONT, _SB, _SE = 255, 251, 252, 253, 254, 250, 240
    _ID_PATTERN = re.compile(
        r"^(?:New[_ ]?Focus|Newport)[,\s]+(?:Model\s+)?8742(?=[,\s]|$)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        host: str,
        port: int = 23,
        timeout_s: float = 2.0,
        controller_address: int = 0,
        connection_factory=None,
    ):
        if not isinstance(host, str) or not host or host != host.strip():
            raise ValueError("host must be a nonempty hostname or IP address")
        if any(char.isspace() or ord(char) < 32 for char in host):
            raise ValueError("host must not contain whitespace or control characters")
        self._port = _integer(port, 1, 65535, "port")
        self._controller_address = _integer(
            controller_address, 0, 31, "controller_address"
        )
        if (
            isinstance(timeout_s, bool)
            or not isinstance(timeout_s, (int, float))
            or not math.isfinite(timeout_s)
            or timeout_s <= 0
        ):
            raise ValueError("timeout_s must be finite and positive")
        if connection_factory is not None and not callable(connection_factory):
            raise ValueError("connection_factory must be callable")
        self._host = host
        self._timeout_s = float(timeout_s)
        self._connection_factory = connection_factory
        self._lock = RLock()
        self._socket = None
        self._identification = None
        self._buffer = bytearray()
        self._telnet_state = "data"
        self._telnet_option_command = None

    @property
    def connected(self) -> bool:
        """Whether this driver owns an identified session; no network probe."""
        with self._lock:
            return self._socket is not None

    @property
    def controller_address(self) -> int:
        return self._controller_address

    def connect(self) -> str:
        """Identify the selected controller with *IDN?; perform no motion/setup."""
        with self._lock:
            if self._socket is not None:
                return self._identification
            deadline = time.monotonic() + self._timeout_s
            try:
                # Resolve the default factory now, preserving network guards.
                factory = self._connection_factory or socket.create_connection
                self._socket = factory(
                    (self._host, self._port), timeout=self._remaining(deadline)
                )
                self._negotiate_startup(deadline)
                identification = self._query("*IDN?", deadline=deadline)
                if not self._ID_PATTERN.match(identification):
                    self._fail_protocol(
                        f"Expected a New Focus/Newport 8742, got {identification!r}"
                    )
                self._identification = identification
                return identification
            except OSError as exc:
                self._fail_transport("Connection/identification failed", exc)

    def close(self) -> None:
        """Close communication without sending motion or configuration commands."""
        with self._lock:
            current, self._socket = self._socket, None
            self._identification = None
            self._buffer.clear()
            self._telnet_state = "data"
            self._telnet_option_command = None
            if current is not None:
                try:
                    current.close()
                except OSError:
                    pass

    def position(self, axis: int) -> int:
        axis = _integer(axis, 1, 4, "axis")
        with self._lock:
            return self._reply_integer(self._query(f"{axis}TP?"), "TP?")

    def motion_done(self, axis: int) -> bool:
        axis = _integer(axis, 1, 4, "axis")
        with self._lock:
            reply = self._query(f"{axis}MD?")
            if reply not in {"0", "1"}:
                self._fail_protocol(f"MD? must return 0 or 1, got {reply!r}")
            return reply == "1"

    def error_code(self) -> int:
        """Consume and return exactly one error queue entry using TE?."""
        with self._lock:
            return self._reply_integer(self._query("TE?"), "TE?")

    def move_relative(self, axis: int, steps: int) -> None:
        self._axis_write(axis, "PR", steps)

    def move_absolute(self, axis: int, steps: int) -> None:
        self._axis_write(axis, "PA", steps)

    def define_position(self, axis: int, steps: int) -> None:
        self._axis_write(axis, "DH", steps)

    def stop(self, axis: int) -> None:
        axis = _integer(axis, 1, 4, "axis")
        self._write_checked(f"{axis}ST")

    def abort(self) -> None:
        self._write_checked("AB")

    def _axis_write(self, axis: int, command: str, steps: int) -> None:
        axis = _integer(axis, 1, 4, "axis")
        steps = _integer(steps, self._MIN_STEPS, self._MAX_STEPS, "steps")
        self._write_checked(f"{axis}{command}{steps}")

    def _write_checked(self, command: str) -> None:
        with self._lock:
            self._require_connected()
            deadline = time.monotonic() + self._timeout_s
            try:
                self._send(self._format(command).encode("ascii") + b"\r", deadline)
                code = self._reply_integer(self._query("TE?", deadline=deadline), "TE?")
                if code != 0:
                    # TE? may report an older queued error; do not drain/retry.
                    raise PicomotorDeviceError(code, command)
            except OSError as exc:
                self._fail_transport(f"Transport failed after {command!r}", exc)

    def _query(self, command: str, *, deadline=None) -> str:
        with self._lock:
            self._require_connected()
            if deadline is None:
                deadline = time.monotonic() + self._timeout_s
            try:
                self._send(self._format(command).encode("ascii") + b"\r", deadline)
                reply = self._readline(deadline)
                if self._controller_address:
                    prefix = f"{self._controller_address}>"
                    if not reply.startswith(prefix):
                        self._fail_protocol(
                            f"Expected slave reply prefix {prefix!r}, got {reply!r}"
                        )
                    reply = reply[len(prefix) :].strip()
                elif ">" in reply:
                    self._fail_protocol(f"Unexpected slave reply for master: {reply!r}")
                if not reply:
                    self._fail_protocol("Controller returned an empty reply")
                return reply
            except OSError as exc:
                self._fail_transport(f"Transport failed during {command!r}", exc)

    def _format(self, command: str) -> str:
        if self._controller_address:
            return f"{self._controller_address}>{command}"
        return command

    def _require_connected(self) -> None:
        if self._socket is None:
            raise PicomotorTransportError("Controller is disconnected; call connect()")

    @staticmethod
    def _remaining(deadline) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Controller transaction deadline expired")
        return remaining

    def _send(self, payload: bytes, deadline) -> None:
        self._socket.settimeout(self._remaining(deadline))
        self._socket.sendall(payload)
        self._remaining(deadline)

    def _readline(self, deadline) -> str:
        wire_bytes = 0
        while True:
            self._remaining(deadline)
            end = self._buffer.find(b"\r\n")
            if end >= 0:
                if end > self._MAX_REPLY_BYTES:
                    self._fail_protocol("Controller reply exceeds byte limit")
                raw = bytes(self._buffer[:end])
                del self._buffer[: end + 2]
                if self._buffer:
                    self._fail_protocol("Unsolicited data after controller reply")
                if any(byte < 32 or byte == 127 for byte in raw):
                    self._fail_protocol("Control character in controller reply")
                try:
                    return raw.decode("ascii").strip()
                except UnicodeDecodeError:
                    self._fail_protocol("Non-ASCII controller reply")
            if len(self._buffer) > self._MAX_REPLY_BYTES + 1:
                self._fail_protocol("Controller reply exceeds byte limit")
            self._socket.settimeout(self._remaining(deadline))
            chunk = self._socket.recv(self._RECV_CHUNK)
            self._remaining(deadline)
            if not chunk:
                raise ConnectionError(
                    "Controller closed connection before full CRLF reply"
                )
            wire_bytes += len(chunk)
            if wire_bytes > self._MAX_WIRE_BYTES:
                self._fail_protocol("Controller/Telnet input exceeds byte limit")
            self._consume_telnet(chunk, deadline)

    def _negotiate_startup(self, deadline) -> None:
        """Refuse startup Telnet echo before sending the identification query.

        A quiet socket with no partial negotiation is valid. A partial IAC frame
        must complete before the transaction deadline; arbitrary startup bytes
        are not discarded under the assumption that all firmware sends six.
        """
        wire_bytes = 0
        while True:
            remaining = self._remaining(deadline)
            timeout = remaining
            if self._telnet_state == "data":
                timeout = min(timeout, self._STARTUP_IDLE_S)
            self._socket.settimeout(timeout)
            try:
                chunk = self._socket.recv(self._RECV_CHUNK)
            except TimeoutError:
                self._remaining(deadline)
                if self._telnet_state == "data":
                    return
                raise
            self._remaining(deadline)
            if not chunk:
                raise ConnectionError("Controller closed connection during startup")
            wire_bytes += len(chunk)
            if wire_bytes > self._MAX_WIRE_BYTES:
                self._fail_protocol("Startup Telnet input exceeds byte limit")
            self._consume_telnet(chunk, deadline)
            if self._buffer:
                self._fail_protocol(
                    "Unexpected application bytes before identification"
                )

    def _consume_telnet(self, chunk: bytes, deadline) -> None:
        for byte in chunk:
            state = self._telnet_state
            if state == "data":
                if byte == self._IAC:
                    self._telnet_state = "iac"
                else:
                    self._buffer.append(byte)
            elif state == "iac":
                if byte == self._IAC:
                    self._buffer.append(byte)
                    self._telnet_state = "data"
                elif byte in {self._WILL, self._WONT, self._DO, self._DONT}:
                    self._telnet_option_command = byte
                    self._telnet_state = "option"
                elif byte == self._SB:
                    self._telnet_state = "subnegotiation"
                elif 241 <= byte <= 249:
                    self._telnet_state = "data"
                else:
                    self._fail_protocol(f"Unexpected Telnet command {byte}")
            elif state == "option":
                command = self._telnet_option_command
                self._telnet_state = "data"
                self._telnet_option_command = None
                if command in {self._WILL, self._DO}:
                    refusal = self._DONT if command == self._WILL else self._WONT
                    self._send(bytes((self._IAC, refusal, byte)), deadline)
            elif state == "subnegotiation":
                if byte == self._IAC:
                    self._telnet_state = "subnegotiation_iac"
            else:  # subnegotiation_iac: escaped IAC or end of subnegotiation
                if byte == self._SE:
                    self._telnet_state = "data"
                elif byte == self._IAC:
                    self._telnet_state = "subnegotiation"
                else:
                    self._fail_protocol("Malformed Telnet subnegotiation")

    def _reply_integer(self, reply: str, command: str) -> int:
        if not re.fullmatch(r"[+-]?[0-9]+", reply):
            self._fail_protocol(f"{command} returned a noninteger reply: {reply!r}")
        try:
            result = int(reply)
        except ValueError:
            self._fail_protocol(f"{command} integer reply exceeds parser limit")
        if not self._MIN_STEPS <= result <= self._MAX_STEPS:
            self._fail_protocol(
                f"{command} integer reply is outside signed 32-bit range"
            )
        return result

    def _fail_protocol(self, message: str):
        self.close()
        raise PicomotorProtocolError(message)

    def _fail_transport(self, message: str, cause: OSError):
        self.close()
        raise PicomotorTransportError(message) from cause
