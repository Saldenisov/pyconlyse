"""Unaveraged native AI contracts; stdlib-only, actual Python 3.4 compatible.

All tasks are Python fakes. These tests never initialize cards, import NI or
NumPy, open a socket, launch a process, or communicate with a live server.
The finite ten-sample hardware acquisition remains unchanged; only the Python
projection selects the last raw sample instead of calculating a mean.
"""
import builtins
import copy
import json
import threading
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent import acquisition_backend
from legacy.xp_acq_control.elyse_agent import hardware_tasks
from legacy.xp_acq_control.elyse_agent.hardware_plan import (
    AI_BANKS, DI_BANKS, analog_startup_logical_image, digital_startup_image,
)
from legacy.xp_acq_control.elyse_agent.input_tasks import AI_TIMING, InputTaskSet
from legacy.xp_acq_control.elyse_agent.standard_banks import (
    BANKS, COMMANDS, INPUTS, UNAVAILABLE, standard_packet,
    validate_standard_packet,
)
from legacy.xp_acq_control.elyse_agent.transforms import channel_last_samples


class ReadFailure(RuntimeError):
    pass


class FakeTask(object):
    def __init__(self, name, values, events=None):
        self.name, self.values = name, values
        self.events = events if events is not None else []
        self.read_calls = []
        self.error = None

    def start(self):
        self.events.append((self.name, "start"))

    def read(self, **kwargs):
        self.events.append((self.name, "read"))
        self.read_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return copy.deepcopy(self.values)

    def stop(self):
        self.events.append((self.name, "stop"))


def block(count, final=8.0):
    return [[0.0] * 9 + [final + index] for index in range(count)]


def fake_owner(events=None):
    events = events if events is not None else []
    tasks = dict((name, FakeTask(name, block(count), events))
                 for name, device, count in AI_BANKS)
    for name, device, first, last, count in DI_BANKS:
        tasks[name] = FakeTask(name, [False] * count, events)
    return hardware_tasks.LegacyCardTasks(None, {}, tasks, {}), events


def fake_backend():
    owner, events = fake_owner()
    backend = acquisition_backend.CardBackend(factory=lambda **kwargs: None,
                                               read_timeout=0.25)
    backend.owner = owner
    backend.startup_complete = True  # Explicit fully initialized offline fixture.
    backend.calibration = dict(((name, index), (2.0, 0.25))
                               for name, device, count in AI_BANKS
                               for index in range(count))
    backend.commanded_digital = dict((name, list(values))
                                     for name, values in digital_startup_image().items())
    backend.commanded_analog = dict((name, list(values))
                                    for name, values in analog_startup_logical_image().items())
    backend.initial_images = dict(digital=copy.deepcopy(backend.commanded_digital))
    return backend, owner, events


class LastSampleTransformTests(unittest.TestCase):
    def test_final_impulse_is_not_a_mean(self):
        self.assertEqual(channel_last_samples([[0.0] * 9 + [10.0]], 1, 10), [10.0])

    def test_huge_finite_prefix_is_not_summed(self):
        self.assertEqual(channel_last_samples([[1e308] * 9 + [1.5]], 1, 10), [1.5])

    def test_all_channel_blocks_select_their_own_last_value(self):
        for name, device, count in AI_BANKS:
            with self.subTest(bank=name):
                values = block(count)
                before = copy.deepcopy(values)
                self.assertEqual(channel_last_samples(values, count, 10),
                                 [8.0 + index for index in range(count)])
                self.assertEqual(values, before)

    def test_tuple_blocks_and_integer_samples_are_supported(self):
        self.assertEqual(channel_last_samples(((1, 2, 3), (4, 5, 6)), 2, 3), [3.0, 6.0])

    def test_exact_positive_shape_arguments_required(self):
        invalid = (0, -1, True, False, 1.0, "1", None)
        for value in invalid:
            for channels, samples in ((value, 10), (1, value)):
                with self.subTest(channels=channels, samples=samples):
                    with self.assertRaises(ValueError):
                        channel_last_samples([[1.0] * 10], channels, samples)

    def test_empty_short_extra_and_malformed_outer_blocks_rejected(self):
        invalid = (None, {}, "bad", iter([[1.0] * 10]), [],
                   [[1.0] * 10] * 63, [[1.0] * 10] * 65)
        for values in invalid:
            with self.subTest(block_type=type(values).__name__):
                with self.assertRaises(ValueError):
                    channel_last_samples(values, 64, 10)

    def test_empty_short_extra_and_malformed_channel_rows_rejected(self):
        for row in ([], [1.0] * 9, [1.0] * 11, None, 3.0, {}, "0123456789"):
            values = block(64)
            values[31] = row
            with self.subTest(row_type=type(row).__name__):
                with self.assertRaises(ValueError):
                    channel_last_samples(values, 64, 10)

    def test_invalid_values_anywhere_in_prefix_or_final_sample_rejected(self):
        bad_values = (True, False, None, "2.0", complex(2, 0), object(),
                      float("nan"), float("inf"), -float("inf"), 10 ** 400)
        for bad in bad_values:
            for channel, sample in ((0, 0), (31, 4), (63, 9)):
                values = block(64)
                values[channel][sample] = bad
                with self.subTest(type=type(bad).__name__, channel=channel, sample=sample):
                    with self.assertRaises(ValueError):
                        channel_last_samples(values, 64, 10)


class LastSampleTaskTests(unittest.TestCase):
    def test_finite_timing_trigger_and_channel_counts_are_unchanged(self):
        self.assertEqual(AI_BANKS, (("C1_NI6071E_AI", 1, 64),
                                    ("C2_NI6071E_AI", 2, 64),
                                    ("C11_NI6220_AI", 11, 16)))
        self.assertEqual(AI_TIMING, {
            "C1_NI6071E_AI": ("/1/PFI0", 5000.0, 10),
            "C2_NI6071E_AI": ("/2/PFI0", 5000.0, 10),
            "C11_NI6220_AI": ("/11/PFI0", 5000.0, 10),
        })

    def test_each_task_reads_complete_ten_sample_block_without_starting_or_stopping(self):
        owner, events = fake_owner()
        for name, device, count in AI_BANKS:
            with self.subTest(bank=name):
                self.assertEqual(owner.read_analog_latest(name, timeout_seconds=0.125),
                                 [8.0 + index for index in range(count)])
                self.assertEqual(owner.tasks[name].read_calls,
                                 [dict(number_of_samples_per_channel=10, timeout=0.125)])
        self.assertEqual(events, [(name, "read") for name, device, count in AI_BANKS])

    def test_default_and_integer_timeout_are_forwarded_as_floats(self):
        owner, events = fake_owner()
        name = AI_BANKS[0][0]
        owner.read_analog_latest(name)
        owner.read_analog_latest(name, timeout_seconds=2)
        self.assertEqual(owner.tasks[name].read_calls, [
            dict(number_of_samples_per_channel=10, timeout=10.0),
            dict(number_of_samples_per_channel=10, timeout=2.0)])

    def test_invalid_timeout_fails_before_driver_read(self):
        owner, events = fake_owner()
        for timeout in (0, -1, True, False, None, "0.5", float("nan"),
                        float("inf"), -float("inf"), 10 ** 400):
            with self.subTest(timeout_type=type(timeout).__name__):
                with self.assertRaises(ValueError):
                    owner.read_analog_latest(AI_BANKS[0][0], timeout_seconds=timeout)
        self.assertEqual(events, [])

    def test_unknown_bank_and_closed_owner_fail_without_read(self):
        owner, events = fake_owner()
        with self.assertRaises(ValueError):
            owner.read_analog_latest("C9NI6703")
        owner.closed = True
        with self.assertRaises(RuntimeError):
            owner.read_analog_latest(AI_BANKS[0][0])
        self.assertEqual(events, [])

    def test_invalid_configured_sample_count_fails_before_read(self):
        owner, events = fake_owner()
        name = AI_BANKS[0][0]
        for count in (0, -1, True, 10.0):
            with mock.patch.dict(AI_TIMING, {name: ("/1/PFI0", 5000.0, count)}):
                with self.assertRaises(ValueError):
                    owner.read_analog_latest(name)
        self.assertEqual(events, [])

    def test_driver_exception_propagates_without_retry_or_cached_fallback(self):
        owner, events = fake_owner()
        name = AI_BANKS[0][0]
        owner.read_analog_latest(name)
        failure = ReadFailure("fixture native read failure")
        owner.tasks[name].error = failure
        with self.assertRaises(ReadFailure) as raised:
            owner.read_analog_latest(name)
        self.assertIs(raised.exception, failure)
        self.assertEqual(len(owner.tasks[name].read_calls), 2)

    def test_invalid_block_never_falls_back_to_last_successful_sample(self):
        owner, events = fake_owner()
        name = AI_BANKS[0][0]
        owner.read_analog_latest(name)
        owner.tasks[name].values[4][0] = float("nan")
        with self.assertRaises(ValueError):
            owner.read_analog_latest(name)
        self.assertEqual(len(owner.tasks[name].read_calls), 2)


class UnaveragedBackendTests(unittest.TestCase):
    def test_snapshot_last_samples_calibration_once_metadata_and_no_command_mutation(self):
        backend, owner, events = fake_backend()
        before = copy.deepcopy((backend.commanded_digital, backend.commanded_analog,
                                backend.software_status_assignments, backend.initial_images))
        snapshot = backend.read_snapshot(threading.Event())
        for name, device, count in AI_BANKS:
            with self.subTest(bank=name):
                record = snapshot["banks"][name]
                selected = [8.0 + index for index in range(count)]
                self.assertEqual(record["values"], selected)
                self.assertEqual(record["legacy_scaled_values"],
                                 [value * 2.0 + 0.25 for value in selected])
                self.assertEqual(record["processing"], "last_raw_sample_of_finite_block")
                self.assertIs(record["software_averaging"], False)
                self.assertEqual(record["samples_per_channel_acquired"], 10)
                self.assertEqual(record["selected_sample_index"], 9)
                self.assertEqual(record["calibration"],
                                 "calibration_map.csv: selected_sample*scale+offset")
        expected = []
        for name, device, count in AI_BANKS:
            expected.extend((name, action) for action in ("start", "read", "stop"))
        expected.extend((name, "read") for name, device, first, last, count in DI_BANKS)
        self.assertEqual(events, expected)
        self.assertEqual((backend.commanded_digital, backend.commanded_analog,
                          backend.software_status_assignments, backend.initial_images), before)
        self.assertEqual(snapshot["commanded_analog_logical"], before[1])
        self.assertEqual(snapshot["commanded_digital"], before[0])

    def test_snapshot_driver_failure_still_stops_current_task_and_skips_later_reads(self):
        backend, owner, events = fake_backend()
        failure = ReadFailure("fixture failing input read")
        name = AI_BANKS[0][0]
        owner.tasks[name].error = failure
        with self.assertRaises(ReadFailure) as raised:
            backend.read_snapshot(threading.Event())
        self.assertIs(raised.exception, failure)
        self.assertEqual(events, [(name, "start"), (name, "read"), (name, "stop")])

    def test_snapshot_validation_failure_still_stops_current_task(self):
        backend, owner, events = fake_backend()
        name = AI_BANKS[0][0]
        owner.tasks[name].values[0][0] = float("nan")
        with self.assertRaises(ValueError):
            backend.read_snapshot(threading.Event())
        self.assertEqual(events, [(name, "start"), (name, "read"), (name, "stop")])

    def test_cancelled_snapshot_never_reads_or_starts_tasks(self):
        backend, owner, events = fake_backend()
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(acquisition_backend.AcquisitionCancelled):
            backend.read_snapshot(cancel)
        self.assertEqual(events, [])

    def test_unaveraged_snapshot_keeps_27_banks_12_valid_and_15_unavailable(self):
        backend, owner, events = fake_backend()
        snapshot = backend.read_snapshot(threading.Event())
        # The isolated JSON process boundary normalizes command-memory tuples.
        latest = json.loads(json.dumps(snapshot, allow_nan=False))
        runtime = dict(session_id="a" * 32, sequence=1, state_revision=2,
                       state="RUNNING", stale=False, age_seconds=0.1,
                       error="", latest=latest)
        packet = standard_packet(runtime, 1)
        validate_standard_packet(packet)
        records = dict((record["publication"], record) for record in packet["data"]["banks"])
        self.assertEqual(tuple(record["publication"] for record in packet["data"]["banks"]), BANKS)
        self.assertEqual(len(records), 27)
        valid = set(name for name, record in records.items() if not record["error"]["status"])
        self.assertEqual(valid, set(INPUTS) | set(COMMANDS))
        self.assertEqual(len(valid), 12)
        for name in set(BANKS) - valid:
            self.assertIsNone(records[name]["data"])
            self.assertEqual(records[name]["error"]["code"], UNAVAILABLE)
        self.assertEqual(records["C1NI6071E"]["data"],
                         [value * 2.0 + 0.25 for value in (8.0 + index for index in range(64))])
        for name, (section, source, count, kind) in COMMANDS.items():
            self.assertEqual(records[name]["data"], latest[section][source])

    def test_ht_shutdown_uses_same_last_sample_and_preserves_active_low_contact(self):
        for raw_contact in (False, True):
            backend, owner, events = fake_backend()
            owner.tasks["C2_NI6071E_AI"].values[7] = [0.0] * 9 + [3.0]
            owner.tasks["C4_DIO96_DI"].values[48] = raw_contact
            sample = backend._read_ht_shutdown_sample()
            self.assertEqual(sample["voltage_kv"], 6.25)
            self.assertIs(sample["raw_supply_contact"], raw_contact)
            self.assertIs(sample["supply_on"], not raw_contact)
            self.assertGreaterEqual(sample["age_seconds"], 0.0)
            self.assertEqual(events, [("C2_NI6071E_AI", "start"),
                                      ("C2_NI6071E_AI", "read"),
                                      ("C2_NI6071E_AI", "stop"),
                                      ("C4_DIO96_DI", "read")])

    def test_ht_shutdown_read_failure_stops_ai_and_does_not_read_contact(self):
        backend, owner, events = fake_backend()
        failure = ReadFailure("fixture HT read failure")
        owner.tasks["C2_NI6071E_AI"].error = failure
        with self.assertRaises(ReadFailure) as raised:
            backend._read_ht_shutdown_sample()
        self.assertIs(raised.exception, failure)
        self.assertEqual(events, [("C2_NI6071E_AI", "start"),
                                  ("C2_NI6071E_AI", "read"),
                                  ("C2_NI6071E_AI", "stop")])

    def test_ht_shutdown_invalid_prefix_still_stops_ai_without_contact_read(self):
        backend, owner, events = fake_backend()
        owner.tasks["C2_NI6071E_AI"].values[0][0] = float("inf")
        with self.assertRaises(ValueError):
            backend._read_ht_shutdown_sample()
        self.assertEqual(events, [("C2_NI6071E_AI", "start"),
                                  ("C2_NI6071E_AI", "read"),
                                  ("C2_NI6071E_AI", "stop")])

    def test_cold_import_and_construction_never_import_native_dependencies(self):
        original_import = builtins.__import__
        attempted = []

        def guarded_import(name, *args, **kwargs):
            if name.split(".")[0] in ("numpy", "nidaqmx"):
                attempted.append(name)
                raise AssertionError("Native dependency import forbidden in cold test")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            # Execute module code in fresh namespaces without reloading shared
            # module objects or changing exception/class identity for other tests.
            for module in (hardware_tasks, acquisition_backend):
                namespace = dict(__name__=module.__name__ + "_cold_fixture",
                                 __package__=module.__package__, __file__=module.__file__)
                exec(module.__loader__.get_code(module.__name__), namespace)
            factory = mock.Mock(side_effect=AssertionError("No task factory permitted"))
            backend = namespace["CardBackend"](factory=factory)
            owner, events = fake_owner()
            self.assertEqual(backend.resource_count, 0)
            self.assertIsNone(backend.owner)
            self.assertEqual(events, [])
            self.assertEqual(len(owner.tasks), 6)
            self.assertFalse(factory.called)
        self.assertEqual(attempted, [])


class InputOnlyProbeTests(unittest.TestCase):
    def test_legacy_probe_selects_last_sample_for_all_three_banks(self):
        owner, events = fake_owner()
        probe = InputTaskSet(owner.tasks)
        for name, device, count in AI_BANKS:
            self.assertEqual(probe.read_analog_latest(name, timeout_seconds=0.2),
                             [8.0 + index for index in range(count)])
            self.assertEqual(owner.tasks[name].read_calls,
                             [dict(number_of_samples_per_channel=10, timeout=0.2)])
        self.assertEqual(events, [(name, "read") for name, device, count in AI_BANKS])

    def test_probe_rejects_unknown_bank_and_invalid_timeouts_before_read(self):
        owner, events = fake_owner()
        probe = InputTaskSet(owner.tasks)
        with self.assertRaises(ValueError):
            probe.read_analog_latest("unknown")
        for timeout in (0, -1, True, False, None, "0.5", float("nan"),
                        float("inf"), -float("inf"), 10 ** 400):
            with self.assertRaises(ValueError):
                probe.read_analog_latest(AI_BANKS[0][0], timeout_seconds=timeout)
        self.assertEqual(events, [])

    def test_probe_rejects_malformed_and_nonfinite_blocks_without_cached_fallback(self):
        owner, events = fake_owner()
        probe = InputTaskSet(owner.tasks)
        name = AI_BANKS[0][0]
        probe.read_analog_latest(name)
        for malformed in ([], block(63), block(65), [[1.0] * 9] * 64,
                          [[1.0] * 11] * 64, [[float("nan")] + [1.0] * 9] * 64,
                          [[True] + [1.0] * 9] * 64):
            owner.tasks[name].values = malformed
            with self.assertRaises(ValueError):
                probe.read_analog_latest(name)
        self.assertEqual(len(owner.tasks[name].read_calls), 8)

    def test_probe_preserves_driver_exception_without_retry(self):
        owner, events = fake_owner()
        probe = InputTaskSet(owner.tasks)
        name = AI_BANKS[0][0]
        failure = ReadFailure("fixture probe read failure")
        owner.tasks[name].error = failure
        with self.assertRaises(ReadFailure) as raised:
            probe.read_analog_latest(name)
        self.assertIs(raised.exception, failure)
        self.assertEqual(events, [(name, "read")])


if __name__ == "__main__":
    unittest.main()
