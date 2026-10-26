"""Explicit legacy NI startup + bounded input reads. Python 3.4 compatible.

No import of nidaqmx, task creation, discovery or writes until initialize().
No arbitrary setpoint API. Startup images are fixed reviewed legacy constants;
General Marche/Arret are separate, explicitly confirmed local procedures.
Additional source-qualified stages have independent, default-disabled gates.
"""
from __future__ import division

import csv
import copy
from contextlib import contextmanager
import io
import json
import math
import os
import threading
import time

from .hardware_plan import AI_BANKS, DI_BANKS
from .hardware_tasks import create_legacy_card_tasks, PartialTaskCreationError
from .input_tasks import AI_TIMING
from .acquisition_procedures import (
    execute_general_start, execute_general_stop, execute_general_only_stop, GeneralStopError,
)
from .chroma_focal_stop import ChromaFocalStop
from .hardware_plan import analog_startup_logical_image, digital_startup_image, load_ao_calibration
from .acquisition_source_controls import SourceControls
from .acquisition_beamline import BEAMLINE_OPERATIONS
from .acquisition_ht_shutdown import (
    execute_ht_shutdown, execute_ht_supply_stop, validate_policy,
    PULSE_STOP_TASKS, PULSE_STOP_EPS, PULSE_STOP_DPS,
)


CONTROL_PROFILES = ("legacy_full", "general_only_test", "extended_ht_stop")
HT_STAGE_OPERATIONS = ("alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset")
FOCAL_STAGE_OPERATIONS = ("focales.start", "focales.stop")
_ENERGY_REDUCING_OPERATIONS = ("modulator.general.stop", "chauffage.stop",
    "prema.stop", "focales.stop", "relays_ht.stop", "alimentation_ht.stop",
    "modulator_impulse.stop", "acquisition.outer_controlled_stop", "alimentation_ht.nonincrease")
_LEGACY_CHROMA_STOP_TYPE = ChromaFocalStop
# Source root Timeout dispatcher + named event reset tails. This maps request
# intent only, never a physical permit or acknowledgement. Outer stop and AO
# setpoints have no equivalent DPS request field in this qualified subset.
PROCEDURE_DPS_REQUESTS = {
    "cooling.start": 0, "cooling.stop": 1,
    "modulator.general.start": 2, "modulator.general.stop": 3,
    "chauffage.start": 4, "chauffage.stop": 5,
    "prema.start": 6, "prema.stop": 7,
    "relays_ht.start": 8, "relays_ht.stop": 9,
    "focales.start": 10, "focales.stop": 11, "modulator.reset": 12,
    "alimentation_ht.start": 15, "alimentation_ht.reset": 16,
    "alimentation_ht.stop": 17,
    "modulator_impulse.start": 18, "modulator_impulse.stop": 19,
}


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

    def set_execution_observer(self, observer, interval_seconds=.2):
        """Install optional checkpoints; observer runs on the existing NI owner.

        event includes operation/frame/source_uid, safe_to_sample,
        remaining_seconds and minimum_next_action_deadline (monotonic). The
        observer may obtain a same-owner snapshot only with sufficient dwell
        budget; it must not dispatch another output procedure. Sampling
        checkpoints never occur during an asserted/uncertain source pulse.
        Separate SOFTWARE_STATE_NOT_MEASUREMENT events are RAM-only and never
        authorize NI reads. Native sampling can overrun a budget and is not
        forcibly interruptible.
        """
        from .cooperative_execution import CooperativeExecution
        self._execution_scheduler = CooperativeExecution(observer, interval_seconds)

    def _execution_waiter(self, wait_seconds):
        def wait(seconds, safe_to_sample=False, phase=None):
            scheduler = getattr(self, "_execution_scheduler", None)
            if scheduler is None or scheduler.observer is None:
                return wait_seconds(seconds)
            if self.procedure is not None:
                self.procedure["execution_phase"] = dict(phase or {},
                    safe_to_sample=bool(safe_to_sample), nominal_wait_seconds=seconds,
                    hardware_acknowledged=False)
            try:
                return scheduler.wait(seconds, wait_seconds, safe_to_sample, phase)
            finally:
                if self.procedure is not None:
                    self.procedure["execution_checkpoints"] = scheduler.snapshot()
        return wait

    def _ensure_execution_not_reentrant(self):
        scheduler = getattr(self, "_execution_scheduler", None)
        if ((scheduler is not None and scheduler.active)
                or getattr(self, "_software_state_observer_active", False)
                or getattr(self, "_beamline_operation_active", False)):
            raise RuntimeError("Execution observer may sample, not reenter NI procedures or cleanup")

    def get_software_state(self):
        """Complete source EPS/DPS software memory; no NI read or health test.

        Invalid before successful initialization or after resources release.
        Each result is detached; immutable vectors cannot mutate local memory.
        Revision is independent of acquisition sample sequence and age.
        """
        self._stage_require_initialized()
        if self._software_state_valid is not True:
            raise RuntimeError("Complete initialized software status is unavailable")
        return dict(revision=self._software_state_revision,
                    EPS=tuple(self._stage_status[44]), DPS=tuple(self._stage_status[36]))

    def record_procedure_request(self, operation):
        """Record admitted source request intent, not execution success.

        Caller must have admitted the named command before invoking this RAM
        update. This method never clears a pending request on rejection, fault
        or cancellation. Only the reached source tail may clear its own bit.
        Other pending fields are preserved, not replaced or dispatched here.
        """
        self._ensure_execution_not_reentrant()
        self._stage_require_initialized()
        if type(operation) is not str:
            raise ValueError("Explicit source operation name required")
        field = PROCEDURE_DPS_REQUESTS.get(operation)
        if field is None:
            return False
        self.get_software_state()
        self._software_request_operation = operation
        try:
            self._stage_write_local(36, ((field, True),))
        finally:
            self._software_request_operation = None
        return True

    def _emit_software_state(self, source_effect, publication=None, source_uid=None):
        """Bounded RAM-only observer event; never enter the NI sampling path."""
        scheduler = getattr(self, "_execution_scheduler", None)
        if scheduler is None or scheduler.observer is None:
            return
        observed = time.monotonic()
        event = dict(kind="SOFTWARE_STATE_NOT_MEASUREMENT",
                     software_state_observed_monotonic=observed,
                     software_state=self.get_software_state(),
                     source_effect=source_effect, simulated=self._stage_simulated,
                     safe_to_sample=False, hardware_acknowledged=False)
        if self.procedure is not None:
            event.update(operation=self.procedure.get("name"),
                         frame=self.procedure.get("frame"),
                         source_uid=self.procedure.get("source_uid"))
        if getattr(self, "_software_request_operation", None) is not None:
            event["operation"] = self._software_request_operation
            event["frame"] = None
            event["source_uid"] = None
            event["request_intent_only"] = True
        if source_uid is not None:
            event["source_uid"] = source_uid
        if publication is not None:
            event["publication"] = dict(name=publication["name"],
                                        values=tuple(publication["values"]),
                                        sequence=publication["sequence"])
        self._software_state_observer_active = True
        try:
            scheduler.observer(event)
        except Exception as error:
            # Status reporting must not skip a source pulse release or stop.
            self._software_state_observer_error_count += 1
            self._software_state_observer_error = (type(error).__name__ + ": " + str(error))[:2048]
        finally:
            self._software_state_observer_active = False

    def _reset_stage_state(self):
        # Saved root frame 33052 resets local refs 44/36 to these literals.
        # C3/C4 images come from the reviewed startup commands, not DI values.
        self._stage_status = {44: (False,) * 77, 36: (False,) * 29}
        self._software_state_revision = getattr(self, "_software_state_revision", 0) + 1
        self._software_state_valid = False
        self._software_state_observer_error_count = 0
        self._software_state_observer_error = None
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
        self._pending_beamline_release = None
        self._beamline_operation_active = False
        self._beamline_safe_stop_owner_ident = None
        self._beamline_initialization_owner_ident = None
        self.last_beamline_command = None
        self._ht_supply_sequence_completed = False
        self._ht_pulses_sequence_completed = False

    def _invalidate_ht_sequence_completion(self):
        # Additional Python ordering fence; never changes source EPS/DPS.
        self._ht_supply_sequence_completed = False
        self._ht_pulses_sequence_completed = False

    @contextmanager
    def _energy_reducing_scope(self, operation):
        """Private owner-only stop scope; cannot replay or write any C5 bank.

        An unresolved independent C5 release must not make reviewed C4/C9/
        counter stops unreachable. Serial worker quiescence remains required.
        """
        self._ensure_execution_not_reentrant()
        if operation not in _ENERGY_REDUCING_OPERATIONS:
            raise ValueError("Unqualified energy-reducing scope")
        ident = threading.current_thread().ident
        if (self._pending_beamline_release is not None
                and ident != self._beamline_initialization_owner_ident):
            raise RuntimeError("Retained C5 ownership allows protective stops on original NI owner only")
        previous = self._beamline_safe_stop_owner_ident
        self._beamline_safe_stop_owner_ident = ident
        try:
            yield
        finally:
            self._beamline_safe_stop_owner_ident = previous

    def _ensure_focal_quiescent(self):
        if (self._pending_beamline_release is not None
                and (self._beamline_safe_stop_owner_ident != threading.current_thread().ident
                     or self._beamline_safe_stop_owner_ident != self._beamline_initialization_owner_ident)):
            raise RuntimeError("Unconfirmed C5 pulse release: retain owner; qualified release reconciliation required")
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
            self._software_state_revision += 1
            self._emit_software_state("LOCAL_ASSIGNMENT")

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
        if name in ("EPS", "DPS"):
            self._software_state_revision += 1
            self._emit_software_state("SOURCE_PUBLICATION", self.stage_publications[name])

    def _stage_snapshot(self):
        return dict(
            local_banks={"C3_OUT_DIO96": self._stage_read_local(17),
                         "C4_OUT_DIO96": self._stage_read_local(15),
                         "C5_OUT_DIO96": tuple(self.commanded_digital.get("C5_DIO96_DO", ())),
                         "EPS": self._stage_read_local(44),
                         "DPS": self._stage_read_local(36)},
            update_indicator=self.stage_update_indicator,
            update_indicator_interpretation="Remembered literal software assignment, initially unknown",
            interpretation="DO banks are last successful commands; EPS/DPS are software memory, not readback or permits",
            publications=copy.deepcopy(self.stage_publications),
            publication_count=self.stage_publication_count,
            software_state_revision=self._software_state_revision,
            software_status_valid=self._software_state_valid,
            software_state_interpretation="Complete EPS/DPS source software memory; not NI input measurements or permits",
            software_state_observer_error_count=self._software_state_observer_error_count,
            software_state_observer_error=self._software_state_observer_error,
            publication_storage="bounded_latest_per_name_in_RAM",
            psp_delivery_acknowledged=False, hardware_acknowledged=False,
            stage_controls_verified=self.stage_controls_verified,
            cooling_trip_verified=self.cooling_trip_verified,
            ht_controls_verified=self.ht_controls_verified,
            focal_controls_verified=self.focal_controls_verified,
            beamline_controls_verified=self.beamline_controls_verified,
            pending_beamline_release=copy.deepcopy(self._pending_beamline_release),
            last_beamline_command=copy.deepcopy(self.last_beamline_command),
            beamline_position_feedback_qualified=False,
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
        self._ensure_execution_not_reentrant()
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
        if operation in _ENERGY_REDUCING_OPERATIONS:
            with self._energy_reducing_scope(operation):
                return self._execute_stage(operation, cancel, operator_confirmed, new_value)
        return self._execute_stage(operation, cancel, operator_confirmed, new_value)

    def _execute_stage(self, operation, cancel, operator_confirmed=False, new_value=True):
        """Execute one qualified local stage path; no public/remote mutation API."""
        if operation in BEAMLINE_OPERATIONS:
            return self.execute_beamline(operation, cancel, operator_confirmed, new_value)
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
            if operation == "alimentation_ht.start":
                self._ht_supply_sequence_completed = False
            elif operation.endswith((".stop", ".reset")):
                self._invalidate_ht_sequence_completion()
            if operation in FOCAL_STAGE_OPERATIONS:
                self._ensure_focal_ready()
            self._ensure_focal_quiescent()
            self._retry_stage_restorations()
            self.record_procedure_request(operation)
            result = execute_stage(
                operation, self._stage_read_local, self._stage_write_local,
                self._stage_publish, cancel.wait, cancel.is_set, observe,
                operator_confirmed=True, new_value=new_value, focal_helper=focal_helper,
                execution_wait=self._execution_waiter(cancel.wait))
        except Exception as error:
            self._invalidate_ht_sequence_completion()
            self._remember_stage_restorations(error)
            self.procedure.update(state="INTERRUPTED_OR_FAILED",
                                  report=copy.deepcopy(getattr(error, "report", None)))
            raise
        self.procedure.update(state="SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK",
                              report=copy.deepcopy(result))
        if operation == "alimentation_ht.start":
            self._ht_supply_sequence_completed = True
        return result

    def execute_beamline(self, operation, cancel, operator_confirmed=False, new_value=True):
        """Explicit command pulse only; never a position/feedback acknowledgement.

        Independent commissioning is additional Python policy. The retained
        initialization owner alone may write the pulse or its mandatory False
        release. A failed release blocks new energizing/motion paths and close;
        independent reviewed protective stops remain available without C5 writes.
        No automatic motion replay or implicit latch clearing is offered.
        """
        from .acquisition_beamline import execute_beamline_pulse, validate_c5
        self._ensure_execution_not_reentrant()
        if operation not in BEAMLINE_OPERATIONS or type(new_value) is not bool:
            raise ValueError("Reviewed beamline operation and exact Boolean NewVal required")
        if operator_confirmed is not True:
            raise ValueError("Explicit beamline command confirmation required")
        if (self.stage_controls_verified is not True or self.beamline_controls_verified is not True
                or self.control_profile == "general_only_test"):
            raise RuntimeError("Beamline controls are not independently commissioned")
        self._stage_require_initialized()
        owner_ident = threading.current_thread().ident
        if owner_ident != self._beamline_initialization_owner_ident:
            raise RuntimeError("Beamline pulse requires the existing initialization NI owner thread")
        if not new_value:
            return execute_beamline_pulse(operation, lambda: None, lambda i, v: None,
                                          cancel.wait, cancel.is_set, new_value=False)
        self._ensure_focal_quiescent()
        require_known = getattr(self, "_require_known_source_commands", None)
        if require_known is not None:
            require_known()
        if any(self.commanded_digital["C4_DIO96_DO"][i] is not False for i in (0, 2)):
            raise RuntimeError("Release General/RAZ before a beamline pulse")
        if self._pending_stage_restorations or getattr(self, "_pending_counter_stops", ()):
            raise RuntimeError("Resolve retained source restoration before a beamline pulse")
        validate_c5(tuple(self.commanded_digital.get("C5_DIO96_DO", ())))
        self.procedure = dict(name=operation, state="EXECUTING", frame=None,
                              hardware_acknowledged=False, safe_to_sample=False,
                              software_command_only=True, position_feedback_qualified=False,
                              simulated=self._stage_simulated)
        self._beamline_operation_active = True

        def commit(index, value):
            # This private scope is the sole exception to the pending-release
            # guard. No public procedure or input read may reenter it; exact
            # False restoration stays on the original initialized NI owner.
            if (not self._beamline_operation_active
                    or threading.current_thread().ident != owner_ident):
                raise RuntimeError("Beamline write left the original NI owner")
            self._stage_require_initialized()
            current = validate_c5(tuple(self.commanded_digital["C5_DIO96_DO"]))
            pending = self._pending_beamline_release
            if value is True:
                if pending is not None:
                    raise RuntimeError("A retained pulse cannot be replayed")
                self._pending_beamline_release = dict(operation=operation, field=index,
                    value=False, command_state="ASSERT_OR_RELEASE_MAY_HAVE_APPLIED",
                    hardware_acknowledged=False)
            elif (value is not False or pending is None or pending["field"] != index):
                raise RuntimeError("Only the scoped selected-field False release is permitted")
            changed = list(current)
            changed[index] = value
            if self._stage_simulated is False:
                self.owner.write_digital_bank("C5_DIO96_DO", changed)
            self.commanded_digital["C5_DIO96_DO"] = tuple(changed)
            if value is False:
                self._pending_beamline_release = None

        def observe(frame, uid):
            self.procedure.update(frame=frame, source_uid=uid, safe_to_sample=False)

        try:
            result = execute_beamline_pulse(operation,
                lambda: tuple(self.commanded_digital["C5_DIO96_DO"]), commit,
                cancel.wait, cancel.is_set, observe)
        except Exception as error:
            self.last_beamline_command = copy.deepcopy(getattr(error, "report", None))
            if isinstance(self.last_beamline_command, dict):
                self.last_beamline_command["simulated"] = self._stage_simulated
            self.procedure.update(state="INTERRUPTED_OR_FAILED", report=self.last_beamline_command)
            raise
        else:
            result["simulated"] = self._stage_simulated
            self.last_beamline_command = copy.deepcopy(result)
            self.procedure.update(state="SOFTWARE_PULSE_COMPLETED_NOT_POSITION_ACK", report=result)
            return result
        finally:
            self._beamline_operation_active = False

    def execute_cooling_guard(self, snapshot, cancel):
        """Saved raw cooling predicate only; not a klystron safety permit."""
        self._ensure_execution_not_reentrant()
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
                self._invalidate_ht_sequence_completion()
                self._ensure_focal_quiescent()
                self._retry_stage_restorations()
            result = execute_cooling_trip(
                c4, c3, self._stage_read_local, self._stage_write_local,
                self._stage_publish, cancel.wait, cancel.is_set, observe,
                enabled_arm=True, execution_wait=self._execution_waiter(cancel.wait))
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
                 counter_timing_controls_verified=False, beamline_controls_verified=False):
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
        if type(beamline_controls_verified) is not bool:
            raise ValueError("Exact Boolean beamline commissioning required")
        self.beamline_controls_verified = beamline_controls_verified
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
        if name == "C5_DIO96_DO" and self._beamline_safe_stop_owner_ident is not None:
            raise RuntimeError("Protective stop scope cannot replay C5 motion")
        self._ensure_focal_quiescent()
        self.owner.write_digital_bank(name, values)

    @property
    def resource_count(self):
        return len(self.owner.tasks) if self.owner is not None else 0

    def _initialization_notice(self, event):
        scheduler = getattr(self, "_execution_scheduler", None)
        if scheduler is not None and scheduler.observer is not None:
            scheduler.observer(dict(event, kind="INITIALIZATION_CALL_BOUNDARY_NOT_MEASUREMENT",
                                    operation="initialize", safe_to_sample=False,
                                    hardware_acknowledged=False))

    def prepare_isolated_dependencies(self):
        """Load modules and native driver metadata before the stdin pump starts.

        No calls on injected/offline factories. This is not a public operation
        and cannot create, configure, start, read, write or release any card.
        Driver-version metadata queries do not acquire a card task.
        """
        if self.factory is create_legacy_card_tasks:
            from .hardware_tasks import prepare_driver_dependencies, prepare_driver_runtime
            prepare_driver_dependencies(self._initialization_notice)
            prepare_driver_runtime(self._initialization_notice)

    def initialize(self, cancel, startup_confirmed=False):
        self._ensure_execution_not_reentrant()
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
            self._initialization_notice(dict(phase="ENTER", call="create_legacy_card_tasks"))
            options = dict(authorized=True, outputs_commissioned=True)
            if self.factory is create_legacy_card_tasks:
                options["observer"] = self._initialization_notice
            self.owner = self.factory(**options)
            self._initialization_notice(dict(phase="RETURNED", call="create_legacy_card_tasks"))
        except PartialTaskCreationError as error:
            self.owner = error.owner
            raise
        if cancel.is_set():
            raise AcquisitionCancelled()
        self._initialization_notice(dict(phase="ENTER", call="start_legacy_counters"))
        self.started_counters = self.owner.start_legacy_counters()
        self._initialization_notice(dict(phase="RETURNED", call="start_legacy_counters"))
        if cancel.is_set():
            raise AcquisitionCancelled()
        self._initialization_notice(dict(phase="ENTER", call="write_initial_images"))
        self.initial_images = self.owner.write_initial_images()
        self._initialization_notice(dict(phase="RETURNED", call="write_initial_images"))
        self.commanded_digital = copy.deepcopy(self.initial_images["digital"])
        self.commanded_analog = analog_startup_logical_image()
        self.software_status_assignments = {"EPS": {}, "DPS": {}}
        self._reset_stage_state()
        self._reset_source_controls()
        self.procedure = None
        if cancel.is_set():
            raise AcquisitionCancelled()

        self._software_state_valid = True
        self._beamline_initialization_owner_ident = threading.current_thread().ident
        self._emit_software_state("INITIAL_LITERAL", source_uid="33052")

    def general_start(self, cancel, operator_confirmed=False):
        self._ensure_execution_not_reentrant()
        if self.owner is None or not self.commanded_digital:
            raise RuntimeError("General Marche requires initialized card ownership")
        if operator_confirmed is not True:
            raise ValueError("General Marche confirmation required")
        self._invalidate_ht_sequence_completion()
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
            if frame == 9:
                # Source frame35570 independently reads local36 (35614) and
                # publishes DPS (35620) after frame35413's request reset.
                self._stage_publish("DPS", 36, self._stage_read_local(36))

        try:
            self._retry_stage_restorations()
            self.record_procedure_request("modulator.general.start")
            execute_general_start(commit, assign, cancel.wait, cancel.is_set,
                                  observe, operator_confirmed=True,
                                  execution_wait=self._execution_waiter(cancel.wait))
        except Exception:
            self.procedure["state"] = "INTERRUPTED_OR_FAILED"
            raise
        self.procedure["state"] = "SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK"

    def general_stop(self, operator_confirmed=False):
        with self._energy_reducing_scope("modulator.general.stop"):
            return self._general_stop(operator_confirmed)

    def _general_stop(self, operator_confirmed=False):
        self._ensure_execution_not_reentrant()
        if self.owner is None or not self.commanded_digital:
            raise RuntimeError("General Arret requires existing card ownership")
        if operator_confirmed is not True:
            raise ValueError("General Arret confirmation required")
        self._invalidate_ht_sequence_completion()
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
            if frame == 16:
                # Source frame35146: fresh DPS local37688 -> writer37694.
                self._stage_publish("DPS", 36, self._stage_read_local(36))

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
            self.record_procedure_request("modulator.general.stop")
            if self.control_profile == "general_only_test":
                self.procedure.update(other_stages_stopped=False, full_event_6_executed=False)
                def assign_if_restored(eps, dps):
                    if not restore_failures:
                        assign(eps, dps)

                try:
                    execute_general_only_stop(commit, assign_if_restored, self.stop_wait,
                                              observe, operator_confirmed=True,
                                              execution_wait=self._execution_waiter(self.stop_wait))
                except GeneralStopError as error:
                    raise GeneralStopError(restore_failures + list(error.failures))
            else:
                if self.control_profile == "extended_ht_stop":
                    def preamble_observer(stage):
                        self.procedure["ht_preamble_phase"] = stage
                    try:
                        def ht_wait(seconds):
                            return self._execution_waiter(self.stop_wait)(
                                seconds, True,
                                dict(operation="modulator.general.stop", phase="ht_preamble_wait",
                                     ht_preamble_phase=self.procedure.get("ht_preamble_phase")))
                        self.procedure["ht_preamble_result"] = execute_ht_shutdown(
                            self.commanded_analog["C9NI6703"][0], self._read_ht_shutdown_sample,
                            self._lower_ht_shutdown_command,
                            lambda: execute_ht_supply_stop(commit, assign, self.stop_wait),
                            lambda: self._stop_modulator_pulses(assign), ht_wait,
                            feedback_verified=self.ht_feedback_verified,
                            zero_tolerance_kv=self.ht_zero_tolerance_kv,
                            timeout_seconds=self.ht_zero_timeout, observer=preamble_observer)
                    except GeneralStopError as error:
                        raise GeneralStopError(restore_failures + list(error.failures))
                try:
                    execute_general_stop(commit, focal_off, assign, self.stop_wait,
                                         observe, operator_confirmed=True,
                                         execution_wait=self._execution_waiter(self.stop_wait))
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
            raw = self.owner.read_analog_latest("C2_NI6071E_AI", timeout_seconds=self.read_timeout)
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
        return self._read_snapshot(cancel, None)

    def execution_sample_budget_seconds(self):
        """Conservative opt-in budget; not a bound on native start/stop calls."""
        return (len(AI_BANKS) + len(DI_BANKS)) * self.read_timeout + .05

    def read_snapshot_for_execution(self, cancel, deadline_monotonic):
        """Read on the current NI owner only; reject partial or late results.

        Remaining dwell is divided among remaining reads. Native start/stop
        calls may still overrun and cannot be preempted; every started AI is
        stopped in finally. This optional method never enables sampling by
        itself and does not publish or change a procedure/output.
        """
        if (type(deadline_monotonic) not in (int, float)
                or not math.isfinite(deadline_monotonic)):
            raise ValueError("Finite child-local monotonic sample deadline required")
        return self._read_snapshot(cancel, deadline_monotonic)

    def _read_snapshot(self, cancel, deadline_monotonic):
        if (getattr(self, "_software_state_observer_active", False)
                or self._beamline_operation_active):
            raise RuntimeError("Software-state observer or active beamline pulse cannot read NI inputs")
        if self.owner is None:
            raise RuntimeError("Cards not initialized")
        remaining_reads = [len(AI_BANKS) + len(DI_BANKS)]

        def read_timeout():
            if deadline_monotonic is None:
                return self.read_timeout
            remaining = deadline_monotonic - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Safe execution sample deadline exhausted; sample discarded")
            return min(self.read_timeout, remaining / max(1, remaining_reads[0]))

        banks = {}
        for name, device, count in AI_BANKS:
            if cancel.is_set():
                raise AcquisitionCancelled()
            read_timeout()  # Do not start another AI after dwell expired.
            task = self.owner.tasks[name]
            task.start()
            try:
                values = self.owner.read_analog_latest(name, timeout_seconds=read_timeout())
            finally:
                task.stop()
            remaining_reads[0] -= 1
            if len(values) != count or any(not math.isfinite(value) for value in values):
                raise ValueError("Invalid/nonfinite analog bank: " + name)
            scaled = [value * self.calibration[(name, index)][0] + self.calibration[(name, index)][1]
                      for index, value in enumerate(values)]
            if any(not math.isfinite(value) for value in scaled):
                raise ValueError("Nonfinite calibrated analog bank: " + name)
            banks[name] = dict(kind="analog_input", device=device,
                               values=values, unit="V", processing="last_raw_sample_of_finite_block",
                               software_averaging=False,
                               samples_per_channel_acquired=AI_TIMING[name][2],
                               selected_sample_index=AI_TIMING[name][2] - 1,
                               legacy_scaled_values=scaled,
                               calibration="calibration_map.csv: selected_sample*scale+offset")
        for name, device, first, last, count in DI_BANKS:
            if cancel.is_set():
                raise AcquisitionCancelled()
            values = list(self.owner.tasks[name].read(timeout=read_timeout()))
            remaining_reads[0] -= 1
            if len(values) != count or any(type(value) is not bool for value in values):
                raise ValueError("Invalid Boolean bank shape: " + name)
            banks[name] = dict(kind="digital_input", device=device, values=values)
        if deadline_monotonic is not None:
            if cancel.is_set():
                raise AcquisitionCancelled()
            read_timeout()  # A late final native call is never a fresh sample.
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
        self._ensure_execution_not_reentrant()
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
                 counter_timing_controls_verified=False, beamline_controls_verified=False):
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
        if type(beamline_controls_verified) is not bool:
            raise ValueError("Exact Boolean beamline commissioning required")
        self.beamline_controls_verified = beamline_controls_verified
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
        if name == "C5_DIO96_DO" and self._beamline_safe_stop_owner_ident is not None:
            raise RuntimeError("Protective stop scope cannot replay C5 motion")
        self._ensure_focal_quiescent()

    @property
    def resource_count(self):
        return 0

    def initialize(self, cancel, startup_confirmed=False):
        self._ensure_execution_not_reentrant()
        if cancel.is_set():
            raise AcquisitionCancelled()
        self._ensure_focal_quiescent()
        self.commanded_digital = digital_startup_image()
        self.software_status_assignments = {"EPS": {}, "DPS": {}}
        self.procedure = None
        self._reset_stage_state()
        self.active = True
        self._software_state_valid = True
        self._beamline_initialization_owner_ident = threading.current_thread().ident
        self._emit_software_state("INITIAL_LITERAL", source_uid="33052")

    def read_snapshot(self, cancel):
        if self._beamline_operation_active:
            raise RuntimeError("An active beamline pulse cannot be sampled")
        if cancel.is_set():
            raise AcquisitionCancelled()
        return dict(source="python_acquisition_demo", simulated=True, banks={},
                    control_profile=self.control_profile,
                    hardware_writes=False, runtime_setpoint_commands_enabled=False,
                    commanded_digital=copy.deepcopy(self.commanded_digital),
                    software_status_assignments=copy.deepcopy(self.software_status_assignments),
                    stage_state=self._stage_snapshot(), procedure=copy.deepcopy(self.procedure))

    def general_start(self, cancel, operator_confirmed=False):
        self._ensure_execution_not_reentrant()
        self._ensure_focal_quiescent()
        self._stage_require_initialized()
        if operator_confirmed is not True:
            raise ValueError("General Marche confirmation required")
        self.procedure = dict(name="modulator.general.start", state="EXECUTING", frame=None,
                              control_profile=self.control_profile, hardware_acknowledged=False)
        def observe(frame, source_uid):
            self.procedure.update(frame=frame, source_uid=source_uid)
            if frame == 9:
                self._stage_publish("DPS", 36, self._stage_read_local(36))
        self.record_procedure_request("modulator.general.start")
        try:
            execute_general_start(lambda index, value: self._stage_write_local(15, ((index, value),)),
                                  self._stage_assign_status, cancel.wait, cancel.is_set,
                                  observe, operator_confirmed=True,
                                  execution_wait=self._execution_waiter(cancel.wait))
        except Exception:
            self.procedure["state"] = "INTERRUPTED_OR_FAILED"
            raise
        self.procedure["state"] = "SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK"

    def general_stop(self, operator_confirmed=False):
        with self._energy_reducing_scope("modulator.general.stop"):
            return self._general_stop(operator_confirmed)

    def _general_stop(self, operator_confirmed=False):
        self._ensure_execution_not_reentrant()
        self._ensure_focal_quiescent()
        self._stage_require_initialized()
        if operator_confirmed is not True:
            raise ValueError("General Arret confirmation required")
        self.procedure = dict(name="modulator.general.stop", state="EXECUTING", frame=None,
                              control_profile=self.control_profile, hardware_acknowledged=False)
        def observe(frame, source_uid):
            self.procedure.update(frame=frame, source_uid=source_uid)
            if frame == 16:
                self._stage_publish("DPS", 36, self._stage_read_local(36))
        commit = lambda index, value: self._stage_write_local(15, ((index, value),))
        self.record_procedure_request("modulator.general.stop")
        try:
            if self.control_profile == "general_only_test":
                execute_general_only_stop(commit, self._stage_assign_status,
                                          time.sleep, observe, operator_confirmed=True,
                                          execution_wait=self._execution_waiter(time.sleep))
            else:
                if self.control_profile == "extended_ht_stop":
                    # Explicit demo callbacks only, never an NI-backed fallback.
                    execute_ht_shutdown(6.5, lambda: dict(voltage_kv=0.0, supply_on=False, age_seconds=0.0),
                                        lambda _value: None, lambda: None, lambda: None, time.sleep,
                                        feedback_verified=True)
                execute_general_stop(commit, lambda: None, self._stage_assign_status,
                                     time.sleep, observe, operator_confirmed=True,
                                     execution_wait=self._execution_waiter(time.sleep))
        except Exception:
            self.procedure["state"] = "INTERRUPTED_OR_FAILED"
            raise
        self.procedure["state"] = "SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK"

    def close(self):
        self._ensure_execution_not_reentrant()
        self._ensure_focal_quiescent()
        self.active = False
        self.commanded_digital = {}
        self._reset_stage_state()
