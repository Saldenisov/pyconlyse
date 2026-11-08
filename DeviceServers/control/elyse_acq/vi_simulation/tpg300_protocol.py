"""Pure byte-loop projections, not a serial transport or complete driver.

Source: copied TPG300-Driver Core.vi SHA256
7A0ECCF170459E5B56F49E38AA613246B17D09E9E118ABC73BE2C0B019488F2B.
All VISA returns and elapsed-time values are supplied snapshots. No clock,
sleep, socket, VISA import, device discovery or write occurs here.
Match Pattern projection is restricted to saved one-byte ACK/NAK/CR tokens.
"""

from dataclasses import dataclass

from .boundary import ErrorCluster

ACK = b"\x06"
NAK = b"\x15"
ENQ = b"\x05"
CR = b"\r"


@dataclass(frozen=True)
class ByteLoopState:
    buffer: bytes = b""
    offset: int = -1

    def __post_init__(self):
        if type(self.buffer) is not bytes:
            raise TypeError("explicit byte buffer required")
        if type(self.offset) is not int or not -1 <= self.offset < 2**31:
            raise ValueError("supported I32 offset snapshot required")


@dataclass(frozen=True)
class ByteLoopResult:
    state: ByteLoopState
    keep_running: bool
    flag_a: bool
    flag_b: bool
    requested_wait_ms: int
    returned_error: ErrorCluster


@dataclass(frozen=True)
class PhaseOneBypassResult:
    """Wrapper outputs only; no loop state or offset exists in this arm."""

    buffer: bytes
    flag_a: bool
    flag_b: bool
    returned_error: ErrorCluster


def framed_command(command: bytes, *, write_read: bool) -> bytes:
    """False selects the first three bytes; True selects the full command."""
    if type(command) is not bytes or type(write_read) is not bool:
        raise TypeError("explicit bytes and Boolean selector required")
    return (command if write_read else command[:3]) + CR


def response_phase_enabled(*, flag_a: bool, flag_b: bool) -> bool:
    """Core 1580/1592: NOT (phase-one flag A OR flag B), not error.status."""
    if type(flag_a) is not bool or type(flag_b) is not bool:
        raise TypeError("explicit phase-one Boolean flags required")
    return not (flag_a or flag_b)


def phase_one_error_bypass(error: ErrorCluster) -> PhaseOneBypassResult:
    """Case 829, only after the Bytes-at-Port property returns status=True."""
    if type(error) is not ErrorCluster or not error.status:
        raise ValueError("error-case snapshot required")
    return PhaseOneBypassResult(b"", True, False, error)


def _match(data, token):
    index = data.find(token)
    if index < 0:
        # NI Match Pattern: entire before string, empty after, offset=-1.
        return data, b"", -1
    return data[:index], data[index + 1 :], index + 1


def byte_loop_step(
    *,
    phase: str,
    state: ByteLoopState,
    bytes_available: int,
    read_bytes: bytes | None,
    elapsed_ms: int,
    timeout_ms: int,
    returned_error: ErrorCluster,
) -> ByteLoopResult:
    """Project one iteration from supplied property/read/clock outcomes.

    elapsed_ms is the already calculated U32 tick-difference snapshot.
    Python validates representations, not VISA reliability or graph reachability.
    read_bytes is None for the no-data branch; its length need not equal the
    requested byte count, since the external read may return fewer bytes.
    Caller supplies the error returned by the selected property/read branch.
    That error is published but is not an input of this loop's continue gate.
    """
    if phase not in ("ack", "response"):
        raise ValueError("ack or response phase required")
    if type(state) is not ByteLoopState or type(returned_error) is not ErrorCluster:
        raise TypeError("explicit state and error snapshots required")
    if any(
        type(value) is not int or not 0 <= value < 2**32
        for value in (bytes_available, elapsed_ms, timeout_ms)
    ):
        raise ValueError("U32 property/elapsed/timeout snapshots required")
    within_timeout = elapsed_ms < timeout_ms
    if bytes_available == 0:
        if read_bytes is not None:
            raise ValueError("no read return in the no-data case")
        candidate = state.buffer
        offset = state.offset
        gate = within_timeout
        recognition = offset >= 0
        wait = 50 if within_timeout else 0
    else:
        if type(read_bytes) is not bytes:
            raise TypeError("explicit VISA read byte snapshot required")
        wait = 0
        if phase == "ack" and state.offset < 0:
            _, after_ack, offset = _match(read_bytes, ACK)
            candidate = state.buffer + after_ack
            gate = recognition = _match(read_bytes, NAK)[2] < 0
        else:
            # ACK's recognized branch and both response subcases.
            candidate = state.buffer + read_bytes
            offset = 1
            gate = recognition = True
    before_cr, _, cr_offset = _match(candidate, CR)
    return ByteLoopResult(
        ByteLoopState(before_cr, offset),
        cr_offset < 0 and gate,
        not gate,
        not recognition,
        wait,
        returned_error,
    )
