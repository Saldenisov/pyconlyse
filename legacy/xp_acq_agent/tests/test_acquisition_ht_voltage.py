"""Offline scalar HT transfer tests: callback fakes, no device or endpoint."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elyse_agent.acquisition_ht_voltage import (
    BANK_NAME, DRIVER_DOMAIN_POLICY, HTVoltageCancelled, HTVoltageError,
    SOURCE_PROVENANCE, execute_ht_voltage,
)
from elyse_agent.hardware_plan import (
    analog_startup_logical_image, load_ao_calibration, logical_ao_to_volts,
)


class FakeBank(object):
    def __init__(self):
        self.bank = (6.5, 0.0, 4.755, 4.755, 2.126, 2.126, 2.126, 0, -0.25, 1)
        self.trace = []
        self.cancel = False
        self.read_error = False
        self.commit_error = False
        self.cancel_stage = None
        self.observer_error = None

    def read(self, name):
        self.trace.append(("read", name))
        if self.read_error:
            raise RuntimeError("injected read failure")
        return self.bank

    def commit(self, name, values):
        self.trace.append(("commit", name, values))
        self.bank = values
        if self.commit_error:
            raise RuntimeError("injected write may already have applied")

    def cancelled(self):
        return self.cancel

    def observe(self, stage):
        self.trace.append(("observe", stage))
        if self.cancel_stage == stage:
            self.cancel = True
        if self.observer_error == stage:
            raise RuntimeError("injected observer failure")

    def run(self, value=12.7, **changes):
        callbacks = dict(read_bank=self.read, commit_bank=self.commit,
                         cancelled=self.cancelled, observer=self.observe)
        callbacks.update(changes)
        return execute_ht_voltage(value, **callbacks)


class HTVoltageTests(unittest.TestCase):
    def test_complete_bank_transfer_preserves_other_fields_and_has_no_ack(self):
        fake = FakeBank()
        before = fake.bank
        report = fake.run()
        after = (12.7,) + before[1:]
        self.assertEqual(fake.trace, [
            ("observe", "read_bank"), ("read", BANK_NAME),
            ("observe", "commit_bank"), ("commit", BANK_NAME, after),
            ("observe", "complete"),
        ])
        self.assertEqual(fake.bank, after)
        self.assertEqual(report["bank_before"], before)
        self.assertEqual(report["requested_bank"], after)
        self.assertEqual(report["last_successful_bank"], after)
        self.assertEqual(report["last_successful_command_kv"], 12.7)
        self.assertEqual(report["attempted_command_kv"], 12.7)
        self.assertEqual(report["driver_target_volts"], 6.35)
        self.assertEqual(report["status"], "COMPLETE")
        self.assertTrue(report["commit_completed"])
        self.assertTrue(report["software_command_only"])
        self.assertFalse(report["command_uncertain"])
        self.assertFalse(report["hardware_acknowledged"])
        self.assertFalse(report["operating_permit_qualified"])
        self.assertEqual(report["driver_domain_policy"], DRIVER_DOMAIN_POLICY)

    def test_source_domain_not_supervision_operating_clamp_or_autonomous_ramp(self):
        for command in (-20.0, -7.2, 0, 0.1, 5.9, 6.5, 20.0):
            fake = FakeBank()
            result = fake.run(command)
            commits = [row for row in fake.trace if row[0] == "commit"]
            self.assertEqual(len(commits), 1)
            self.assertEqual(commits[0][2][0], command)
            self.assertEqual(result["driver_target_volts"], command * 0.5)
            self.assertEqual(result["last_successful_command_kv"], command)

    def test_same_command_still_commits_once_no_invented_noop(self):
        fake = FakeBank()
        fake.run(6.5)
        self.assertEqual(len([row for row in fake.trace if row[0] == "commit"]), 1)

    def test_invalid_command_rejected_before_any_callback(self):
        values = [True, False, None, "12.7", (), complex(1, 0),
                  float("nan"), float("inf"), -float("inf"),
                  20.000001, -20.000001, 10 ** 400]
        for command in values:
            fake = FakeBank()
            with self.assertRaises(ValueError):
                fake.run(command)
            self.assertEqual(fake.trace, [])

    def test_all_callback_shapes_preflight(self):
        for name in ("read_bank", "commit_bank", "cancelled", "observer"):
            fake = FakeBank()
            with self.assertRaises(TypeError):
                fake.run(**{name: 4})
            self.assertEqual(fake.trace, [])

    def test_optional_observer(self):
        fake = FakeBank()
        result = fake.run(observer=None)
        self.assertEqual([row[0] for row in fake.trace], ["read", "commit"])
        self.assertEqual(result["status"], "COMPLETE")

    def test_complete_snapshot_rejects_malformed_nonfinite_or_boolean(self):
        invalid = [None, [], [0.0] * 10, (0.0,) * 9, (0.0,) * 11]
        invalid.extend((0.0,) * index + (bad,) + (0.0,) * (9 - index)
                       for index in range(10)
                       for bad in (True, False, None, "1", float("nan"),
                                   float("inf"), -float("inf"), 10 ** 400))
        for bank in invalid:
            fake = FakeBank()
            fake.bank = bank
            with self.assertRaises(HTVoltageError) as caught:
                fake.run()
            report = caught.exception.report
            self.assertEqual(report["status"], "FAILED")
            self.assertFalse(report["commit_attempted"])
            self.assertFalse(report["command_uncertain"])
            self.assertIsNone(report["last_successful_command_kv"])
            self.assertEqual(report["failures"][0]["stage"], "read_bank")
            self.assertFalse(any(row[0] == "commit" for row in fake.trace))

    def test_snapshot_need_not_restrict_previous_field0_to_new_driver_domain(self):
        # A valid new command may replace an invalid historic software request.
        fake = FakeBank()
        fake.bank = (40.0,) + fake.bank[1:]
        result = fake.run(0)
        self.assertEqual(result["bank_before"][0], 40.0)
        self.assertEqual(fake.bank[0], 0)

    def test_read_error_never_commits_or_claims_unknown_previous_command(self):
        fake = FakeBank()
        fake.read_error = True
        with self.assertRaises(HTVoltageError) as caught:
            fake.run()
        result = caught.exception.report
        self.assertIsNone(result["last_successful_command_kv"])
        self.assertFalse(result["commit_attempted"])
        self.assertFalse(result["command_uncertain"])

    def test_commit_failure_preserves_success_image_and_marks_ambiguous_no_retry(self):
        fake = FakeBank()
        before = fake.bank
        fake.commit_error = True
        with self.assertRaises(HTVoltageError) as caught:
            fake.run()
        result = caught.exception.report
        self.assertEqual(result["last_successful_command_kv"], before[0])
        self.assertEqual(result["last_successful_bank"], before)
        self.assertEqual(result["requested_bank"], fake.bank)
        self.assertEqual(result["attempted_command_kv"], 12.7)
        self.assertTrue(result["commit_attempted"])
        self.assertFalse(result["commit_completed"])
        self.assertTrue(result["command_uncertain"])
        self.assertEqual(result["failures"][0]["stage"], "commit_bank")
        self.assertEqual(len([row for row in fake.trace if row[0] == "commit"]), 1)

    def test_cancel_before_read_prevents_bank_and_observer_callbacks(self):
        fake = FakeBank()
        fake.cancel = True
        with self.assertRaises(HTVoltageCancelled) as caught:
            fake.run()
        self.assertEqual(fake.trace, [])
        self.assertTrue(caught.exception.report["cancelled"])
        self.assertFalse(caught.exception.report["command_uncertain"])

    def test_callback_public_error_cannot_replace_this_invocations_uncertainty(self):
        foreign = dict(operation="foreign", status="CANCELLED",
                       command_uncertain=False)
        for error_type in (HTVoltageError, HTVoltageCancelled):
            fake = FakeBank()
            before = fake.bank

            def commit(name, values):
                fake.commit(name, values)
                raise error_type(foreign)

            with self.assertRaises(HTVoltageError) as caught:
                fake.run(commit_bank=commit)
            result = caught.exception.report
            self.assertEqual(result["operation"], "alimentation_ht.voltage")
            self.assertEqual(result["status"], "FAILED")
            self.assertTrue(result["command_uncertain"])
            self.assertFalse(result["cancelled"])
            self.assertEqual(result["last_successful_bank"], before)
            self.assertEqual(result["attempted_command_kv"], 12.7)

    def test_cancel_from_read_or_commit_observer_prevents_output_callback(self):
        for stage in ("read_bank", "commit_bank"):
            fake = FakeBank()
            before = fake.bank
            fake.cancel_stage = stage
            with self.assertRaises(HTVoltageCancelled) as caught:
                fake.run()
            result = caught.exception.report
            self.assertEqual(fake.bank, before)
            self.assertFalse(result["commit_attempted"])
            self.assertFalse(result["command_uncertain"])
            self.assertFalse(any(row[0] == "commit" for row in fake.trace))

    def test_cancel_arrives_during_read_prevents_commit(self):
        fake = FakeBank()

        def read(name):
            value = fake.read(name)
            fake.cancel = True
            return value

        with self.assertRaises(HTVoltageCancelled) as caught:
            fake.run(read_bank=read)
        self.assertFalse(caught.exception.report["commit_attempted"])
        self.assertEqual(caught.exception.report["last_successful_command_kv"], 6.5)

    def test_cancel_after_commit_never_rolls_back_or_raises_command(self):
        fake = FakeBank()

        def commit(name, bank):
            fake.commit(name, bank)
            fake.cancel = True

        with self.assertRaises(HTVoltageCancelled) as caught:
            fake.run(0, commit_bank=commit)
        result = caught.exception.report
        self.assertEqual(fake.bank[0], 0)
        self.assertEqual(result["last_successful_command_kv"], 0)
        self.assertTrue(result["commit_completed"])
        self.assertFalse(result["command_uncertain"])
        self.assertEqual(len([row for row in fake.trace if row[0] == "commit"]), 1)

    def test_cancel_after_complete_observer_retains_success(self):
        fake = FakeBank()
        fake.cancel_stage = "complete"
        with self.assertRaises(HTVoltageCancelled) as caught:
            fake.run()
        self.assertEqual(caught.exception.report["last_successful_command_kv"], 12.7)
        self.assertTrue(caught.exception.report["commit_completed"])

    def test_cancellation_must_be_exact_bool(self):
        for value in (None, 0, 1, "False"):
            fake = FakeBank()
            with self.assertRaises(HTVoltageError) as caught:
                fake.run(cancelled=lambda: value)
            self.assertEqual(fake.trace, [])
            self.assertFalse(caught.exception.report["commit_attempted"])

    def test_observer_failures_distinguish_precommit_and_acknowledged_commit(self):
        for stage in ("read_bank", "commit_bank", "complete"):
            fake = FakeBank()
            fake.observer_error = stage
            with self.assertRaises(HTVoltageError) as caught:
                fake.run()
            result = caught.exception.report
            completed = stage == "complete"
            self.assertEqual(result["commit_completed"], completed)
            self.assertFalse(result["command_uncertain"])
            if completed:
                self.assertEqual(result["last_successful_command_kv"], 12.7)
            self.assertEqual(len([row for row in fake.trace if row[0] == "commit"]),
                             1 if completed else 0)

    def test_cancel_probe_error_after_commit_does_not_erase_ack_or_retry(self):
        fake = FakeBank()

        def cancelled():
            if any(row[0] == "commit" for row in fake.trace):
                raise RuntimeError("cancel probe failed")
            return False

        with self.assertRaises(HTVoltageError) as caught:
            fake.run(cancelled=cancelled)
        result = caught.exception.report
        self.assertTrue(result["commit_completed"])
        self.assertFalse(result["command_uncertain"])
        self.assertEqual(result["last_successful_command_kv"], 12.7)
        self.assertEqual(len([row for row in fake.trace if row[0] == "commit"]), 1)

    def test_source_provenance_report_is_not_shared_mutable_state(self):
        report = FakeBank().run()
        report["source_path"]["logical_field"] = 8
        self.assertEqual(SOURCE_PROVENANCE["logical_field"], 0)
        self.assertEqual(FakeBank().run()["source_path"]["logical_field"], 0)


class HTVoltageSourceCrosscheckTests(unittest.TestCase):
    def test_committed_psp_contract_maps_c9_reader_to_local12_complete_dbl_bank(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data",
                            "saved_psp_reads_contract.json")
        with open(path, "r") as stream:
            contract = json.load(stream)
        matches = [row for row in contract["sites"] if row["tag"] == BANK_NAME]
        self.assertEqual(len(matches), 1)
        row = matches[0]
        self.assertEqual(row["frame_uid"], SOURCE_PROVENANCE["timeout_frame_uid"])
        self.assertEqual(row["node_uid"], SOURCE_PROVENANCE["dynamic_reader_uid"])
        self.assertEqual(row["local_bank"], SOURCE_PROVENANCE["local_bank"])
        self.assertEqual(row["size"], 10)
        self.assertEqual(row["element_family"], "NumFloat64")
        self.assertFalse(row["native_return_semantics_qualified"])
        self.assertFalse(contract["atomic_snapshots_qualified"])

    def test_existing_calibration_maps_12point7_to_6point35_volts(self):
        calibration = load_ao_calibration()
        row = calibration[(BANK_NAME, 0)]
        self.assertEqual((row["scale"], row["offset"]), (0.5, 0.0))
        self.assertEqual(row["physical_channel"], "/9/ao0")
        self.assertEqual(logical_ao_to_volts(BANK_NAME, 0, 12.7, calibration), 6.35)
        self.assertEqual(logical_ao_to_volts(BANK_NAME, 0, -20, calibration), -10)
        self.assertEqual(logical_ao_to_volts(BANK_NAME, 0, 20, calibration), 10)

    def test_existing_startup6point5_maps_to_3point25_volts_not_operating_clamp(self):
        initial = analog_startup_logical_image()[BANK_NAME][0]
        self.assertEqual(initial, 6.5)
        self.assertEqual(logical_ao_to_volts(BANK_NAME, 0, initial), 3.25)
        self.assertEqual(FakeBank().run(initial)["driver_target_volts"], 3.25)


if __name__ == "__main__":
    unittest.main()
