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
        self.assertCountEqual(attrs, ["_ensure_focal_quiescent", "close", "_reset_stage_state"])
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
                     "focal_controls_verified"):
            self.assertIs(ast.literal_eval(defaults[flag]), False)

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
