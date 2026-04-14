from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Sequence


CR = "\r"
READY_GREETING = "RemoteEx Ready"
DATA_READY_GREETING = "RemoteEx Data Ready"


class RemoteExError(Exception):
    """Base RemoteEx exception."""


class RemoteExProtocolError(RemoteExError):
    """Raised when a RemoteEx line cannot be parsed."""


class RemoteExTransportError(RemoteExError):
    """Raised when socket transport fails."""


class RemoteExCommandError(RemoteExError):
    """Raised when a RemoteEx command returns a non-zero error code."""

    def __init__(self, message: str, response: "RemoteExResponse"):
        super().__init__(message)
        self.response = response


class RemoteExErrorCode(IntEnum):
    ECNoError = 0
    ECInvalidSyntax = 1
    ECUnknownCommandOrParameters = 2
    ECCommandNotPossible = 3
    ECMessage = 4
    ECMsgBoxReply = 5
    ECMissingParameter = 6
    ECCannotExecute = 7
    ECErrorDuringExecution = 8
    ECCannotSendData = 9
    ECValueOutOfRange = 10


MESSAGE_CODES = {
    RemoteExErrorCode.ECMessage,
    RemoteExErrorCode.ECMsgBoxReply,
}


@dataclass(frozen=True)
class RemoteExResponse:
    raw_line: str
    error_code: int
    command_name: str
    parameters: List[str]

    @property
    def is_ok(self) -> bool:
        return self.error_code == int(RemoteExErrorCode.ECNoError)

    @property
    def is_message(self) -> bool:
        try:
            return RemoteExErrorCode(self.error_code) in MESSAGE_CODES
        except ValueError:
            return False

    def parameter(self, index: int, default: Optional[str] = None) -> Optional[str]:
        if 0 <= index < len(self.parameters):
            return self.parameters[index]
        return default

    def parameter_int(self, index: int, default: Optional[int] = None) -> Optional[int]:
        value = self.parameter(index)
        if value is None:
            return default
        return int(value)

    def parameter_float(
        self, index: int, default: Optional[float] = None
    ) -> Optional[float]:
        value = self.parameter(index)
        if value is None:
            return default
        return float(value)


def base_command_name(command: str) -> str:
    return command.split("(", 1)[0].strip()


def ensure_command_terminated(command: str) -> str:
    return command if command.endswith(CR) else f"{command}{CR}"


def format_bool(value: bool) -> str:
    return "1" if bool(value) else "0"


def build_command(command_name: str, *parameters: object) -> str:
    if not parameters:
        return f"{command_name}()"
    joined = ",".join("" if value is None else str(value) for value in parameters)
    return f"{command_name}({joined})"


def build_app_start_command(
    *,
    visible: bool = True,
    ini_path: str = "",
    no_dialogs: bool = True,
    encoding: str = "ASCII",
) -> str:
    if not ini_path:
        return "AppStart()"
    return build_command(
        "AppStart",
        format_bool(visible),
        ini_path,
        format_bool(no_dialogs),
        encoding,
    )


def parse_response_line(line: str) -> RemoteExResponse:
    cleaned = line.strip("\r\n")
    if not cleaned:
        raise RemoteExProtocolError("Empty RemoteEx line")

    parts = cleaned.split(",")
    if len(parts) < 2:
        raise RemoteExProtocolError(f"Not a RemoteEx response line: {cleaned!r}")

    try:
        error_code = int(parts[0])
    except ValueError as exc:
        raise RemoteExProtocolError(f"Missing numeric error code in {cleaned!r}") from exc

    command_name = parts[1].strip()
    parameters = [part.strip() for part in parts[2:]]
    return RemoteExResponse(
        raw_line=cleaned,
        error_code=error_code,
        command_name=command_name,
        parameters=parameters,
    )


def response_summary(response: RemoteExResponse) -> str:
    if response.parameters:
        return f"{response.error_code},{response.command_name},{','.join(response.parameters)}"
    return f"{response.error_code},{response.command_name}"


def stringify_response_list(responses: Sequence[RemoteExResponse]) -> str:
    return "\n".join(response_summary(response) for response in responses)
