"""All nine caller graphs reject unknown fanout and connector mutations."""

import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

import pytest
from validate_acq_initializer_caller_frame import (
    DIAGRAM_UIDS,
    FALLBACK_NETS,
    LITERALS,
    PARENT_NETS,
    validate_caller,
    validate_disabled_parent,
    validate_discovery,
    validate_fallback,
    validate_parents,
)
from validate_acq_modulator_start_event_guards import unique
from validate_acq_vam_status import checked_vam

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def source():
    return checked_vam(
        ROOT / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
    )


def test_pinned_source_passes(source):
    assert "29 nets" in validate_caller(*source)
    assert "23 nets" in validate_fallback(*source)
    assert "four nets" in validate_parents(*source)
    assert "14 nets" in validate_discovery(*source)
    assert "73-net sibling" in validate_disabled_parent(*source)


@pytest.mark.parametrize(
    "tag", ["activeDiag", "defaultDiag", "commentMode", "CommentSelLabFlags"]
)
def test_initialization_disable_metadata_is_not_missing_and_rejects_mutation(
    source, tag
):
    root, metadata = source
    value = unique(root, "commentNode", "76550").find(tag)
    before = value.text
    value.text = "changed"
    try:
        with pytest.raises(AssertionError, match="metadata"):
            validate_disabled_parent(root, metadata)
    finally:
        value.text = before


def test_empty_disabled_arm_cannot_acquire_a_call(source):
    root, metadata = source
    ops = unique(root, "diag", "76564").find("zPlaneList")
    extra = ET.SubElement(ops, "SL__arrayElement", **{"class": "iUse", "uid": "extra"})
    try:
        with pytest.raises(AssertionError, match="operations"):
            validate_disabled_parent(root, metadata)
    finally:
        ops.remove(extra)


@pytest.mark.parametrize("uid", ["21518", "74296"])
def test_discovery_unused_operation_cannot_be_added(source, uid):
    root, metadata = source
    ops = unique(root, "diag", uid).find("zPlaneList")
    extra = ET.SubElement(ops, "SL__arrayElement", uid="new-unconnected-literal")
    try:
        with pytest.raises(AssertionError, match="operations"):
            validate_discovery(root, metadata)
    finally:
        ops.remove(extra)


@pytest.mark.parametrize("uid", tuple(PARENT_NETS))
def test_every_parent_graph_rejects_unknown_operations(source, uid):
    root, metadata = source
    ops = unique(root, "diag", uid).find("zPlaneList")
    extra = ET.SubElement(
        ops, "SL__arrayElement", **{"class": "prim", "uid": "unknown"}
    )
    try:
        with pytest.raises(AssertionError, match="operations"):
            validate_parents(root, metadata)
    finally:
        ops.remove(extra)


def test_clock_command_and_handler_wire_changes_rejected(source):
    original, metadata = source
    root = deepcopy(original)
    unique(root, "diag", "17949").find(
        "nodeList/*/termList/*[@uid='18773']/dco/ConstValue"
    ).text = "00000000"
    with pytest.raises(AssertionError, match="command"):
        validate_parents(root, metadata)
    root = deepcopy(original)
    unique(root, "diag", "17949").find("signalList/*/termList/*[@uid='21049']").set(
        "uid", "9244"
    )
    with pytest.raises(AssertionError, match="wire set"):
        validate_parents(root, metadata)


@pytest.mark.parametrize("uid", tuple(FALLBACK_NETS))
def test_every_fallback_diagram_rejects_added_fanout(source, uid):
    root, metadata = source
    terms = unique(root, "diag", uid).find("signalList/*/termList")
    extra = ET.SubElement(terms, "SL__arrayElement", uid="unknown-fanout")
    try:
        with pytest.raises(AssertionError, match="wire set"):
            validate_fallback(root, metadata)
    finally:
        terms.remove(extra)


def test_no_sample_count_argument_injected_into_test_read(source):
    root, metadata = source
    terms = unique(root, "diag", "133").find("signalList/*/termList")
    extra = ET.SubElement(terms, "SL__arrayElement", uid="2642")
    try:
        with pytest.raises(AssertionError, match="wire set"):
            validate_fallback(root, metadata)
    finally:
        terms.remove(extra)


@pytest.mark.parametrize("uid", DIAGRAM_UIDS)
def test_every_diagram_rejects_added_fanout(source, uid):
    root, metadata = source
    frame = unique(root, "diag", uid)
    terms = frame.find("signalList/*/termList")
    extra = ET.SubElement(terms, "SL__arrayElement", uid="unknown-fanout")
    try:
        with pytest.raises(AssertionError, match="wire set"):
            validate_caller(root, metadata)
    finally:
        terms.remove(extra)


@pytest.mark.parametrize("uid,typ,raw", LITERALS)
def test_each_argument_literal_rejected_if_changed(source, uid, typ, raw):
    root, metadata = source
    literal = unique(root, "diag", "227").find(
        f"nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue"
    )
    before = literal.text
    literal.text = "00"
    try:
        with pytest.raises(AssertionError, match="literal"):
            validate_caller(root, metadata)
    finally:
        literal.text = before


def test_unwired_first_error_input_cannot_acquire_net(source):
    root, metadata = source
    signals = unique(root, "diag", "227").find("signalList")
    extra = ET.SubElement(
        signals, "SL__arrayElement", **{"class": "signal", "uid": "new"}
    )
    terms = ET.SubElement(extra, "termList")
    ET.SubElement(terms, "SL__arrayElement", uid="610")
    ET.SubElement(terms, "SL__arrayElement", uid="1131")
    try:
        with pytest.raises(AssertionError, match="wire set"):
            validate_caller(root, metadata)
    finally:
        signals.remove(extra)


def test_connector_direction_and_unused_type_mutations(source):
    original, metadata = source
    root = deepcopy(original)
    node = unique(root, "iUse", "593")
    node.find("termList/*/dco/objFlags").text = "512"
    with pytest.raises(AssertionError, match="direction"):
        validate_caller(root, metadata)
    root = deepcopy(original)
    node = unique(root, "iUse", "593")
    node.find("termList/*[@uid='604']/dco/typeDesc").text = "TypeID(1608)"
    with pytest.raises(AssertionError, match="unused"):
        validate_caller(root, metadata)
