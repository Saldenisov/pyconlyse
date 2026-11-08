"""Mutation tests reject merged startup errors and new hidden consumers."""

import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

import pytest
from validate_acq_modulator_start_event_guards import unique
from validate_acq_runtime_io_frame import checked_trees
from validate_acq_startup_error_lanes import (
    ERROR_LANES,
    validate_error_lanes,
    validate_trees,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def source():
    return checked_trees(
        ROOT / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
    )


def test_original_composition_and_complete_lane_census(source):
    results = validate_trees(*source)
    assert len(results) == 9
    assert "18 ports, 6 exact" in results[0]


@pytest.mark.parametrize("port", [p for row in ERROR_LANES for p in row[3]])
def test_every_used_or_unused_port_rejects_added_downstream_consumer(source, port):
    root, metadata = source
    signals = unique(root, "diag", "21518").find("signalList")
    new = ET.SubElement(
        signals, "SL__arrayElement", **{"class": "signal", "uid": "extra"}
    )
    terms = ET.SubElement(new, "termList")
    ET.SubElement(terms, "SL__arrayElement", uid=port)
    ET.SubElement(terms, "SL__arrayElement", uid="new-readiness-selector")
    try:
        with pytest.raises(AssertionError, match="whole-source wire census"):
            validate_error_lanes(root, metadata)
    finally:
        signals.remove(new)


@pytest.mark.parametrize("uid", [row[0] for row in ERROR_LANES])
@pytest.mark.parametrize("field", ["objFlags", "diagDefined", "typeDesc"])
def test_lane_definition_direction_or_type_mutation(source, uid, field):
    root, metadata = source
    value = unique(root, "sLoc", uid).find(field)
    before = value.text
    value.text = "changed"
    try:
        with pytest.raises(AssertionError, match="definition/type/ports"):
            validate_error_lanes(root, metadata)
    finally:
        value.text = before


def test_original_pilot_wire_cannot_be_replaced_by_cleared_error_lane(source):
    original, metadata = source
    root = deepcopy(original)
    unique(root, "diag", "7580").find("signalList/*/termList/*[@uid='25691']").set(
        "uid", "7590"
    )
    with pytest.raises(AssertionError, match="whole-source wire census"):
        validate_error_lanes(root, metadata)


def test_same_frame_ports_cannot_be_aliased_between_error_lanes(source):
    original, metadata = source
    root = deepcopy(original)
    unique(root, "sLoc", "306").find("termList/*[@uid='1320']").set("uid", "25688")
    with pytest.raises(AssertionError, match="definition/type/ports"):
        validate_error_lanes(root, metadata)


def test_lane_population_and_frame_order_are_closed(source):
    original, metadata = source
    root = deepcopy(original)
    locals_ = unique(root, "sequence", "201").find("seqLocDCOList")
    locals_.append(deepcopy(locals_[0]))
    with pytest.raises(AssertionError, match="population/order"):
        validate_error_lanes(root, metadata)
    root = deepcopy(original)
    frames = unique(root, "sequence", "201").find("diagramList")
    first = frames[0]
    frames.remove(first)
    frames.append(first)
    with pytest.raises(AssertionError, match="ordered frame"):
        validate_error_lanes(root, metadata)


def test_error_cluster_boolean_code_source_order_required(source):
    root, original_metadata = source
    metadata = deepcopy(original_metadata)
    # First flat descriptor is the independently checked Boolean status type.
    metadata.find("VCTP/Section/TypeDesc").set("Type", "NumFloat64")
    with pytest.raises(AssertionError, match="cluster field order"):
        validate_error_lanes(root, metadata)
