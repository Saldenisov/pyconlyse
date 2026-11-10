"""Frame cadence readback from native Hamamatsu HIS headers."""
import math
from pathlib import Path
import struct


def read_frame_intervals_ms(path, frame_count):
    """Read the 64-byte ITEX sequence headers and return successive timestamps."""
    if frame_count < 2:
        raise ValueError("At least two HIS frames are required to verify cadence")
    path = Path(path)
    size = path.stat().st_size
    timestamps = []
    with path.open("rb") as stream:
        offset = 0
        for _ in range(frame_count):
            stream.seek(offset)
            header = stream.read(64)
            if len(header) != 64 or header[:2] != b"IM":
                raise ValueError("Invalid HIS frame header")
            comments, width, height = struct.unpack_from("<HHH", header, 2)
            pixel_type = struct.unpack_from("<H", header, 12)[0]
            pixel_bytes = {1: 1, 2: 2, 3: 4}.get(pixel_type)
            if not width or not height or not pixel_bytes:
                raise ValueError("Unsupported HIS frame layout")
            timestamps.append(struct.unpack_from("<d", header, 22)[0])
            offset += 64 + comments + width * height * pixel_bytes
            if offset > size:
                raise ValueError("Truncated HIS frame data")
    intervals = [end - start for start, end in zip(timestamps, timestamps[1:])]
    if any(not math.isfinite(interval) or interval <= 0 for interval in intervals):
        raise ValueError("HIS frame timestamps do not increase")
    return intervals


def verify_frame_rate(path, frame_count, rate_hz):
    intervals = read_frame_intervals_ms(path, frame_count)
    expected = 1000.0 / rate_hz
    if any(abs(period - expected) > 5 for period in intervals):
        raise ValueError(
            f"Expected {expected:g} ms between frames; recorded {min(intervals):.3f} to {max(intervals):.3f} ms"
        )
