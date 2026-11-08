"""Original Supervision structure, reference identities and qualified limits."""

import xml.etree.ElementTree as ET
from types import SimpleNamespace

import pytest
from tools.audit_sup_lvkit_native_contracts import (
    MAIN_SHA,
    MUTABLE_MAIN_SHA,
    REFERENCES,
    audit,
    validate_references,
)


@pytest.fixture(scope="module")
def proof():
    return audit()


def test_all_39_original_application_members_preserve_structure_and_net_members(proof):
    assert len(proof["members"]) == 39
    assert proof["totals"] == {
        "sequences": 79,
        "cases": 166,
        "loops": 41,
        "disable_structures": 4,
        "events": 3,
        "frames": 773,
        "nets": 5869,
        "psp_nodes": 102,
    }


def test_resaved_main_cannot_substitute_for_pinned_original(proof):
    assert proof["original_main_sha256"] == MAIN_SHA != MUTABLE_MAIN_SHA
    assert proof["members"][0]["sha256"] == MAIN_SHA


def test_eleven_reference_controls_and_35_local_aliases_are_preserved(proof):
    refs = proof["restored_reference_controls"]
    assert {name: len(row["controls"]) for name, row in refs.items()} == {
        "0_SUP_ELYSE.vi": 9,
        "1_SUP_PROFILS XY.vi": 2,
    }
    assert len(refs["0_SUP_ELYSE.vi"]["local_nodes_checked"]) == 35
    assert len(proof["updated_reader_metadata"]) == 2
    assert all(
        row["diagram_and_panel_unchanged"] for row in proof["updated_reader_metadata"]
    )
    assert proof["historical_stub_metadata_is_not_type_or_default_authority"]


def test_original_ht_and_modulator_request_maps_are_not_hardware_authorization(proof):
    assert len(proof["original_request_maps"]["HT"]) == 5
    assert len(proof["original_request_maps"]["Modulateur"]) == 11
    assert not proof["native_or_hardware_or_psp_executed"]
    assert not proof["whole_supervision_closed"]
    assert not proof["raw_event_NewVal_decoder_qualified"]


def test_two_named_images_do_not_close_unmapped_native_frames_or_protected_vi(proof):
    images = proof["manually_inspected_images_this_pass"]
    assert len(images) == 2
    assert all(
        row["source_sha_at_capture"] is None
        and not row["original_source_capture_binding_qualified"]
        for row in images
    )
    assert not proof["all_native_frames_reviewed"]
    assert not proof["protected_error_database_implemented"]


@pytest.mark.parametrize("replacement", [None, "Void", "Boolean"])
def test_recovered_name_alone_cannot_qualify_lost_or_wrong_type(replacement):
    name = "0_SUP_ELYSE.vi"
    controls = [
        SimpleNamespace(
            uid=uid,
            name=label,
            control_type="stdRefNum",
            lv_type=SimpleNamespace(
                underlying_type=replacement, ref_type="UsrDefTagFlt"
            ),
        )
        for uid, label in REFERENCES[name].items()
    ]
    parsed = SimpleNamespace(front_panel=SimpleNamespace(controls=controls))
    with pytest.raises(AssertionError, match="saved IMAQ type lost"):
        validate_references(name, parsed, ET.fromstring("<FPHb/>"))
