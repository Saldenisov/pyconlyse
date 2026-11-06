"""Bounded status polling leaves Tango available for sequence preview reads."""
import logging
import time

SEQUENCE_WAIT_QUERY = "AsyncCommandStatus()"
SEQUENCE_TIMEOUT_S = 120.0
_logger = logging.getLogger(__name__)


def camera_serialization_timeout(exc: Exception) -> bool:
    message = str(exc).lower()
    return "api_commandtimedout" in message and "acquire serialization monitor" in message


def wait_for_sequence(proxy, *, timeout_s=SEQUENCE_TIMEOUT_S, poll_interval_s=0.75):
    deadline = time.monotonic() + timeout_s
    transport_failures = 0
    serialization_failures = 0
    while time.monotonic() < deadline:
        try:
            raw = str(proxy.command_inout("ExecuteRaw", SEQUENCE_WAIT_QUERY)).strip()
        except Exception as exc:
            if camera_serialization_timeout(exc):
                serialization_failures += 1
            elif "remoteextransporterror" in str(exc).lower():
                transport_failures += 1
                _logger.warning("%s RemoteEx read failed (%d/3): %s", SEQUENCE_WAIT_QUERY,
                                transport_failures, str(exc).splitlines()[0])
                if transport_failures >= 3:
                    raise RuntimeError(f"Sequence completion remains unconfirmed after status retries; acquisition not replayed: {exc}") from exc
            else:
                raise
            time.sleep(min(poll_interval_s, max(0.0, deadline - time.monotonic())))
            continue
        if transport_failures or serialization_failures:
            _logger.info("%s read resumed after %d RemoteEx errors and %d Tango serialization delays",
                         SEQUENCE_WAIT_QUERY, transport_failures, serialization_failures)
        transport_failures = 0
        serialization_failures = 0
        fields = raw.split(",", 5)
        if (len(fields) < 5 or fields[:2] != ["0", "AsyncCommandStatus"]
                or any(flag not in {"0", "1"} for flag in fields[2:5])):
            raise RuntimeError(
                f"Invalid sequence status; acquisition not replayed: {raw}"
            )
        if fields[2:5] == ["0", "0", "0"]:
            return
        time.sleep(poll_interval_s)
    raise TimeoutError(
        f"Sequence did not become idle within {timeout_s:g}s; acquisition not replayed"
    )
