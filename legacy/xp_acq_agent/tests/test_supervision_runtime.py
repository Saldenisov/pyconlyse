"""These tests run unchanged on CPython 3.4.4; no hardware driver imports."""
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest

from elyse_agent.supervision_runtime import MemoryOutputs, Rejected, SupervisionRuntime, load_plans


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.path = os.path.join(self.directory, "state.sqlite3")
        self.runtime = SupervisionRuntime(self.path, time_scale=0)

    def tearDown(self):
        self.runtime.close()
        shutil.rmtree(self.directory)

    def submit(self, intent_id, procedure="cooling.start"):
        state = self.runtime.read_state()
        return self.runtime.submit_procedure(intent_id, procedure, state["revision"], state["session_id"])

    def finished(self):
        self.runtime._worker.join(5)
        self.assertFalse(self.runtime._worker.is_alive())
        return self.runtime.read_state()

    def test_all_20_routable_procedures_follow_every_reviewed_step(self):
        for name, plan in sorted(self.runtime.plans.items()):
            if plan["blocked_reason"]:
                continue
            with self.subTest(procedure=name):
                intent_id = "all-{0}".format(plan["legacy_event_case"])
                self.assertEqual(self.submit(intent_id, name)["state"], "ACCEPTED")
                self.assertEqual(self.finished()["run"]["state"], "SUCCEEDED")
                trace = self.runtime.trace(intent_id)
                succeeded = [item for item in trace if item["outcome"] == "SUCCEEDED" and item["step_index"] >= 0]
                self.assertEqual([item["operation"] for item in succeeded], [step["operation"] for step in plan["steps"]])
                self.assertEqual([item["step_index"] for item in succeeded], list(range(len(plan["steps"]))))
                self.assertFalse(any(self.runtime.read_state()["dps"]))

    def test_all_29_dps_bits_gate_admission(self):
        for index in range(29):
            with self.subTest(index=index):
                flags = [False] * 29
                flags[index] = True
                with self.runtime._db() as db:
                    self.runtime._put(db, "dps", json.dumps(flags))
                with self.assertRaises(Rejected):
                    self.submit("bit-{0}".format(index))
                self.assertEqual(self.runtime.read_state()["dps"], flags)

    def test_atomic_revision_deduplication_and_same_id_payload_conflict(self):
        before = self.runtime.read_state()
        receipt = self.submit("one")
        self.finished()
        count = len(self.runtime.trace("one"))
        repeated = self.runtime.submit_procedure("one", "cooling.start", before["revision"], before["session_id"])
        self.assertEqual(repeated["state"], "SUCCEEDED")
        self.assertEqual(len(self.runtime.trace("one")), count)
        with self.assertRaises(Rejected):
            self.runtime.submit_procedure("one", "cooling.stop", before["revision"], before["session_id"])
        with self.assertRaises(Rejected):
            self.runtime.submit_procedure("other", "cooling.start", before["revision"], before["session_id"])
        self.assertEqual(receipt["state"], "ACCEPTED")

    def test_single_flight_while_worker_running(self):
        entered, release = threading.Event(), threading.Event()

        def hook(index, step):
            if index == 0:
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("Test worker was not released")

        self.runtime.step_hook = hook
        try:
            self.submit("first")
            self.assertTrue(entered.wait(5))
            with self.assertRaises(Rejected):
                self.submit("second", "cooling.stop")
        finally:
            release.set()
        self.assertEqual(self.finished()["run"]["state"], "SUCCEEDED")

    def test_failure_at_every_routable_step_records_failure_then_permits_next_intent(self):
        for name, plan in sorted(self.runtime.plans.items()):
            if plan["blocked_reason"]:
                continue
            for fault_index in range(len(plan["steps"])):
                with self.subTest(procedure=name, step=fault_index):
                    def hook(index, step, expected=fault_index):
                        if index == expected:
                            raise RuntimeError("Injected step failure")
                    self.runtime.step_hook = hook
                    intent_id = "failure-{0}-{1}".format(plan["legacy_event_case"], fault_index)
                    self.submit(intent_id, name)
                    state = self.finished()
                    self.assertEqual(state["run"]["state"], "FAILED")
                    self.assertIn("Injected step failure", state["run"]["error"])
                    self.assertFalse(any(state["dps"]))
                    started = [item for item in self.runtime.trace(intent_id) if item["outcome"] == "STARTED"]
                    self.assertEqual(len(started), fault_index + 1)

    def test_magnets_orphan_pt_and_raw_io_are_not_dispatchable(self):
        for name in ("magnets_power.start", "magnets_power.stop", "magnets_power.zero_v", "magnets_power.pt", "write_digital"):
            with self.assertRaises(Rejected):
                self.submit("blocked", name)
        self.assertEqual(self.runtime.read_state()["run"]["state"], "IDLE")

    def test_restart_restores_terminal_history_and_logical_image(self):
        self.submit("completed", "modulator.heating.start")
        self.finished()
        image = self.runtime.outputs.image.copy()
        old_session = self.runtime.session_id
        trace = self.runtime.trace("completed")
        self.runtime.close()
        self.runtime = SupervisionRuntime(self.path, time_scale=0)
        self.assertNotEqual(self.runtime.session_id, old_session)
        self.assertEqual(self.runtime.read_intent("completed")["session_id"], old_session)
        self.assertEqual(self.runtime.read_intent("completed")["run"]["state"], "SUCCEEDED")
        self.assertEqual(self.runtime.outputs.image, image)
        self.assertEqual(self.runtime.trace("completed"), trace)

    def test_incomplete_admission_is_unknown_on_restart_not_reset_or_reexecuted(self):
        self.submit("crash")
        self.finished()
        with self.runtime._db() as db:
            db.execute("UPDATE intents SET state='RUNNING' WHERE intent_id='crash'")
            db.execute("INSERT INTO active(slot,intent_id) VALUES (1,'crash')")
            flags = [False] * 29
            flags[0] = True
            self.runtime._put(db, "dps", json.dumps(flags))
        self.runtime.close()
        self.runtime = SupervisionRuntime(self.path, time_scale=0)
        self.assertEqual(self.runtime.read_state()["run"]["state"], "UNKNOWN")
        self.assertTrue(self.runtime.read_state()["dps"][0])
        with self.assertRaises(Rejected):
            self.submit("new")
        self.assertIsNone(self.runtime._worker)

    def test_second_process_owner_is_rejected_without_resetting_first(self):
        with self.assertRaises(sqlite3.OperationalError):
            SupervisionRuntime(self.path, time_scale=0)
        self.assertEqual(self.runtime.read_state()["run"]["state"], "IDLE")

    def test_simulated_images_of_all_23_plans_are_pure_data(self):
        for name, plan in load_plans().items():
            with self.subTest(procedure=name):
                image = MemoryOutputs()
                waits = []
                for step in plan["steps"]:
                    image.execute(step, waits.append)
                self.assertIsInstance(image.image, dict)
                self.assertTrue(all(seconds >= 0 for seconds in waits))

    def test_completion_resets_only_own_dps_flag(self):
        def hook(index, step):
            if index == 0:
                with self.runtime._db() as db:
                    flags = json.loads(self.runtime._meta(db, "dps"))
                    flags[28] = True
                    self.runtime._put(db, "dps", json.dumps(flags))

        self.runtime.step_hook = hook
        self.submit("preserve-unrelated", "cooling.start")
        flags = self.finished()["dps"]
        self.assertTrue(flags[28])
        self.assertFalse(flags[0])
        with self.assertRaises(Rejected):
            self.submit("still-busy")


if __name__ == "__main__":
    unittest.main()
