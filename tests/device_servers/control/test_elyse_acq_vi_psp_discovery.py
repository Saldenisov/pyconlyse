"""Discovery array/error dependencies are explicit, without a live client."""

import pytest
from DeviceServers.control.elyse_acq.vi_simulation.boundary import ErrorCluster
from DeviceServers.control.elyse_acq.vi_simulation.psp_discovery import (
    NAMED_OPEN_TYPES,
    DiscoveryChild,
    VariableToken,
    project_discovery_frame,
    project_named_open_arm,
)


def child(i):
    return DiscoveryChild(
        VariableToken(f"enum:{i}"),
        VariableToken(f"property:{i}"),
        f"opaque-type:{i}",
        ErrorCluster(True, -1 - i),
        VariableToken(f"opened:{i}"),
        ErrorCluster(True, -10 - i),
    )


@pytest.mark.parametrize("count", [0, 1, 2, 27, 31])
def test_auto_index_cardinality_not_expected_names_and_error_does_not_abort(count):
    enum_error = ErrorCluster(True, -99)
    children = tuple(child(i) for i in range(count))
    actual = project_discovery_frame(enumeration_error=enum_error, children=children)
    assert len(actual.steps) == count
    assert actual.local_61 == tuple(c.opened_reference for c in children)
    assert actual.unused_final_error is (
        children[-1].open_error if count else enum_error
    )
    for i, step in enumerate(actual.steps):
        assert step.iteration == i
        assert step.wait_request_ms == 1
        assert step.property_error_in is (
            children[i - 1].open_error if i else enum_error
        )
        assert step.open_error_in is children[i].property_error
        assert step.property_reference_in == children[i].enumerated_reference
        assert step.open_reference_in == children[i].property_reference
        assert step.data_type_token == children[i].data_type_token


def test_only_explicit_in_memory_values_accepted():
    with pytest.raises(TypeError):
        project_discovery_frame(enumeration_error=None, children=())
    with pytest.raises(TypeError):
        project_discovery_frame(enumeration_error=ErrorCluster(False, 0), children=[])
    with pytest.raises(TypeError):
        project_discovery_frame(
            enumeration_error=ErrorCluster(False, 0), children=(object(),)
        )
    with pytest.raises(TypeError):
        VariableToken("")
    with pytest.raises(TypeError):
        DiscoveryChild(
            object(),
            VariableToken("p"),
            "t",
            ErrorCluster(False, 0),
            VariableToken("o"),
            ErrorCluster(False, 0),
        )


def test_named_open_sibling_keeps_read_anchors_and_error_chain_without_publications():
    errors = tuple(ErrorCluster(True, i, f"open:{i}") for i in range(24))
    initial = ErrorCluster(True, -999)
    result = project_named_open_arm(
        enabled=True, error_in=initial, returned_errors=errors
    )
    assert (
        tuple((s.name, s.type_anchor_read_bank) for s in result.steps)
        == NAMED_OPEN_TYPES
    )
    for i, step in enumerate(result.steps):
        assert step.error_in is (errors[i - 1] if i else initial)
        assert step.supplied_error_out is errors[i]
    assert result.handler_error_in is errors[-1]
    empty = project_named_open_arm(enabled=False, error_in=initial, returned_errors=())
    assert empty.steps == () and empty.handler_error_in is None


def test_named_open_activation_and_returns_cannot_be_inferred():
    initial = ErrorCluster(False, 0)
    with pytest.raises(TypeError):
        project_named_open_arm(enabled=None, error_in=initial, returned_errors=())
    with pytest.raises(ValueError):
        project_named_open_arm(enabled=True, error_in=initial, returned_errors=())
    with pytest.raises(ValueError):
        project_named_open_arm(
            enabled=False, error_in=initial, returned_errors=(initial,)
        )
