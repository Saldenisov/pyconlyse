"""Raw persisted bytes, all DCO fields and explicit connector mutations."""

from copy import deepcopy

import pytest
from validate_acq_helper_source_facets import ARCHIVE
from validate_acq_modulator_start_event_guards import unique
from validate_acq_runtime_io_frame import checked_trees
from validate_acq_saved_ni6071e_data import (
    PROFILES,
    READER,
    checked_roots,
    compare_control_identities,
    compare_pilot_count_wires,
    compare_source_data,
    decode_saved,
    read_source_data,
    validate_all,
)


@pytest.fixture(scope="module")
def source():
    return {p.name: (*read_source_data(p), checked_roots(p)) for p in PROFILES}


def test_complete_original_associations_and_count_distinction():
    result = validate_all()
    assert result["dco_rows"] == 15
    assert result["independent_dco_fields"] == 480
    assert result["saved_parameters"] == 9
    assert (result["reader_samples"], result["initializer_samples"]) == (1000, 10)
    assert result["native_loading_proven"] is False
    assert result["unwritten_output_return_proven"] is False


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.name)
def test_every_saved_parameter_byte_is_required(source, profile):
    payload, data, _ = source[profile.name]
    for spec in profile.parameters:
        for index in range(*spec.span):
            changed = bytearray(payload)
            changed[index] ^= 1
            with pytest.raises(AssertionError, match="DFDS bytes"):
                compare_source_data(profile, bytes(changed), data)


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.name)
def test_each_parsed_field_and_record_interval_is_required(source, profile):
    payload, data, _ = source[profile.name]
    for bank, record in data["parameters"].items():
        for field in record:
            changed = deepcopy(data)
            changed["parameters"][bank][field] = "wrong"
            with pytest.raises(AssertionError, match="typed metadata"):
                compare_source_data(profile, payload, changed)


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.name)
def test_dco_480_field_equality_cannot_be_replaced_by_positional_guess(source, profile):
    payload, data, _ = source[profile.name]
    for index, row in enumerate(data["dcos"]):
        for field, value in enumerate(row):
            changed = deepcopy(data)
            rows = list(changed["dcos"])
            item = list(row)
            item[field] = value + 1 if type(value) is int else b"wrong"
            rows[index] = tuple(item)
            changed["dcos"] = tuple(rows)
            with pytest.raises(AssertionError, match="DCO independent"):
                compare_source_data(profile, payload, changed)


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.name)
def test_source_control_count_connector_and_widget_mutations_rejected(source, profile):
    _, _, roots = source[profile.name]
    for spec in profile.parameters:
        for field in ("control_type", "ddo", "widget", "caption", "connector"):
            changed = deepcopy(roots)
            control = unique(changed["vi_FPHb.xml"], "fPDCO", spec.control)
            if field == "control_type":
                control.find("typeDesc").text = "TypeID(999)"
            elif field == "ddo":
                control.find("ddo").set("uid", "wrong")
            elif field == "widget":
                control.find("ddo").set("class", "wrong")
            elif field == "caption":
                control.find(
                    "ddo/partsList/*[@class='label']/textRec/text"
                ).text = "wrong"
            else:
                changed["vi.xml"].findall("CPMp/Section/TypeDesc")[spec.slot].set(
                    "Flags", "0x6300"
                )
            with pytest.raises(AssertionError, match="front-panel/connector"):
                compare_control_identities(profile, changed)


def test_saved_read_count_cannot_be_replaced_by_initializer_count(source):
    payload, data, _ = source[READER.name]
    changed = deepcopy(data)
    changed["parameters"][5]["value"] = 10
    with pytest.raises(AssertionError, match="typed metadata"):
        compare_source_data(READER, payload, changed)


@pytest.mark.parametrize(
    "raw,kind",
    [
        (b"\0", "NumInt32"),
        (b"\0", "NumFloat64"),
        (b"\0\0\0\x04x", "Tag"),
        (b"\0" * 8, "Cluster"),
        (b"\x02" + b"\0" * 8, "Cluster"),
        (b"\0" * 8 + b"\x01", "Cluster"),
    ],
)
def test_independent_scalar_tag_error_decoders_reject_truncation(raw, kind):
    with pytest.raises(AssertionError):
        decode_saved(raw, kind)


def test_pilot_count_is_unwired_and_helper_count_feeds_both_reads(source):
    root, _ = checked_trees(ARCHIVE.parent / "0_ACQ_ELYSE_XML_sha6fe8.zip")
    _, _, roots = source[READER.name]
    compare_pilot_count_wires(root, roots)
    frame = unique(root, "diag", "133")
    term = frame.find("signalList/*/termList/*")
    before = term.get("uid")
    term.set("uid", "2642")
    try:
        with pytest.raises(AssertionError, match="unwired slot9"):
            compare_pilot_count_wires(root, roots)
    finally:
        term.set("uid", before)
