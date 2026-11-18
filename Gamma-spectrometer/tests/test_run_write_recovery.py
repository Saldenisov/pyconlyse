from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import h5py
import numpy as np

from avantes_run import AvantesRun, optical_density


class RunWriteRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.grid = np.array([250.0, 300.0, 350.0])
        self.counts = np.array([12.0, 14.0, 18.0])
        self.run = AvantesRun.create(
            Path(directory.name) / "test.h5", (self.grid, self.grid), ["sample", "monitor"], 100, {}, {},
        )

    def fail_dataset_write(self, filename):
        write = h5py.Dataset.__setitem__

        def fail_once(dataset, index, value):
            nonlocal filename
            if dataset.name == filename:
                filename = None
                raise OSError("injected HDF5 write failure")
            return write(dataset, index, value)

        return patch.object(h5py.Dataset, "__setitem__", fail_once)

    def test_failed_sample_row_keeps_all_dataset_lengths_aligned(self):
        def append(elapsed):
            return self.run.append(elapsed, 100 + elapsed, self.counts, self.counts, None, None, {})

        self.assertEqual(append(1), 1)
        with self.fail_dataset_write("/entry/instrument/detector_2/data"):
            with self.assertRaisesRegex(OSError, "injected"):
                append(2)
        with h5py.File(self.run.path, "r") as file:
            entry = file["entry"]
            self.assertEqual(entry["acquisition"].attrs["committed_rows"], 1)
            for _, dataset in self.run._row_fields(entry):
                self.assertEqual(len(dataset), 1, dataset.name)
            np.testing.assert_array_equal(entry["raw_ch1/data"][0], self.counts)
        self.assertEqual(append(2), 2)

    def test_failed_calibration_block_can_be_retried_without_extra_rows(self):
        name = self.run.begin_capture("background", repeats=1, blocks_per_repeat=1)
        path = f"/entry/calibration_captures/{name}"
        block = dict(ch1=self.counts, ch2=self.counts, metadata={"utc_s": 101})
        with self.fail_dataset_write(f"{path}/ch2_counts"):
            with self.assertRaisesRegex(OSError, "injected"):
                self.run.append_capture_block(name, block)
        with h5py.File(self.run.path, "r") as file:
            capture = file[path]
            self.assertEqual(capture.attrs["committed_blocks"], 0)
            self.assertTrue(all(len(dataset) == 0 for dataset in capture.values()))
        self.assertEqual(self.run.append_capture_block(name, block), 1)
        self.assertEqual(len(self.run.finish_capture(name)), 1)

    def test_failed_irradiation_marker_does_not_change_reported_state(self):
        with self.fail_dataset_write("/entry/irradiation/state/value"):
            with self.assertRaisesRegex(OSError, "injected"):
                self.run.mark_irradiation(True, 101)
        with h5py.File(self.run.path, "r") as file:
            state = file["entry/irradiation/state"]
            np.testing.assert_array_equal(state["time"][:], [0])
            np.testing.assert_array_equal(state["value"][:], [0])
        self.assertFalse(self.run.irradiation_state()[1])
        self.run.mark_irradiation(True, 101)
        self.assertTrue(self.run.irradiation_state()[1])

    def test_latest_complete_calibration_replaces_selection_and_archives_zeros(self):
        run = AvantesRun.create(
            self.run.path.with_name("draft.h5"), (self.grid, self.grid), ["sample", "monitor"],
            100, {"sample_name": "calibration-retake"}, {},
        )
        block = dict(ch1=self.counts, ch2=self.counts, metadata={"utc_s": 101})

        def capture(role):
            name = run.begin_capture(role, repeats=1, blocks_per_repeat=1)
            run.append_capture_block(name, block)
            return name

        first_background = capture("background")
        run.finish_capture(first_background)
        for role in ("empty", "reference"):
            run.finish_capture(capture(role))
            run.set_preparation_zero(role, np.zeros_like(self.grid))

        latest_background = capture("background")
        self.assertTrue(run.has_preparation_zero("reference"))

        link = h5py.Group.__setitem__

        def fail_reselect(group, key, value):
            if group.name == "/entry/calibration" and key == "background" and value.name.endswith(latest_background):
                raise OSError("injected selection failure")
            return link(group, key, value)

        with patch.object(h5py.Group, "__setitem__", fail_reselect):
            with self.assertRaisesRegex(OSError, "injected"):
                run.finish_capture(latest_background)
        self.assertTrue(run.has_preparation_zero("reference"))

        run.finish_capture(latest_background)
        run.finish_capture(first_background)
        self.assertFalse(run.has_preparation_zero("empty"))
        self.assertFalse(run.has_preparation_zero("reference"))
        with h5py.File(run.path, "r") as file:
            entry = file["entry"]
            self.assertEqual(entry["calibration/background"].attrs["capture_id"], latest_background)
            self.assertTrue(entry[f"calibration_captures/{first_background}"].attrs["complete"])
            self.assertEqual(len(entry["calibration_zero_history"]), 3)
            self.assertEqual(len(entry["blanks"]), 0)

    def test_restart_archives_only_new_rows_in_the_same_file(self):
        def append(elapsed, offset):
            counts = self.counts + offset
            self.run.append(elapsed, 100 + elapsed, counts, counts, counts, counts, {})

        append(1, 0)
        append(2, 1)
        self.assertEqual(self.run.begin_collection_segment(103), "00000000")
        self.assertIsNone(self.run.begin_collection_segment(103))
        append(4, 2)
        self.assertEqual(self.run.begin_collection_segment(105), "00000001")
        append(6, 3)

        renamed = self.run.path.rename(self.run.path.with_name("moved.h5"))
        with h5py.File(renamed, "r") as file:
            entry = file["entry"]
            self.assertEqual(entry["acquisition"].attrs["committed_rows"], 4)
            archived = entry["acquisition_segments"]
            self.assertEqual(len(archived), 2)
            np.testing.assert_array_equal(archived["00000000/time"][:], [1, 2])
            np.testing.assert_array_equal(archived["00000001/time"][:], [4])
            np.testing.assert_array_equal(archived["00000000/ch1_counts"][:],
                                          [self.counts, self.counts + 1])
            np.testing.assert_array_equal(archived["00000001/ch2_counts"][:], [self.counts + 2])

    def test_raw_recalculation_with_earlier_background_and_optional_zero(self):
        setup = dict(sample_volume_ml=1, window_diameter_mm=8, path_length_mm=10, cell_type="QZ")
        run = AvantesRun.create(
            self.run.path.with_name("raw.h5"), (self.grid, self.grid), ["sample", "monitor"],
            100, {"sample_name": "raw"}, {},
        )

        def measure(role, ch1, ch2):
            name = run.begin_capture(role, repeats=1, blocks_per_repeat=1)
            run.append_capture_block(name, dict(ch1=ch1, ch2=ch2, metadata={"utc_s": 99}))
            run.finish_capture(name)
            return name

        older_dark = np.ones_like(self.grid)
        earlier = measure("background", older_dark, older_dark)
        measure("background", older_dark * 2, older_dark * 2)
        empty = (self.counts + 12, self.counts + 9)
        measure("empty", *empty)
        measure("reference", self.counts + 8, self.counts + 8)
        run.start_prepared_collection(100, setup)
        original = np.ones_like(self.grid) * 3
        run.append(1, 101, self.counts, self.counts, original, original, {})
        revision = run.reprocess_raw({"background": earlier}, zero="empty")

        expected = optical_density(self.counts, self.counts, empty, (older_dark, older_dark), (self.grid, self.grid))
        np.testing.assert_allclose(run.view("od_reprocessed")[1][0], expected)
        np.testing.assert_array_equal(run.view("od_raw")[1][0], original)
        with h5py.File(run.path, "r") as file:
            self.assertNotIn("calibration_zeros", file["entry"])
            self.assertTrue(file["entry/blanks/00000000/initial"][()])
            self.assertEqual(file[revision]["parameters/background"].asstr()[()],
                             f"/entry/calibration_captures/{earlier}")
            np.testing.assert_array_equal(file["entry/raw_ch1/data"][0], self.counts)

    def test_preview_raw_counts_and_failed_channel_are_separate_from_the_sample(self):
        self.run.append_preview_block(dict(ch1=self.counts, ch2=None, metadata={"utc_s": 101}))
        with h5py.File(self.run.path, "r") as file:
            self.assertEqual(file["entry/acquisition"].attrs["committed_rows"], 0)
            preview = file["entry/preview_captures"]
            self.assertEqual(preview.attrs["committed_blocks"], 1)
            np.testing.assert_array_equal(preview["ch1_counts"][0], self.counts)
            self.assertTrue(np.isnan(preview["ch2_counts"][0]).all())
