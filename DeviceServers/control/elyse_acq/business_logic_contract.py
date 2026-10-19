"""Static migration boundaries, not authorization or a live health report.

Importing this module performs no I/O. Each call returns independent JSON data;
callers cannot modify a shared registry. Source identities refer to reviewed
saved files, never to an asserted deployment or electrically qualified system.
Changing a fact here does not enable a command, change timing or qualify safety.
"""


def business_logic_contract():
    """Describe the deliberately separate source, replay and runtime layers."""
    return {
        "schema_version": 1,
        "scope": "STATIC_BUSINESS_LOGIC_MIGRATION_CONTRACT",
        "replacement_ready": False,
        "is_live_status": False,
        "qualifies_hardware_operation": False,
        "deployed_source_identity_verified": False,
        "originals_require_external_evidence": True,
        "sources": {
            "original_acquisition": {
                "vi": "0_ACQ_ELYSE.vi",
                "vi_sha256": "6FE801E023CF755FBDE89B4AD17854D5FC08447517010C2122E66C9F3DF5C3CF",
                "xml_archive": "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip",
                "xml_archive_sha256": "6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527",
                "complete_native_runtime_equivalence_proven": False,
                "admission_evidence": "docs/ELYSE_ACQ_STAGE_ADMISSION_2026-10-19.json",
                "fault_evidence": "docs/ELYSE_ACQ_RUNNING_FAULT_RESPONSE_2026-10-19.json",
                "sampling_validator": "tools/validate_acq_runtime_io_frame.py",
                "stage_eps_ok_is_physical_ack": False,
                "reviewed_cooling_guard": "(C4_IN[19] OR C4_IN[38]) AND ((NOT C3_IN[0]) OR (NOT C3_IN[6]))",
                "cooling_guard_is_klystron_stage_trip": False,
                "physical_input_polarity_qualified": False,
            },
            "original_supervision": {
                "vi_sha256": "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B",
                "source_identity_reference": "web/backend/elyse_supervision_service.py:SOURCE_SHA256",
                "complete_native_runtime_equivalence_proven": False,
                "display_colour_is_control_admission": False,
            },
        },
        "layers": {
            "pure_acquisition_model": {
                "module": "legacy/xp_acq_agent/elyse_agent/acquisition_stage_model.py",
                "catalog": "legacy/xp_acq_agent/data/modulator_stage_catalog.json",
                "catalog_sha256": "A9D821E7519EA50F6B35593E58C78129EC7D8A7BFEDCC06098E247BEF011A0B0",
                "stage_procedures": 16,
                "stage_frames_including_nested": 120,
                "hardware_callbacks_accepted": False,
                "live_stage_controls": False,
                "source_cooling_trip_modeled": True,
                "source_cooling_trip_live": False,
                "external_returns": "explicit supplied values; missing is not successful",
            },
            "xp_gui_runtime": {
                "module": "legacy/xp_acq_agent/elyse_agent/acquisition_runtime.py",
                "backend": "legacy/xp_acq_agent/elyse_agent/acquisition_backend.py",
                "http_port": 8771,
                "http_port_role": "reviewed default; configurable, not a protocol constant",
                "http_read_paths": ["/status", "/snapshot"],
                "http_hardware_commands_enabled": False,
                "local_operation_implementations": [
                    "initialize", "general_start", "general_stop", "deinitialize", "request_shutdown"
                ],
                "auto_initialize": False,
                "configuration_default_profile": "legacy_full",
                "full_general_start_preflights_focal_stop": True,
                "general_only_test_is_full_shutdown": False,
                "initialize_is_read_only": False,
                "initialize_effects": ["configure NI tasks", "start saved counters", "write saved AO/DO images"],
                "source_cooling_trip_live": False,
                "chauffage_prema_focales_start_controls_enabled": False,
                "snapshot_bank_names": [
                    "C1_NI6071E_AI", "C2_NI6071E_AI", "C11_NI6220_AI",
                    "C3_DIO96_DI", "C4_DIO96_DI", "C5_DIO96_DI"
                ],
                "snapshot_bank_count": 6,
                "snapshot_schema": "python_daqmx_acquisition",
                "readback_sampling": "sequential; not atomic",
                "normal_reads_during_general_procedure": False,
                "normal_reads_in_fault": False,
                "deinitialize_is_electrical_stop": False,
                "commanded_outputs_are_physical_readback": False,
                "software_eps_is_physical_ack": False,
                "general_stop_is_original_outer_stop": False,
                "legacy_full_general_stop_includes_ht_supply_stop": False,
                "extended_ht_stop_is_source_equivalent": False,
                "extended_ht_stop_requires_separate_feedback_qualification": True,
            },
            "copied_labview_telemetry_bridge": {
                "module": "legacy/xp_acq_agent/elyse_agent/shared_state.py",
                "bank_count": 27,
                "snapshot_schema": "copied_labview_telemetry",
                "storage": "latest snapshot plus bounded in-flight retry in RAM",
                "atomic_across_banks": False,
                "initializes_or_controls_cards": False,
                "interchangeable_with_xp_gui_snapshot": False,
            },
            "everest_tango": {
                "labview_bridge_facade": "DeviceServers/control/elyse_acq/DS_AcqTelemetry.py",
                "python_runtime_facade": "DeviceServers/control/elyse_acq/DS_AcqRuntime.py",
                "labview_attribute": "telemetry_json",
                "python_runtime_attribute": "runtime_json",
                "hardware_command_routes": False,
                "initializes_cards": False,
                "facades_are_interchangeable": False,
            },
            "web_supervision": {
                "telemetry_adapter": "web/backend/acq_telemetry_api.py",
                "source_model_adapter": "web/backend/elyse_supervision_service.py",
                "telemetry_expected_schema": "copied_labview_telemetry",
                "telemetry_hardware_commands_enabled": False,
                "replay_results_are_live_telemetry": False,
                "source_display_equivalence_is_hardware_qualification": False,
            },
        },
        "parity_gaps": {
            "ni6071e_requested_samples": {
                "cards": ["C1_NI6071E_AI", "C2_NI6071E_AI"],
                "source_io_callers": ["startup", "runtime", "controlled_stop"],
                "original_requested_samples_per_channel": 1000,
                "xp_requested_samples_per_channel": 10,
                "equivalent": False,
                "ratio_is_measured_averaging_time_or_precision": False,
                "blind_change_to_sample_count_is_authorized": False,
                "review_required": "finite task timing, triggers, read count and timeout together",
                "source_probe_sample_count": "unwired; not inferred from the three explicit I/O literals",
            },
            "bank_schemas": {
                "xp_runtime_banks": 6,
                "labview_bridge_banks": 27,
                "equivalent": False,
                "missing_banks_may_be_filled_with_guessed_values": False,
            },
            "lifecycle": {
                "pure_frame_coverage_is_live_control_coverage": False,
                "loop_stop_is_stage_shutdown": False,
                "general_event6_is_outer_controlled_stop": False,
                "resource_release_is_electrical_off": False,
                "software_completion_is_physical_readiness": False,
            },
        },
    }
