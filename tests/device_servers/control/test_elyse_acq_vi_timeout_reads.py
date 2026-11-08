"""Whole-cluster copies/error chain are projections, never real PSP commands."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import UNWIRED, ErrorCluster
from DeviceServers.control.elyse_acq.vi_simulation.timeout_reads import (
    SITES,
    PspReturn,
    read_frame,
)


class TimeoutReadsProjectionTests(unittest.TestCase):
    def fixtures(self):
        prior, returned = {}, {}
        for uid, _, _, size, element in SITES:
            prior[uid] = (False if element is bool else 1.0,) * size
            returned[uid] = PspReturn(
                (True if element is bool else 2.0,) * size, ErrorCluster(False, 0)
            )
        return dict(
            default_snapshots=prior,
            returned_snapshots=returned,
            stop_before=True,
            tcp_ed_before=True,
        )

    def test_all_twelve_calls_preserve_uri_order_and_own_prior_default(self):
        args = self.fixtures()
        result = read_frame(**args)
        self.assertEqual(
            tuple(c.node_uid for c in result.calls), tuple(s[0] for s in SITES)
        )
        self.assertEqual(
            tuple(b for b, _ in result.data_assignments),
            (9, 10, 11, 12, 39, 17, 15, 13, 36, 37, 44, 38),
        )
        for call in result.calls:
            self.assertIs(call.default_data, args["default_snapshots"][call.node_uid])
            self.assertTrue(call.uri.startswith("ni.var.psp://10.20.30.2/SUPERVISION/"))
        self.assertIs(result.calls[0].error_in, UNWIRED)

    def test_error_dependency_is_not_data_write_gate_or_automatic_hold(self):
        args = self.fixtures()
        fault = ErrorCluster(True, -100, "fixture")
        args["returned_snapshots"]["10310"] = PspReturn((7.0,) * 10, fault)
        result = read_frame(**args)
        self.assertEqual(result.calls[1].error_in, fault)
        self.assertEqual(dict(result.data_assignments)[9], (7.0,) * 10)
        # Later supplied returns may clear a fault. Caller uses final error only.
        self.assertEqual(result.fault_assignments, ())
        self.assertTrue(result.stop_after)

    def test_final_fault_explicitly_clears_existing_stop_and_tcp_flags(self):
        args = self.fixtures()
        fault = ErrorCluster(True, -999, "last read")
        args["returned_snapshots"]["22840"] = PspReturn((False,) * 12, fault)
        result = read_frame(**args)
        self.assertEqual(result.fault_assignments, ((30, False), (45, False)))
        self.assertFalse(result.stop_after)
        self.assertFalse(result.tcp_ed_after)
        self.assertEqual(dict(result.data_assignments)[38], (False,) * 12)

    def test_no_fault_does_not_set_or_reset_stop(self):
        args = self.fixtures()
        args["stop_before"] = False
        result = read_frame(**args)
        self.assertFalse(result.stop_after)
        self.assertTrue(result.tcp_ed_after)
        self.assertEqual(result.fault_assignments, ())

    def test_warning_code_does_not_substitute_for_error_status(self):
        args = self.fixtures()
        args["returned_snapshots"]["22840"] = PspReturn(
            (True,) * 12, ErrorCluster(False, 123)
        )
        self.assertEqual(read_frame(**args).fault_assignments, ())

    def test_missing_return_and_wrong_cluster_shape_not_normalized(self):
        args = self.fixtures()
        args["returned_snapshots"].pop("22840")
        with self.assertRaises(ValueError):
            read_frame(**args)
        args = self.fixtures()
        args["returned_snapshots"]["19997"] = PspReturn(
            (True,) * 80, ErrorCluster(False, 0)
        )
        with self.assertRaises(TypeError):
            read_frame(**args)


if __name__ == "__main__":
    unittest.main()
