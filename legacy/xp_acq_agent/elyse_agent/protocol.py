from __future__ import print_function

import json
import struct

from .errors import ProtocolError


HEADER_SIZE = 4


def recv_exact(sock, byte_count):
    chunks = []
    remaining = byte_count
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise EOFError("connection closed while receiving frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_message(sock, max_frame_bytes):
    header = recv_exact(sock, HEADER_SIZE)
    size = struct.unpack("!I", header)[0]
    if size == 0 or size > max_frame_bytes:
        raise ProtocolError("invalid frame size: {0}".format(size))
    payload = recv_exact(sock, size)
    try:
        message = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ProtocolError("invalid UTF-8 JSON: {0}".format(error))
    if not isinstance(message, dict):
        raise ProtocolError("request must be a JSON object")
    return message


def encode_message(message, max_frame_bytes=1048576):
    payload = json.dumps(
        message, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if not payload or len(payload) > max_frame_bytes:
        raise ProtocolError("encoded frame has invalid size: {0}".format(len(payload)))
    return struct.pack("!I", len(payload)) + payload


def send_message(sock, message, max_frame_bytes=1048576):
    sock.sendall(encode_message(message, max_frame_bytes))

