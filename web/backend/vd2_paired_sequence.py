"""Native paired Sequence capture. Lamp timing ends before HIS save or analysis."""
from pathlib import Path
import struct
import time

import numpy as np


def sequence_header(path):
    with Path(path).open("rb") as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b"IM":
            raise ValueError("Invalid paired HIS header")
        count = struct.unpack_from("<H", header, 14)[0]
        comments = struct.unpack_from("<H", header, 2)[0]
        description = stream.read(comments).decode("utf-8", errors="replace")
    return count, description


def frames(path, count, shape):
    with Path(path).open("rb") as stream:
        for sequence in range(count):
            header = stream.read(64)
            if len(header) != 64 or header[:2] != b"IM":
                raise ValueError("Invalid paired HIS frame")
            comments, width, height = struct.unpack_from("<HHH", header, 2)
            kind = struct.unpack_from("<H", header, 12)[0]
            size = {1: 1, 2: 2, 3: 4}.get(kind)
            if (width, height) != shape or size is None:
                raise ValueError("Paired HIS geometry differs from Bruit")
            stream.seek(comments, 1)
            pixels = stream.read(width * height * size)
            if len(pixels) != width * height * size:
                raise ValueError("Truncated paired HIS frame")
            image = np.frombuffer(pixels, dtype=f"<u{size}").reshape(height, width).T
            yield image, sequence, struct.unpack_from("<d", header, 22)[0]


def _sequence_status(api, camera):
    status = api._remoteex_readback(camera, "AsyncCommandStatus()").split(",")[:3]
    if len(status) != 3 or any(flag not in {"0", "1"} for flag in status):
        raise RuntimeError(f"Unverified HPD-TA sequence status: {status}")
    return status == ["0", "0", "0"]


def native_capture(api, camera, clock, source, stop, count, path, update):
    previous = api._remoteex_readback(camera, "SeqParamGet(NoOfLoops)")
    if not previous.isdigit():
        raise RuntimeError("Cannot read the current HPD-TA sequence length")
    attempted = complete = False

    def arm():
        nonlocal attempted
        attempted = True
        camera.command_inout("StartSequence")

    try:
        camera.write_attribute("sequence_loops", str(count))
        if api._remoteex_readback(camera, "SeqParamGet(NoOfLoops)") != str(count):
            raise RuntimeError(f"HPD-TA did not confirm {count} frames")
        with clock(api, camera, source, stop, arm) as running:
            if running:
                update(status="acquiring", stage=f"Recording {count} frames at 10 Hz")
                # Avoid competing for the RemoteEx command channel during startup.
                nominal = count / 10
                deadline = time.monotonic() + nominal + 18
                stop.wait(nominal)
                last_error = None
                while not stop.is_set() and time.monotonic() < deadline:
                    try:
                        complete = _sequence_status(api, camera)
                    except Exception as exc:
                        if not any(word in str(exc).lower() for word in ("timed out", "timeout", "transport", "serializ")):
                            raise
                        last_error = exc
                    if complete:
                        break
                    stop.wait(.5)
                if not complete and not stop.is_set():
                    raise RuntimeError(f"HPD-TA sequence completion unverified: {last_error or 'still active'}")
        if complete:
            update(status="saving", stage="Saving native HIS")
            camera.set_timeout_millis(120_000)
            camera.command_inout("SaveCurrentSequence", str(path))
        return complete
    finally:
        if attempted and not complete:
            camera.command_inout("StopSequence")
        if _sequence_status(api, camera):
            camera.write_attribute("sequence_loops", previous)
