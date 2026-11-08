"""Pressure read wiring projection, never an instrument or numeric parser.

TPG300-Get Pressure-Status.vi SHA256:
00EAA9357276529C2B70FF44B2AC0C64CCA88D77FD3FF2C15844AA1CC51520B8.
Numeric conversion returns are explicit fixtures: actual LabVIEW locale,
malformed input, overflow and nonfinite conversion behavior is not emulated.
"""

from dataclasses import dataclass

from .boundary import ErrorCluster


@dataclass(frozen=True)
class SeparatorStep:
    text: str
    offset: int
    keep_running: bool


def separator_step(text: str, offset: int) -> SeparatorStep:
    """One saved replacement-loop iteration; offset remains a byte offset."""
    if type(text) is not str or not text.isascii():
        raise ValueError("ASCII response fixture required")
    if type(offset) is not int or offset < 0:
        raise ValueError("nonnegative offset fixture required")
    match = text.find(".", offset)
    if match < 0:
        return SeparatorStep(text, -1, False)
    return SeparatorStep(text[:match] + "," + text[match + 1 :], match + 1, True)


def pressure_command(sensor: int) -> str:
    """Only four evidenced sensor selections; returns text, never sends it."""
    if type(sensor) is not int or not 0 <= sensor <= 3:
        raise ValueError("sensor fixture outside evidenced 0..3 domain")
    return "P" + ("A1", "A2", "B1", "B2")[sensor]


@dataclass(frozen=True)
class ParseInputs:
    normalized_response: str
    status_string: str
    pressure_string: str
    use_system_decimal_point: bool = True


def pressure_parse_inputs(response: str) -> ParseInputs:
    state = separator_step(response, 0)
    while state.keep_running:
        state = separator_step(state.text, state.offset)
    before, separator, after = state.text.partition(",")
    return ParseInputs(state.text, before, after if separator else "")


@dataclass(frozen=True)
class PressureReturn:
    status: int
    pressure: float
    error: ErrorCluster

    def __post_init__(self):
        if type(self.status) is not int or not -(2**31) <= self.status < 2**31:
            raise ValueError("supplied I32 conversion return required")
        if type(self.pressure) is not float or type(self.error) is not ErrorCluster:
            raise TypeError(
                "supplied DBL conversion and error-cluster returns required"
            )


@dataclass(frozen=True)
class PressureAssignment:
    bank: int
    pressure: float
    error_handler_input: ErrorCluster


# Frame order does not impose an order between independent calls within 48320.
ROOT_READS = (
    ("48320", "46178", 52, 0, 53),
    ("48320", "53865", 51, 0, 54),
    ("52460", "52475", 51, 3, 60),
)
REQUESTED_FRAME_WAIT_MS = (500, 500)


def root_pressure_assignment(
    node_uid: str, returned: PressureReturn
) -> PressureAssignment:
    """Status is unwired; error feeds handler independently of pressure write."""
    if type(returned) is not PressureReturn:
        raise TypeError("explicit pressure-return snapshot required")
    for _, uid, _, _, bank in ROOT_READS:
        if uid == node_uid:
            return PressureAssignment(bank, returned.pressure, returned.error)
    raise ValueError("unknown saved root pressure call")


def pressure_publication_fault(error: ErrorCluster) -> tuple[tuple[int, bool], ...]:
    """Assignments only, no PSP operation or implicit success reset."""
    if type(error) is not ErrorCluster:
        raise TypeError("explicit publication error snapshot required")
    return ((30, True), (45, True)) if error.status else ()
