"""Fail-closed call plans for the four exported FW102x operational VIs.

This module models only the visible LabVIEW dataflow.  ``extFunc``, IVI
refnums, IVI session primitives, the FW102x DLL binding, and the IVI error
converter remain external contracts.  Consequently, these functions produce
immutable plans and never invoke a driver, DLL, refnum, filesystem, network,
or instrument.

The evidence is the LabVIEW Print export plus both lvkit descriptions for
``FW102x Close.vi``, ``FW102x Initialize.vi``, ``FW102x Get Position.vi``,
and ``FW102x Set Position.vi``.  The exported diagrams establish terminal
wiring and error-status case gates, but not the external function names,
calling convention, return values, or runtime refnum semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from .fw102x_errors import ErrorCluster


I32_MIN = -(2**31)
I32_MAX = 2**31 - 1


@dataclass(frozen=True)
class Fw102xOperationsEvidenceBlock:
    """Unresolved boundary shared by all operation plans."""

    vi_names: tuple[str, ...]
    implementation_allowed: bool
    unresolved_contracts: tuple[str, ...]


FW102X_OPERATIONS_BLOCKED = Fw102xOperationsEvidenceBlock(
    vi_names=(
        "FW102x Close.vi",
        "FW102x Initialize.vi",
        "FW102x Get Position.vi",
        "FW102x Set Position.vi",
    ),
    implementation_allowed=False,
    unresolved_contracts=(
        "extFunc binding/library path, exported symbol, and calling convention",
        "FW102x driver return-code and output-value contracts",
        "IVI New Session and IVI Delete Session refnum lifetime semantics",
        "FW102x IVI Error Converter output contract when driver status is nonzero",
        "runtime Current VI's Path and Strip Path semantics",
        "Get Position error-frame position output/default-tunnel semantics",
    ),
)


@dataclass(frozen=True)
class WiredTerminal:
    """One explicitly wired primitive terminal, recorded without coercion."""

    index: int | str
    nominal_type: str
    value: object


@dataclass(frozen=True)
class ExternalResultReference:
    """A value produced by an unexecuted primitive terminal."""

    call_id: str
    terminal_index: int
    nominal_type: str


@dataclass(frozen=True)
class UnresolvedRuntimeValue:
    """A wired runtime primitive result that copied artifacts cannot resolve."""

    expression: str
    nominal_type: str
    copied_vi_name: str


@dataclass(frozen=True)
class OperationCallPlan:
    """A non-executable primitive/IVI invocation with its visible terminals."""

    call_id: str
    primitive_name: str
    source_vi_name: str
    inputs: tuple[WiredTerminal, ...]
    outputs: tuple[ExternalResultReference, ...]
    execution_allowed: bool = False


@dataclass(frozen=True)
class Fw102xClosePlan:
    """Dataflow plan and bounded output knowledge for ``FW102x Close.vi``."""

    instrument_handle_identity: object
    error_in: ErrorCluster
    error_out: ErrorCluster | None
    calls: tuple[OperationCallPlan, ...]
    evaluation_layers: tuple[tuple[str, ...], ...]
    blocked: Fw102xOperationsEvidenceBlock


@dataclass(frozen=True)
class Fw102xGetPositionPlan:
    """Dataflow plan for ``FW102x Get Position.vi``."""

    vi_out_identity: object
    error_out: ErrorCluster | None
    position_output_source: ExternalResultReference | None
    calls: tuple[OperationCallPlan, ...]
    evaluation_layers: tuple[tuple[str, ...], ...]
    blocked: Fw102xOperationsEvidenceBlock | None


@dataclass(frozen=True)
class Fw102xInitializePlan:
    """Dataflow plan for ``FW102x Initialize.vi``."""

    id_query_u16: int
    reset_device_u16: int
    id_query_u32: int
    error_out: ErrorCluster | None
    instrument_handle_out_source: ExternalResultReference | None
    calls: tuple[OperationCallPlan, ...]
    evaluation_layers: tuple[tuple[str, ...], ...]
    blocked: Fw102xOperationsEvidenceBlock | None


@dataclass(frozen=True)
class Fw102xSetPositionPlan:
    """Dataflow plan for ``FW102x Set Position.vi``."""

    vi_out_identity: object
    error_out: ErrorCluster | None
    calls: tuple[OperationCallPlan, ...]
    evaluation_layers: tuple[tuple[str, ...], ...]
    blocked: Fw102xOperationsEvidenceBlock | None


def _require_i32(value: int, *, name: str) -> None:
    if type(value) is not int or not I32_MIN <= value <= I32_MAX:
        raise TypeError(f"{name} must be a signed I32 int")


def _require_bool(value: bool, *, name: str) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")


def _require_error_cluster(value: ErrorCluster, *, name: str) -> None:
    if not isinstance(value, ErrorCluster):
        raise TypeError(f"{name} must be ErrorCluster")
    _require_bool(value.status, name=f"{name}.status")
    _require_i32(value.code, name=f"{name}.code")
    if not isinstance(value.source, str):
        raise TypeError(f"{name}.source must be str")


def _result(call_id: str, terminal_index: int, nominal_type: str) -> ExternalResultReference:
    return ExternalResultReference(call_id, terminal_index, nominal_type)


def _error_out_if_prior_error(error_in: ErrorCluster) -> ErrorCluster | None:
    """Return the case/IVI-converter result only when it is dataflow-proved."""

    return error_in if error_in.status else None


def _error_converter_call(
    *,
    call_id: str,
    source_vi_name: str,
    error_in: ErrorCluster,
    driver_status: ExternalResultReference,
    instrument_handle: object,
) -> OperationCallPlan:
    """Record the converter terminals without claiming its unresolved output."""

    return OperationCallPlan(
        call_id=call_id,
        primitive_name="FW102x IVI Error Converter.vi",
        source_vi_name=source_vi_name,
        inputs=(
            WiredTerminal("error in (no error)", "Error", error_in),
            WiredTerminal(
                "name of VI (\"\")",
                "String",
                UnresolvedRuntimeValue(
                    expression="Current VI's Path -> Strip Path.name",
                    nominal_type="String",
                    copied_vi_name=source_vi_name,
                ),
            ),
            WiredTerminal("IVI error code (0)", "I32", driver_status),
            WiredTerminal("instrument handle", "instrument handle", instrument_handle),
        ),
        outputs=(),
    )


def plan_fw102x_close(
    instrument_handle_identity: object, error_in: ErrorCluster
) -> Fw102xClosePlan:
    """Plan ``FW102x Close.vi`` without closing a session.

    Unlike the other three VIs, the visible diagram has no incoming-error
    case gate.  It therefore schedules both the external close call and
    ``IVI Delete Session`` even when ``error_in.status`` is true.  They have
    no visible dataflow ordering relative to one another; both are recorded
    in the first evaluation layer.  The close extFunc status feeds the error
    converter, which receives a visible constant ``0`` as its handle input.
    """

    _require_error_cluster(error_in, name="error_in")
    vi_name = "FW102x Close.vi"
    close_call_id = "external_close"
    close_status = _result(close_call_id, 5, "I32")
    close = OperationCallPlan(
        call_id=close_call_id,
        primitive_name="extFunc",
        source_vi_name=vi_name,
        inputs=(WiredTerminal(6, "U32", instrument_handle_identity),),
        outputs=(close_status,),
    )
    delete_session = OperationCallPlan(
        call_id="ivi_delete_session",
        primitive_name="IVI Delete Session",
        source_vi_name=vi_name,
        inputs=(WiredTerminal(11, "IVIRef refnum", instrument_handle_identity),),
        outputs=(),
    )
    converter = _error_converter_call(
        call_id="ivi_error_converter",
        source_vi_name=vi_name,
        error_in=error_in,
        driver_status=close_status,
        instrument_handle=0,
    )
    return Fw102xClosePlan(
        instrument_handle_identity=instrument_handle_identity,
        error_in=error_in,
        error_out=_error_out_if_prior_error(error_in),
        calls=(close, delete_session, converter),
        evaluation_layers=((close.call_id, delete_session.call_id), (converter.call_id,)),
        blocked=FW102X_OPERATIONS_BLOCKED,
    )


def plan_fw102x_get_position(
    vi_identity: object, error_in: ErrorCluster
) -> Fw102xGetPositionPlan:
    """Plan ``FW102x Get Position.vi`` without querying the driver.

    The error-status case calls extFunc only in its ``No Error`` frame.  The
    position terminal is passed to extFunc as an I32 output-storage input and
    returned from extFunc terminal 9.  The Print export does not establish a
    value/default for that output in the ``Error`` frame, so this model marks
    it unavailable rather than inventing an I32 value.
    """

    _require_error_cluster(error_in, name="error_in")
    if error_in.status:
        return Fw102xGetPositionPlan(
            vi_out_identity=vi_identity,
            error_out=error_in,
            position_output_source=None,
            calls=(),
            evaluation_layers=(),
            blocked=None,
        )

    vi_name = "FW102x Get Position.vi"
    call_id = "external_get_position"
    driver_status = _result(call_id, 5, "I32")
    driver_handle = _result(call_id, 7, "U32")
    position = _result(call_id, 9, "I32")
    external = OperationCallPlan(
        call_id=call_id,
        primitive_name="extFunc",
        source_vi_name=vi_name,
        inputs=(
            WiredTerminal(6, "U32", vi_identity),
            WiredTerminal(8, "I32 output storage", "position"),
        ),
        outputs=(driver_status, driver_handle, position),
    )
    converter = _error_converter_call(
        call_id="ivi_error_converter",
        source_vi_name=vi_name,
        error_in=error_in,
        driver_status=driver_status,
        instrument_handle=driver_handle,
    )
    return Fw102xGetPositionPlan(
        vi_out_identity=vi_identity,
        error_out=None,
        position_output_source=position,
        calls=(external, converter),
        evaluation_layers=((external.call_id,), (converter.call_id,)),
        blocked=FW102X_OPERATIONS_BLOCKED,
    )


def plan_fw102x_initialize(
    resource_name: str,
    baud_rate: int,
    id_query: bool,
    reset_device: bool,
    error_in: ErrorCluster,
) -> Fw102xInitializePlan:
    """Plan ``FW102x Initialize.vi`` without opening an IVI session.

    Both visible ``Boolean To (0,1)`` nodes feed U16 extFunc terminals.  The
    raw ``id query`` Boolean separately feeds external terminal 14, shown as
    U32 after LabVIEW coercion.  IVI New Session and the error converter both
    depend on extFunc outputs but have no visible dataflow dependency on each
    other, so they occupy the same second evaluation layer.
    """

    if not isinstance(resource_name, str):
        raise TypeError("resource_name must be str")
    _require_i32(baud_rate, name="baud_rate")
    _require_bool(id_query, name="id_query")
    _require_bool(reset_device, name="reset_device")
    _require_error_cluster(error_in, name="error_in")

    id_query_u16 = int(id_query)
    reset_device_u16 = int(reset_device)
    id_query_u32 = int(id_query)
    if error_in.status:
        return Fw102xInitializePlan(
            id_query_u16=id_query_u16,
            reset_device_u16=reset_device_u16,
            id_query_u32=id_query_u32,
            error_out=error_in,
            instrument_handle_out_source=None,
            calls=(),
            evaluation_layers=(),
            blocked=None,
        )

    vi_name = "FW102x Initialize.vi"
    call_id = "external_initialize"
    driver_status = _result(call_id, 5, "I32")
    driver_resource_name = _result(call_id, 7, "String")
    driver_handle = _result(call_id, 15, "U32")
    external = OperationCallPlan(
        call_id=call_id,
        primitive_name="extFunc",
        source_vi_name=vi_name,
        inputs=(
            WiredTerminal(6, "String", resource_name),
            WiredTerminal(8, "I32", baud_rate),
            WiredTerminal(10, "U16", id_query_u16),
            WiredTerminal(12, "U16", reset_device_u16),
            WiredTerminal(14, "U32", id_query_u32),
        ),
        outputs=(driver_status, driver_resource_name, driver_handle),
    )
    session_call_id = "ivi_new_session"
    session_handle = _result(session_call_id, 3, "IVIRef refnum")
    new_session = OperationCallPlan(
        call_id=session_call_id,
        primitive_name="IVI New Session",
        source_vi_name=vi_name,
        inputs=(
            WiredTerminal(9, "U32", driver_handle),
            WiredTerminal(10, "String", driver_resource_name),
            WiredTerminal(11, "TF", id_query),
        ),
        outputs=(session_handle,),
    )
    converter = _error_converter_call(
        call_id="ivi_error_converter",
        source_vi_name=vi_name,
        error_in=error_in,
        driver_status=driver_status,
        instrument_handle=driver_handle,
    )
    return Fw102xInitializePlan(
        id_query_u16=id_query_u16,
        reset_device_u16=reset_device_u16,
        id_query_u32=id_query_u32,
        error_out=None,
        instrument_handle_out_source=session_handle,
        calls=(external, new_session, converter),
        evaluation_layers=((external.call_id,), (new_session.call_id, converter.call_id)),
        blocked=FW102X_OPERATIONS_BLOCKED,
    )


def plan_fw102x_set_position(
    vi_identity: object, new_position: int, error_in: ErrorCluster
) -> Fw102xSetPositionPlan:
    """Plan ``FW102x Set Position.vi`` without moving the filter wheel."""

    _require_i32(new_position, name="new_position")
    _require_error_cluster(error_in, name="error_in")
    if error_in.status:
        return Fw102xSetPositionPlan(
            vi_out_identity=vi_identity,
            error_out=error_in,
            calls=(),
            evaluation_layers=(),
            blocked=None,
        )

    vi_name = "FW102x Set Position.vi"
    call_id = "external_set_position"
    driver_status = _result(call_id, 5, "I32")
    driver_handle = _result(call_id, 7, "U32")
    external = OperationCallPlan(
        call_id=call_id,
        primitive_name="extFunc",
        source_vi_name=vi_name,
        inputs=(
            WiredTerminal(6, "U32", vi_identity),
            WiredTerminal(8, "I32", new_position),
        ),
        outputs=(driver_status, driver_handle),
    )
    converter = _error_converter_call(
        call_id="ivi_error_converter",
        source_vi_name=vi_name,
        error_in=error_in,
        driver_status=driver_status,
        instrument_handle=driver_handle,
    )
    return Fw102xSetPositionPlan(
        vi_out_identity=vi_identity,
        error_out=None,
        calls=(external, converter),
        evaluation_layers=((external.call_id,), (converter.call_id,)),
        blocked=FW102X_OPERATIONS_BLOCKED,
    )


def execute_fw102x_operation_plan(_: object) -> NoReturn:
    """Deny execution until a separately reviewed adapter is approved."""

    raise PermissionError(
        "FW102x operation plans are evidence models only; driver execution is denied"
    )
