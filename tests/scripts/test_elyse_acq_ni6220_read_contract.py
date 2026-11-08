"""NI6220 source mutations and bounded non-actuating mean projection tests."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))
from validate_acq_ni6220_read_error_contract import (
    checked_ni6220_roots, checked_root, unique,
    validate_initializer_error, validate_read_tree, validate_runtime_boundary,
    validate_initializer_configuration,
)
from DeviceServers.control.elyse_acq.ni6220_projection import project_ni6220_channel_means


class NI6220EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_ni6220_roots(REPOSITORY /
            "legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip")
        cls.parent = checked_root(REPOSITORY /
            "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip")

    def setUp(self):
        self.init = deepcopy(self.original["1_ACQ_INIT_NI6220.vi"])
        self.read = deepcopy(self.original["1_ACQ_READ_NI6220.vi"])

    def test_saved_initializer_passes(self):
        self.assertIn("local index 0", validate_initializer_error(self.init))

    def test_saved_initializer_configuration_passes(self):
        self.assertIn("sixteen RSE channels", validate_initializer_configuration(self.init))

    def test_initializer_voltage_range_change_rejected(self):
        node = self.init["vi_BDHb.xml"].find("root/nodeList/*/termList/*[@uid='1808']/dco/ConstValue")
        node.text = node.text.replace("4024000000000000", "4014000000000000", 1)
        with self.assertRaisesRegex(AssertionError, "voltage range"):
            validate_initializer_configuration(self.init)

    def test_initializer_channel_count_connection_removed_rejected(self):
        self.init["vi_BDHb.xml"].find("root/signalList/*/termList/*[@uid='2682']").set("uid", "2685")
        with self.assertRaisesRegex(AssertionError, "initializer root wire set"):
            validate_initializer_configuration(self.init)

    def test_initializer_trigger_source_change_rejected(self):
        self.init["vi_BDHb.xml"].find("root/nodeList/*/termList/*[@uid='750']/dco/ConstValue").text = "000000082F31312F50464931"
        with self.assertRaisesRegex(AssertionError, "literal argument"):
            validate_initializer_configuration(self.init)

    def test_initializer_sample_clock_change_rejected(self):
        self.init["vi_BDHb.xml"].find("root/nodeList/*/termList/*[@uid='3732']/dco/ConstValue").text = "0000000C4F6E626F617264436C6F636A"
        with self.assertRaisesRegex(AssertionError, "literal argument"):
            validate_initializer_configuration(self.init)

    def test_initializer_rse_change_rejected(self):
        unique(self.init["vi_BDHb.xml"], "diag", "2798").find("nodeList/*/termList/*[@uid='616']/dco/ConstValue").text = "00002764"
        with self.assertRaisesRegex(AssertionError, "not RSE"):
            validate_initializer_configuration(self.init)

    def test_initializer_read_property_change_rejected(self):
        unique(self.init["vi_BDHb.xml"], "propNode", "2561").find("termList/*/dco/propList/*/PropItemCode").text = "6411"
        with self.assertRaisesRegex(AssertionError, "Read properties"):
            validate_initializer_configuration(self.init)

    def test_error_out_local_mapping_change_rejected(self):
        self.init["vi.xml"].find("CPMp/Section/TypeDesc[8]").set("Flags", "0x0100")
        with self.assertRaisesRegex(AssertionError, "public-to-local mapping"):
            validate_initializer_error(self.init)

    def test_error_out_local_write_removed_rejected(self):
        unique(self.init["vi_BDHb.xml"], "gRef", "2820").find("termList/*/objFlags").text = "4096"
        with self.assertRaisesRegex(AssertionError, "write direction"):
            validate_initializer_error(self.init)

    def test_internal_error_not_returned_rejected(self):
        self.init["vi_BDHb.xml"].find("root/signalList/*/termList/*[@uid='2832']").set("uid", "583")
        with self.assertRaisesRegex(AssertionError, "public error input connected"):
            validate_initializer_error(self.init)

    def test_saved_reader_passes(self):
        self.assertIn("mean-For N", validate_read_tree(self.read))

    def test_mean_n_disconnected_rejected(self):
        self.read["vi_BDHb.xml"].find("root/signalList/*/termList/*[@uid='2442']").set("uid", "2441")
        with self.assertRaisesRegex(AssertionError, "reader root wire set"):
            validate_read_tree(self.read)

    def test_sample_count_public_control_swap_rejected(self):
        unique(self.read["vi_BDHb.xml"], "fPTerm", "763").find("dco").set("uid", "163")
        with self.assertRaisesRegex(AssertionError, "public terminal identity"):
            validate_read_tree(self.read)

    def test_timeout_change_rejected(self):
        self.read["vi_BDHb.xml"].find("root/nodeList/*/termList/*[@uid='57']/dco/ConstValue").text = "3FF0000000000000"
        with self.assertRaisesRegex(AssertionError, "timeout is not -1"):
            validate_read_tree(self.read)

    def test_scaling_true_rejected(self):
        self.read["vi_BDHb.xml"].find("root/nodeList/*/termList/*[@uid='1160']/dco/ConstValue").text = "01"
        with self.assertRaisesRegex(AssertionError, "scaling selector is not False"):
            validate_read_tree(self.read)

    def test_array_indexing_removed_rejected(self):
        unique(self.read["vi_BDHb.xml"], "forLoop", "612").find("termList/*[@uid='276']/dco/TunnelType").text = "00"
        with self.assertRaisesRegex(AssertionError, "array indexing"):
            validate_read_tree(self.read)

    def test_read_error_return_changed_rejected(self):
        self.read["vi_BDHb.xml"].find("root/signalList/*/termList/*[@uid='979']").set("uid", "1074")
        with self.assertRaisesRegex(AssertionError, "reader root wire set"):
            validate_read_tree(self.read)

    def test_saved_parent_boundary_passes(self):
        self.assertIn("not a cancellation", validate_runtime_boundary(self.parent))

    def test_parent_sample_bank_change_rejected(self):
        parent = deepcopy(self.parent)
        unique(parent, "gRef", "48193").find("termList/*/dco/paramIdx").text = "58"
        with self.assertRaisesRegex(AssertionError, "sample-count source bank"):
            validate_runtime_boundary(parent)

    def test_parent_stop_wired_to_read_rejected(self):
        parent = deepcopy(self.parent)
        frame = unique(parent, "whileLoop", "47483").find("diagramList")[0]
        frame.find("signalList/*/termList/*[@uid='47496']").set("uid", "45001")
        with self.assertRaisesRegex(AssertionError, "runtime body wire set"):
            validate_runtime_boundary(parent)


class NI6220BoundedProjectionTests(unittest.TestCase):
    def test_sample_count_ten_caps_sixteen_returned_channels(self):
        rows = [(i, i + 2) for i in range(16)]
        self.assertEqual(project_ni6220_channel_means(rows, 10), tuple(i + 1 for i in range(10)))

    def test_sample_count_larger_than_channel_count_preserves_all_means(self):
        rows = [(i, i + 2) for i in range(16)]
        self.assertEqual(project_ni6220_channel_means(rows, 1000), tuple(i + 1 for i in range(16)))

    def test_returned_fewer_channels_bounds_loop(self):
        self.assertEqual(project_ni6220_channel_means([(2, 4), (8, 10)], 10), (3, 9))

    def test_no_fixed_eight_channel_limit(self):
        self.assertEqual(len(project_ni6220_channel_means([(1,)] * 12, 20)), 12)

    def test_zero_iterations(self):
        self.assertEqual(project_ni6220_channel_means([(2, 4)], 0), ())

    def test_invalid_n_is_python_only_guard(self):
        for value in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                project_ni6220_channel_means([(2, 4)], value)

    def test_empty_row_is_outside_bounded_model(self):
        with self.assertRaises(ValueError):
            project_ni6220_channel_means([()], 1)


if __name__ == "__main__":
    unittest.main()
