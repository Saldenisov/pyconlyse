"""Web adapter for evidence-backed SuperVision models, never a hardware adapter.

Imports repository-owned reconstructions without copying their arithmetic. Inputs
are operator-supplied replay data, not trusted Acquisition telemetry. No procedure
engine, Tango proxy, PSP publisher, file writer or background loop is constructed.
"""

from sys import modules as _refactor_modules

from elyse_supervision_service_parts_json_value import _bind_elyse_supervision_service_parts_json_value

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


_elyse_supervision_service_parts_json_value = _bind_elyse_supervision_service_parts_json_value(_refactor_modules[__name__])
json_value = _elyse_supervision_service_parts_json_value["json_value"]


exact = _elyse_supervision_service_parts_json_value["exact"]


snapshot = _elyse_supervision_service_parts_json_value["snapshot"]


def _frequency(data):
    exact(data, ("new_value",))
    return model("machine_frequency").plan_machine_frequency_change(data["new_value"])


_parameter = _elyse_supervision_service_parts_json_value["_parameter"]


_command = _elyse_supervision_service_parts_json_value["_command"]


_with_acquisition_preview = _elyse_supervision_service_parts_json_value["_with_acquisition_preview"]


_magnets = _elyse_supervision_service_parts_json_value["_magnets"]


_synchronisation = _elyse_supervision_service_parts_json_value["_synchronisation"]


_monitoring = _elyse_supervision_service_parts_json_value["_monitoring"]


_display = _elyse_supervision_service_parts_json_value["_display"]


_profiles = _elyse_supervision_service_parts_json_value["_profiles"]


_journal = _elyse_supervision_service_parts_json_value["_journal"]


_external_error = _elyse_supervision_service_parts_json_value["_external_error"]


_video_tools = _elyse_supervision_service_parts_json_value["_video_tools"]


_camera_event = _elyse_supervision_service_parts_json_value["_camera_event"]


def _camera_thresholds(data):
    return _camera_event(data, model("video_events").plan_threshold_mouse_up)


def _camera_channel(data):
    return _camera_event(data, model("video_events").plan_camera_channel_change)


def _video_density(data):
    exact(data, ())
    return model("video_events").plan_density_change()


_save_image = _elyse_supervision_service_parts_json_value["_save_image"]


_slit_position = _elyse_supervision_service_parts_json_value["_slit_position"]


_diagnostic_position = _elyse_supervision_service_parts_json_value["_diagnostic_position"]


_digital_projection = _elyse_supervision_service_parts_json_value["_digital_projection"]


_faraday_position = _elyse_supervision_service_parts_json_value["_faraday_position"]


_faraday_tab = _elyse_supervision_service_parts_json_value["_faraday_tab"]


_laser_mirror = _elyse_supervision_service_parts_json_value["_laser_mirror"]


_slit_supply = _elyse_supervision_service_parts_json_value["_slit_supply"]


def _centroid_reset(data):
    exact(data, ())
    return model("diagnostic_events").plan_centroid_average_reset()


_translator_selection = _elyse_supervision_service_parts_json_value["_translator_selection"]
del _elyse_supervision_service_parts_json_value


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
