"""Bind manual native20 observations to original source and frozen PNGs.

This validates an evidence record, not pixels automatically or native12
execution. No app, driver, PSP or network is opened or operated.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prepare_acq_readonly_review import audit_copy
from validate_acq_controlled_stop import CONTROLLED_STOP, validate_stop
from validate_acq_final_cleanup import validate_cleanup_tree
from validate_acq_initialization_error_gates import GATES
from validate_acq_initializer_caller_frame import (
    validate_caller,
    validate_disabled_parent,
    validate_fallback,
)
from validate_acq_lifecycle_envelopes import validate_envelopes
from validate_acq_modulator_start_event_guards import require, unique
from validate_acq_output_initializers import (
    AO_FRAMES,
    checked_roots,
    validate_ao,
    validate_dio,
)
from validate_acq_startup_error_lanes import validate_trees as validate_startup_lanes
from validate_acq_stop_state_memory import validate_memory
from validate_acq_timeout_cooling_sequence import validate_cooling
from validate_acq_vam_status import checked_vam

REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / "docs/ELYSE_ACQ_NATIVE_STATIC_OBSERVATIONS_2026-10-15.json"
STOP_RECORD = REPO / "docs/ELYSE_ACQ_NATIVE_STOP_OBSERVATIONS_2026-10-15.json"
INIT_RECORD = REPO / "docs/ELYSE_ACQ_NATIVE_INITIALIZER_OBSERVATIONS_2026-10-15.json"
MAIN_SHA = "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF"
COMMENTS = {
    "76550": ("1356", ("76558", "76564"), "01", 1, False),
    "68772": ("47487", ("68780", "68786"), "01", 1, False),
    "14478": ("42045", ("21070", "21403"), None, 0, True),
}


def validate(record=None):
    if record is None:
        record = json.loads(RECORD.read_text("utf-8"))
    require(record["source_vi_sha256"] == MAIN_SHA, "native source identity changed")
    require(
        record["native_executable_file_version"] == "20.0f1"
        and record["no_native_run_or_save"] is True
        and record["hardware_or_psp_executed"] is False
        and record["native_original_lv2012_runtime_equivalence"] is False
        and record["whole_acquisition_closed"] is False
        and record["native_evidence_complete"] is False,
        "native observation scope or qualification changed",
    )
    copies = audit_copy()
    require(copies["all_17_byte_identical"], "original or review copies changed")
    require(
        str(Path(record["loaded_copy"]))
        == str(Path(copies["review_directory"]) / "0_ACQ_ELYSE.vi"),
        "observed loaded file path differs",
    )
    root, metadata = checked_vam(
        REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
    )
    source_comments = root.findall(".//*[@class='commentNode']")
    require(
        {n.get("uid") for n in source_comments} == set(COMMENTS)
        and len(source_comments) == 3,
        "whole Main Diagram Disable census changed",
    )
    rows = record["comment_nodes"]
    require(
        len(rows) == 3 and {row["uid"] for row in rows} == set(COMMENTS),
        "recorded Diagram Disable population changed",
    )
    used_images = set()
    for row in rows:
        parent, arms, explicit, observed, nonempty = COMMENTS[row["uid"]]
        node = unique(root, "commentNode", row["uid"])
        require(
            node in unique(root, "diag", parent).iter()
            and tuple(d.get("uid") for d in node.findall("diagramList/*")) == arms
            and node.findtext("activeDiag") == explicit
            and node.findtext("defaultDiag") == explicit
            and node.findtext("commentMode") == "True",
            "saved disable metadata changed",
        )
        require(
            row["parent_diagram"] == parent
            and tuple(row["arm_diagrams"]) == arms
            and row["saved_active_diag"] == explicit
            and row["saved_default_diag"] == explicit
            and row["observed_active_index"] == observed
            and row["active_arm_contains_controller_operations"] is nonempty,
            "manual import observation identity changed",
        )
        selected = unique(root, "diag", arms[observed])
        require(
            bool(selected.findall("zPlaneList/*")) is nonempty,
            "observed active arm source operation population changed",
        )
        used_images.update(row["images"])
    validate_disabled_parent(root, metadata)
    cooling_source = validate_cooling(root, metadata)
    validate_memory(root, metadata)
    flow = record["cooling_guard"]
    require(
        flow["case_uid"] == "11044"
        and flow["false_diagram"] == "44189"
        and flow["false_arm_empty"] is True
        and flow["true_sequence_uid"] == "8256"
        and flow["visited_frames"] == list(range(7))
        and flow["requested_wait_ms_by_frame"] == [150, None, 400, 150, None, None, 100]
        and flow["physical_polarity_inferred"] is False
        and flow["electrical_pulse_width_inferred"] is False,
        "native cooling-flow frame record changed",
    )
    used_images.update(flow["images"])
    error = record["timeout_read_error"]
    require(
        error["selector_uid"] == "40205"
        and error["stop_writer_uid"] == "85095"
        and error["tcp_writer_uid"] == "68231"
        and error["observed_value_for_both"] is False,
        "native timeout-error record changed",
    )
    used_images.add(error["image"])
    require(
        used_images == set(record["image_sha256"]) and len(used_images) == 18,
        "native image census changed",
    )
    for name, expected in record["image_sha256"].items():
        require(Path(name).name == name, "image path must be a simple basename")
        actual = hashlib.sha256((Path(record["image_directory"]) / name).read_bytes())
        require(actual.hexdigest().upper() == expected, "native evidence image changed")
    return {
        "manual_native_version_file": record["native_executable_file_version"],
        "byte_identical_original_members": len(copies["members"]),
        "comment_nodes_visually_reviewed": 3,
        "disable_arms_visually_reviewed": 6,
        "cooling_trip_frames_visually_reviewed": 7,
        "frozen_images": 18,
        "cooling_source_validation": cooling_source,
        "original_lv2012_runtime_equivalence": False,
        "whole_acquisition_closed": False,
    }


def validate_stop_observations(record=None):
    """Cross-check limited manual stop views; never promote all nested visits."""
    if record is None:
        record = json.loads(STOP_RECORD.read_text("utf-8"))
    require(
        record["source_vi_sha256"] == MAIN_SHA
        and record["native_executable_file_version"] == "20.0f1"
        and record["no_native_run_or_save"] is True
        and record["original_lv2012_runtime_equivalence"] is False
        and record["whole_acquisition_closed"] is False
        and record["all_nested_stop_diagrams_visually_reviewed"] is False
        and record["case_display_is_not_runtime_case_entry"] is True,
        "stop observation scope changed",
    )
    require(
        [(row["index"], row["diagram"]) for row in record["phase_views"]]
        == [(index, uid) for index, (uid, _) in enumerate(CONTROLLED_STOP)]
        and record["outer_tcp_selector_uid"] == "43488"
        and record["tcp_false_diagram"] == "43496"
        and record["tcp_false_arm_empty"] is True
        and record["general_selector_uid"] == "52981"
        and record["general_false_arm_empty"] is False
        and record["general_false_ui_properties"] == 5
        and record["general_false_disabled_enum_value"] == 0
        and record["general_false_direct_card_command"] is False
        and record["outer_loop_stop_bank"] == 46
        and record["cleanup_diagram"] == "246"
        and record["cleanup_fixed_uri_tags"] == 27
        and record["cleanup_tpg_close_calls"] == 2
        and record["cleanup_explicit_daq_stop_clear_or_zero"] is False,
        "stop observation controller identity changed",
    )
    audit_copy()
    root, metadata = checked_vam(
        REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
    )
    stop_source = validate_stop(root, metadata)
    envelopes = validate_envelopes(root, metadata)
    cleanup_source = validate_cleanup_tree(root, metadata)
    images = record["image_sha256"]
    require(len(images) == 12, "stop image population changed")
    for name, expected in images.items():
        require(Path(name).name == name, "stop image path must be a basename")
        actual = hashlib.sha256((Path(record["image_directory"]) / name).read_bytes())
        require(actual.hexdigest().upper() == expected, "stop evidence image changed")
    return {
        "static_native_outer_phase_views": 7,
        "frozen_stop_images": 12,
        "source_stop_graphs": stop_source["diagrams"],
        "source_stop_nets": stop_source["nets"],
        "source_envelope_graphs": envelopes["diagrams"],
        "source_cleanup_validation": cleanup_source,
        "all_nested_stop_diagrams_visually_reviewed": False,
        "whole_acquisition_closed": False,
    }


def validate_initializer_observations(record=None):
    """Bind selected initializer views; retain unobserved DIO path readback."""
    if record is None:
        record = json.loads(INIT_RECORD.read_text("utf-8"))
    require(
        record["source_vi_sha256"] == MAIN_SHA
        and record["native_executable_file_version"] == "20.0f1"
        and record["no_native_run_or_save"] is True
        and record["hardware_or_psp_executed"] is False
        and record["original_lv2012_runtime_equivalence"] is False
        and record["whole_initialization_closed"] is False
        and record["whole_acquisition_closed"] is False
        and record["case_display_is_not_runtime_case_entry"] is True,
        "initializer observation scope changed",
    )
    caller, pilot = record["caller"], record["pilot_fallback"]
    require(
        caller["diagram"] == "227"
        and caller["initializer_call_uids"] == [r[0] for r in GATES]
        and caller["error_case_uids"] == [r[3] for r in GATES]
        and caller["clear_error_call_uids"] == [r[-3] for r in GATES]
        and caller["both_arms_visually_reviewed"] is True
        and caller["sample_rate_literal_hz"] == 5000
        and caller["sample_count_literal"] == 10
        and caller["triggers"] == ["/1/PFI0", "/2/PFI0"]
        and caller["retry_or_rollback_in_this_frame"] is False
        and pilot["diagram"] == "133"
        and pilot["outer_error_case_uid"] == "2105"
        and pilot["inner_error_case_uid"] == "2239"
        and pilot["both_arms_of_both_cases_visually_reviewed"] is True
        and pilot["error_code_equality_guard"] is False
        and pilot["annotation_only_code"] == -200284
        and pilot["fallback_initializer_uid"] == "1198"
        and pilot["replacement_triggers"] == ["/1/20MHzTimebase", "/2/20MHzTimebase"]
        and pilot["successful_recovery_proven"] is False,
        "initializer caller/fallback observation changed",
    )
    startup = record["discovery_and_startup"]
    require(
        startup["discovery_diagram"] == "21518"
        and startup["discovery_loop_diagram"] == "74296"
        and startup["discovery_has_expected_name_whitelist"] is False
        and startup["discovery_final_error_consumed"] is False
        and startup["startup_sequence_uid"] == "24603"
        and startup["visited_startup_frame_diagrams"]
        == ["14803", "24611", "25990", "33052", "17881"]
        and startup["command_publications"] == 7
        and startup["initial_io_call_order"]
        == ["1_ACQ_READ_NI6071E.vi", "1_ACQ_RW_DIO96.vi", "1_ACQ_WRITE_NI6703.vi"]
        and startup["initial_read_sample_count"] == 1000
        and startup["postinit_instrument_error_handlers"] == 3
        and startup["postinit_resets_gated_by_instrument_success"] is False
        and startup["long_status_constants_fully_visible_in_native_image"] is False
        and startup["pilot_present_uses_original_pilot_read_error"] is True
        and startup["pilot_present_is_aggregate_readiness"] is False
        and startup["final_status_publications"] == ["DPS", "EPS", "VDM-A"]
        and startup["final_independent_wait_argument_ms"] == 100,
        "discovery/startup observation changed",
    )
    copies = audit_copy()
    identities = {r["vi"]: r["sha256"] for r in copies["members"]}
    helpers = record["helpers"]
    require(
        [r["vi"] for r in helpers] == ["1_ACQ_INIT_NI6703.vi", "1_ACQ_INIT_DIO96.vi"]
        and all(identities[r["vi"]] == r["source_vi_sha256"] for r in helpers),
        "initializer helper identity changed",
    )
    ao, dio = helpers
    require(
        Path(ao["loaded_path_readback"]) == Path(copies["review_directory"]) / ao["vi"]
        and ao["properties_source_version"] == "12.0"
        and ao["sequence_uid"] == "784"
        and ao["visited_frame_diagrams"] == [r[0] for r in AO_FRAMES]
        and ao["visited_loop_diagrams"] == [r[2] for r in AO_FRAMES]
        and ao["channels_per_task"] == 10
        and ao["connected_channel_range_volts"] == [-10, 10]
        and ao["scale_arrays_connected"] is False
        and ao["output_voltage_write_in_helper"] is False
        and ao["create_task_errors_returned"] is False
        and ao["channel_error_shift_register"] is False
        and ao["public_error_source"] == "C9 last channel iteration only"
        and dio["loaded_path_readback"] is None
        and dio["native_path_readback_pending"] is True
        and dio["diagram"] == "3"
        and dio["task_names"]
        == [
            "C3_IN_DIO",
            "C4_IN_DIO",
            "C5_IN_DIO",
            "C3_OUT_DIO",
            "C4_OUT_DIO",
            "C5_OUT_DIO",
        ]
        and dio["physical_channels"]
        == [
            "3/port0:6",
            "4/port0:7",
            "5/port0:6",
            "3/port7:11",
            "4/port8:11",
            "5/port7:11",
        ]
        and dio["continuous_public_error_chain"] is True
        and dio["output_write_start_stop_or_clear_in_helper"] is False,
        "initializer helper observation changed",
    )
    root, metadata = checked_vam(
        REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
    )
    caller_source = validate_caller(root, metadata)
    fallback_source = validate_fallback(root, metadata)
    startup_source = validate_startup_lanes(root, metadata)
    roots = checked_roots(
        REPO
        / "legacy/xp_acq_agent/data/source_exports"
        / "ACQ_17_original_members_XML_20261001.zip"
    )
    validate_ao(roots[ao["vi"]])
    validate_dio(roots[dio["vi"]])
    images = record["image_sha256"]
    require(len(images) == 17, "initializer image population changed")
    for name, expected in images.items():
        require(Path(name).name == name, "initializer image must be a basename")
        actual = hashlib.sha256((Path(record["image_directory"]) / name).read_bytes())
        require(actual.hexdigest().upper() == expected, "initializer image changed")
    return {
        "frozen_initializer_images": 17,
        "caller_error_cases_both_arms_reviewed": 4,
        "pilot_error_cases_both_arms_reviewed": 2,
        "ao_frames_reviewed": 4,
        "final_startup_frames_reviewed": 5,
        "dio_loaded_path_readback_pending": True,
        "caller_source_validation": caller_source,
        "fallback_source_validation": fallback_source,
        "startup_source_validation": startup_source,
        "whole_initialization_closed": False,
        "whole_acquisition_closed": False,
    }


if __name__ == "__main__":
    print(
        json.dumps(
            {
                "disable_and_flow": validate(),
                "stop": validate_stop_observations(),
                "initializers": validate_initializer_observations(),
            },
            indent=2,
        )
    )
