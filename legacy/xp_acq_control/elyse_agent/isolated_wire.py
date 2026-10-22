"""Private bounded JSON IPC; no pickle, native imports or arbitrary execution.

Tuple identity and integer dictionary keys are preserved: several source
procedures deliberately reject mutable lists or distinguish integer locals.
The tagged representation is internal to anonymous parent/child pipes, not a
network protocol or a general object deserializer. Python 3.4 compatible.
"""
import json
import math
import struct


MAX_FRAME_BYTES = 1048576
MAX_DEPTH = 48


class IsolationProtocolError(RuntimeError):
    pass


def pack_value(value, depth=0):
    if depth > MAX_DEPTH:
        raise IsolationProtocolError("IPC value exceeds nesting limit")
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise IsolationProtocolError("IPC requires finite numbers")
        return value
    if type(value) in (tuple, list, set):
        return {"type": type(value).__name__, "items": [pack_value(item, depth + 1) for item in value]}
    if type(value) is dict:
        return {"type": "dict", "items": [[pack_value(key, depth + 1), pack_value(item, depth + 1)]
                                            for key, item in value.items()]}
    raise IsolationProtocolError("Unsupported IPC value type: " + type(value).__name__)


def unpack_value(value, depth=0):
    if depth > MAX_DEPTH:
        raise IsolationProtocolError("IPC value exceeds nesting limit")
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is not dict or set(value) != {"type", "items"} or type(value["items"]) is not list:
        raise IsolationProtocolError("Invalid IPC value envelope")
    kind, items = value["type"], value["items"]
    if kind in ("tuple", "list", "set"):
        values = [unpack_value(item, depth + 1) for item in items]
        return tuple(values) if kind == "tuple" else set(values) if kind == "set" else values
    if kind == "dict":
        result = {}
        for pair in items:
            if type(pair) is not list or len(pair) != 2:
                raise IsolationProtocolError("Invalid IPC dictionary pair")
            key, item = (unpack_value(part, depth + 1) for part in pair)
            if type(key) not in (str, int, tuple) or key in result:
                raise IsolationProtocolError("Invalid or duplicate IPC dictionary key")
            result[key] = item
        return result
    raise IsolationProtocolError("Unknown IPC value tag")


def encode_frame(message):
    if type(message) is not dict:
        raise IsolationProtocolError("IPC message must be a dictionary")
    payload = json.dumps(pack_value(message), allow_nan=False, separators=(",", ":")).encode("utf-8")
    if not payload or len(payload) > MAX_FRAME_BYTES:
        raise IsolationProtocolError("IPC frame exceeds bounded size")
    return struct.pack("!I", len(payload)) + payload


def write_frame(stream, message):
    frame, offset = encode_frame(message), 0
    while offset < len(frame):
        count = stream.write(frame[offset:])
        if count is None or count <= 0:
            raise EOFError("IPC pipe closed during write")
        offset += count
    stream.flush()


def _read_exact(stream, count):
    parts, remaining = [], count
    while remaining:
        part = stream.read(remaining)
        if not part:
            raise EOFError("IPC pipe closed during read")
        parts.append(part)
        remaining -= len(part)
    return b"".join(parts)


def read_frame(stream):
    length = struct.unpack("!I", _read_exact(stream, 4))[0]
    if not 0 < length <= MAX_FRAME_BYTES:
        raise IsolationProtocolError("Invalid IPC frame length")
    try:
        message = unpack_value(json.loads(_read_exact(stream, length).decode("utf-8")))
    except (ValueError, TypeError, UnicodeDecodeError) as error:
        raise IsolationProtocolError("Invalid IPC frame: " + str(error))
    if type(message) is not dict:
        raise IsolationProtocolError("IPC message must be a dictionary")
    return message
