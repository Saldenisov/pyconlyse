"""One saved TPG initializer state transition from explicit local snapshots.

No serial protocol or scheduling emulation. Only root-used selectors 0..4
and saved Max Value=4 are supported. Driver/serial returns are fixtures.
The root's Def.Value local write is not assumed ordered before the loop.
"""

from dataclasses import dataclass
from enum import IntEnum

from .boundary import ErrorCluster


class TpgStartupState(IntEnum):
    INIT_TEST = 0
    NEXT_BAUD = 1
    SET_DEFAULT = 2
    COMMUNICATION_OK = 3
    ERROR_BOX = 4


@dataclass(frozen=True)
class TpgStartupTransition:
    next_state: TpgStartupState
    keep_running: bool
    current_selector: int
    returned_error: ErrorCluster | None
    requested_operations: tuple[tuple[str, object], ...]


def transition(
    state: TpgStartupState,
    *,
    requested_selector: int,
    current_selector: int,
    default_selector_snapshot: int,
    max_selector_snapshot: int,
    serial_return: ErrorCluster | None = None,
    command_return: ErrorCluster | None = None,
) -> TpgStartupTransition:
    """Select slots are output/f/selector/t, not output/t/selector/f.

    `returned_error` is the case output of this iteration, not the next
    iteration's error input: that input is an ordinary tunnel. None means
    an unmodeled forwarded input, not a fabricated successful return.
    """
    if type(state) is not TpgStartupState:
        raise TypeError("saved enum state required")
    if (
        any(
            type(v) is not int or not 0 <= v <= 4
            for v in (requested_selector, current_selector, default_selector_snapshot)
        )
        or type(max_selector_snapshot) is not int
        or max_selector_snapshot != 4
    ):
        raise ValueError(
            "projection limited to root-used five-rate search and Max Value=4"
        )
    operations = ()
    error = None
    current = current_selector
    keep_running = True
    if state in (TpgStartupState.INIT_TEST, TpgStartupState.COMMUNICATION_OK):
        if type(serial_return) is not ErrorCluster:
            raise TypeError("explicit serial return required")
        selector = current if state == TpgStartupState.INIT_TEST else requested_selector
        operations = (("SerialInit", selector),)
        if state == TpgStartupState.INIT_TEST and serial_return.status:
            next_state = TpgStartupState.ERROR_BOX
            error = serial_return
        else:
            if type(command_return) is not ErrorCluster:
                raise TypeError("explicit PNR return required")
            operations += (("PNR timeout_ms", 700),)
            error = command_return
            if state == TpgStartupState.COMMUNICATION_OK:
                current = requested_selector
                next_state = state
                keep_running = False
            elif command_return.status:
                next_state = TpgStartupState.NEXT_BAUD
            else:
                next_state = (
                    TpgStartupState.COMMUNICATION_OK
                    if current == requested_selector
                    else TpgStartupState.SET_DEFAULT
                )
    elif state == TpgStartupState.NEXT_BAUD:
        current = (current + 1) % (max_selector_snapshot + 1)
        next_state = (
            TpgStartupState.ERROR_BOX
            if current == default_selector_snapshot
            else TpgStartupState.INIT_TEST
        )
    elif state == TpgStartupState.SET_DEFAULT:
        if type(command_return) is not ErrorCluster:
            raise TypeError("explicit BAU return required")
        operations = (
            (
                "BAU command",
                "BAU," + ("3", "1", "2", "4", "9")[default_selector_snapshot],
            ),
        )
        error = command_return
        next_state = TpgStartupState.COMMUNICATION_OK
    else:
        error = ErrorCluster(True, 0, "Init Error")
        next_state = state
        keep_running = False
    return TpgStartupTransition(next_state, keep_running, current, error, operations)
