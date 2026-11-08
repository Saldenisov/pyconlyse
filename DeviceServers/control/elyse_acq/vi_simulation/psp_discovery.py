"""Inert discovery-loop trace: supplied references/types/errors, no PSP calls."""

from dataclasses import dataclass

from .boundary import ErrorCluster

NAMED_OPEN_TYPES = (
    ("C1NI6071E", 19),
    ("C2NI6071E", 20),
    ("C3_IN_DIO96", 18),
    ("C3_OUT_DIO96", 17),
    ("C4_IN_DIO96", 16),
    ("C4_OUT_DIO96", 15),
    ("C5_IN_DIO96", 14),
    ("C5_OUT_DIO96", 13),
    ("C6NI6703", 9),
    ("C7NI6703", 10),
    ("C8NI6703", 11),
    ("C9NI6703", 12),
    ("C1011NI6602", 39),
    ("C12NI1409", 8),
    ("DPC", 37),
    ("DPS", 36),
    ("EPC", 38),
    ("EPS", 44),
    ("VAD", 3),
    ("VAM-A", 41),
    ("VDM-A", 7),
    ("VTA", 2),
    ("VTL", 0),
    ("VTS", 1),
)


@dataclass(frozen=True)
class NamedOpenStep:
    name: str
    type_anchor_read_bank: int
    error_in: ErrorCluster
    supplied_error_out: ErrorCluster


@dataclass(frozen=True)
class NamedOpenProjection:
    steps: tuple[NamedOpenStep, ...]
    handler_error_in: ErrorCluster | None


def project_named_open_arm(*, enabled, error_in, returned_errors):
    """Trace the saved sibling only when explicitly selected by a fixture.

    This is not a decoder of commentNode activation. All 24 locals are reads
    feeding type anchors, never write destinations. Returned reference/access
    outputs and handler outputs are unused in the checked graph. No actual
    open, publication, variable update or hardware operation is performed.
    """
    if type(enabled) is not bool or type(error_in) is not ErrorCluster:
        raise TypeError("explicit branch selection and incoming error required")
    if type(returned_errors) is not tuple or any(
        type(e) is not ErrorCluster for e in returned_errors
    ):
        raise TypeError("explicit immutable open-error fixtures required")
    if not enabled:
        if returned_errors:
            raise ValueError("empty arm cannot consume named-open fixtures")
        return NamedOpenProjection((), None)
    if len(returned_errors) != len(NAMED_OPEN_TYPES):
        raise ValueError("24 named-open returned errors required")
    steps = []
    prior = error_in
    for (name, bank), returned in zip(NAMED_OPEN_TYPES, returned_errors):
        steps.append(NamedOpenStep(name, bank, prior, returned))
        prior = returned
    return NamedOpenProjection(tuple(steps), prior)


@dataclass(frozen=True)
class VariableToken:
    """Opaque variable-reference fixture, not an NI or network handle."""

    token: str

    def __post_init__(self):
        if type(self.token) is not str or not self.token:
            raise TypeError("variable token requires a nonempty string")


@dataclass(frozen=True)
class DiscoveryChild:
    enumerated_reference: VariableToken
    property_reference: VariableToken
    data_type_token: str
    property_error: ErrorCluster
    opened_reference: VariableToken
    open_error: ErrorCluster

    def __post_init__(self):
        if any(
            type(t) is not VariableToken
            for t in (
                self.enumerated_reference,
                self.property_reference,
                self.opened_reference,
            )
        ):
            raise TypeError(
                "discovery references require opaque VariableToken fixtures"
            )
        if type(self.data_type_token) is not str or not self.data_type_token:
            raise TypeError("explicit data-type token required, not inferred variant")
        if (
            type(self.property_error) is not ErrorCluster
            or type(self.open_error) is not ErrorCluster
        ):
            raise TypeError("explicit property/open returned errors required")


@dataclass(frozen=True)
class DiscoveryStep:
    iteration: int
    property_reference_in: VariableToken
    property_error_in: ErrorCluster
    open_reference_in: VariableToken
    open_error_in: ErrorCluster
    data_type_token: str
    wait_request_ms: int


@dataclass(frozen=True)
class DiscoveryProjection:
    steps: tuple[DiscoveryStep, ...]
    local_61: tuple[VariableToken, ...]
    unused_final_error: ErrorCluster


def project_discovery_frame(*, enumeration_error, children):
    """Record dependency order only; wait/open within a body stay unordered.

    Returned child cardinality drives the auto-indexed For. No name/type
    whitelist, successful-open filter, retry, handler or stop guard is added.
    Data types are opaque supplied tokens; no NI variant conversion occurs.
    Final error has no exterior consumer in this saved parent frame.
    """
    if type(enumeration_error) is not ErrorCluster:
        raise TypeError("explicit enumerator returned error required")
    if type(children) is not tuple or any(
        type(c) is not DiscoveryChild for c in children
    ):
        raise TypeError("immutable ordered child fixtures required")
    steps = []
    refs = []
    error = enumeration_error
    for i, child in enumerate(children):
        steps.append(
            DiscoveryStep(
                i,
                child.enumerated_reference,
                error,
                child.property_reference,
                child.property_error,
                child.data_type_token,
                1,
            )
        )
        refs.append(child.opened_reference)
        error = child.open_error
    return DiscoveryProjection(tuple(steps), tuple(refs), error)
