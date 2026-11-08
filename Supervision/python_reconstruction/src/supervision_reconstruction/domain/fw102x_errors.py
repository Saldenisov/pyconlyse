"""Pure, fail-closed evidence models for FW102x IVI error helper VIs.

The exported diagrams prove error-buffer allocation and outer conversion gate,
but the driver functions (``error_message``, ``GetErrorInfo``) and IVI Error
Message Builder output contract remain unexecuted/unproven.  No driver, IVI
session, refnum, DLL, path, or hardware operation is exposed here.
"""

from __future__ import annotations

from dataclasses import dataclass


I32_MIN = -(2**31)
I32_MAX = 2**31 - 1
U32_MAX = 2**32 - 1


@dataclass(frozen=True)
class ErrorCluster:
    """Value-only representation of LabVIEW's status/code/source cluster."""

    status: bool
    code: int
    source: str


@dataclass(frozen=True)
class Fw102xEvidenceBlock:
    vi_names: tuple[str, ...]
    implementation_allowed: bool
    unresolved_contracts: tuple[str, ...]


FW102X_ERROR_MESSAGE_BLOCKED = Fw102xEvidenceBlock(
    vi_names=("FW102x Error Message.vi",),
    implementation_allowed=False,
    unresolved_contracts=(
        "extFunc binding/library path and calling convention",
        "driver error-message text and return-code semantics",
        "runtime Current VI's Path and LabVIEW Strip Path platform semantics",
        "U32-to-I32 Initialize Array dimension coercion above I32_MAX",
    ),
)

FW102X_IVI_CONVERSION_BLOCKED = Fw102xEvidenceBlock(
    vi_names=("FW102x IVI Error Converter.vi",),
    implementation_allowed=False,
    unresolved_contracts=(
        "IVI error_message and GetErrorInfo return contracts",
        "meaning of IVI status constant 0x3FFF0085",
        "IVI Error Message Builder text/source formatting contract",
    ),
)


@dataclass(frozen=True)
class Fw102xErrorMessageCallPlan:
    """Observed zero-buffer/external-call preparation; no call is made."""

    instrument_handle_identity: object
    error_code: int
    requested_buffer_size_u32: int
    zero_initialized_buffer_size: int
    incoming_error: ErrorCluster
    blocked: Fw102xEvidenceBlock


@dataclass(frozen=True)
class Fw102xIviConversionPlan:
    """Outer case decision of FW102x IVI Error Converter.vi."""

    instrument_handle: int
    ivi_error_code: int
    name_of_vi: str
    conversion_attempted: bool
    error_out: ErrorCluster | None
    external_buffer_sizes: tuple[int, ...]
    blocked: Fw102xEvidenceBlock | None


def _require_i32(value: int, *, name: str) -> None:
    if type(value) is not int or not I32_MIN <= value <= I32_MAX:
        raise TypeError(f"{name} must be a signed I32 int")


def _require_u32(value: int, *, name: str) -> None:
    if type(value) is not int or not 0 <= value <= U32_MAX:
        raise TypeError(f"{name} must be an unsigned U32 int")


def _require_error_cluster(value: ErrorCluster, *, name: str) -> None:
    if not isinstance(value, ErrorCluster):
        raise TypeError(f"{name} must be ErrorCluster")
    if type(value.status) is not bool:
        raise TypeError(f"{name}.status must be bool")
    _require_i32(value.code, name=f"{name}.code")
    if not isinstance(value.source, str):
        raise TypeError(f"{name}.source must be str")


def plan_fw102x_error_message(
    instrument_handle_identity: object,
    error_code: int,
    size_of_error_message: int,
    error_in: ErrorCluster,
) -> Fw102xErrorMessageCallPlan:
    """Capture FW102x Error Message.vi's proved external-call preparation.

    The VI initializes ``size_of_error_message`` U8 zeros, converts them to a
    string, and wires that string with handle/code to an unresolved extFunc.
    Allocation is represented by length only, avoiding a hostile U32 request.
    """

    _require_i32(error_code, name="error_code")
    _require_u32(size_of_error_message, name="size_of_error_message")
    _require_error_cluster(error_in, name="error_in")
    if size_of_error_message > I32_MAX:
        raise OverflowError(
            "size_of_error_message U32-to-I32 array-dimension coercion is unproven above I32_MAX"
        )
    return Fw102xErrorMessageCallPlan(
        instrument_handle_identity=instrument_handle_identity,
        error_code=error_code,
        requested_buffer_size_u32=size_of_error_message,
        zero_initialized_buffer_size=size_of_error_message,
        incoming_error=error_in,
        blocked=FW102X_ERROR_MESSAGE_BLOCKED,
    )


def plan_fw102x_ivi_error_conversion(
    instrument_handle: int,
    ivi_error_code: int,
    name_of_vi: str,
    error_in: ErrorCluster,
) -> Fw102xIviConversionPlan:
    """Model outer case gate while failing closed before IVI driver calls.

    The case selector is ``not error_in.status AND ivi_error_code != 0``.
    Its False frame passes ``error in`` unchanged.  Its True frame prepares
    four visibly wired 256-byte zero buffers and invokes unresolved IVI calls;
    output error text/code/source is therefore deliberately unavailable.
    """

    _require_i32(instrument_handle, name="instrument_handle")
    _require_i32(ivi_error_code, name="ivi_error_code")
    if not isinstance(name_of_vi, str):
        raise TypeError("name_of_vi must be str")
    _require_error_cluster(error_in, name="error_in")

    conversion_attempted = not error_in.status and ivi_error_code != 0
    if not conversion_attempted:
        return Fw102xIviConversionPlan(
            instrument_handle=instrument_handle,
            ivi_error_code=ivi_error_code,
            name_of_vi=name_of_vi,
            conversion_attempted=False,
            error_out=error_in,
            external_buffer_sizes=(),
            blocked=None,
        )

    return Fw102xIviConversionPlan(
        instrument_handle=instrument_handle,
        ivi_error_code=ivi_error_code,
        name_of_vi=name_of_vi,
        conversion_attempted=True,
        error_out=None,
        external_buffer_sizes=(256, 256, 256, 256),
        blocked=FW102X_IVI_CONVERSION_BLOCKED,
    )
