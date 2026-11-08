"""Implementation for _json_helper_diagnostics and related operations."""


def _bind_acquisition_backend_parts_json_helper_diagnostics(api):
    """Bind implementation to the owning module and its runtime state."""

    def _json_helper_diagnostics(value):
        try:
            return api.json.loads(api.json.dumps(value, allow_nan=False))
        except (TypeError, ValueError):
            # Never expose process handles/native objects through HTTP JSON.
            return dict(returned_type=type(value).__name__, retained=False,
                        reason="Only finite JSON-compatible helper diagnostics are retained")

    _json_helper_diagnostics.__module__ = api.__name__
    _json_helper_diagnostics.__qualname__ = "_json_helper_diagnostics"

    class _DemoFocalCommand(object):
        """Pure RAM fixture, not qualification of a COM port or native driver."""
        simulated = True
        resources_verified = True

        def ensure_ready(self):
            pass

        def ensure_quiescent(self):
            pass

        def snapshot(self):
            return dict(simulated=True, pending_worker_count=0, workers=[],
                        hardware_acknowledged=False, physical_output_state="UNKNOWN")

        def execute(self, output_enabled, cancelled):
            if type(output_enabled) is not bool or not callable(cancelled):
                raise ValueError("Explicit Boolean simulated Focal command required")
            if cancelled():
                raise RuntimeError("Simulated Focal command cancelled")
            return dict(simulated=True, output_enabled=output_enabled,
                        native_calls=False, hardware_acknowledged=False)

    _DemoFocalCommand.__module__ = api.__name__
    _DemoFocalCommand.__qualname__ = "_DemoFocalCommand"

    class _OwnedFocalOff(object):
        """General OFF uses the same retained worker owner as standalone ON/OFF."""
        def __init__(self, backend):
            self.backend = backend

        def ensure_ready(self):
            self.backend._ensure_focal_ready()

        def __call__(self):
            self.ensure_ready()
            return self.backend._stage_focal_helper("1_Focales OFF.vi", lambda: False)

    _OwnedFocalOff.__module__ = api.__name__
    _OwnedFocalOff.__qualname__ = "_OwnedFocalOff"

    class _StageState(object):
        """Local command memory is not hardware readback or a PSP delivery ACK."""

        def _reset_stage_state(self):
            # Saved root frame 33052 resets local refs 44/36 to these literals.
            # C3/C4 images come from the reviewed startup commands, not DI values.
            self._stage_status = {44: (False,) * 77, 36: (False,) * 29}
            self.stage_update_indicator = None  # No qualified startup assignment.
            self.stage_publications = {}
            self.stage_publication_count = 0
            self.last_cooling_guard = None
            self._pending_stage_restorations = {}
            self._stage_restoration_origin = None
            self._stage_restoration_attempts = []
            self._stage_restoration_attempt_count = 0
            self._focal_helper_results = {}
            self._focal_quiescence_error = None

        def _ensure_focal_quiescent(self):
            # A timed-out ON worker must not race a subsequent OFF or DO write.
            # This process-ownership guard does not infer electrical output state.
            try:
                self.focal_command.ensure_quiescent()
            except Exception as error:
                self._focal_quiescence_error = type(error).__name__ + ": " + str(error)
                raise
            self._focal_quiescence_error = None

        def _ensure_focal_ready(self):
            if getattr(self.focal_command, "resources_verified", False) is not True:
                raise RuntimeError("Focal commands blocked: serial resources not commissioned")
            self.focal_command.ensure_ready()

        def _stage_focal_helper(self, helper_name, cancelled):
            if helper_name not in ("1_Focales ON.vi", "1_Focales OFF.vi"):
                raise ValueError("Unqualified Focal helper")
            enabled = helper_name == "1_Focales ON.vi"
            self._ensure_focal_quiescent()
            result = dict(helper=helper_name, output_enabled=enabled, state="EXECUTING",
                          simulated=self._stage_simulated, hardware_acknowledged=False)
            self._focal_helper_results[helper_name] = result
            try:
                returned = self.focal_command.execute(enabled, cancelled)
                self._ensure_focal_quiescent()
            except Exception as error:
                result.update(state="FAILED_OR_CANCELLED", error_type=type(error).__name__, error=str(error))
                raise
            retained = api._json_helper_diagnostics(returned)
            result.update(state="CALLBACK_COMPLETED_NOT_HARDWARE_ACK", returned=retained)
            return returned

        def _focal_diagnostics(self):
            snapshot = getattr(self.focal_command, "snapshot", None)
            if not callable(snapshot):
                return dict(available=False, hardware_acknowledged=False)
            try:
                return api._json_helper_diagnostics(snapshot())
            except Exception as error:
                return dict(available=False, error_type=type(error).__name__, error=str(error),
                            hardware_acknowledged=False)

        def _remember_stage_restorations(self, error, cooling=False):
            report = getattr(error, "result" if cooling else "report", None)
            if not isinstance(report, dict):
                return
            pending = report.get("pending_output_restorations", ())
            if not pending:
                return
            for entry in pending:
                bank, index, baseline = (17, entry[0], entry[1]) if cooling else tuple(entry)
                if (bank not in (15, 17) or type(index) is not int
                        or not 0 <= index < (32 if bank == 15 else 40)
                        or type(baseline) is not bool):
                    raise ValueError("Invalid pending source-command restoration")
                self._pending_stage_restorations[(bank, index)] = baseline
            self._stage_restoration_origin = api.copy.deepcopy(report)

        def _retry_stage_restorations(self):
            """Python recovery policy, not an inferred native General sequence.

        Only known unfinished fields are patched to their preprocedure image.
        Any failed retry aborts the next procedure before its whole-bank writes,
        so an uncertain asserted pulse cannot be echoed by an unrelated stop.
        """
            failures = []
            for bank in sorted(set(bank for bank, index in self._pending_stage_restorations)):
                changes = tuple((index, baseline) for (entry_bank, index), baseline in
                                sorted(self._pending_stage_restorations.items()) if entry_bank == bank)
                attempt = dict(bank=bank, changes=changes, succeeded=False)
                self._stage_restoration_attempt_count += 1
                attempt["attempt"] = self._stage_restoration_attempt_count
                try:
                    self._stage_write_local(bank, changes)
                except Exception as error:
                    attempt.update(error_type=type(error).__name__, error=str(error))
                    failures.append("Pending stage restoration bank {0}: {1}: {2}".format(
                        bank, type(error).__name__, error))
                else:
                    attempt["succeeded"] = True
                    for index, baseline in changes:
                        self._pending_stage_restorations.pop((bank, index), None)
                self._stage_restoration_attempts.append(attempt)
                # Bounded diagnostics, not telemetry history. Count exposes truncation.
                self._stage_restoration_attempts = self._stage_restoration_attempts[-128:]
            if self.procedure is not None:
                self.procedure.update(
                    pending_output_restorations=self._stage_pending_snapshot(),
                    stage_restoration_attempts=api.copy.deepcopy(self._stage_restoration_attempts))
            if failures:
                raise api.GeneralStopError(failures)

        def _stage_pending_snapshot(self):
            return [(bank, index, baseline) for (bank, index), baseline in
                    sorted(self._pending_stage_restorations.items())]

        def _stage_read_local(self, bank):
            if bank in (15, 17):
                name = "C4_DIO96_DO" if bank == 15 else "C3_DIO96_DO"
                return tuple(self.commanded_digital[name])
            if bank in (36, 44):
                return tuple(self._stage_status[bank])
            if bank == 35:
                return self.stage_update_indicator
            raise ValueError("Unqualified stage local bank")

        def _stage_assign_status(self, eps, dps):
            for bank, assignments, name in ((44, eps, "EPS"), (36, dps, "DPS")):
                changes = tuple(dict(assignments).items())
                if changes:
                    self._stage_write_local(bank, changes)

        def _stage_write_local(self, bank, changes):
            changes = tuple(changes)
            if bank == 35:
                if changes != ((-1, True),):
                    raise ValueError("Only the source literal update indicator is qualified")
                self.stage_update_indicator = True
                return
            sizes = {15: 32, 17: 40, 36: 29, 44: 77}
            if bank not in sizes or not changes:
                raise ValueError("Unqualified stage local assignment")
            current = self._stage_read_local(bank)
            if len(current) != sizes[bank] or any(type(value) is not bool for value in current):
                raise ValueError("Complete Boolean command/status bank required")
            changed = list(current)
            seen = set()
            for index, value in changes:
                if (type(index) is not int or not 0 <= index < sizes[bank]
                        or type(value) is not bool or index in seen):
                    raise ValueError("Qualified Boolean field assignment required")
                seen.add(index)
                changed[index] = value
            if bank in (15, 17):
                name = "C4_DIO96_DO" if bank == 15 else "C3_DIO96_DO"
                # Commit remembered image only after the owner reports success.
                self._stage_write_digital(name, changed)
                self.commanded_digital[name] = tuple(changed)
            else:
                self._stage_status[bank] = tuple(changed)
                name = "EPS" if bank == 44 else "DPS"
                self.software_status_assignments[name].update(dict(changes))

        def _stage_publish(self, name, bank, snapshot):
            qualified = {"DPS": (36, 29), "EPS": (44, 77), "C4_OUT_DIO96": (15, 32)}
            values = tuple(snapshot)
            if (name not in qualified or bank != qualified[name][0]
                    or len(values) != qualified[name][1]
                    or any(type(value) is not bool for value in values)):
                raise ValueError("Qualified complete publication snapshot required")
            self.stage_publication_count += 1
            # Bounded RAM: retain one snapshot per name, never telemetry history.
            self.stage_publications[name] = dict(
                name=name, local_bank=bank, values=values,
                sequence=self.stage_publication_count,
                transport="LOCAL_RAM_REPLACEMENT_NOT_PSP",
                psp_delivered=False, hardware_acknowledged=False,
                snapshot_interpretation="Supplied source-frame read snapshot; not a physical output readback")

        def _stage_snapshot(self):
            return dict(
                local_banks={"C3_OUT_DIO96": self._stage_read_local(17),
                             "C4_OUT_DIO96": self._stage_read_local(15),
                             "EPS": self._stage_read_local(44),
                             "DPS": self._stage_read_local(36)},
                update_indicator=self.stage_update_indicator,
                update_indicator_interpretation="Remembered literal software assignment, initially unknown",
                interpretation="DO banks are last successful commands; EPS/DPS are software memory, not readback or permits",
                publications=api.copy.deepcopy(self.stage_publications),
                publication_count=self.stage_publication_count,
                publication_storage="bounded_latest_per_name_in_RAM",
                psp_delivery_acknowledged=False, hardware_acknowledged=False,
                stage_controls_verified=self.stage_controls_verified,
                cooling_trip_verified=self.cooling_trip_verified,
                ht_controls_verified=self.ht_controls_verified,
                focal_controls_verified=self.focal_controls_verified,
                focal_resources_verified=getattr(self.focal_command, "resources_verified", False) is True,
                focal_helper_results=api.copy.deepcopy(self._focal_helper_results),
                focal_quiescence_error=self._focal_quiescence_error,
                focal_command_diagnostics=self._focal_diagnostics(),
                pending_output_restorations=self._stage_pending_snapshot(),
                restoration_origin=api.copy.deepcopy(self._stage_restoration_origin),
                restoration_attempts=api.copy.deepcopy(self._stage_restoration_attempts),
                restoration_attempt_count=self._stage_restoration_attempt_count,
                restoration_diagnostics_retained_limit=128,
                last_cooling_guard=api.copy.deepcopy(self.last_cooling_guard))

        def _stage_preflight(self, operator_confirmed, operation=None):
            if operator_confirmed is not True:
                raise ValueError("Explicit local stage confirmation required")
            if self.stage_controls_verified is not True:
                raise RuntimeError("Stage commands blocked: stage controls not commissioned")
            if operation in api.HT_STAGE_OPERATIONS and self.ht_controls_verified is not True:
                # Deliberate Python commissioning gate, not a recovered VI permit.
                # Starting HT can energize the already-commanded startup voltage;
                # it is independent of extended-stop feedback qualification.
                raise RuntimeError("HT stage commands blocked: HT controls not commissioned")
            if operation in api.FOCAL_STAGE_OPERATIONS and self.focal_controls_verified is not True:
                raise RuntimeError("Focal stage commands blocked: Focal controls not commissioned")
            if self.control_profile == "general_only_test":
                raise RuntimeError("General-only profile forbids other stage commands")
            self._stage_require_initialized()
            if operation is not None and operation.endswith(".start"):
                require_known_ht = getattr(self, "_require_known_source_commands", None)
                if require_known_ht is not None:
                    require_known_ht()
            if (getattr(self, "_stage_simulated", True) is False
                    and any(self.commanded_digital["C4_DIO96_DO"][i] is not False for i in (0, 2))):
                raise RuntimeError("Unreleased General/RAZ pulse requires General Arret before another stage")
            retry_counters = getattr(self, "_retry_source_counter_stops", None)
            if retry_counters is not None:
                retry_counters()

        def execute_stage(self, operation, cancel, operator_confirmed=False, new_value=True):
            """Execute one qualified local stage path; no public/remote mutation API."""
            self._stage_preflight(operator_confirmed, operation)
            from .acquisition_stage_execution import execute_stage
            self.procedure = dict(name=operation, state="EXECUTING", frame=None,
                                  control_profile=self.control_profile, hardware_acknowledged=False)

            def observe(frame, source_uid):
                self.procedure.update(frame=frame, source_uid=source_uid)

            def focal_helper(helper_name):
                return self._stage_focal_helper(helper_name, cancel.is_set)

            try:
                # Validate the source operation even before any recovery write.
                # False NewVal is source-empty and must never drain old pulses.
                preflight = execute_stage(
                    operation, self._stage_read_local, self._stage_write_local,
                    self._stage_publish, cancel.wait, cancel.is_set, observe,
                    operator_confirmed=True, new_value=False, focal_helper=focal_helper)
                if type(new_value) is not bool:
                    raise ValueError("Explicit Boolean NewVal required")
                if not new_value:
                    self.procedure.update(state="SOURCE_NEWVAL_FALSE_NOOP", report=preflight)
                    return preflight
                if operation in api.FOCAL_STAGE_OPERATIONS:
                    self._ensure_focal_ready()
                self._ensure_focal_quiescent()
                self._retry_stage_restorations()
                result = execute_stage(
                    operation, self._stage_read_local, self._stage_write_local,
                    self._stage_publish, cancel.wait, cancel.is_set, observe,
                    operator_confirmed=True, new_value=new_value, focal_helper=focal_helper)
            except Exception as error:
                self._remember_stage_restorations(error)
                self.procedure.update(state="INTERRUPTED_OR_FAILED",
                                      report=api.copy.deepcopy(getattr(error, "report", None)))
                raise
            self.procedure.update(state="SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK",
                                  report=api.copy.deepcopy(result))
            return result

        def execute_cooling_guard(self, snapshot, cancel):
            """Saved raw cooling predicate only; not a klystron safety permit."""
            if (self.stage_controls_verified is not True or self.cooling_trip_verified is not True
                    or self.control_profile == "general_only_test"):
                self.last_cooling_guard = dict(
                    status="DISABLED", effects_enabled=False, hardware_acknowledged=False,
                    reason="Both commissioning gates and a non-General-only profile are required")
                return api.copy.deepcopy(self.last_cooling_guard)
            self._stage_require_initialized()
            if not isinstance(snapshot, dict) or snapshot.get("simulated") is not self._stage_simulated:
                raise ValueError("Current backend raw input snapshot required")
            from .acquisition_cooling_trip import execute_cooling_trip, cooling_trip_predicate
            try:
                c4 = tuple(snapshot["banks"]["C4_DIO96_DI"]["values"])
                c3 = tuple(snapshot["banks"]["C3_DIO96_DI"]["values"])
            except (KeyError, TypeError):
                raise ValueError("Complete current C4/C3 raw input banks required")

            def observe(frame, source_uid):
                self.procedure = dict(name="cooling.timeout_trip", state="EXECUTING",
                                      frame=frame, source_uid=source_uid,
                                      hardware_acknowledged=False)

            try:
                if cooling_trip_predicate(c4, c3):
                    self._ensure_focal_quiescent()
                    self._retry_stage_restorations()
                result = execute_cooling_trip(
                    c4, c3, self._stage_read_local, self._stage_write_local,
                    self._stage_publish, cancel.wait, cancel.is_set, observe,
                    enabled_arm=True)
            except Exception as error:
                self._remember_stage_restorations(error, cooling=True)
                report = getattr(error, "result", None)
                if report is None:
                    report = dict(status="recovery_or_preflight_failed", hardware_acknowledged=False,
                                  error_type=type(error).__name__, error=str(error),
                                  pending_output_restorations=self._stage_pending_snapshot())
                self.last_cooling_guard = api.copy.deepcopy(report)
                if self.procedure is not None:
                    self.procedure["state"] = "INTERRUPTED_OR_FAILED"
                raise
            self.last_cooling_guard = api.copy.deepcopy(result)
            if self.procedure is not None and self.procedure.get("name") == "cooling.timeout_trip":
                self.procedure.update(state="SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK",
                                      report=api.copy.deepcopy(result))
            return result

    _StageState.__module__ = api.__name__
    _StageState.__qualname__ = "_StageState"

    return {
        "_json_helper_diagnostics": _json_helper_diagnostics,
        "_DemoFocalCommand": _DemoFocalCommand,
        "_OwnedFocalOff": _OwnedFocalOff,
        "_StageState": _StageState,
    }
