"""Explicit legacy NI startup + bounded input reads. Python 3.4 compatible.

No import of nidaqmx, task creation, discovery or writes until initialize().
No arbitrary setpoint API. Startup images are fixed reviewed legacy constants;
General Marche/Arret are separate, explicitly confirmed local procedures.
Additional source-qualified stages have independent, default-disabled gates.
"""
from __future__ import division

import csv
import copy
import io
import json
import math
import os
import time

from .hardware_plan import AI_BANKS, DI_BANKS
from .hardware_tasks import create_legacy_card_tasks, PartialTaskCreationError
from .acquisition_procedures import (
    execute_general_start, execute_general_stop, execute_general_only_stop, GeneralStopError,
)
from .chroma_focal_stop import ChromaFocalStop
from .hardware_plan import analog_startup_logical_image, digital_startup_image, load_ao_calibration
from .acquisition_source_controls import SourceControls
from .acquisition_ht_shutdown import (
    execute_ht_shutdown, execute_ht_supply_stop, validate_policy,
    PULSE_STOP_TASKS, PULSE_STOP_EPS, PULSE_STOP_DPS,
)


CONTROL_PROFILES = ("legacy_full", "general_only_test", "extended_ht_stop")
HT_STAGE_OPERATIONS = ("alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset")
FOCAL_STAGE_OPERATIONS = ("focales.start", "focales.stop")
_LEGACY_CHROMA_STOP_TYPE = ChromaFocalStop


class AcquisitionCancelled(Exception):
    pass


def _json_helper_diagnostics(value):
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError):
        # Never expose process handles/native objects through HTTP JSON.
        return dict(returned_type=type(value).__name__, retained=False,
                    reason="Only finite JSON-compatible helper diagnostics are retained")


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


class _OwnedFocalOff(object):
    """General OFF uses the same retained worker owner as standalone ON/OFF."""
    def __init__(self, backend):
        self.backend = backend

    def ensure_ready(self):
        self.backend._ensure_focal_ready()

    def __call__(self):
        self.ensure_ready()
        return self.backend._stage_focal_helper("1_Focales OFF.vi", lambda: False)


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
        retained = _json_helper_diagnostics(returned)
        result.update(state="CALLBACK_COMPLETED_NOT_HARDWARE_ACK", returned=retained)
        return returned

    def _focal_diagnostics(self):
        snapshot = getattr(self.focal_command, "snapshot", None)
        if not callable(snapshot):
            return dict(available=False, hardware_acknowledged=False)
        try:
            return _json_helper_diagnostics(snapshot())
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
        self._stage_restoration_origin = copy.deepcopy(report)

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
                stage_restoration_attempts=copy.deepcopy(self._stage_restoration_attempts))
        if failures:
            raise GeneralStopError(failures)

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
            publications=copy.deepcopy(self.stage_publications),
            publication_count=self.stage_publication_count,
            publication_storage="bounded_latest_per_name_in_RAM",
            psp_delivery_acknowledged=False, hardware_acknowledged=False,
            stage_controls_verified=self.stage_controls_verified,
            cooling_trip_verified=self.cooling_trip_verified,
            ht_controls_verified=self.ht_controls_verified,
            focal_controls_verified=self.focal_controls_verified,
            focal_resources_verified=getattr(self.focal_command, "resources_verified", False) is True,
            focal_helper_results=copy.deepcopy(self._focal_helper_results),
            focal_quiescence_error=self._focal_quiescence_error,
            focal_command_diagnostics=self._focal_diagnostics(),
            pending_output_restorations=self._stage_pending_snapshot(),
            restoration_origin=copy.deepcopy(self._stage_restoration_origin),
            restoration_attempts=copy.deepcopy(self._stage_restoration_attempts),
            restoration_attempt_count=self._stage_restoration_attempt_count,
            restoration_diagnostics_retained_limit=128,
            last_cooling_guard=copy.deepcopy(self.last_cooling_guard))

    def _stage_preflight(self, operator_confirmed, operation=None):
        if operator_confirmed is not True:
            raise ValueError("Explicit local stage confirmation required")
        if self.stage_controls_verified is not True:
            raise RuntimeError("Stage commands blocked: stage controls not commissioned")
        if operation in HT_STAGE_OPERATIONS and self.ht_controls_verified is not True:
            # Deliberate Python commissioning gate, not a recovered VI permit.
            # Starting HT can energize the already-commanded startup voltage;
            # it is independent of extended-stop feedback qualification.
            raise RuntimeError("HT stage commands blocked: HT controls not commissioned")
        if operation in FOCAL_STAGE_OPERATIONS and self.focal_controls_verified is not True:
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
            if operation in FOCAL_STAGE_OPERATIONS:
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
                                  report=copy.deepcopy(getattr(error, "report", None)))
            raise
        self.procedure.update(state="SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK",
                              report=copy.deepcopy(result))
        return result

    def execute_cooling_guard(self, snapshot, cancel):
        """Saved raw cooling predicate only; not a klystron safety permit."""
        if (self.stage_controls_verified is not True or self.cooling_trip_verified is not True
                or self.control_profile == "general_only_test"):
            self.last_cooling_guard = dict(
                status="DISABLED", effects_enabled=False, hardware_acknowledged=False,
                reason="Both commissioning gates and a non-General-only profile are required")
            return copy.deepcopy(self.last_cooling_guard)
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
            self.last_cooling_guard = copy.deepcopy(report)
            if self.procedure is not None:
                self.procedure["state"] = "INTERRUPTED_OR_FAILED"
            raise
        self.last_cooling_guard = copy.deepcopy(result)
        if self.procedure is not None and self.procedure.get("name") == "cooling.timeout_trip":
            self.procedure.update(state="SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK",
                                  report=copy.deepcopy(result))
        return result


class CardBackend(SourceControls, _StageState):
    def __init__(self, factory=None, read_timeout=0.5, focal_off=None, stop_wait=None,
                 control_profile="legacy_full", ht_feedback_verified=False,
                 ht_zero_tolerance_kv=0.0, ht_zero_timeout=10.0,
                 stage_controls_verified=False, cooling_trip_verified=False,
                 ht_controls_verified=False, focal_controls_verified=False,
                 focal_command=None, counter_controls_verified=False,
                 ht_voltage_controls_verified=False, outer_stop_verified=False,
                 counter_timing_controls_verified=False):
        if not 0 < read_timeout <= 2:
            raise ValueError("read timeout must be in (0, 2] seconds")
        if control_profile not in CONTROL_PROFILES:
            raise ValueError("Unknown acquisition control profile")
        self.control_profile = control_profile
        if (type(stage_controls_verified) is not bool or type(cooling_trip_verified) is not bool
                or type(ht_controls_verified) is not bool or type(focal_controls_verified) is not bool):
            raise ValueError("Explicit Boolean stage commissioning flags required")
        self.stage_controls_verified = stage_controls_verified
        self.cooling_trip_verified = cooling_trip_verified
        self.ht_controls_verified = ht_controls_verified
        self.focal_controls_verified = focal_controls_verified
        for name, value in (("counter_controls_verified", counter_controls_verified),
                            ("ht_voltage_controls_verified", ht_voltage_controls_verified),
                            ("outer_stop_verified", outer_stop_verified),
                            ("counter_timing_controls_verified", counter_timing_controls_verified)):
            if type(value) is not bool:
                raise ValueError("Exact Boolean source-control commissioning required")
            setattr(self, name, value)
        legacy_focal = isinstance(focal_off, _LEGACY_CHROMA_STOP_TYPE)
        legacy_settings = None
        if legacy_focal:
            legacy_settings = dict(dll_path=focal_off.dll_path,
                                   resources_verified=focal_off.resources_verified,
                                   timeout=focal_off.timeout)
        if focal_command is None:
            from .chroma_focal_command import ChromaFocalCommand
            focal_command = ChromaFocalCommand(**(legacy_settings or {}))
        elif legacy_focal and any(getattr(focal_command, name, None) != value
                                  for name, value in legacy_settings.items()):
            raise ValueError("Conflicting legacy OFF and owned Focal command configuration")
        self.focal_command = focal_command
        self._stage_simulated = False
        validate_policy(ht_feedback_verified, ht_zero_tolerance_kv, ht_zero_timeout)
        self.ht_feedback_verified = ht_feedback_verified
        self.ht_zero_tolerance_kv = ht_zero_tolerance_kv
        self.ht_zero_timeout = ht_zero_timeout
        self.factory = factory or create_legacy_card_tasks
        self.read_timeout = read_timeout
        self.owner = None
        self.initial_images = None
        self.started_counters = []
        self.calibration = {}
        self.commanded_digital = {}
        self.commanded_analog = {}
        self.software_status_assignments = {"EPS": {}, "DPS": {}}
        self.procedure = None
        # Plain callable injection remains an offline-test boundary. Production
        # defaults and known legacy native adapters share ONE retained worker
        # owner; an unconfirmed OFF must also block later ON/reopen/cleanup.
        self.focal_off = (None if control_profile == "general_only_test" else
                          _OwnedFocalOff(self) if focal_off is None or legacy_focal else focal_off)
        self.stop_wait = stop_wait or time.sleep
        self._reset_stage_state()
        self._reset_source_controls()
        self._ao_control_calibration = {}

    def _stage_require_initialized(self):
        if self.owner is None or not self.commanded_digital:
            raise RuntimeError("Stage command requires initialized card ownership")

    def _stage_write_digital(self, name, values):
        self._ensure_focal_quiescent()
        self.owner.write_digital_bank(name, values)

    @property
    def resource_count(self):
        return len(self.owner.tasks) if self.owner is not None else 0

    def initialize(self, cancel, startup_confirmed=False):
        if startup_confirmed is not True:
            raise ValueError("Explicit local confirmation of legacy startup effects required")
        if self.owner is not None:
            raise RuntimeError("Resources already owned; deinitialize first")
        self._ensure_focal_quiescent()
        if cancel.is_set():
            raise AcquisitionCancelled()
        # Pin and validate the calibration before any driver/resource calls.
        self.calibration = {}
        groups = {"C1NI6071E": ("C1_NI6071E_AI", 64, 1),
                  "C2NI6071E": ("C2_NI6071E_AI", 64, 2),
                  "C11_NI6220": ("C11_NI6220_AI", 16, 11)}
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "calibration_map.csv")
        with io.open(path, "r", encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                if row["group"] not in groups:
                    continue
                name, count, device = groups[row["group"]]
                index = int(row["index"])
                key = (name, index)
                scale, offset = float(row["scale"]), float(row["offset"])
                if (key in self.calibration or not 0 <= index < count
                        or row["physical_channel"] != "/{0}/ai{1}".format(device, index)
                        or not math.isfinite(scale) or not math.isfinite(offset)):
                    raise ValueError("Invalid AI calibration entry")
                self.calibration[key] = (scale, offset)
        if len(self.calibration) != 144:
            raise ValueError("All 144 AI calibration entries required")
        self._ao_control_calibration = load_ao_calibration()
        try:
            self.owner = self.factory(authorized=True, outputs_commissioned=True)
        except PartialTaskCreationError as error:
            self.owner = error.owner
            raise
        if cancel.is_set():
            raise AcquisitionCancelled()
        self.started_counters = self.owner.start_legacy_counters()
        if cancel.is_set():
            raise AcquisitionCancelled()
        self.initial_images = self.owner.write_initial_images()
        self.commanded_digital = copy.deepcopy(self.initial_images["digital"])
        self.commanded_analog = analog_startup_logical_image()
        self.software_status_assignments = {"EPS": {}, "DPS": {}}
        self._reset_stage_state()
        self._reset_source_controls()
        self.procedure = None
        if cancel.is_set():
            raise AcquisitionCancelled()

    def general_start(self, cancel, operator_confirmed=False):
        if self.owner is None or not self.commanded_digital:
            raise RuntimeError("General Marche requires initialized card ownership")
        if operator_confirmed is not True:
            raise ValueError("General Marche confirmation required")
        self._require_known_source_commands()
        self._ensure_focal_quiescent()
        self._retry_source_counter_stops()
        if self.control_profile == "general_only_test":
            # This verifies command scope, not the physical state of switches
            # operated outside Python. The GUI requires those stages OFF.
            for name, expected in self.initial_images["digital"].items():
                current = self.commanded_digital.get(name, ())
                ignored = (0, 1, 2) if name == "C4_DIO96_DO" else ()
                if (len(current) != len(expected) or any(
                        type(value) is not bool or (i not in ignored and value != expected[i])
                        for i, value in enumerate(current))):
                    raise RuntimeError("General-only test refuses changed non-General command image: " + name)
            if tuple(self.commanded_digital["C4_DIO96_DO"][i] for i in (0, 1, 2)) != (False, True, False):
                raise RuntimeError("General-only test requires released Marche/RAZ and idle Arret commands")
        else:
            if self.control_profile == "extended_ht_stop" and not self.ht_feedback_verified:
                raise RuntimeError("Extended stop unavailable: verify HT feedback before General Marche")
            # The full legacy profile still requires its complete stop path.
            if hasattr(self.focal_off, "ensure_ready"):
                self.focal_off.ensure_ready()
        self.procedure = dict(name="modulator.general.start", state="EXECUTING", frame=None,
                              control_profile=self.control_profile)

        def commit(index, value):
            bank = list(self.commanded_digital["C4_DIO96_DO"])
            bank[index] = value
            self._stage_write_digital("C4_DIO96_DO", bank)
            self.commanded_digital["C4_DIO96_DO"] = tuple(bank)

        def assign(eps, dps):
            self._stage_assign_status(eps, dps)

        def observe(frame, source_uid):
            self.procedure.update(frame=frame, source_uid=source_uid)

        try:
            self._retry_stage_restorations()
            execute_general_start(commit, assign, cancel.wait, cancel.is_set,
                                  observe, operator_confirmed=True)
        except Exception:
            self.procedure["state"] = "INTERRUPTED_OR_FAILED"
            raise
        self.procedure["state"] = "SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK"

    def general_stop(self, operator_confirmed=False):
        if self.owner is None or not self.commanded_digital:
            raise RuntimeError("General Arret requires existing card ownership")
        if operator_confirmed is not True:
            raise ValueError("General Arret confirmation required")
        if self.control_profile == "extended_ht_stop" and not self.ht_feedback_verified:
            raise RuntimeError("Extended stop blocked: HT feedback mapping/polarity/calibration unverified")
        self.procedure = dict(name="modulator.general.stop", state="EXECUTING", frame=None,
                              control_profile=self.control_profile,
                              stop_scope=("general_only_test" if self.control_profile == "general_only_test" else
                                          "python_ht_preamble_then_event_6" if self.control_profile == "extended_ht_stop"
                                          else "labview_event_6"),
                              source_frames_attempted=[], command_sequence_completed=False,
                              failures=[], hardware_off_confirmed=False)
        if self.control_profile != "general_only_test":
            self.procedure.update(
                requested_stop_stages=["chroma_focales", "focale_klystron", "relais_ht",
                                       "premagnetisation", "chauffage", "general"],
                ht_supply_stop_included=self.control_profile == "extended_ht_stop",
                source_psp_write_replaced_by_ram_status=True)

        def commit(index, value):
            bank = list(self.commanded_digital["C4_DIO96_DO"])
            if self.control_profile != "general_only_test" or index == 1:
                # Every stop-bank write also releases General/RAZ, including
                # after a failed earlier restore. Never reassert an uncertain
                # start/reset pulse while stopping any of the legacy stages.
                # This interrupted-start safeguard is explicit Python policy;
                # normal source command images already have both bits False.
                bank[0] = bank[2] = False
            bank[index] = value
            self._stage_write_digital("C4_DIO96_DO", bank)
            self.commanded_digital["C4_DIO96_DO"] = tuple(bank)

        def assign(eps, dps):
            self._stage_assign_status(eps, dps)

        def observe(frame, source_uid):
            self.procedure.update(frame=frame, source_uid=source_uid)
            self.procedure["source_frames_attempted"].append(frame)

        def focal_off():
            self._ensure_focal_quiescent()
            return self.focal_off()

        try:
            self._ensure_focal_quiescent()
            self._retry_source_counter_stops()
            self._retry_stage_restorations()
            # A failed start can retain a last-successful asserted pulse image.
            # Release it before either stop profile, on this same NI owner. A
            # restore error must not gate Focales OFF or later NI stop stages.
            restore_failures = []
            for line in (0, 2):
                if self.commanded_digital["C4_DIO96_DO"][line] is not False:
                    try:
                        commit(line, False)
                    except Exception as error:
                        restore_failures.append("restore C4[{0}]=False: {1}: {2}".format(
                            line, type(error).__name__, error))
            if self.control_profile == "general_only_test":
                self.procedure.update(other_stages_stopped=False, full_event_6_executed=False)
                def assign_if_restored(eps, dps):
                    if not restore_failures:
                        assign(eps, dps)

                try:
                    execute_general_only_stop(commit, assign_if_restored, self.stop_wait,
                                              observe, operator_confirmed=True)
                except GeneralStopError as error:
                    raise GeneralStopError(restore_failures + list(error.failures))
            else:
                if self.control_profile == "extended_ht_stop":
                    def preamble_observer(stage):
                        self.procedure["ht_preamble_phase"] = stage
                    try:
                        self.procedure["ht_preamble_result"] = execute_ht_shutdown(
                            self.commanded_analog["C9NI6703"][0], self._read_ht_shutdown_sample,
                            self._lower_ht_shutdown_command,
                            lambda: execute_ht_supply_stop(commit, assign, self.stop_wait),
                            lambda: self._stop_modulator_pulses(assign), self.stop_wait,
                            feedback_verified=self.ht_feedback_verified,
                            zero_tolerance_kv=self.ht_zero_tolerance_kv,
                            timeout_seconds=self.ht_zero_timeout, observer=preamble_observer)
                    except GeneralStopError as error:
                        raise GeneralStopError(restore_failures + list(error.failures))
                try:
                    execute_general_stop(commit, focal_off, assign, self.stop_wait,
                                         observe, operator_confirmed=True)
                except GeneralStopError as error:
                    raise GeneralStopError(restore_failures + list(error.failures))
            if restore_failures:
                raise GeneralStopError(restore_failures)
        except GeneralStopError as error:
            self.procedure.update(state="PARTIAL_STOP_FAILURE", failures=list(error.failures))
            raise
        except Exception as error:
            self.procedure.update(state="PARTIAL_STOP_FAILURE", failures=[str(error)])
            raise
        self.procedure["state"] = "SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK"
        self.procedure["command_sequence_completed"] = True

    def _read_ht_shutdown_sample(self):
        """Fresh NI reads on owner thread, never a cached telemetry/EPS flag."""
        started = time.monotonic()
        task = self.owner.tasks["C2_NI6071E_AI"]
        task.start()
        try:
            raw = self.owner.read_analog_means("C2_NI6071E_AI", timeout_seconds=self.read_timeout)
        finally:
            task.stop()
        inputs = list(self.owner.tasks["C4_DIO96_DI"].read(timeout=self.read_timeout))
        if len(raw) != 64 or len(inputs) != 64 or any(type(v) is not bool for v in inputs):
            raise ValueError("HT readback bank shape/type changed")
        scale, offset = self.calibration[("C2_NI6071E_AI", 7)]
        # The saved Supervision path passes this raw bit unchanged to an
        # active-low indicator: False=green EN MARCHE, True=gray OFF.
        # Do not mistake the raw contact True for a running HT supply.
        # Electrical qualification still requires ht_feedback_verified.
        return dict(voltage_kv=raw[7] * scale + offset, supply_on=not inputs[48],
                    raw_supply_contact=inputs[48],
                    age_seconds=time.monotonic() - started)

    def _lower_ht_shutdown_command(self, command_kv):
        self._require_known_ht_command()
        bank = list(self.commanded_analog["C9NI6703"])
        if (type(command_kv) not in (int, float) or not math.isfinite(command_kv)
                or not 0 <= command_kv < bank[0]):
            raise ValueError("Shutdown HT command must strictly decrease")
        bank[0] = command_kv
        self._source_commit_analog("C9NI6703", bank)

    def _stop_modulator_pulses(self, assign_status):
        self._ensure_focal_quiescent()
        failures = []
        for number in PULSE_STOP_TASKS:
            try:
                task = self.owner.tasks["C10_NI6602_CO_{0}".format(number)]
            except Exception as error:
                failures.append("counter {0} task: {1}".format(number, error))
                continue
            try:
                for iteration in range(42):
                    done = self.owner.read_counter_pulse_done(number)
                    if type(done) is not bool:
                        raise ValueError("Counter Done must be Boolean")
                    self.stop_wait(.001)
                    if done or iteration > 40:
                        break
            except Exception as error:
                failures.append("counter {0} poll: {1}".format(number, error))
            try:
                self._source_counter_stop(number)
            except Exception as error:
                failures.append("counter {0} stop: {1}".format(number, error))
        try:
            # Preserve the source's EPS42/52 asymmetry; these are NOT ACKs.
            assign_status(PULSE_STOP_EPS, PULSE_STOP_DPS)
            self.stop_wait(.1)
        except Exception as error:
            failures.append("pulse source status/wait: " + str(error))
        if failures:
            raise GeneralStopError(failures)

    def read_snapshot(self, cancel):
        if self.owner is None:
            raise RuntimeError("Cards not initialized")
        banks = {}
        for name, device, count in AI_BANKS:
            if cancel.is_set():
                raise AcquisitionCancelled()
            task = self.owner.tasks[name]
            task.start()
            try:
                values = self.owner.read_analog_means(name, timeout_seconds=self.read_timeout)
            finally:
                task.stop()
            if len(values) != count or any(not math.isfinite(value) for value in values):
                raise ValueError("Invalid/nonfinite analog bank: " + name)
            scaled = [value * self.calibration[(name, index)][0] + self.calibration[(name, index)][1]
                      for index, value in enumerate(values)]
            if any(not math.isfinite(value) for value in scaled):
                raise ValueError("Nonfinite calibrated analog bank: " + name)
            banks[name] = dict(kind="analog_input", device=device,
                               values=values, unit="V", processing="mean_of_10_raw_samples",
                               legacy_scaled_values=scaled,
                               calibration="calibration_map.csv: mean*scale+offset")
        for name, device, first, last, count in DI_BANKS:
            if cancel.is_set():
                raise AcquisitionCancelled()
            values = list(self.owner.tasks[name].read(timeout=self.read_timeout))
            if len(values) != count or any(type(value) is not bool for value in values):
                raise ValueError("Invalid Boolean bank shape: " + name)
            banks[name] = dict(kind="digital_input", device=device, values=values)
        return dict(
            source="python_daqmx_acquisition", simulated=False,
            control_profile=self.control_profile,
            sample_kind="sequential_card_reads_not_atomic",
            banks=banks, startup_commands=self.initial_images,
            commanded_digital=copy.deepcopy(self.commanded_digital),
            commanded_analog_logical=copy.deepcopy(self.commanded_analog),
            software_status_assignments=copy.deepcopy(self.software_status_assignments),
            stage_state=self._stage_snapshot(),
            source_controls=self._source_control_snapshot(),
            procedure=copy.deepcopy(self.procedure),
            started_counters=list(self.started_counters),
            output_interpretation="Last successful software bank commands, not physical output readback",
            units_note="AI values are raw volts; legacy_scaled_values are separate. Not the 27-bank LabVIEW schema",
            runtime_setpoint_commands_enabled=False,
        )

    def close(self):
        self._ensure_focal_quiescent()
        if self.owner is not None:
            self.owner.close()
            self.owner = None
        self.initial_images = None
        self.started_counters = []
        self.commanded_digital = {}
        self.commanded_analog = {}
        self._reset_stage_state()
        self._reset_source_controls()
        self._ao_control_calibration = {}


class DemoBackend(_StageState):
    """Explicit GUI/test mode. Never imports or delegates to an NI adapter."""
    def __init__(self, control_profile="legacy_full", stage_controls_verified=False,
                 cooling_trip_verified=False, ht_controls_verified=False,
                 focal_controls_verified=False, focal_command=None, counter_controls_verified=False,
                 ht_voltage_controls_verified=False, outer_stop_verified=False,
                 counter_timing_controls_verified=False):
        if control_profile not in CONTROL_PROFILES:
            raise ValueError("Unknown acquisition control profile")
        self.control_profile = control_profile
        if (type(stage_controls_verified) is not bool or type(cooling_trip_verified) is not bool
                or type(ht_controls_verified) is not bool or type(focal_controls_verified) is not bool):
            raise ValueError("Explicit Boolean stage commissioning flags required")
        self.stage_controls_verified = stage_controls_verified
        self.cooling_trip_verified = cooling_trip_verified
        self.ht_controls_verified = ht_controls_verified
        self.focal_controls_verified = focal_controls_verified
        for name, value in (("counter_controls_verified", counter_controls_verified),
                            ("ht_voltage_controls_verified", ht_voltage_controls_verified),
                            ("outer_stop_verified", outer_stop_verified),
                            ("counter_timing_controls_verified", counter_timing_controls_verified)):
            if type(value) is not bool or value is True:
                raise ValueError("Demo cannot commission NI source controls; use injected offline executors")
            setattr(self, name, False)
        if focal_command is not None and getattr(focal_command, "simulated", False) is not True:
            raise ValueError("Demo Focal adapter must explicitly be simulated")
        self.focal_command = focal_command if focal_command is not None else _DemoFocalCommand()
        self._stage_simulated = True
        self.active = False
        self.commanded_digital = {}
        self.software_status_assignments = {"EPS": {}, "DPS": {}}
        self.procedure = None
        self._reset_stage_state()

    def _stage_require_initialized(self):
        if not self.active:
            raise RuntimeError("Stage simulation requires initialization")

    def _stage_write_digital(self, name, values):
        # No NI owner exists in demo mode. The shared adapter updates RAM only.
        self._ensure_focal_quiescent()

    @property
    def resource_count(self):
        return 0

    def initialize(self, cancel, startup_confirmed=False):
        if cancel.is_set():
            raise AcquisitionCancelled()
        self._ensure_focal_quiescent()
        self.commanded_digital = digital_startup_image()
        self.software_status_assignments = {"EPS": {}, "DPS": {}}
        self.procedure = None
        self._reset_stage_state()
        self.active = True

    def read_snapshot(self, cancel):
        if cancel.is_set():
            raise AcquisitionCancelled()
        return dict(source="python_acquisition_demo", simulated=True, banks={},
                    control_profile=self.control_profile,
                    hardware_writes=False, runtime_setpoint_commands_enabled=False,
                    commanded_digital=copy.deepcopy(self.commanded_digital),
                    software_status_assignments=copy.deepcopy(self.software_status_assignments),
                    stage_state=self._stage_snapshot(), procedure=copy.deepcopy(self.procedure))

    def general_start(self, cancel, operator_confirmed=False):
        self._ensure_focal_quiescent()
        execute_general_start(lambda *_args: None, lambda *_args: None,
                              cancel.wait, cancel.is_set, operator_confirmed=operator_confirmed)

    def general_stop(self, operator_confirmed=False):
        self._ensure_focal_quiescent()
        if self.control_profile == "general_only_test":
            execute_general_only_stop(lambda *_args: None, lambda *_args: None,
                                      time.sleep, operator_confirmed=operator_confirmed)
        else:
            if self.control_profile == "extended_ht_stop":
                # Explicit demo callbacks only, never an NI-backed fallback.
                execute_ht_shutdown(6.5, lambda: dict(voltage_kv=0.0, supply_on=False, age_seconds=0.0),
                                    lambda _value: None, lambda: None, lambda: None, time.sleep,
                                    feedback_verified=True)
            execute_general_stop(lambda *_args: None, lambda: None, lambda *_args: None,
                                 time.sleep, operator_confirmed=operator_confirmed)

    def close(self):
        self._ensure_focal_quiescent()
        self.active = False
        self.commanded_digital = {}
        self._reset_stage_state()
