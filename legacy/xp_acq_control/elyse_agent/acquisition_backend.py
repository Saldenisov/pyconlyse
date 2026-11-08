"""Explicit legacy NI startup + bounded input reads. Python 3.4 compatible.

No import of nidaqmx, task creation, discovery or writes until initialize().
No arbitrary setpoint API. Startup images are fixed reviewed legacy constants;
General Marche/Arret are separate, explicitly confirmed local procedures.
Additional source-qualified stages have independent, default-disabled gates.
"""
from __future__ import division

from sys import modules as _refactor_modules

from legacy.xp_acq_control.elyse_agent.acquisition_backend_parts_json_helper_diagnostics import _bind_acquisition_backend_parts_json_helper_diagnostics

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


_acquisition_backend_parts_json_helper_diagnostics = _bind_acquisition_backend_parts_json_helper_diagnostics(_refactor_modules[__name__])
_json_helper_diagnostics = _acquisition_backend_parts_json_helper_diagnostics["_json_helper_diagnostics"]


_DemoFocalCommand = _acquisition_backend_parts_json_helper_diagnostics["_DemoFocalCommand"]


_OwnedFocalOff = _acquisition_backend_parts_json_helper_diagnostics["_OwnedFocalOff"]


_StageState = _acquisition_backend_parts_json_helper_diagnostics["_StageState"]
del _acquisition_backend_parts_json_helper_diagnostics


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
