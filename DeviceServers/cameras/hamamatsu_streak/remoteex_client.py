from __future__ import annotations

import socket
import threading
import re
from dataclasses import dataclass
from typing import List, Optional

from .remoteex_protocol import (
    DATA_READY_GREETING,
    READY_GREETING,
    RemoteExCommandError,
    RemoteExError,
    RemoteExProtocolError,
    RemoteExResponse,
    RemoteExTransportError,
    ensure_command_terminated,
    parse_response_line,
    response_summary,
)


class RemoteExLiveFrameUnavailable(RemoteExError):
    """No frame newer than the last delivered Live frame is available."""

    def __init__(self, initial: bool = False):
        super().__init__("Waiting for next Live frame" if initial else "No new Live frame")
        self.initial = initial


@dataclass(frozen=True)
class RemoteExImage:
    """One image returned by HPD-TA through the RemoteEx data port."""

    width: int
    height: int
    bytes_per_pixel: int
    data_type: str
    pixels: bytes
    sequence_number: Optional[int] = None


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
        self.last_ring_buffer_sequence: Optional[int] = None

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
                try:
                    greeting = self._read_line(self._command_socket)
                except Exception:
                    self.close()
                    raise
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
            try:
                greeting = self._read_line(self._data_socket)
            except Exception:
                self.close_data_port()
                raise
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

    def get_current_image(self, data_type: str = "Display") -> RemoteExImage:
        """Read the selected HPD-TA image through the binary data port.

        RemoteEx requires the data connection to exist before ``ImgDataGet`` and
        sends exactly ``width * height * bytes_per_pixel`` bytes after its reply.
        Keeping the full exchange under one lock prevents interleaved requests.
        """
        with self._lock:
            self.connect(connect_data_port=True)
            self._discard_pending_data()
            response = self.send_command_checked(f"ImgDataGet(Current,{data_type})")
            return self._read_image_response(response, "ImgDataGet")

    def get_ring_buffer_image(
        self, data_type: str = "Data", sequence_number: Optional[int] = None
    ) -> RemoteExImage:
        """Read a frame captured by ``AcqLiveMonitor(RingBuffer, N)``.

        When no sequence is supplied, request the successor to the last frame.
        RemoteEx returns the oldest retained frame when that sequence has fallen
        out of its short ring buffer, keeping the browser preview moving even
        after a delayed request.
        """
        with self._lock:
            self.connect(connect_data_port=True)
            self._discard_pending_data()
            if sequence_number is None:
                sequence_number = (
                    0
                    if self.last_ring_buffer_sequence is None
                    else self.last_ring_buffer_sequence + 1
                )
            response = self.send_command_checked(
                f"ImgRingBufferGet({data_type},{int(sequence_number)})"
            )
            image = self._read_image_response(response, "ImgRingBufferGet")
            if image.sequence_number is not None:
                self.last_ring_buffer_sequence = image.sequence_number
            return image

    def get_latest_live_image(self, data_type: str = "Data") -> RemoteExImage:
        """Return only a frame announced after the previous preview request.

        Querying the ring buffer from sequence zero replays historical frames
        after Live has stopped. Probing above its current maximum yields the
        newest sequence without transferring an image; only a newer sequence is
        then fetched through the data channel.
        """
        with self._lock:
            self.connect(connect_data_port=True)
            probe = self.send_command(f"ImgRingBufferGet({data_type},2147483647)")
            if probe.is_ok:
                raise RemoteExProtocolError(
                    f"Unexpected successful Live ring probe: {probe.raw_line!r}"
                )

            match = re.search(r"current max\s*=\s*(\d+)", probe.raw_line, re.IGNORECASE)
            if match is None:
                raise RemoteExCommandError(
                    f"RemoteEx Live ring probe failed: {response_summary(probe)}", probe
                )
            latest_sequence = int(match.group(1))
            if self.last_ring_buffer_sequence is None:
                self.last_ring_buffer_sequence = latest_sequence
                raise RemoteExLiveFrameUnavailable(initial=True)
            if latest_sequence <= self.last_ring_buffer_sequence:
                raise RemoteExLiveFrameUnavailable()

            self._discard_pending_data()
            response = self.send_command_checked(
                f"ImgRingBufferGet({data_type},{latest_sequence})"
            )
            image = self._read_image_response(response, "ImgRingBufferGet")
            self.last_ring_buffer_sequence = image.sequence_number or latest_sequence
            return image

    def _read_image_response(
        self, response: RemoteExResponse, command_name: str
    ) -> RemoteExImage:
        if len(response.parameters) < 4:
            raise RemoteExProtocolError(
                f"Unexpected {command_name} response: {response.raw_line!r}"
            )

        try:
            width = int(response.parameters[0])
            height = int(response.parameters[1])
            bytes_per_pixel = int(response.parameters[2])
        except ValueError as exc:
            raise RemoteExProtocolError(
                f"Invalid {command_name} dimensions: {response.raw_line!r}"
            ) from exc

        if width <= 0 or height <= 0 or bytes_per_pixel <= 0:
            raise RemoteExProtocolError(
                f"Invalid {command_name} dimensions: {response.raw_line!r}"
            )

        pixel_count = width * height * bytes_per_pixel
        sequence_number = None
        if command_name == "ImgRingBufferGet" and len(response.parameters) >= 5:
            try:
                sequence_number = int(response.parameters[4])
            except ValueError:
                pass

        return RemoteExImage(
            width=width,
            height=height,
            bytes_per_pixel=bytes_per_pixel,
            data_type=response.parameters[3],
            pixels=self.read_data_exact(pixel_count),
            sequence_number=sequence_number,
        )

    def _discard_pending_data(self) -> None:
        """Clear stale binary data before requesting the next image."""
        sock = self.data_socket
        previous_timeout = sock.gettimeout()
        sock.setblocking(False)
        try:
            while True:
                try:
                    if not sock.recv(65536):
                        return
                except BlockingIOError:
                    return
        finally:
            sock.settimeout(previous_timeout)

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
