"""Source-control integration on an existing NI owner; no I/O on import.

Separate from General event 6 and the Python 8-kV shutdown extension. These
entrypoints are local, independently gated, and never authorize physical OFF.
"""
import copy
import math

from .acquisition_procedures import GeneralStopError
from .hardware_plan import logical_ao_to_volts


IMPULSION_OPERATIONS = ("modulator_impulse.start", "modulator_impulse.stop")
AO_LOCALS = {9: "C6NI6703", 10: "C7NI6703", 12: "C9NI6703"}


def validate_ht_command(value):
    if type(value) not in (int, float) or not -20 <= value <= 20 or not math.isfinite(value):
        raise ValueError("Finite HT command within the +/-10-V driver domain required; not a physical permit")
    return float(value)


class SourceControls(object):
    """Mixin requiring CardBackend's NI owner, remembered images and gates."""
    def _reset_source_controls(self):
        self._source_scalars = {}  # No invented startup values for unassigned VI locals.
        self._pending_counter_stops = set()
        self.last_impulsion = self.last_ht_command = self.last_outer_stop = None
        self.ht_command_uncertain = False
        self._counter_configuration_uncertain = set()
        self.commanded_counter_ticks = {}
        self._counter_timing_bank = None  # Explicit supplied local39 image only.
        self.last_counter_timing = self.counter_timing_publication = None

    def _source_counter_start(self, number):
        self._ensure_focal_quiescent()
        if number in self._counter_configuration_uncertain:
            raise RuntimeError("Counter timing uncertain: qualified reconciliation required before restart")
        self._pending_counter_stops.add(number)  # A failing call may have applied.
        self.owner.start_counter(number)
        if number not in self.started_counters:
            self.started_counters.append(number)
        self._pending_counter_stops.discard(number)

    def _source_counter_stop(self, number):
        self._ensure_focal_quiescent()
        self._pending_counter_stops.add(number)
        self.owner.stop_counter(number)
        self._pending_counter_stops.discard(number)
        if number in self.started_counters:
            self.started_counters.remove(number)

    def _retry_source_counter_stops(self):
        failures = []
        for number in sorted(self._pending_counter_stops):
            try:
                self._source_counter_stop(number)
            except Exception as error:
                failures.append("Unconfirmed counter {0} stop: {1}: {2}".format(
                    number, type(error).__name__, error))
        if failures:
            raise GeneralStopError(failures)

    def _source_preflight(self, flag, confirmed, retry_counters=True):
        guard = getattr(self, "_ensure_execution_not_reentrant", None)
        if guard is not None:
            guard()
        if confirmed is not True:
            raise ValueError("Explicit local source-control confirmation required")
        if (self.stage_controls_verified is not True or getattr(self, flag) is not True
                or self.control_profile == "general_only_test"):
            raise RuntimeError("Separate source controls are not commissioned")
        self._stage_require_initialized()
        self._ensure_focal_quiescent()
        if retry_counters:
            self._require_known_source_commands()
        if retry_counters and any(self.commanded_digital["C4_DIO96_DO"][i] is not False for i in (0, 2)):
            raise RuntimeError("Release unconfirmed General/RAZ pulse before further source energy commands")
        if retry_counters:
            self._retry_source_counter_stops()
        self._retry_stage_restorations()

    def _source_read_local(self, bank):
        if bank in AO_LOCALS:
            if bank == 12:
                self._require_known_ht_command()
            return tuple(self.commanded_analog[AO_LOCALS[bank]])
        if bank in (46, 47, 48, 50):
            return self._source_scalars.get(bank)
        return self._stage_read_local(bank)

    def _require_known_ht_command(self):
        if self.ht_command_uncertain:
            raise RuntimeError("Ambiguous C9 write: retained command is not current; qualified reconciliation required")

    def _require_known_source_commands(self):
        self._require_known_ht_command()
        if self._counter_configuration_uncertain:
            raise RuntimeError("Ambiguous counter timing properties: qualified reconciliation required")

    def _source_counter_timing_properties(self, number, initial, low, high):
        self._ensure_focal_quiescent()
        # A property callback may partially apply before raising. Never claim
        # the previous three-property image still describes this channel.
        self._counter_configuration_uncertain.add(number)
        self.owner.write_counter_ticks(number, initial, low, high)
        self.commanded_counter_ticks[number] = dict(
            initial_delay_ticks=initial, low_ticks=low, high_ticks=high)
        self._counter_configuration_uncertain.discard(number)

    def configure_counter_timing(self, snapshot, cancel, operator_confirmed=False):
        from .acquisition_counter_timing import (
            decode_counter_bank, execute_counter_timing, validate_counter_bank,
        )
        snapshot = validate_counter_bank(snapshot)
        request = decode_counter_bank(snapshot)
        if operator_confirmed is not True:
            raise ValueError("Explicit local counter timing confirmation required")
        if request is None:
            return False
        self._source_preflight("counter_timing_controls_verified", True)
        self._counter_timing_bank = snapshot
        self.procedure = dict(name="counter.timing", state="EXECUTING", hardware_acknowledged=False)

        def read_bank():
            return self._counter_timing_bank

        def write_bank(values):
            self._counter_timing_bank = validate_counter_bank(values)

        def publish(values):
            self.counter_timing_publication = dict(
                name="C1011NI6602", values=validate_counter_bank(values),
                transport="LOCAL_RAM_REPLACEMENT_NOT_PSP", psp_delivered=False,
                hardware_acknowledged=False, physical_readback=False)

        try:
            result = execute_counter_timing(
                read_bank, write_bank, publish, self.owner.read_counter_pulse_done,
                self._source_counter_stop, self._source_counter_timing_properties,
                self._source_counter_start, cancel.wait, cancel.is_set)
        except Exception as error:
            self._retain_control_failure(error)
            self.last_counter_timing = copy.deepcopy(self.procedure.get("report"))
            if isinstance(self.last_counter_timing, dict):
                self._pending_counter_stops.update(self.last_counter_timing.get("pending_counter_stops", ()))
            raise
        self.last_counter_timing = copy.deepcopy(result)
        self.procedure.update(state="SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK", report=result)
        return result

    def _source_commit_analog(self, group, values):
        if group == "C9NI6703":
            self._require_known_ht_command()
        vector = tuple(values)
        if len(vector) != 10 or any(type(value) not in (int, float) or not math.isfinite(value)
                                    for value in vector):
            raise ValueError("Complete finite ten-channel logical AO bank required")
        # Validate the WHOLE bank before invoking any driver method. This is
        # representability, not source admission or physical operating range.
        for index, value in enumerate(vector):
            logical_ao_to_volts(group, index, value, self._ao_control_calibration)
        self._ensure_focal_quiescent()
        if group == "C9NI6703":
            self.ht_command_uncertain = True
        self.owner.write_analog_logical_bank(group, vector)
        self.commanded_analog[group] = tuple(float(value) for value in vector)
        if group == "C9NI6703":
            self.ht_command_uncertain = False

    def _source_write_local(self, bank, changes):
        changes = tuple(changes)
        if bank in AO_LOCALS:
            vector = list(self._source_read_local(bank))
            seen = set()
            for index, value in changes:
                if (type(index) is not int or not 0 <= index < 10 or index in seen
                        or type(value) not in (int, float) or not math.isfinite(value)):
                    raise ValueError("Finite named AO field assignment required")
                vector[index] = float(value)
                seen.add(index)
            if not seen:
                raise ValueError("Nonempty source AO assignment required")
            self._source_commit_analog(AO_LOCALS[bank], vector)
        elif bank in (46, 47, 48, 50):
            if len(changes) != 1 or changes[0][0] != -1:
                raise ValueError("Exact scalar source assignment required")
            value = changes[0][1]
            if (bank in (46, 47) and type(value) is not bool) or (
                    bank in (48, 50) and (type(value) is not float or not math.isfinite(value))):
                raise ValueError("Source scalar type changed")
            self._source_scalars[bank] = value
        else:
            released = []
            if bank == 15:
                # Explicit interrupted-General recovery policy. Without this,
                # a whole-bank stop could echo a remembered held Marche/RAZ.
                # Nominal source images already contain False in both fields.
                current = self._stage_read_local(15)
                for index in (0, 2):
                    if current[index] is not False:
                        self._pending_stage_restorations[(15, index)] = False
                        released.append(index)
                if released:
                    patches = dict(changes)
                    patches.update((index, False) for index in released)
                    changes = tuple(sorted(patches.items()))
            self._stage_write_local(bank, changes)
            for index in released:
                self._pending_stage_restorations.pop((15, index), None)

    def _retain_control_failure(self, error):
        report = getattr(error, "report", getattr(error, "result", None))
        if isinstance(report, dict):
            for bank, index, value in report.get("pending_output_restorations", ()):
                if (bank not in (15, 17) or type(index) is not int
                        or not 0 <= index < (32 if bank == 15 else 40) or type(value) is not bool):
                    raise ValueError("Invalid retained source pulse restoration")
                self._pending_stage_restorations[(bank, index)] = value
        self.procedure.update(state="INTERRUPTED_OR_FAILED", report=copy.deepcopy(report),
                              error_type=type(error).__name__)

    def execute_impulsion(self, operation, cancel, operator_confirmed=False, new_value=True):
        from .acquisition_impulsion import execute_impulsion
        if operation not in IMPULSION_OPERATIONS or type(new_value) is not bool:
            raise ValueError("Reviewed impulsion operation and Boolean NewVal required")
        if operator_confirmed is not True:
            raise ValueError("Explicit local impulsion confirmation required")
        if not new_value:
            return False
        self._source_preflight("counter_controls_verified", True,
                               retry_counters=not operation.endswith(".stop"))
        self.procedure = dict(name=operation, state="EXECUTING", hardware_acknowledged=False)
        self.record_procedure_request(operation)
        try:
            result = execute_impulsion(
                operation, self._source_counter_start, self.owner.read_counter_pulse_done,
                self._source_counter_stop, self._source_read_local, self._source_write_local,
                self._stage_publish, self.stop_wait if operation.endswith(".stop") else cancel.wait,
                (lambda: False) if operation.endswith(".stop") else cancel.is_set,
                lambda frame, uid: self.procedure.update(frame=frame, source_uid=uid),
                execution_wait=self._execution_waiter(
                    self.stop_wait if operation.endswith(".stop") else cancel.wait))
        except Exception as error:
            self._retain_control_failure(error)
            self.last_impulsion = copy.deepcopy(self.procedure.get("report"))
            raise
        self.last_impulsion = copy.deepcopy(result)
        self.procedure.update(state="SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK", report=result)
        return result

    def set_ht_voltage(self, command_kv, cancel, operator_confirmed=False):
        from .acquisition_ht_voltage import execute_ht_voltage
        command_kv = validate_ht_command(command_kv)
        self._source_preflight("ht_voltage_controls_verified", operator_confirmed)
        self.procedure = dict(name="alimentation_ht.voltage", state="EXECUTING", hardware_acknowledged=False)
        try:
            result = execute_ht_voltage(
                command_kv, lambda name: tuple(self.commanded_analog[name]),
                self._source_commit_analog, cancel.is_set)
        except Exception as error:
            self._retain_control_failure(error)
            self.last_ht_command = copy.deepcopy(self.procedure.get("report"))
            if isinstance(self.last_ht_command, dict):
                self.ht_command_uncertain = self.last_ht_command.get("command_uncertain") is True
            raise
        self.ht_command_uncertain = False
        self.last_ht_command = copy.deepcopy(result)
        self.procedure.update(state="SOFTWARE_COMMAND_COMPLETED_NOT_HARDWARE_ACK", report=result)
        return result

    def outer_controlled_stop(self, operator_confirmed=False):
        from .acquisition_outer_stop import execute_outer_stop
        self._source_preflight("outer_stop_verified", operator_confirmed, retry_counters=False)
        self.procedure = dict(name="acquisition.outer_controlled_stop", state="EXECUTING",
                              hardware_acknowledged=False, source_general_event6=False,
                              resource_release=False, physical_off_confirmed=False)
        try:
            result = execute_outer_stop(
                self._source_read_local, self._source_write_local, self.owner.read_counter_pulse_done,
                self._source_counter_stop, self.stop_wait, lambda: False,
                lambda frame, uid: self.procedure.update(frame=frame, source_uid=uid),
                execution_wait=self._execution_waiter(self.stop_wait))
        except Exception as error:
            self._retain_control_failure(error)
            self.last_outer_stop = copy.deepcopy(self.procedure.get("report"))
            raise
        self.last_outer_stop = copy.deepcopy(result)
        self.procedure.update(state="SOFTWARE_SEQUENCE_COMPLETED_NOT_HARDWARE_ACK", report=result)
        return result

    def _source_control_snapshot(self):
        return dict(source_scalars=copy.deepcopy(self._source_scalars),
                    pending_counter_stops=sorted(self._pending_counter_stops),
                    ht_command_uncertain=self.ht_command_uncertain,
                    counter_configuration_uncertain=sorted(self._counter_configuration_uncertain),
                    commanded_counter_ticks=copy.deepcopy(self.commanded_counter_ticks),
                    counter_ticks_interpretation="Last successful property callbacks; not physical timing readback",
                    counter_timing_local_image=self._counter_timing_bank,
                    counter_timing_publication=copy.deepcopy(self.counter_timing_publication),
                    last_counter_timing=copy.deepcopy(self.last_counter_timing),
                    last_impulsion=copy.deepcopy(self.last_impulsion),
                    last_ht_command=copy.deepcopy(self.last_ht_command),
                    last_outer_stop=copy.deepcopy(self.last_outer_stop),
                    physical_off_confirmed=False, resource_release=False)
