"""Source-only boundary checks; no external XML, NI imports or network calls."""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "DeviceServers/control/elyse_acq/business_logic_contract.py"
SPEC = importlib.util.spec_from_file_location("_elyse_business_logic_contract", MODULE)
CONTRACT_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT_MODULE)


def tree(path):
    return ast.parse((ROOT / path).read_text(encoding="utf-8"))


def literal_assignment(path, name):
    for node in tree(path).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("Missing source assignment: " + name)


def class_method(path, class_name, method_name):
    cls = next(node for node in tree(path).body if isinstance(node, ast.ClassDef)
               and node.name == class_name)
    return next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                and node.name == method_name)


class BusinessLogicContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = CONTRACT_MODULE.business_logic_contract()

    def test_independent_nested_snapshots_and_strict_json(self):
        json.dumps(self.contract, allow_nan=False)
        self.contract["layers"]["xp_gui_runtime"]["snapshot_bank_names"].clear()
        self.contract["sources"]["original_acquisition"]["vi_sha256"] = "changed"
        fresh = CONTRACT_MODULE.business_logic_contract()
        self.assertEqual(len(fresh["layers"]["xp_gui_runtime"]["snapshot_bank_names"]), 6)
        self.assertNotEqual(fresh["sources"]["original_acquisition"]["vi_sha256"], "changed")

    def test_registry_import_has_no_runtime_dependencies(self):
        parsed = tree("DeviceServers/control/elyse_acq/business_logic_contract.py")
        self.assertFalse(any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(parsed)))
        self.assertFalse(any(isinstance(node, ast.Call) for node in parsed.body))

    def test_fail_closed_semantic_boundaries(self):
        self.assertFalse(self.contract["replacement_ready"])
        self.assertFalse(self.contract["qualifies_hardware_operation"])
        self.assertFalse(self.contract["deployed_source_identity_verified"])
        self.assertTrue(self.contract["originals_require_external_evidence"])
        self.assertFalse(self.contract["is_live_status"])
        runtime = self.contract["layers"]["xp_gui_runtime"]
        for key in (
            "auto_initialize", "initialize_is_read_only", "source_cooling_trip_live",
            "deinitialize_is_electrical_stop", "software_eps_is_physical_ack",
            "commanded_outputs_are_physical_readback", "general_stop_is_original_outer_stop",
            "chauffage_prema_focales_start_controls_enabled",
            "legacy_full_general_stop_includes_ht_supply_stop",
            "extended_ht_stop_is_source_equivalent", "http_hardware_commands_enabled",
        ):
            self.assertIs(runtime[key], False, key)

    def test_six_bank_runtime_and_twenty_seven_bank_bridge_are_distinct(self):
        path = "legacy/xp_acq_agent/elyse_agent/hardware_plan.py"
        expected = [row[0] for name in ("AI_BANKS", "DI_BANKS")
                    for row in literal_assignment(path, name)]
        runtime = self.contract["layers"]["xp_gui_runtime"]
        bridge = self.contract["layers"]["copied_labview_telemetry_bridge"]
        banks = literal_assignment("legacy/xp_acq_agent/elyse_agent/shared_state.py", "BANKS")
        self.assertEqual(runtime["snapshot_bank_names"], expected)
        self.assertEqual(runtime["snapshot_bank_count"], len(expected))
        self.assertEqual(bridge["bank_count"], len(banks))
        self.assertFalse(bridge["interchangeable_with_xp_gui_snapshot"])
        self.assertFalse(self.contract["parity_gaps"]["bank_schemas"]["equivalent"])

    def test_recovery_and_new_runtime_view_never_enable_hardware_control(self):
        runtime = self.contract["layers"]["xp_gui_runtime"]
        self.assertEqual(runtime["runtime_protocol_version"], 2)
        self.assertTrue(runtime["dirty_owner_blocks_initialization"])
        self.assertTrue(runtime["state_revision_fencing"])
        self.assertFalse(runtime["build_fingerprint_is_deployment_attestation"])
        self.assertFalse(runtime["qualified_process_recovery_checker_shipped"])
        self.assertFalse(runtime["automatic_ni_recovery"])
        supervisor = runtime["cold_supervisor"]
        self.assertTrue(supervisor["restart_only_after_confirmed_nonzero_child_exit"])
        self.assertEqual(supervisor["restart_budget"], 3)
        self.assertTrue(supervisor["qualified_local_prior_child_recovery_api"])
        self.assertFalse(supervisor["production_quiescence_verifier_included"])
        for key in ("normal_exit_restarts", "kills_live_or_unresponsive_card_owner",
                    "initializes_cards_or_replays_commands", "startup_installed_by_this_change"):
            self.assertFalse(supervisor[key])
        self.assertFalse(runtime["command_admission"]["default_enabled"])
        self.assertFalse(runtime["command_admission"]["wired_to_gui_http_or_tango"])
        web = self.contract["layers"]["web_supervision"]
        self.assertFalse(web["python_runtime_hardware_commands_enabled"])
        self.assertFalse(web["python_runtime_falls_back_to_labview_or_simulator"])
        self.assertEqual(web["python_runtime_path"], "/api/elyse/acquisition/runtime")
        self.assertEqual(web["python_runtime_tango_caller_wait_seconds"], 2.0)
        self.assertFalse(web["python_runtime_replaces_unresolved_read_worker"])
        self.assertTrue(web["browser_age_includes_http_json_elapsed"])

    def test_requested_sample_discrepancy_is_tied_to_two_source_implementations(self):
        gap = self.contract["parity_gaps"]["ni6071e_requested_samples"]
        original = tree("DeviceServers/control/elyse_acq/vi_simulation/runtime_io.py")
        supplied = [ast.literal_eval(keyword.value) for node in ast.walk(original)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "read" for keyword in node.keywords
                    if keyword.arg == "samples_per_channel"]
        self.assertEqual(supplied, [gap["original_requested_samples_per_channel"]])
        method = class_method("legacy/xp_acq_agent/elyse_agent/hardware_tasks.py",
                              "LegacyCardTasks", "read_analog_means")
        defaults = dict(zip([arg.arg for arg in method.args.args][-len(method.args.defaults):],
                            method.args.defaults))
        self.assertEqual(ast.literal_eval(defaults["samples_per_channel"]),
                         gap["xp_requested_samples_per_channel"])
        backend = class_method("legacy/xp_acq_agent/elyse_agent/acquisition_backend.py",
                               "CardBackend", "read_snapshot")
        calls = [node for node in ast.walk(backend) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "read_analog_means"]
        self.assertEqual(len(calls), 1)
        self.assertNotIn("samples_per_channel", [keyword.arg for keyword in calls[0].keywords])
        self.assertFalse(gap["equivalent"])
        self.assertFalse(gap["ratio_is_measured_averaging_time_or_precision"])
        self.assertFalse(gap["blind_change_to_sample_count_is_authorized"])

    def test_catalog_counts_and_provenance_do_not_enable_controls(self):
        model = self.contract["layers"]["pure_acquisition_model"]
        raw = (ROOT / model["catalog"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), model["catalog_sha256"])
        catalog = json.loads(raw)
        self.assertFalse(catalog["hardware_enabled"])
        self.assertEqual(len(catalog["procedures"]), model["stage_procedures"])

        def count_frames(frames):
            return sum(1 + sum(count_frames(effect[1]) for effect in effects
                               if effect[0] == "subsequence") for _, effects in frames)

        self.assertEqual(sum(count_frames(row["frames"]) for row in catalog["procedures"].values()),
                         model["stage_frames_including_nested"])
        self.assertEqual(catalog["source_archive_sha256"],
                         self.contract["sources"]["original_acquisition"]["xml_archive_sha256"])
        self.assertFalse(model["live_stage_controls"])
        self.assertTrue(model["source_cooling_trip_modeled"])
        self.assertFalse(model["source_cooling_trip_live"])

    def test_deinitialization_releases_not_stops(self):
        close = class_method("legacy/xp_acq_agent/elyse_agent/acquisition_backend.py", "CardBackend", "close")
        attrs = [node.func.attr for node in ast.walk(close)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        self.assertCountEqual(attrs, ["_ensure_focal_quiescent", "close", "_reset_stage_state",
                                      "_reset_source_controls"])
        self.assertFalse(self.contract["parity_gaps"]["lifecycle"]["resource_release_is_electrical_off"])

    def test_integrated_stage_paths_and_cooling_remain_separately_uncommissioned(self):
        runtime = self.contract["layers"]["xp_gui_runtime"]
        implementation = runtime["source_stage_execution"]
        paths = literal_assignment(
            "legacy/xp_acq_agent/elyse_agent/acquisition_stage_execution.py", "SUPPORTED_OPERATIONS")
        self.assertEqual(implementation["implemented"], list(paths))
        raw = (ROOT / self.contract["layers"]["pure_acquisition_model"]["catalog"]).read_bytes()
        catalog = json.loads(raw)["procedures"]
        def count_frames(frames):
            return sum(1 + sum(count_frames(effect[1]) for effect in effects
                               if effect[0] == "subsequence") for _, effects in frames)
        self.assertEqual(implementation["source_frame_count"],
                         sum(count_frames(catalog[path]["frames"]) for path in paths))
        self.assertTrue(implementation["source_frame_count_includes_nested"])
        self.assertTrue(implementation["nominal_paths_executable"])
        self.assertFalse(implementation["default_commissioned"])
        self.assertFalse(implementation["psp_delivery_acknowledged"])
        self.assertTrue(implementation["standalone_ht_requires_separate_commissioning"])
        self.assertFalse(implementation["standalone_ht_default_commissioned"])
        self.assertFalse(implementation["standalone_ht_procedure_is_voltage_ramp"])
        self.assertFalse(implementation["standalone_ht_completion_is_zero_or_off_ack"])
        self.assertFalse(implementation["legacy_general_stop_clears_ht_release_requirement"])
        self.assertTrue(implementation["focal_requires_separate_commissioning"])
        self.assertFalse(implementation["focal_default_commissioned"])
        self.assertTrue(implementation["native_on_workers_must_quiesce_before_other_outputs_or_release"])
        self.assertFalse(implementation["native_worker_exit_is_physical_off_ack"])
        self.assertTrue(runtime["cooling_trip_execution"]["executable"])
        self.assertFalse(runtime["cooling_trip_execution"]["default_commissioned"])
        backend = class_method("legacy/xp_acq_agent/elyse_agent/acquisition_backend.py",
                               "CardBackend", "__init__")
        defaults = dict(zip([arg.arg for arg in backend.args.args][-len(backend.args.defaults):],
                            backend.args.defaults))
        for flag in ("stage_controls_verified", "cooling_trip_verified", "ht_controls_verified",
                     "focal_controls_verified", "counter_controls_verified",
                     "counter_timing_controls_verified", "ht_voltage_controls_verified", "outer_stop_verified"):
            self.assertIs(ast.literal_eval(defaults[flag]), False)

    def test_original_xml_archive_is_external_evidence_not_claimed_bundled(self):
        source = self.contract["sources"]["original_acquisition"]
        self.assertFalse(source["xml_archive_bundled"])
        self.assertTrue(source["xml_archive_external_location_hash_verified_at_review"])
        self.assertFalse(source["xml_archive_review_is_current_availability_or_deployment_attestation"])
        self.assertIn("external reviewed evidence", source["xml_archive_path_role"])
        self.assertTrue(source["xml_archive_external_evidence_path"].startswith("C:/dev/pyconlyse/"))
        self.assertEqual(len(source["xml_archive_sha256"]), 64)
        # Availability is an explicit provenance boundary, not an existence
        # test against another chat's ignored/local evidence directory.
        self.assertTrue(self.contract["originals_require_external_evidence"])

    def test_source_impulsion_counts_match_two_paths_and_nine_saved_frames(self):
        path = "legacy/xp_acq_agent/elyse_agent/acquisition_impulsion.py"
        implementation = self.contract["layers"]["xp_gui_runtime"]["source_impulsion_execution"]
        paths = literal_assignment(path, "SUPPORTED_OPERATIONS")
        frames = literal_assignment(path, "FRAME_UIDS")
        self.assertEqual(implementation["implemented"], list(paths))
        self.assertEqual(implementation["source_events"], [23, 24])
        self.assertEqual(implementation["source_frame_count"], sum(map(len, frames.values())))
        self.assertEqual(implementation["physical_counter_numbers"], [3, 4])
        self.assertEqual(implementation["maximum_polls_if_done_false"], 42)
        self.assertEqual(implementation["poll_wait_ms_including_final_iteration"], 1)
        self.assertFalse(implementation["poll_limit_is_wall_clock_deadline"])
        self.assertFalse(implementation["completion_is_physical_ack"])
        self.assertFalse(implementation["releases_resources"])

    def test_ht_transfer_contract_maps_only_c9_field0_without_operating_permit(self):
        path = "legacy/xp_acq_agent/elyse_agent/acquisition_ht_voltage.py"
        implementation = self.contract["layers"]["xp_gui_runtime"]["source_ht_voltage_transfer"]
        self.assertEqual(implementation["logical_bank"], literal_assignment(path, "BANK_NAME"))
        self.assertEqual(implementation["logical_field"], literal_assignment(path, "HT_FIELD"))
        self.assertEqual(implementation["gain_to_driver_volts"], literal_assignment(path, "HT_GAIN_TO_VOLTS"))
        self.assertEqual(implementation["driver_domain_kv"], [
            literal_assignment(path, "HT_DRIVER_MIN_KV"),
            literal_assignment(path, "HT_DRIVER_MAX_KV")])
        self.assertTrue(implementation["whole_bank_commit_preserves_other_fields"])
        self.assertTrue(implementation["ambiguous_commit_blocks_later_c9_commands"])
        for key in ("driver_domain_is_operating_permit", "automatic_retry_or_rollback",
                    "is_voltage_ramp_or_zero_procedure", "completion_is_physical_ack",
                    "releases_resources"):
            self.assertFalse(implementation[key], key)

    def test_counter_timing_contract_preserves_source_routing_conversion_and_reads(self):
        path = "legacy/xp_acq_agent/elyse_agent/acquisition_counter_timing.py"
        implementation = self.contract["layers"]["xp_gui_runtime"]["source_counter_timing_transfer"]
        for key, constant in (("logical_bank", "BANK_NAME"), ("local_bank", "BANK_LOCAL"),
                              ("bank_size", "BANK_SIZE"), ("selector_field", "SELECTOR_INDEX"),
                              ("source_helper_sha256", "SOURCE_HELPER_SHA256")):
            self.assertEqual(implementation[key], literal_assignment(path, constant))
        self.assertEqual(implementation["source_selector_guard"], "0 < n < 17")
        self.assertEqual(implementation["proved_integer_selectors"], [1, 16])
        self.assertEqual(implementation["physical_counter_mapping"],
                         "q = floor((n - 1.0) / 2.0) in DBL, then I32 Index Array; C10 ctr0..7")
        self.assertFalse(implementation["fractional_selector_routing_qualified"])
        self.assertTrue(implementation["fractional_in_bounds_selector_routing_qualified"])
        self.assertEqual(implementation["finite_valid_task_selector_interval"], "1 <= n < 17")
        self.assertEqual(implementation["source_admitted_invalid_task_interval"], "0 < n < 1 -> q=-1")
        self.assertFalse(implementation["native_invalid_task_return_qualified"])
        self.assertTrue(implementation["native_error_wire_preview_implemented"])
        self.assertEqual(implementation["source_clear_error_code_default"], 0)
        self.assertFalse(implementation["clear_errors_resets_driver_or_task"])
        self.assertEqual(implementation["saved_simple_handler_dialog_mode"], 1)
        self.assertEqual(implementation["inspected_local_2020_default_buttons"], ["Continue"])
        self.assertFalse(implementation["saved_dialog_mode_input_wired"])
        self.assertFalse(implementation["deployed_xp_handler_binary_qualified"])
        self.assertFalse(implementation["automatic_continue_or_python_exception_clear"])
        self.assertEqual(implementation["delay_field_mapping"], "2 * q")
        self.assertEqual(implementation["width_field_mapping"], "2 * q + 1")
        self.assertIn("saturating I32, ties to even", implementation["timing_conversion"])
        self.assertIn("low 32 bits as U32", implementation["timing_conversion"])
        self.assertEqual(implementation["property_codes_in_order"],
                         list(literal_assignment(path, "PROPERTY_CODES")))
        limit = literal_assignment(path, "POLL_LIMIT_INDEX")
        self.assertEqual(implementation["pulse_done_or_iteration_greater_than"], limit)
        self.assertEqual(implementation["maximum_polls_if_done_false"], limit + 2)
        self.assertEqual(implementation["poll_wait_ms_including_final_iteration"], 1)
        self.assertEqual(implementation["independent_bank_reads"], 3)
        self.assertEqual(implementation["selector_reset_value"], -1.0)
        self.assertTrue(implementation["publication_uses_independently_reread_bank"])
        self.assertEqual(implementation["publication_transport"], "LOCAL_RAM_REPLACEMENT_NOT_PSP")
        self.assertTrue(implementation["nominal_path_executable"])
        for key in ("selects_c11",
                    "conversion_is_driver_acceptance_or_operating_permit",
                    "poll_limit_is_wall_clock_deadline", "atomic_snapshot_or_compare_exchange",
                    "psp_delivery_acknowledged", "automatic_property_retry_or_rollback",
                    "completion_is_physical_ack", "releases_resources",
                    "native_error_or_dialog_equivalence", "native_timing_equivalence"):
            self.assertFalse(implementation[key], key)
        self.assertTrue(implementation["configuration_ambiguity_blocks_starts"])
        gap = self.contract["parity_gaps"]["counter_timing_native_integration"]
        self.assertTrue(gap["local_source_path_transferred"])
        self.assertTrue(gap["fractional_selector_coercion_proven"])
        self.assertTrue(all(value is False for key, value in gap.items()
                            if key not in ("local_source_path_transferred", "fractional_selector_coercion_proven")))

    def test_counter_timing_release_latch_covers_every_retimed_counter_not_only_3_4(self):
        implementation = self.contract["layers"]["xp_gui_runtime"]["source_counter_timing_transfer"]
        release = implementation["release_latch"]
        self.assertEqual(release["snapshot_key"], "counter_timing_stop_required")
        self.assertTrue(release["tracks_every_retimed_counter"])
        self.assertTrue(release["latches_backend_dispatch_not_queue_admission"])
        self.assertEqual(release["legacy_general_stop_acknowledges"], [])
        self.assertEqual(release["extended_general_or_outer_stop_acknowledges"], [3, 4])
        self.assertEqual(release["impulsion_stop_acknowledges"], [3, 4])
        self.assertTrue(release["other_counters_require_explicit_electrical_off_confirmation"])
        self.assertFalse(release["command_stop_ack_is_physical_off"])
        configure = class_method("legacy/xp_acq_agent/elyse_agent/acquisition_runtime.py",
                                 "AcquisitionRuntime", "configure_counter_timing")
        def latch_additions(method):
            return [node for node in ast.walk(method) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr == "add"
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "_counter_timing_stop_required"]

        self.assertEqual(latch_additions(configure), [])
        owner = class_method("legacy/xp_acq_agent/elyse_agent/acquisition_runtime.py",
                             "AcquisitionRuntime", "_run")
        additions = latch_additions(owner)
        self.assertEqual(len(additions), 1)
        self.assertEqual(ast.dump(additions[0].args[0]),
                         ast.dump(ast.parse('decode_counter_bank(counter_timing_command)["counter"]',
                                            mode="eval").body))
        callbacks = [node for node in ast.walk(owner) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute)
                     and node.func.attr == "configure_counter_timing"]
        self.assertEqual(len(callbacks), 1)
        self.assertLess(additions[0].lineno, callbacks[0].lineno)

    def test_outer_stop_counts_and_threshold_are_not_general_event6_or_release(self):
        path = "legacy/xp_acq_agent/elyse_agent/acquisition_outer_stop.py"
        implementation = self.contract["layers"]["xp_gui_runtime"]["source_outer_controlled_stop"]
        module = tree(path)
        plan = next(node.value for node in module.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "CONTROLLED_STOP"
                            for target in node.targets))
        frames = [node for node in ast.walk(plan) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == "_phase"]
        self.assertEqual(implementation["source_phase_count"], len(plan.elts))
        self.assertEqual(implementation["source_frame_count_including_wrappers"], len(frames))
        waits = [ast.literal_eval(node.elts[1]) for node in ast.walk(plan)
                 if isinstance(node, ast.Tuple) and len(node.elts) == 2
                 and isinstance(node.elts[0], ast.Constant) and node.elts[0].value == "wait"]
        self.assertEqual(implementation["source_fixed_wait_ms_excluding_ramp_and_polls"], sum(waits))
        executor = next(node for node in module.body if isinstance(node, ast.FunctionDef)
                        and node.name == "execute_outer_stop")
        defaults = dict(zip([arg.arg for arg in executor.args.args][-len(executor.args.defaults):],
                            executor.args.defaults))
        self.assertEqual(implementation["python_max_ramp_decrements"],
                         ast.literal_eval(defaults["max_ramp_steps"]))
        self.assertEqual(implementation["ht_command_stop_comparison"], "C9NI6703[0] < 6.6")
        self.assertTrue(implementation["duplicate_dps_eps_frames_preserved"])
        self.assertEqual(implementation["preserved_analog_fields"],
                         {"C6NI6703": [8], "C7NI6703": [2]})
        for key in ("aliases_general_event6_or_deinitialize", "ramp_bound_is_source_property",
                    "uses_physical_ht_feedback_or_zero_extension", "final_flags_are_physical_off_ack",
                    "releases_resources", "native_failure_or_timing_equivalence",
                    "prior_failure_allows_cooling_off_or_final_flags"):
            self.assertFalse(implementation[key], key)

    def test_new_source_control_gates_are_independent_local_and_default_false(self):
        runtime = self.contract["layers"]["xp_gui_runtime"]
        config = json.loads((ROOT / "legacy/xp_acq_agent/config.acquisition.example.json").read_text())
        flags = set()
        for section in ("source_impulsion_execution", "source_ht_voltage_transfer",
                        "source_outer_controlled_stop", "source_counter_timing_transfer"):
            implementation = runtime[section]
            self.assertFalse(implementation["default_commissioned"])
            self.assertTrue(implementation["local_only"])
            self.assertTrue(implementation["requires_stage_controls_verified"])
            flag = implementation["commissioning_flag"]
            self.assertIs(config[flag], False)
            flags.add(flag)
        self.assertEqual(flags, {"counter_controls_verified", "counter_timing_controls_verified",
                                 "ht_voltage_controls_verified", "outer_stop_verified"})
        self.assertFalse(runtime["http_hardware_commands_enabled"])
        for method in ("execute_impulsion", "configure_counter_timing", "set_ht_voltage", "outer_controlled_stop"):
            adapter = class_method("legacy/xp_acq_agent/elyse_agent/acquisition_source_controls.py",
                                   "SourceControls", method)
            called = [node.func.attr for node in ast.walk(adapter) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute)]
            self.assertNotIn("close", called)

    def test_counter_pulse_property_is_not_task_done_and_stream_properties_are_explicit(self):
        implementation = self.contract["layers"]["xp_gui_runtime"]["ni_driver_semantics"]
        path = "legacy/xp_acq_agent/elyse_agent/hardware_tasks.py"
        pulse = class_method(path, "LegacyCardTasks", "read_counter_pulse_done")
        attrs = {node.attr for node in ast.walk(pulse) if isinstance(node, ast.Attribute)}
        self.assertIn("co_pulse_done", attrs)
        self.assertNotIn("is_task_done", attrs)
        self.assertEqual(implementation["counter_completion_source_property"], "CO.PulseDone (6414)")
        self.assertFalse(implementation["task_is_task_done_is_pulse_done"])
        self.assertTrue(implementation["counter_property_result_requires_exact_bool"])
        writer = class_method(path, "LegacyCardTasks", "write_counter_ticks")
        properties = [node.targets[0].attr for node in writer.body if isinstance(node, ast.Assign)
                      and len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute)]
        self.assertEqual(properties, implementation["counter_tick_properties_in_order"])
        self.assertTrue(implementation["counter_tick_write_validates_all_u32_before_first_write"])
        self.assertTrue(implementation["counter_tick_property_failure_retains_owner"])
        self.assertFalse(implementation["counter_tick_write_automatically_manages_lifecycle"])
        lifecycle_calls = {node.func.attr for node in ast.walk(writer) if isinstance(node, ast.Call)
                           and isinstance(node.func, ast.Attribute)}
        self.assertFalse(lifecycle_calls & {"start", "stop", "close", "sleep", "is_task_done",
                                          "read_counter_pulse_done"})
        factory = next(node for node in tree(path).body if isinstance(node, ast.FunctionDef)
                       and node.name == "create_legacy_card_tasks")
        two_cards_loop = next(node for node in ast.walk(factory)
                              if isinstance(node, ast.For) and isinstance(node.iter, ast.Subscript)
                              and isinstance(node.iter.value, ast.Name) and node.iter.value.id == "AI_BANKS")
        self.assertEqual(ast.literal_eval(two_cards_loop.iter.slice.upper), 2)
        assignments = {node.targets[0].attr: node.value for node in ast.walk(two_cards_loop)
                       if isinstance(node, ast.Assign) and len(node.targets) == 1
                       and isinstance(node.targets[0], ast.Attribute)
                       and isinstance(node.targets[0].value, ast.Attribute)
                       and node.targets[0].value.attr == "in_stream"}
        self.assertEqual(assignments["relative_to"].attr, implementation["ni6071e_read_relative_to"])
        self.assertIs(ast.literal_eval(assignments["auto_start"]), implementation["ni6071e_read_auto_start"])
        self.assertFalse(implementation["ni6220_stream_properties_inferred"])
        self.assertFalse(implementation["finite_read_sample_parity_closed"])
        self.assertFalse(self.contract["parity_gaps"]["ni6071e_requested_samples"]["equivalent"])

    def test_source_hash_matches_supervision_adapter_not_deployment(self):
        expected = literal_assignment("web/backend/elyse_supervision_service.py", "SOURCE_SHA256")
        self.assertEqual(self.contract["sources"]["original_supervision"]["vi_sha256"], expected)
        self.assertFalse(self.contract["sources"]["original_supervision"]["display_colour_is_control_admission"])

    def test_runtime_uses_cold_read_only_http_configuration(self):
        facade = tree("DeviceServers/control/elyse_acq/DS_AcqRuntime.py")
        port = next(node for node in ast.walk(facade) if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "xp_port"
                            for target in node.targets))
        default = next(keyword.value for keyword in port.value.keywords if keyword.arg == "default_value")
        self.assertEqual(self.contract["layers"]["xp_gui_runtime"]["http_port"], ast.literal_eval(default))
        runtime_class = next(node for node in tree("legacy/xp_acq_agent/elyse_agent/acquisition_runtime.py").body
                             if isinstance(node, ast.ClassDef) and node.name == "AcquisitionRuntime")
        names = {node.name for node in runtime_class.body if isinstance(node, ast.FunctionDef)}
        self.assertTrue(set(self.contract["layers"]["xp_gui_runtime"]["local_operation_implementations"]) <= names)
        handler = next(node for node in tree("legacy/xp_acq_agent/elyse_agent/acquisition_http.py").body
                       if isinstance(node, ast.ClassDef) and node.name == "_Handler")
        denied_methods = set()
        for node in handler.body:
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
                    and node.value.id == "_no_control"):
                denied_methods.update(target.id for target in node.targets if isinstance(target, ast.Name))
        self.assertEqual(denied_methods, {"do_POST", "do_PUT", "do_DELETE", "do_PATCH"})


if __name__ == "__main__":
    unittest.main()
