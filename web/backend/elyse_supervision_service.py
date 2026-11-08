"""Web adapter for evidence-backed SuperVision models, never a hardware adapter.

Imports repository-owned reconstructions without copying their arithmetic. Inputs
are operator-supplied replay data, not trusted Acquisition telemetry. No procedure
engine, Tango proxy, PSP publisher, file writer or background loop is constructed.
"""

import base64
import hashlib
import importlib
import json
import math
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path

SUPERVISION_ROOT = Path(__file__).resolve().parents[2] / "Supervision"
MODEL_PACKAGE = "Supervision.python_reconstruction.src.supervision_reconstruction"
SOURCE_SHA256 = "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B"


def model(name):
    # Names originate exclusively in this module, never from an HTTP request.
    return importlib.import_module(f"{MODEL_PACKAGE}.domain.{name}")


def json_value(value):
    if is_dataclass(value):
        return {f.name: json_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return {"base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((json_value(v) for v in value), key=lambda v: json.dumps(v))
    if isinstance(value, (tuple, list)):
        return [json_value(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite result is outside the web replay contract")
    return value


def exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(f"Required fields: {', '.join(keys)}")
    return value


def snapshot():
    parameter = model("parameter_page_events")
    commands = model("page_command_events")
    registry = model("magnet_registry").candidate_registry()
    diagnostics = model("diagnostic_events")
    digital = model("digital_command_events")
    from DeviceServers.control.elyse_acq import supervision_status as display

    # Only enumerate labels. Synthetic zeros never become telemetry.
    display_fields = {
        "ht": list(display.project_ht_display_flags([False] * 64)),
        "radioprotection": list(
            display.project_radioprotection_display_flags([False] * 64)
        ),
        "fluides": list(
            display.project_fluides_raw_display_flags([False] * 56, [False] * 64)
        ),
        "modulator": list(display.project_modulator_stage_ok_from_eps([False] * 77)),
    }
    pages = {}
    for page in parameter.ParameterPage:
        rules = [r for r in parameter.PARAMETER_RULES if r.page is page]
        pages[page.name.lower()] = {
            "page": page.value,
            "arrows": [json_value(r) for r in rules],
            "procedures": [
                source for source, _ in parameter.PROCEDURE_FIELD_MAPS[page]
            ],
        }
    for page, mapping in (
        (commands.CommandPage.ALIMENTATIONS, commands.ALIMENTATIONS_FIELD_MAP),
        (commands.CommandPage.MODULATOR, commands.MODULATOR_FIELD_MAP),
    ):
        pages[page.name.lower()] = {
            "page": page.value,
            "arrows": [],
            "procedures": [source for source, _ in mapping],
        }
    coverage = json.loads(
        (
            SUPERVISION_ROOT / "python_reconstruction" / "EVENT_MODEL_COVERAGE.json"
        ).read_text(encoding="utf-8")
    )
    source = (
        SUPERVISION_ROOT
        / "extracted"
        / "PILOTAGE_ELYSE_SUP"
        / "SUPERVISION_VIs"
        / "0_SUP_ELYSE.vi"
    )
    observed = (
        hashlib.sha256(source.read_bytes()).hexdigest().upper()
        if source.is_file()
        else None
    )
    return {
        "schema_version": 1,
        "mode": "EVIDENCE_REPLAY",
        "execution_allowed": False,
        "physical_status": "NOT_CONNECTED",
        "telemetry": {"quality": "UNAVAILABLE", "timestamp": None},
        "pages": pages,
        "dps_fields": list(commands.DPS_FIELDS),
        "display_fields": display_fields,
        "video_controls": {
            "tool_fields": list(model("video_events").VIDEO_TOOL_FIELDS),
            "image_quality": "UNAVAILABLE",
            "error_input_origin": "OPERATOR_SUPPLIED_SCENARIO",
            "threshold_channel_inputs": "FRESH_LABVIEW_LOCALS_UNRESOLVED",
        },
        "beamline_controls": {
            "diagnostic_stations": [
                r.station.value for r in diagnostics.DIAGNOSTIC_POSITION_RULES
            ],
            "diagnostic_selectors": [
                s for s, _ in diagnostics.DIAGNOSTIC_SELECTOR_VALUES
            ],
            "faraday_stations": [r.station.value for r in digital.FARADAY_PULSE_RULES],
            "faraday_tab_selectors": [0, 1, 2, 3],
            "faraday_en_inputs": list(digital.FARADAY_EN_INPUTS),
            "digital_selectors": [0, 1],
            "engineering_units_qualified": False,
            "physical_state_observed": False,
            "snapshots_origin": "EXPLICIT_PER_FRAME_REPLAY_ONLY",
        },
        "translator_controls": {
            "selections": [
                {"value": s.value, "label": s.name}
                for s in model("translator_selection").TranslatorSelection
            ],
            "polling_expression": json_value(
                model("translator_stop").POLLING_SELECTOR_EXPRESSION
            ),
            "selection_commands_position": False,
            "selection_switches_other_cameras_off": False,
            "stop_implementation_allowed": False,
            "establishes_safe_state": False,
        },
        "file_controls": {
            "path_states": [
                {"value": s.name, "label": s.value}
                for s in model("load_events").LegacyPathState
            ],
            "path_classification_origin": "OPERATOR_SUPPLIED_SCENARIO",
            "filesystem_access_performed": False,
            "load_applies_equipment_preset": False,
            "save_tir_model_status": "EXCLUDED_BY_USER",
        },
        "excluded_ui_features": [
            "TIR",
            "PRE-TIR",
            "VEILLE",
            "ARRÊT",
            "LOAD TIR",
            "SAVE TIR",
            "STOP",
            "LOAD",
            "VALIDER LOAD",
            "Tree",
        ],
        "motion_controls": {
            "jog_labels": list(model("motion_events").MOTION_CONTROLS[:4]),
            "jog_event_indices": [28, 29],
            "error_event_indices": [27, 28, 29],
            "autotune_stages": [
                stage.name for stage in model("autotune_events").AutotuneStage
            ],
            "autotune_channels": [2, 3],
            "autotune_stage_order": list(
                model("autotune_events").plan_autotune().stage_order
            ),
            "motor_numbers_origin": "OPERATOR_SUPPLIED_SYMBOLIC_U32",
            "physical_motion_performed": False,
            "physical_position_observed": False,
            "engineering_units_qualified": False,
            "autotune_complete_runtime": False,
        },
        "registry": model("magnet_readback").magnet_display_snapshot(registry),
        "coverage": coverage,
        "source_integrity": {
            "matches": observed == SOURCE_SHA256,
            "expected_main_sha256": SOURCE_SHA256,
            "observed_main_sha256": observed,
        },
        "replay_operations": list(REPLAY_OPERATIONS),
        "limits": [
            "Supplied replay inputs are not live telemetry or safety permission",
            "No PSP/Tango/DAQmx writes or hardware dispatch endpoint",
            "Unverified magnet routes and limits; no retired DAQmx fallback",
            "Bounded models, not qualified whole-VI replacements",
            "Error Code Database.vi excluded from active migration",
        ],
    }


def _frequency(data):
    exact(data, ("new_value",))
    return model("machine_frequency").plan_machine_frequency_change(data["new_value"])


def _parameter(data):
    exact(data, ("page", "current_dps", "arrows", "procedures", "numeric_newval"))
    module = model("parameter_page_events")
    page = module.ParameterPage(data["page"])
    return _with_acquisition_preview(
        module.plan_parameter_page_change(
            page,
            data["current_dps"],
            data["arrows"],
            data["procedures"],
            data["numeric_newval"],
        )
    )


def _command(data):
    exact(data, ("page", "current_dps", "newval"))
    module = model("page_command_events")
    return _with_acquisition_preview(
        module.plan_page_command_change(
            module.CommandPage(data["page"]),
            data["current_dps"],
            data["newval"],
        )
    )


def _with_acquisition_preview(plan):
    """Decode the saved first-true DPS dispatcher, never construct an engine.

    A selected procedure is a single-snapshot reference, not server acceptance,
    an acknowledgement, a cleared flag, commissioned ownership or execution.
    Hardware steps/targets are deliberately not exposed as dispatch arguments.
    """
    from DeviceServers.control.elyse_acq import dps_bridge

    result = json_value(plan)
    projected = plan.projected_dps
    downstream = {
        "state": "NO_NEW_DPS_WRITE",
        "execution_allowed": False,
        "acceptance_observed": False,
        "physical_ownership_verified": False,
    }
    if projected is not None:
        supplied = dict(projected)
        names = model("page_command_events").DPS_FIELDS
        try:
            procedure = dps_bridge.first_asserted_dps_request(
                tuple(supplied[name] for name in names[:24])
            )
            downstream["state"] = (
                "MODELED_PROCEDURE" if procedure else "NO_ASSERTED_PROCEDURE"
            )
            if procedure:
                downstream.update(
                    procedure=procedure.name,
                    legacy_event_case=procedure.legacy_event_case,
                    modeled_step_count=len(procedure.steps),
                )
        except dps_bridge.UnsupportedDpsIntent as error:
            downstream.update(state="UNSUPPORTED_REQUEST", reason=str(error))
    result["acquisition_preview"] = downstream
    return result


def _magnets(data):
    module = importlib.import_module(f"{MODEL_PACKAGE}.service.shadow")
    registry = model("magnet_registry").candidate_registry()
    return module.preview_currents(registry, module.parse_preview(registry, data))


def _synchronisation(data):
    exact(data, ("current_dps", "oldval", "newval", "stored_flash_index"))
    return model("synchronisation_events").plan_synchronisation_change(
        data["current_dps"],
        data["oldval"],
        data["newval"],
        data["stored_flash_index"],
    )


def _monitoring(data):
    exact(data, ("current", "previous", "finished_late_previous"))
    module = model("timed_monitoring")
    names = tuple(f.name for f in fields(module.MonitoringCounters))
    current = module.MonitoringCounters(**exact(data["current"], names))
    previous = module.MonitoringCounters(**exact(data["previous"], names))
    deltas = module.project_counter_deltas(current, previous)
    return {
        "deltas": deltas,
        "status": module.project_monitoring_status(
            deltas, finished_late_previous=data["finished_late_previous"]
        ),
        "mean_requests": module.plan_mean_requests(
            deltas, finished_late_previous=data["finished_late_previous"]
        ),
        "unit": "RAW_COUNTER_DELTA_NOT_HZ",
        "is_physical_interlock": False,
    }


def _display(data):
    exact(data, ("c3", "c4", "eps"))
    from DeviceServers.control.elyse_acq import supervision_status as module

    radiation = module.project_radioprotection_display_flags(data["c4"])
    return {
        "ht": module.project_ht_display_flags(data["c4"]),
        "radioprotection": radiation,
        "fluides": module.project_fluides_raw_display_flags(data["c3"], data["c4"]),
        "modulator": module.project_modulator_stage_ok_from_eps(data["eps"]),
        "radioprotection_graph_summary": module.radioprotection_graph_summary(
            radiation
        ),
        "is_physical_interlock": False,
        "electrical_polarity_qualified": False,
    }


def _profiles(data):
    exact(data, ("iteration", "average_count", "buffers", "x_samples", "y_samples"))
    iteration, count = data["iteration"], data["average_count"]
    if type(iteration) is not int or iteration < 0:
        raise ValueError("Nonnegative integer iteration required")
    if type(count) is not int or not 1 <= count <= 100:
        raise ValueError("Web replay average_count must be an integer in 1..100")
    buffers = exact(data["buffers"], ("x", "y"))
    vectors = [data["x_samples"], data["y_samples"]]
    for axis in ("x", "y"):
        if type(buffers[axis]) is not list or len(buffers[axis]) != count:
            raise ValueError("Explicit profile buffers must match average_count")
        vectors.extend(buffers[axis])
    if any(type(v) is not list or not 1 <= len(v) <= 4096 for v in vectors):
        raise ValueError("Bounded nonempty numeric profile vectors required")
    if any(type(n) not in (int, float) for v in vectors for n in v):
        raise ValueError("Profile samples must be numeric, not strings or booleans")
    module = model("profiles")
    return module.update_profile_buffers(
        iteration,
        count,
        module.ProfileBuffers(
            tuple(map(tuple, buffers["x"])), tuple(map(tuple, buffers["y"]))
        ),
        data["x_samples"],
        data["y_samples"],
    )


def _journal(data):
    names = ("message_input", "journal_in", "display_timestamp", "file_timestamp")
    exact(data, (*names, "file_path_token"))
    if any(type(data[name]) is not str for name in names):
        raise ValueError("Journal byte inputs require explicit base64 strings")
    module = model("journal")
    projection = module.project_journal_bytes(
        **{name: base64.b64decode(data[name], validate=True) for name in names}
    )
    return {
        "projection": projection,
        "file_intent": module.plan_journal_file_write(
            projection, file_path_token=data["file_path_token"]
        ),
        "encoding": "EXPLICIT_BYTES_BASE64",
        "file_written": False,
    }


def _external_error(value):
    """Typed scenario input, never a manufactured driver success result."""
    exact(value, ("status", "code", "source"))
    if type(value["status"]) is not bool:
        raise ValueError("External error status requires an explicit Boolean")
    code = value["code"]
    if type(code) is not int or not -(2**31) <= code <= 2**31 - 1:
        raise ValueError("External error code requires an I32 integer")
    if type(value["source"]) is not str:
        raise ValueError("External error source requires an explicit string")
    return model("fw102x_errors").ErrorCluster(**value)


def _video_tools(data):
    exact(data, ("values", "final_property_error"))
    values = data["values"]
    if type(values) is not list:
        raise ValueError("Video tools require an ordered Boolean array")
    return model("video_events").plan_video_tools(
        tuple(values),
        final_property_error=_external_error(data["final_property_error"]),
    )


def _camera_event(data, planner):
    exact(data, ("final_error", "formatted_text"))
    text = data["formatted_text"]
    if text is not None and type(text) is not str:
        raise ValueError("External formatter result must be a string or null")
    return planner(
        final_error=_external_error(data["final_error"]), formatted_text=text
    )


def _camera_thresholds(data):
    return _camera_event(data, model("video_events").plan_threshold_mouse_up)


def _camera_channel(data):
    return _camera_event(data, model("video_events").plan_camera_channel_change)


def _video_density(data):
    exact(data, ())
    return model("video_events").plan_density_change()


def _save_image(data):
    exact(data, ("new_value", "resolved_year", "dialog_cancelled", "selected_path"))
    if type(data["new_value"]) is not bool:
        raise ValueError("Save-image NewVal requires an explicit Boolean")
    year, cancelled, path = (
        data["resolved_year"],
        data["dialog_cancelled"],
        data["selected_path"],
    )
    if year is not None and (
        type(year) is not int or not -(2**31) <= year <= 2**31 - 1
    ):
        raise ValueError("Resolved year requires an I32 integer or null")
    if cancelled is not None and type(cancelled) is not bool:
        raise ValueError("Dialog result requires a Boolean or null (pending)")
    if path is not None and type(path) is not str:
        raise ValueError(
            "Selected path is an opaque string or null; never a file target"
        )
    return model("video_events").plan_save_image(
        data["new_value"],
        resolved_year=year,
        dialog_cancelled=cancelled,
        selected_path=path,
    )


def _slit_position(data):
    exact(data, ("axe_h", "gap_h"))
    return model("slit_position").plan_slit_position_change(
        data["axe_h"], data["gap_h"]
    )


def _diagnostic_position(data):
    exact(data, ("station", "selector"))
    module = model("diagnostic_events")
    if type(data["station"]) is not str:
        raise ValueError("Diagnostic station requires T1, T2 or T3")
    return module.plan_diagnostic_position_change(
        module.DiagnosticStation(data["station"]), data["selector"]
    )


def _digital_projection(plan, snapshots):
    """Each writing frame gets its own supplied snapshot; never chain results.

    A caller-provided snapshot is not proof of freshness, coherent sampling,
    ownership or acceptance. Missing snapshots remain unresolved, never zero.
    """
    writing_indices = {f.index for f in plan.frames if f.write_evidence is not None}
    supplied = {}
    if snapshots is not None:
        if type(snapshots) is not list or len(snapshots) != len(writing_indices):
            raise ValueError(
                "Supply exactly one explicit snapshot for each writing frame"
            )
        for entry in snapshots:
            exact(entry, ("frame_index", "cluster"))
            index, cluster = entry["frame_index"], entry["cluster"]
            if (
                type(index) is not int
                or index not in writing_indices
                or index in supplied
            ):
                raise ValueError(
                    "Unique writing-frame indices required; "
                    "waits have no cluster snapshot"
                )
            if type(cluster) is not dict or len(cluster) > 128:
                raise ValueError(
                    "Web replay cluster must be an explicit mapping "
                    "of at most 128 fields"
                )
            if any(
                type(k) is not str or type(v) is not bool for k, v in cluster.items()
            ):
                raise ValueError(
                    "Cluster snapshots require string keys and exact Boolean values"
                )
            supplied[index] = cluster
    result = json_value(plan)
    for frame, projected in zip(plan.frames, result["frames"]):
        projected["fresh_local_cluster_read_required"] = (
            frame.fresh_local_cluster_read_required
        )
        projected["projected_cluster"] = (
            model("digital_command_events").project_digital_frame(
                frame, supplied[frame.index]
            )
            if frame.index in supplied
            else None
        )
    result["cluster_freshness_verified"] = False
    result["coherent_sampling_verified"] = False
    result["live_cluster_read_performed"] = False
    result["projection_origin"] = (
        "EXPLICIT_PER_FRAME_REPLAY_SNAPSHOT"
        if snapshots is not None
        else "UNRESOLVED_LOCAL_READS"
    )
    return result


def _faraday_position(data):
    exact(data, ("station", "new_value", "frame_snapshots"))
    if type(data["station"]) is not int:
        raise ValueError("Faraday station requires an exact integer 1, 2 or 3")
    module = model("digital_command_events")
    return _digital_projection(
        module.plan_faraday_position_change(
            module.FaradayStation(data["station"]), data["new_value"]
        ),
        data["frame_snapshots"],
    )


def _faraday_tab(data):
    exact(data, ("new_value", "en_states", "frame_snapshots"))
    states = data["en_states"]
    if states is not None:
        if (
            type(states) is not list
            or len(states) != 3
            or any(type(s) is not bool for s in states)
        ):
            raise ValueError(
                "Three explicitly supplied Boolean EN states or null required"
            )
        states = tuple(states)
    plan = model("digital_command_events").plan_faraday_tab_change(
        data["new_value"], en_states=states
    )
    return _digital_projection(plan, data["frame_snapshots"])


def _laser_mirror(data):
    exact(data, ("new_value", "frame_snapshots"))
    plan = model("digital_command_events").plan_laser_mirror_change(data["new_value"])
    return _digital_projection(plan, data["frame_snapshots"])


def _slit_supply(data):
    exact(data, ("new_value", "frame_snapshots"))
    plan = model("digital_command_events").plan_slit_supply_change(data["new_value"])
    return _digital_projection(plan, data["frame_snapshots"])


def _centroid_reset(data):
    exact(data, ())
    return model("diagnostic_events").plan_centroid_average_reset()


def _translator_selection(data):
    exact(data, ("selection",))
    if type(data["selection"]) is not int:
        raise ValueError("Translator selection requires an exact integer 1..4")
    module = model("translator_selection")
    return module.plan_translator_selection(
        module.TranslatorSelection(data["selection"])
    )


def _translator_stop(data):
    exact(data, ())
    module = model("translator_stop")
    plan = module.build_translator_stop_plan()
    module.validate_translator_stop_plan(plan)
    return plan


def _translator_loop_selector(data):
    exact(data, ("iteration", "position_miroir_laser", "etat_t1", "etat_mlaser_en"))
    module = model("translator_stop")
    # Evaluate one supplied sample only. No loop, wait, state or stop decision.
    return {
        "expression_value": module.evaluate_translator_loop_selector(**data),
        "expression": module.POLLING_SELECTOR_EXPRESSION,
        "termination_semantics": "NATIVE_UNVERIFIED",
        "establishes_safe_state": False,
        "external_effects_blocked": True,
        "polling_loop_executed": False,
        "elapsed_time_guarantee": None,
    }


def _load_toggle(data):
    exact(data, ("new_value", "path_state", "cached_directory", "dialog_directory"))
    if type(data["new_value"]) is not bool:
        raise ValueError("LOAD NewVal requires an explicit Boolean")
    for name in ("cached_directory", "dialog_directory"):
        if data[name] is not None and type(data[name]) is not str:
            raise ValueError(f"{name} requires an opaque string or null")
    module = model("load_events")
    state = data["path_state"]
    if state is not None and (
        type(state) is not str or state not in module.LegacyPathState.__members__
    ):
        raise ValueError("Path classification requires VALID, EMPTY or NOT_A_PATH")
    if data["new_value"] and state is None:
        raise ValueError(
            "Active LOAD requires an explicit external path classification"
        )
    return module.plan_load_toggle(
        data["new_value"],
        path_state=module.LegacyPathState[state] if state is not None else None,
        cached_directory=data["cached_directory"],
        dialog_directory=data["dialog_directory"],
    )


def _validate_load(data):
    exact(data, ("new_value", "current_tag"))
    if type(data["current_tag"]) is not str:
        raise ValueError("Tree tag requires an explicitly supplied string")
    return model("load_events").plan_validate_load(
        data["new_value"], current_tag=data["current_tag"]
    )


def _tree_selection(data):
    exact(data, ("variant_string_result", "final_error"))
    if type(data["variant_string_result"]) is not str:
        raise ValueError("Variant To Data output requires an explicit string")
    return model("load_events").project_tree_selection(
        variant_string_result=data["variant_string_result"],
        final_error=_external_error(data["final_error"]),
    )


def _motor_initialization(data):
    exact(data, ("discovered_key",))
    key = data["discovered_key"]
    if key is not None and type(key) is not str:
        raise ValueError("Discovery result requires an opaque string or null")
    return model("motion_events").plan_motor_initialization(key)


def _motor_jog(data):
    exact(data, ("control_label", "motor_numbers", "relative_steps"))
    if type(data["control_label"]) is not str:
        raise ValueError("Jog control requires an exact native label")
    motors = data["motor_numbers"]
    if (
        type(motors) is not list
        or len(motors) != 2
        or any(type(n) is not int or not 0 <= n < 2**32 for n in motors)
    ):
        raise ValueError("Supply two explicit U32 motor numbers for X and Y")
    return model("motion_events").plan_manual_jog(
        data["control_label"],
        motor_numbers=tuple(motors),
        relative_steps=data["relative_steps"],
    )


def _motor_jog_poll(data):
    exact(
        data,
        (
            "event_index",
            "motion_done",
            "motion_done_error",
            "stop_motor",
            "position_result",
        ),
    )
    return model("motion_events").project_jog_poll(
        **dict(data, motion_done_error=_external_error(data["motion_done_error"]))
    )


def _motor_error(data):
    exact(data, ("event_index", "final_error"))
    return {
        "journal_intent": model("motion_events").project_motion_error(
            _external_error(data["final_error"]), event_index=data["event_index"]
        ),
        "journal_written": False,
        "external_effects_blocked": True,
    }


def _autotune_plan(data):
    exact(data, ())
    return model("autotune_events").plan_autotune()


def _autotune_iteration(data):
    exact(data, ("stage", "coordinate", "stop_motor", "motor_error"))
    module = model("autotune_events")
    if (
        type(data["stage"]) is not str
        or data["stage"] not in module.AutotuneStage.__members__
    ):
        raise ValueError(
            "Autotune requires an exact CHANNEL3_X/Y or CHANNEL2_X/Y stage"
        )
    return module.project_autotune_iteration(
        module.AutotuneStage[data["stage"]],
        data["coordinate"],
        stop_motor=data["stop_motor"],
        motor_error=data["motor_error"],
    )


def _autotune_outer(data):
    exact(data, ("channel3_y_in_band", "channel2_y_in_band", "stop_motor"))
    return {
        "terminate_outer_loop": model("autotune_events").autotune_outer_termination(
            **data
        ),
        "uses_x_convergence": False,
        "uses_motor_error": False,
        "external_effects_blocked": True,
        "loop_executed": False,
        "physical_alignment_observed": False,
    }


def _autotune_camera(data):
    exact(data, ("channel", "final_error"))
    return model("autotune_events").plan_autotune_camera_switch(
        data["channel"], final_error=_external_error(data["final_error"])
    )


def _saved_xnode(data):
    from DeviceServers.control.elyse_acq.vi_simulation.saved_xnode import replay_saved_xnode

    return replay_saved_xnode(data)


def _saved_timing(data):
    from DeviceServers.control.elyse_acq.vi_simulation.saved_timing import replay_saved_timing

    return replay_saved_timing(data)


def _saved_ni6220(data):
    from DeviceServers.control.elyse_acq.ni6220_projection import replay_saved_ni6220_read

    return replay_saved_ni6220_read(data)


def _saved_initializer(data):
    from DeviceServers.control.elyse_acq.vi_simulation.initialization_caller import replay_saved_initializer

    return replay_saved_initializer(data)


def _saved_cleanup(data):
    from DeviceServers.control.elyse_acq.vi_simulation.final_cleanup import replay_saved_cleanup

    return replay_saved_cleanup(data)


def _saved_requests(data):
    from DeviceServers.control.elyse_acq.supervision_requests import replay_saved_requests

    return replay_saved_requests(data)


def _saved_dispatch(data):
    from DeviceServers.control.elyse_acq.dps_bridge import replay_saved_dispatch

    return replay_saved_dispatch(data)


def _saved_psp_reads(data):
    from DeviceServers.control.elyse_acq.vi_simulation.timeout_reads import replay_saved_psp_reads

    return replay_saved_psp_reads(data)


def _saved_sup_reads(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_reads import replay_saved_sup_reads

    return replay_saved_sup_reads(data)


def _saved_stop(data):
    from legacy.xp_acq_agent.elyse_agent.saved_stop import replay_saved_stop

    return replay_saved_stop(data)


def _saved_numeric(data):
    from legacy.xp_acq_agent.elyse_agent.saved_numeric import replay_payload

    return replay_payload(data)


def _saved_card_init(data):
    from DeviceServers.control.elyse_acq.vi_simulation.saved_card_initializers import replay_saved_card_init

    return replay_saved_card_init(data)


def _saved_sup_helper(data):
    from DeviceServers.control.elyse_acq.vi_simulation.saved_supervision_helpers import replay_saved_sup_helpers

    return replay_saved_sup_helpers(data)


def _saved_acq_control_event(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_control_event import replay_saved_acq_event_33620

    return replay_saved_acq_event_33620(data)


def _saved_sup_frequency_event(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_frequency_event import replay_saved_sup_frequency

    return replay_saved_sup_frequency(data)


def _saved_acq_event_22879(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_22879 import replay_saved_acq_event_22879

    return replay_saved_acq_event_22879(data)


def _saved_sup_gain_event(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_gain_event import replay_saved_sup_gain

    return replay_saved_sup_gain(data)


def _saved_acq_event_45123(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_45123 import replay_saved_acq_event_45123

    return replay_saved_acq_event_45123(data)


def _saved_sup_event_65050(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_65050 import replay_saved_sup_event_65050

    return replay_saved_sup_event_65050(data)


def _saved_acq_event_34191(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_34191 import replay_saved_acq_event_34191

    return replay_saved_acq_event_34191(data)


def _saved_sup_event_38030(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_38030 import replay_saved_sup_event_38030

    return replay_saved_sup_event_38030(data)


def _saved_acq_event_43634(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_43634 import replay_saved_acq_event_43634

    return replay_saved_acq_event_43634(data)


def _saved_sup_event_53716(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_53716 import replay_saved_sup_event_53716

    return replay_saved_sup_event_53716(data)


def _saved_acq_event_31552(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_31552 import replay_saved_acq_event_31552

    return replay_saved_acq_event_31552(data)


def _saved_sup_event_18780(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_18780 import replay_saved_sup_event_18780

    return replay_saved_sup_event_18780(data)


def _saved_acq_event_48846(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_48846 import replay_saved_acq_event_48846

    return replay_saved_acq_event_48846(data)


def _saved_sup_event_33463(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_33463 import replay_saved_sup_event_33463

    return replay_saved_sup_event_33463(data)


def _saved_acq_event_8896(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_8896 import replay_saved_acq_event_8896

    return replay_saved_acq_event_8896(data)


def _saved_sup_event_38707(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_38707 import replay_saved_sup_event_38707

    return replay_saved_sup_event_38707(data)


def _saved_acq_event_23113(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_23113 import replay_saved_acq_event_23113

    return replay_saved_acq_event_23113(data)


def _saved_sup_event_5847(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_5847 import replay_saved_sup_event_5847

    return replay_saved_sup_event_5847(data)


def _saved_acq_event_38732(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_38732 import replay_saved_acq_event_38732

    return replay_saved_acq_event_38732(data)


def _saved_sup_event_26490(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_26490 import replay_saved_sup_event_26490

    return replay_saved_sup_event_26490(data)


def _saved_acq_event_37991(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_37991 import replay_saved_acq_event_37991

    return replay_saved_acq_event_37991(data)


def _saved_sup_event_23880(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_23880 import replay_saved_sup_event_23880

    return replay_saved_sup_event_23880(data)


def _saved_acq_event_17899(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_17899 import replay_saved_acq_event_17899

    return replay_saved_acq_event_17899(data)


def _saved_sup_event_53772(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_53772 import replay_saved_sup_event_53772

    return replay_saved_sup_event_53772(data)


def _saved_acq_event_23143(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_23143 import replay_saved_acq_event_23143

    return replay_saved_acq_event_23143(data)


def _saved_sup_event_23770(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_23770 import replay_saved_sup_event_23770

    return replay_saved_sup_event_23770(data)


def _saved_acq_event_35942(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_35942 import replay_saved_acq_event_35942

    return replay_saved_acq_event_35942(data)


def _saved_sup_event_56943(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_56943 import replay_saved_sup_event_56943

    return replay_saved_sup_event_56943(data)


def _saved_acq_event_40079(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_40079 import replay_saved_acq_event_40079

    return replay_saved_acq_event_40079(data)


def _saved_sup_event_53656(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_53656 import replay_saved_sup_event_53656

    return replay_saved_sup_event_53656(data)


def _saved_acq_event_42457(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_42457 import replay_saved_acq_event_42457

    return replay_saved_acq_event_42457(data)


def _saved_sup_event_47072(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_47072 import replay_saved_sup_event_47072

    return replay_saved_sup_event_47072(data)


def _saved_acq_event_34531(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_34531 import replay_saved_acq_event_34531

    return replay_saved_acq_event_34531(data)


def _saved_sup_event_30817(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_event_30817 import replay_saved_sup_event_30817

    return replay_saved_sup_event_30817(data)


def _saved_acq_event_23449(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_23449 import replay_saved_acq_event_23449

    return replay_saved_acq_event_23449(data)


def _saved_sup_position_t3_event(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_position_t3_event import replay_saved_sup_position_t3

    return replay_saved_sup_position_t3(data)


def _saved_acq_event_26012(data):
    from DeviceServers.control.elyse_acq.vi_simulation.acquisition_event_26012 import replay_saved_acq_event_26012

    return replay_saved_acq_event_26012(data)


def _saved_sup_position_t2_event(data):
    from DeviceServers.control.elyse_acq.vi_simulation.supervision_position_t2_event import replay_saved_sup_position_t2

    return replay_saved_sup_position_t2(data)


REPLAY_OPERATIONS = {
    "saved_acq_event_33620": _saved_acq_control_event,
    "saved_sup_frequency": _saved_sup_frequency_event,
    "saved_acq_event_22879": _saved_acq_event_22879,
    "saved_sup_gain": _saved_sup_gain_event,
    "saved_acq_event_45123": _saved_acq_event_45123,
    "saved_sup_event_65050": _saved_sup_event_65050,
    "saved_acq_event_34191": _saved_acq_event_34191,
    "saved_sup_event_38030": _saved_sup_event_38030,
    "saved_acq_event_43634": _saved_acq_event_43634,
    "saved_sup_event_53716": _saved_sup_event_53716,
    "saved_acq_event_31552": _saved_acq_event_31552,
    "saved_sup_event_18780": _saved_sup_event_18780,
    "saved_acq_event_48846": _saved_acq_event_48846,
    "saved_sup_event_33463": _saved_sup_event_33463,
    "saved_acq_event_8896": _saved_acq_event_8896,
    "saved_sup_event_38707": _saved_sup_event_38707,
    "saved_acq_event_23113": _saved_acq_event_23113,
    "saved_sup_event_5847": _saved_sup_event_5847,
    "saved_acq_event_38732": _saved_acq_event_38732,
    "saved_sup_event_26490": _saved_sup_event_26490,
    "saved_acq_event_37991": _saved_acq_event_37991,
    "saved_sup_event_23880": _saved_sup_event_23880,
    "saved_acq_event_17899": _saved_acq_event_17899,
    "saved_sup_event_53772": _saved_sup_event_53772,
    "saved_acq_event_23143": _saved_acq_event_23143,
    "saved_sup_event_23770": _saved_sup_event_23770,
    "saved_acq_event_35942": _saved_acq_event_35942,
    "saved_sup_event_56943": _saved_sup_event_56943,
    "saved_acq_event_40079": _saved_acq_event_40079,
    "saved_sup_event_53656": _saved_sup_event_53656,
    "saved_acq_event_42457": _saved_acq_event_42457,
    "saved_sup_event_47072": _saved_sup_event_47072,
    "saved_acq_event_34531": _saved_acq_event_34531,
    "saved_sup_event_30817": _saved_sup_event_30817,
    "saved_acq_event_23449": _saved_acq_event_23449,
    "saved_sup_position_t3": _saved_sup_position_t3_event,
    "saved_acq_event_26012": _saved_acq_event_26012,
    "saved_sup_position_t2": _saved_sup_position_t2_event,
    "saved_card_init": _saved_card_init,
    "saved_sup_helper": _saved_sup_helper,
    "saved_numeric": _saved_numeric,
    "saved_psp_reads": _saved_psp_reads,
    "saved_sup_reads": _saved_sup_reads,
    "saved_stop": _saved_stop,
    "saved_dispatch": _saved_dispatch,
    "saved_requests": _saved_requests,
    "saved_cleanup": _saved_cleanup,
    "saved_initializer": _saved_initializer,
    "saved_ni6220": _saved_ni6220,
    "saved_timing": _saved_timing,
    "saved_xnode": _saved_xnode,
    "machine_frequency": _frequency,
    "parameter_page": _parameter,
    "page_command": _command,
    "magnet_currents": _magnets,
    "synchronisation": _synchronisation,
    "monitoring": _monitoring,
    "display_flags": _display,
    "profiles": _profiles,
    "journal": _journal,
    "video_tools": _video_tools,
    "camera_thresholds": _camera_thresholds,
    "camera_channel": _camera_channel,
    "video_density": _video_density,
    "save_image": _save_image,
    "slit_position": _slit_position,
    "diagnostic_position": _diagnostic_position,
    "faraday_position": _faraday_position,
    "faraday_tab": _faraday_tab,
    "laser_mirror": _laser_mirror,
    "slit_supply": _slit_supply,
    "centroid_reset": _centroid_reset,
    "translator_selection": _translator_selection,
    "translator_stop": _translator_stop,
    "translator_loop_selector": _translator_loop_selector,
    "load_toggle": _load_toggle,
    "validate_load": _validate_load,
    "tree_selection": _tree_selection,
    "motor_initialization": _motor_initialization,
    "motor_jog": _motor_jog,
    "motor_jog_poll": _motor_jog_poll,
    "motor_error": _motor_error,
    "autotune_plan": _autotune_plan,
    "autotune_iteration": _autotune_iteration,
    "autotune_outer": _autotune_outer,
    "autotune_camera": _autotune_camera,
}


def replay(body):
    exact(body, ("operation", "inputs"))
    operation = body["operation"]
    if type(operation) is not str or operation not in REPLAY_OPERATIONS:
        raise ValueError("Unsupported replay operation; no dispatch operation exists")
    return {
        "schema_version": 1,
        "operation": operation,
        "input_origin": "OPERATOR_SUPPLIED_REPLAY",
        "execution_allowed": False,
        "physical_status": "NOT_EXECUTED",
        "result": json_value(REPLAY_OPERATIONS[operation](body["inputs"])),
    }
