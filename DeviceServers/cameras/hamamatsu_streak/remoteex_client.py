from __future__ import annotations

import socket
import threading
from typing import List, Optional

from .remoteex_protocol import (
    DATA_READY_GREETING,
    READY_GREETING,
    RemoteExCommandError,
    RemoteExProtocolError,
    RemoteExResponse,
    RemoteExTransportError,
    ensure_command_terminated,
    parse_response_line,
    response_summary,
)


class RemoteExClient:
    """Minimal serialized TCP client for HPD-TA RemoteEx."""

    def __init__(
        self,
        host: str = "localhost",
        command_port: int = 1001,
        data_port: Optional[int] = 1002,
        timeout: float = 5.0,
        encoding: str = "ascii",
    ):
        self.host = host
        self.command_port = int(command_port)
        self.data_port = None if data_port is None else int(data_port)
        self.timeout = float(timeout)
        self.encoding = encoding
        self._command_socket: Optional[socket.socket] = None
        self._data_socket: Optional[socket.socket] = None
        self._lock = threading.RLock()
        self.last_messages: List[RemoteExResponse] = []
        self.last_response: Optional[RemoteExResponse] = None

    @property
    def is_connected(self) -> bool:
        return self._command_socket is not None

    @property
    def command_socket(self) -> socket.socket:
        if self._command_socket is None:
            raise RemoteExTransportError("RemoteEx command socket is not connected")
        return self._command_socket

    @property
    def data_socket(self) -> socket.socket:
        if self._data_socket is None:
            raise RemoteExTransportError("RemoteEx data socket is not connected")
        return self._data_socket

    def connect(self, connect_data_port: bool = False) -> None:
        with self._lock:
            if self._command_socket is None:
                self._command_socket = self._open_socket(self.command_port)
                greeting = self._read_line(self._command_socket)
                if greeting.strip() != READY_GREETING:
                    self.close()
                    raise RemoteExTransportError(
                        f"Unexpected RemoteEx command greeting: {greeting!r}"
                    )

            if connect_data_port:
                self.connect_data_port()

    def connect_data_port(self) -> None:
        if self.data_port is None:
            raise RemoteExTransportError("RemoteEx data port is not configured")

        with self._lock:
            if self._data_socket is not None:
                return
            self._data_socket = self._open_socket(self.data_port)
            greeting = self._read_line(self._data_socket)
            if greeting.strip() != DATA_READY_GREETING:
                self.close_data_port()
                raise RemoteExTransportError(
                    f"Unexpected RemoteEx data greeting: {greeting!r}"
                )

    def close_data_port(self) -> None:
        with self._lock:
            if self._data_socket is not None:
                try:
                    self._data_socket.close()
                finally:
                    self._data_socket = None

    def close(self) -> None:
        with self._lock:
            self.close_data_port()
            if self._command_socket is not None:
                try:
                    self._command_socket.close()
                finally:
                    self._command_socket = None

    def send_command(self, command: str, timeout: Optional[float] = None) -> RemoteExResponse:
        payload = ensure_command_terminated(command).encode(self.encoding, errors="replace")

        with self._lock:
            if self._command_socket is None:
                raise RemoteExTransportError("RemoteEx is not connected")

            self.command_socket.settimeout(timeout or self.timeout)
            try:
                self.command_socket.sendall(payload)
            except OSError as exc:
                raise RemoteExTransportError(
                    f"Could not send RemoteEx command {command!r}: {exc}"
                ) from exc

            messages: List[RemoteExResponse] = []
            unparsable_lines: List[str] = []

            while True:
                line = self._read_line(self.command_socket)
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped in (READY_GREETING, DATA_READY_GREETING):
                    continue

                try:
                    response = parse_response_line(stripped)
                except RemoteExProtocolError:
                    unparsable_lines.append(stripped)
                    if len(unparsable_lines) >= 3:
                        raise RemoteExTransportError(
                            f"Received unparsable RemoteEx lines after {command!r}: {unparsable_lines}"
                        )
                    continue

                if response.is_message:
                    messages.append(response)
                    continue

                self.last_messages = messages
                self.last_response = response
                return response

    def send_command_checked(
        self, command: str, timeout: Optional[float] = None
    ) -> RemoteExResponse:
        response = self.send_command(command, timeout=timeout)
        if not response.is_ok:
            raise RemoteExCommandError(
                f"RemoteEx command failed for {command!r}: {response_summary(response)}",
                response,
            )
        return response

    def read_data_exact(self, size: int) -> bytes:
        remaining = int(size)
        chunks: List[bytes] = []

        with self._lock:
            sock = self.data_socket
            while remaining > 0:
                chunk = sock.recv(remaining)
                if not chunk:
                    raise RemoteExTransportError(
                        f"RemoteEx data socket closed with {remaining} bytes remaining"
                    )
                chunks.append(chunk)
                remaining -= len(chunk)
        return b"".join(chunks)

    def _open_socket(self, port: int) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.host, int(port)))
        except OSError as exc:
            sock.close()
            raise RemoteExTransportError(
                f"Could not connect to RemoteEx at {self.host}:{port}: {exc}"
            ) from exc
        return sock

    @staticmethod
    def _read_line(sock: socket.socket) -> str:
        buffer = bytearray()
        while True:
            try:
                chunk = sock.recv(1)
            except OSError as exc:
                raise RemoteExTransportError(f"Failed reading RemoteEx socket: {exc}") from exc

            if chunk == b"":
                raise RemoteExTransportError("RemoteEx socket closed while reading a line")

            if chunk == b"\r":
                return buffer.decode("utf-8", errors="replace")
            if chunk == b"\n":
                continue
            buffer.extend(chunk)
