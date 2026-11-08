"""Implementation for json_value and related operations."""


def _bind_elyse_supervision_service_parts_json_value(api):
    """Bind implementation to the owning module and its runtime state."""

    def json_value(value):
        if api.is_dataclass(value):
            return {f.name: api.json_value(getattr(value, f.name)) for f in api.fields(value)}
        if isinstance(value, api.Enum):
            return value.value
        if isinstance(value, bytes):
            return {"base64": api.base64.b64encode(value).decode("ascii")}
        if isinstance(value, dict):
            return {str(k): api.json_value(v) for k, v in value.items()}
        if isinstance(value, (set, frozenset)):
            return sorted((api.json_value(v) for v in value), key=lambda v: api.json.dumps(v))
        if isinstance(value, (tuple, list)):
            return [api.json_value(v) for v in value]
        if isinstance(value, float) and not api.math.isfinite(value):
            raise ValueError("Non-finite result is outside the web replay contract")
        return value

    json_value.__module__ = api.__name__
    json_value.__qualname__ = "json_value"

    def exact(value, keys):
        if type(value) is not dict or set(value) != set(keys):
            raise ValueError(f"Required fields: {', '.join(keys)}")
        return value

    exact.__module__ = api.__name__
    exact.__qualname__ = "exact"

    def snapshot():
        parameter = api.model("parameter_page_events")
        commands = api.model("page_command_events")
        registry = api.model("magnet_registry").candidate_registry()
        diagnostics = api.model("diagnostic_events")
        digital = api.model("digital_command_events")
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
                "arrows": [api.json_value(r) for r in rules],
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
        coverage = api.json.loads(
            (
                api.SUPERVISION_ROOT / "python_reconstruction" / "EVENT_MODEL_COVERAGE.json"
            ).read_text(encoding="utf-8")
        )
        source = (
            api.SUPERVISION_ROOT
            / "extracted"
            / "PILOTAGE_ELYSE_SUP"
            / "SUPERVISION_VIs"
            / "0_SUP_ELYSE.vi"
        )
        observed = (
            api.hashlib.sha256(source.read_bytes()).hexdigest().upper()
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
                "tool_fields": list(api.model("video_events").VIDEO_TOOL_FIELDS),
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
                    for s in api.model("translator_selection").TranslatorSelection
                ],
                "polling_expression": api.json_value(
                    api.model("translator_stop").POLLING_SELECTOR_EXPRESSION
                ),
                "selection_commands_position": False,
                "selection_switches_other_cameras_off": False,
                "stop_implementation_allowed": False,
                "establishes_safe_state": False,
            },
            "file_controls": {
                "path_states": [
                    {"value": s.name, "label": s.value}
                    for s in api.model("load_events").LegacyPathState
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
                "jog_labels": list(api.model("motion_events").MOTION_CONTROLS[:4]),
                "jog_event_indices": [28, 29],
                "error_event_indices": [27, 28, 29],
                "autotune_stages": [
                    stage.name for stage in api.model("autotune_events").AutotuneStage
                ],
                "autotune_channels": [2, 3],
                "autotune_stage_order": list(
                    api.model("autotune_events").plan_autotune().stage_order
                ),
                "motor_numbers_origin": "OPERATOR_SUPPLIED_SYMBOLIC_U32",
                "physical_motion_performed": False,
                "physical_position_observed": False,
                "engineering_units_qualified": False,
                "autotune_complete_runtime": False,
            },
            "registry": api.model("magnet_readback").magnet_display_snapshot(registry),
            "coverage": coverage,
            "source_integrity": {
                "matches": observed == api.SOURCE_SHA256,
                "expected_main_sha256": api.SOURCE_SHA256,
                "observed_main_sha256": observed,
            },
            "replay_operations": list(api.REPLAY_OPERATIONS),
            "limits": [
                "Supplied replay inputs are not live telemetry or safety permission",
                "No PSP/Tango/DAQmx writes or hardware dispatch endpoint",
                "Unverified magnet routes and limits; no retired DAQmx fallback",
                "Bounded models, not qualified whole-VI replacements",
                "Error Code Database.vi excluded from active migration",
            ],
        }

    snapshot.__module__ = api.__name__
    snapshot.__qualname__ = "snapshot"

    def _parameter(data):
        api.exact(data, ("page", "current_dps", "arrows", "procedures", "numeric_newval"))
        module = api.model("parameter_page_events")
        page = module.ParameterPage(data["page"])
        return api._with_acquisition_preview(
            module.plan_parameter_page_change(
                page,
                data["current_dps"],
                data["arrows"],
                data["procedures"],
                data["numeric_newval"],
            )
        )

    _parameter.__module__ = api.__name__
    _parameter.__qualname__ = "_parameter"

    def _command(data):
        api.exact(data, ("page", "current_dps", "newval"))
        module = api.model("page_command_events")
        return api._with_acquisition_preview(
            module.plan_page_command_change(
                module.CommandPage(data["page"]),
                data["current_dps"],
                data["newval"],
            )
        )

    _command.__module__ = api.__name__
    _command.__qualname__ = "_command"

    def _with_acquisition_preview(plan):
        """Decode the saved first-true DPS dispatcher, never construct an engine.

    A selected procedure is a single-snapshot reference, not server acceptance,
    an acknowledgement, a cleared flag, commissioned ownership or execution.
    Hardware steps/targets are deliberately not exposed as dispatch arguments.
    """
        from DeviceServers.control.elyse_acq import dps_bridge

        result = api.json_value(plan)
        projected = plan.projected_dps
        downstream = {
            "state": "NO_NEW_DPS_WRITE",
            "execution_allowed": False,
            "acceptance_observed": False,
            "physical_ownership_verified": False,
        }
        if projected is not None:
            supplied = dict(projected)
            names = api.model("page_command_events").DPS_FIELDS
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

    _with_acquisition_preview.__module__ = api.__name__
    _with_acquisition_preview.__qualname__ = "_with_acquisition_preview"

    def _magnets(data):
        module = api.importlib.import_module(f"{api.MODEL_PACKAGE}.service.shadow")
        registry = api.model("magnet_registry").candidate_registry()
        return module.preview_currents(registry, module.parse_preview(registry, data))

    _magnets.__module__ = api.__name__
    _magnets.__qualname__ = "_magnets"

    def _synchronisation(data):
        api.exact(data, ("current_dps", "oldval", "newval", "stored_flash_index"))
        return api.model("synchronisation_events").plan_synchronisation_change(
            data["current_dps"],
            data["oldval"],
            data["newval"],
            data["stored_flash_index"],
        )

    _synchronisation.__module__ = api.__name__
    _synchronisation.__qualname__ = "_synchronisation"

    def _monitoring(data):
        api.exact(data, ("current", "previous", "finished_late_previous"))
        module = api.model("timed_monitoring")
        names = tuple(f.name for f in api.fields(module.MonitoringCounters))
        current = module.MonitoringCounters(**api.exact(data["current"], names))
        previous = module.MonitoringCounters(**api.exact(data["previous"], names))
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

    _monitoring.__module__ = api.__name__
    _monitoring.__qualname__ = "_monitoring"

    def _display(data):
        api.exact(data, ("c3", "c4", "eps"))
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

    _display.__module__ = api.__name__
    _display.__qualname__ = "_display"

    def _profiles(data):
        api.exact(data, ("iteration", "average_count", "buffers", "x_samples", "y_samples"))
        iteration, count = data["iteration"], data["average_count"]
        if type(iteration) is not int or iteration < 0:
            raise ValueError("Nonnegative integer iteration required")
        if type(count) is not int or not 1 <= count <= 100:
            raise ValueError("Web replay average_count must be an integer in 1..100")
        buffers = api.exact(data["buffers"], ("x", "y"))
        vectors = [data["x_samples"], data["y_samples"]]
        for axis in ("x", "y"):
            if type(buffers[axis]) is not list or len(buffers[axis]) != count:
                raise ValueError("Explicit profile buffers must match average_count")
            vectors.extend(buffers[axis])
        if any(type(v) is not list or not 1 <= len(v) <= 4096 for v in vectors):
            raise ValueError("Bounded nonempty numeric profile vectors required")
        if any(type(n) not in (int, float) for v in vectors for n in v):
            raise ValueError("Profile samples must be numeric, not strings or booleans")
        module = api.model("profiles")
        return module.update_profile_buffers(
            iteration,
            count,
            module.ProfileBuffers(
                tuple(map(tuple, buffers["x"])), tuple(map(tuple, buffers["y"]))
            ),
            data["x_samples"],
            data["y_samples"],
        )

    _profiles.__module__ = api.__name__
    _profiles.__qualname__ = "_profiles"

    def _journal(data):
        names = ("message_input", "journal_in", "display_timestamp", "file_timestamp")
        api.exact(data, (*names, "file_path_token"))
        if any(type(data[name]) is not str for name in names):
            raise ValueError("Journal byte inputs require explicit base64 strings")
        module = api.model("journal")
        projection = module.project_journal_bytes(
            **{name: api.base64.b64decode(data[name], validate=True) for name in names}
        )
        return {
            "projection": projection,
            "file_intent": module.plan_journal_file_write(
                projection, file_path_token=data["file_path_token"]
            ),
            "encoding": "EXPLICIT_BYTES_BASE64",
            "file_written": False,
        }

    _journal.__module__ = api.__name__
    _journal.__qualname__ = "_journal"

    def _external_error(value):
        """Typed scenario input, never a manufactured driver success result."""
        api.exact(value, ("status", "code", "source"))
        if type(value["status"]) is not bool:
            raise ValueError("External error status requires an explicit Boolean")
        code = value["code"]
        if type(code) is not int or not -(2**31) <= code <= 2**31 - 1:
            raise ValueError("External error code requires an I32 integer")
        if type(value["source"]) is not str:
            raise ValueError("External error source requires an explicit string")
        return api.model("fw102x_errors").ErrorCluster(**value)

    _external_error.__module__ = api.__name__
    _external_error.__qualname__ = "_external_error"

    def _video_tools(data):
        api.exact(data, ("values", "final_property_error"))
        values = data["values"]
        if type(values) is not list:
            raise ValueError("Video tools require an ordered Boolean array")
        return api.model("video_events").plan_video_tools(
            tuple(values),
            final_property_error=api._external_error(data["final_property_error"]),
        )

    _video_tools.__module__ = api.__name__
    _video_tools.__qualname__ = "_video_tools"

    def _camera_event(data, planner):
        api.exact(data, ("final_error", "formatted_text"))
        text = data["formatted_text"]
        if text is not None and type(text) is not str:
            raise ValueError("External formatter result must be a string or null")
        return planner(
            final_error=api._external_error(data["final_error"]), formatted_text=text
        )

    _camera_event.__module__ = api.__name__
    _camera_event.__qualname__ = "_camera_event"

    def _save_image(data):
        api.exact(data, ("new_value", "resolved_year", "dialog_cancelled", "selected_path"))
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
        return api.model("video_events").plan_save_image(
            data["new_value"],
            resolved_year=year,
            dialog_cancelled=cancelled,
            selected_path=path,
        )

    _save_image.__module__ = api.__name__
    _save_image.__qualname__ = "_save_image"

    def _slit_position(data):
        api.exact(data, ("axe_h", "gap_h"))
        return api.model("slit_position").plan_slit_position_change(
            data["axe_h"], data["gap_h"]
        )

    _slit_position.__module__ = api.__name__
    _slit_position.__qualname__ = "_slit_position"

    def _diagnostic_position(data):
        api.exact(data, ("station", "selector"))
        module = api.model("diagnostic_events")
        if type(data["station"]) is not str:
            raise ValueError("Diagnostic station requires T1, T2 or T3")
        return module.plan_diagnostic_position_change(
            module.DiagnosticStation(data["station"]), data["selector"]
        )

    _diagnostic_position.__module__ = api.__name__
    _diagnostic_position.__qualname__ = "_diagnostic_position"

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
                api.exact(entry, ("frame_index", "cluster"))
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
        result = api.json_value(plan)
        for frame, projected in zip(plan.frames, result["frames"]):
            projected["fresh_local_cluster_read_required"] = (
                frame.fresh_local_cluster_read_required
            )
            projected["projected_cluster"] = (
                api.model("digital_command_events").project_digital_frame(
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

    _digital_projection.__module__ = api.__name__
    _digital_projection.__qualname__ = "_digital_projection"

    def _faraday_position(data):
        api.exact(data, ("station", "new_value", "frame_snapshots"))
        if type(data["station"]) is not int:
            raise ValueError("Faraday station requires an exact integer 1, 2 or 3")
        module = api.model("digital_command_events")
        return api._digital_projection(
            module.plan_faraday_position_change(
                module.FaradayStation(data["station"]), data["new_value"]
            ),
            data["frame_snapshots"],
        )

    _faraday_position.__module__ = api.__name__
    _faraday_position.__qualname__ = "_faraday_position"

    def _faraday_tab(data):
        api.exact(data, ("new_value", "en_states", "frame_snapshots"))
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
        plan = api.model("digital_command_events").plan_faraday_tab_change(
            data["new_value"], en_states=states
        )
        return api._digital_projection(plan, data["frame_snapshots"])

    _faraday_tab.__module__ = api.__name__
    _faraday_tab.__qualname__ = "_faraday_tab"

    def _laser_mirror(data):
        api.exact(data, ("new_value", "frame_snapshots"))
        plan = api.model("digital_command_events").plan_laser_mirror_change(data["new_value"])
        return api._digital_projection(plan, data["frame_snapshots"])

    _laser_mirror.__module__ = api.__name__
    _laser_mirror.__qualname__ = "_laser_mirror"

    def _slit_supply(data):
        api.exact(data, ("new_value", "frame_snapshots"))
        plan = api.model("digital_command_events").plan_slit_supply_change(data["new_value"])
        return api._digital_projection(plan, data["frame_snapshots"])

    _slit_supply.__module__ = api.__name__
    _slit_supply.__qualname__ = "_slit_supply"

    def _translator_selection(data):
        api.exact(data, ("selection",))
        if type(data["selection"]) is not int:
            raise ValueError("Translator selection requires an exact integer 1..4")
        module = api.model("translator_selection")
        return module.plan_translator_selection(
            module.TranslatorSelection(data["selection"])
        )

    _translator_selection.__module__ = api.__name__
    _translator_selection.__qualname__ = "_translator_selection"

    return {
        "json_value": json_value,
        "exact": exact,
        "snapshot": snapshot,
        "_parameter": _parameter,
        "_command": _command,
        "_with_acquisition_preview": _with_acquisition_preview,
        "_magnets": _magnets,
        "_synchronisation": _synchronisation,
        "_monitoring": _monitoring,
        "_display": _display,
        "_profiles": _profiles,
        "_journal": _journal,
        "_external_error": _external_error,
        "_video_tools": _video_tools,
        "_camera_event": _camera_event,
        "_save_image": _save_image,
        "_slit_position": _slit_position,
        "_diagnostic_position": _diagnostic_position,
        "_digital_projection": _digital_projection,
        "_faraday_position": _faraday_position,
        "_faraday_tab": _faraday_tab,
        "_laser_mirror": _laser_mirror,
        "_slit_supply": _slit_supply,
        "_translator_selection": _translator_selection,
    }
