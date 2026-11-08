"""No devices: archive round trips and explicit latest-only capture gaps."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import h5py

spec = importlib.util.spec_from_file_location(
    "recorder", Path(__file__).resolve().parents[2] / "tools/record_acq_telemetry_hdf5.py")
recorder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recorder)


def snapshot(count, sequence, session="receiver", data=None):
    bank = dict(data=data if data is not None else [False, 1.5, 2**63 + 1],
                error=dict(status=False, code=0, source=""), stale=False,
                session_id="source", relay_id="relay", sequence=sequence)
    return dict(source="copied_labview_telemetry", hardware_writes=False,
                storage_mode="ram_latest", receiver_session=session,
                received_this_process=count, publications={"C1NI6071E": bank})


class RecorderTests(unittest.TestCase):
    def python_snapshot(self, count=2):
        from tests.unit.test_acq_standard_telemetry import state, signed, KEY
        from legacy.xp_acq_control.elyse_agent.native_telemetry import standard_packet
        from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkStore
        store = TelemetrySinkStore(KEY, permitted_producer_kind="python_acquisition")
        try:
            store.accept(signed(standard_packet(state(), 1)))
            value = store.snapshot()
            value.update(receiver_session="receiver", received_this_process=count)
            return value
        finally:
            store.close()

    def test_python_standard_banks_keep_source_and_do_not_fabricate_unknown_statistics(self):
        observe = recorder.Observations()
        value = self.python_snapshot()
        self.assertTrue(observe.accept(value)[0])
        self.assertEqual(observe.summary()["telemetry_source"], "python_daqmx_acquisition")
        self.assertEqual(len(value["publications"]), 27)
        self.assertIsNone(value["publications"]["EPS"]["data"])
        self.assertNotIn("EPS", observe.numeric)
        self.assertEqual(observe.summary()["numeric_statistics"]["C1NI6071E/0"]["mean"], 123.)

    def test_producer_switch_is_explicit_and_does_not_mix_summary_statistics(self):
        observe = recorder.Observations()
        observe.accept(snapshot(1, 1, data=[9999.]))
        changed, events = observe.accept(self.python_snapshot())
        self.assertTrue(changed)
        self.assertEqual(events[0]["event"], "telemetry_producer_changed")
        self.assertEqual(observe.summary()["telemetry_source_changes"], 1)
        self.assertEqual(observe.summary()["numeric_statistics"]["C1NI6071E/0"]["n"], 1)
        self.assertEqual(observe.summary()["numeric_statistics"]["C1NI6071E/0"]["mean"], 123.)

    def test_python_source_requires_all_banks_and_explicit_producer(self):
        for defect in ("missing", "producer"):
            value = self.python_snapshot()
            if defect == "missing": value["publications"].pop("EPS")
            else: value["publications"]["EPS"]["producer_kind"] = "copied_acquisition"
            with self.assertRaises(ValueError): recorder.Observations().accept(value)

    def test_transient_cross_process_reader_lock_does_not_kill_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.h5"
            archive = recorder.Archive(path)
            archive.append("probe", {"n": 1})
            archive.flush()
            child = subprocess.Popen(
                [sys.executable, "-u", "-c",
                 "import sys,time,h5py; f=h5py.File(sys.argv[1],'r',swmr=True); "
                 "print('OPEN',flush=True); time.sleep(0.6); f.close()", str(path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "OPEN")
                archive.append("probe", {"n": 2})
                archive.flush()
                self.assertEqual(archive.last_committed_rows, 2)
                if sys.platform == "win32":
                    self.assertGreater(archive.write_retries, 0)
            finally:
                child.communicate(timeout=5)
                archive.close()
            with h5py.File(path, "r", swmr=True) as check:
                self.assertEqual(int(check["committed_rows"][()]), 2)

    def test_final_flush_failure_still_publishes_failed_status(self):
        with tempfile.TemporaryDirectory() as parent:
            folder = Path(parent) / "run"
            with mock.patch.object(recorder.Archive, "flush", side_effect=PermissionError("test lock")):
                state = recorder.run(folder, max_seconds=0)
            health = json.loads((folder / "status.json").read_text())
            self.assertEqual(state, "FAILED")
            self.assertEqual(health["state"], "FAILED")
            self.assertEqual(health["storage_errors"], 1)
            self.assertEqual(health["read_errors"], 0)
            self.assertEqual(health["committed_rows"], 0)
            self.assertIn("test lock", health["last_error"])

    def test_nonpermission_flush_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = recorder.Archive(Path(folder) / "test.h5")
            try:
                with mock.patch.object(archive, "_flush_once", side_effect=OSError("disk failure")) as flush:
                    with self.assertRaises(OSError):
                        archive.flush()
                    self.assertEqual(flush.call_count, 1)
            finally:
                archive.close()

    def test_discrete_changes_available_without_reading_live_hdf5(self):
        observe = recorder.Observations()
        first = snapshot(1, 1, data=[False, True])
        first["publications"]["C4_IN_DIO96"] = first["publications"].pop("C1NI6071E")
        observe.accept(first)
        second = snapshot(2, 2, data=[True, True])
        second["publications"]["C4_IN_DIO96"] = second["publications"].pop("C1NI6071E")
        observe.accept(second)
        status = observe.summary()
        self.assertEqual(status["discrete_values"]["C4_IN_DIO96"], [True, True])
        self.assertEqual(status["recent_discrete_changes"][0]["field"], "C4_IN_DIO96/0")
        self.assertIs(status["recent_discrete_changes"][0]["before"], False)
        self.assertEqual(status["recent_discrete_changes"][0]["receiver_count"], 2)

    def test_hdf5_swmr_roundtrip_and_compression_keep_exact_json_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.h5"
            archive = recorder.Archive(path)
            original = dict(integer=2**63 + 1, negative=-2147483648,
                            values=[True, False, .125, "é", ""], zero=-0.0)
            archive.append("snapshot", original, 23)
            archive.flush()
            with h5py.File(path, "r", swmr=True) as check:
                self.assertEqual(int(check["committed_rows"][()]), 1)
                index = check["index"][0]
                raw = check["payload_utf8"][int(index["offset"]):int(index["offset"] + index["length"])].tobytes()
                self.assertEqual(json.loads(raw), original)
                self.assertEqual(check["payload_utf8"].compression, "gzip")
                self.assertEqual(check["payload_utf8"].compression_opts, 9)
                self.assertTrue(check["payload_utf8"].fletcher32)
                self.assertFalse(check.attrs["hardware_commands"])
            archive.close()
            with self.assertRaises(FileExistsError):
                recorder.Archive(path)

    def test_duplicate_receipt_is_not_a_new_sample_and_gaps_are_counted(self):
        observe = recorder.Observations()
        self.assertTrue(observe.accept(snapshot(100, 1000))[0])
        self.assertFalse(observe.accept(snapshot(100, 1000))[0])
        changed, events = observe.accept(snapshot(103, 1010))
        self.assertTrue(changed)
        self.assertEqual(events[0]["count"], 2)
        self.assertEqual(observe.missed_receiver_receipts, 2)
        self.assertEqual(observe.source_sequence_gaps, 9)
        self.assertEqual(observe.frames, 2)

    def test_receiver_restart_rebaselines_without_fake_missing_receipts(self):
        observe = recorder.Observations()
        observe.accept(snapshot(100, 300))
        changed, events = observe.accept(snapshot(1, 301, "new_receiver"))
        self.assertTrue(changed)
        self.assertEqual(events[0]["event"], "receiver_session_changed")
        self.assertEqual(observe.missed_receiver_receipts, 0)
        self.assertEqual(observe.receiver_changes, 1)

    def test_counter_regression_and_wrong_sources_rejected(self):
        observe = recorder.Observations()
        observe.accept(snapshot(100, 100))
        with self.assertRaises(ValueError):
            observe.accept(snapshot(99, 101))
        for key, value in (("hardware_writes", True), ("source", "synthetic"),
                           ("storage_mode", "sqlite")):
            invalid = snapshot(101, 101)
            invalid[key] = value
            with self.assertRaises(ValueError):
                observe.accept(invalid)

    def test_changed_fields_keep_boolean_types_and_bad_quality_not_statistics(self):
        observe = recorder.Observations()
        observe.accept(snapshot(1, 1, data=[False, 1.0]))
        observe.accept(snapshot(2, 2, data=[0, 3.0]))
        broken = snapshot(3, 3, data=[0, 1000.0])
        broken["publications"]["C1NI6071E"]["error"]["status"] = True
        observe.accept(broken)
        stats = observe.summary()
        self.assertEqual(stats["bank_value_changes"]["C1NI6071E"], 2)
        self.assertEqual(observe.field_changes["C1NI6071E/0"], 1)
        self.assertEqual(stats["numeric_statistics"]["C1NI6071E/1"]["n"], 2)
        self.assertEqual(stats["numeric_statistics"]["C1NI6071E/1"]["mean"], 2.0)


if __name__ == "__main__":
    unittest.main()
