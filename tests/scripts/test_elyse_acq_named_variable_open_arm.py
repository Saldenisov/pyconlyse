"""Named-open sibling cannot be mistaken for writes to data/card banks."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from validate_acq_modulator_start_event_guards import unique
from validate_acq_named_variable_open_arm import ROWS, validate_tree
from validate_acq_vam_status import checked_vam


@pytest.fixture(scope="module")
def source():
    return checked_vam(
        Path(__file__).resolve().parents[2]
        / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
    )


def test_original_passes(source):
    assert "73 complete nets" in validate_tree(*source)


def test_each_uri_and_read_direction_is_pinned(source):
    root, metadata = source
    frame = unique(root, "diag", "76558")
    for _, _, literal_uid, _, alias, _, _ in ROWS:
        literal = frame.find(
            f"nodeList/*/termList/*[@uid='{literal_uid}']/dco/ConstValue"
        )
        before = literal.text
        literal.text = "00000000"
        try:
            with pytest.raises(AssertionError, match="URI"):
                validate_tree(root, metadata)
        finally:
            literal.text = before
        flags = unique(root, "gRef", alias).find("termList/*/objFlags")
        before = flags.text
        flags.text = "36864"
        try:
            with pytest.raises(AssertionError):
                validate_tree(root, metadata)
        finally:
            flags.text = before


def test_each_of_73_nets_rejects_added_fanout(source):
    root, metadata = source
    for signal in unique(root, "diag", "76558").findall("signalList/*"):
        terms = signal.find("termList")
        extra = ET.SubElement(terms, "SL__arrayElement", uid="unknown")
        try:
            with pytest.raises(AssertionError, match="wire set"):
                validate_tree(root, metadata)
        finally:
            terms.remove(extra)


def test_open_return_reference_cannot_gain_consumer(source):
    root, metadata = source
    terms = unique(root, "diag", "76558").find("signalList/*/termList")
    extra = ET.SubElement(terms, "SL__arrayElement", uid=ROWS[0][1][1])
    try:
        with pytest.raises(AssertionError, match="wire set"):
            validate_tree(root, metadata)
    finally:
        terms.remove(extra)
