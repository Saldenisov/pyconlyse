"""Final cleanup at supplied boundaries; no physical-close success claims."""

import unittest
from unittest.mock import patch

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    UNWIRED,
    CallKey,
    ErrorCluster,
    ScriptedBoundary,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.final_cleanup import (
    FIXED_PSP_TAGS,
    CleanupFrameReturned,
    CleanupHandler,
    CleanupStopReset,
    PspClose,
    TpgClose,
    replay_cleanup,
)
from DeviceServers.control.elyse_acq.vi_simulation.outer_stop_schedule import (
    FinalCleanupEntry,
    GeneralStopRead,
    replay_outer_stop,
)
from DeviceServers.control.elyse_acq.vi_simulation.runtime_io import SOURCE
from DeviceServers.control.elyse_acq.vi_simulation.stop_lifecycle import (
    project_stop_reset,
)
from tests.device_servers.control.test_elyse_acq_vi_outer_stop_schedule import (
    late_returning_stop,
    runtime_fault,
    runtime_join,
)


def complete_cleanup():
    return tuple(PspClose(i) for i in range(27)) + (
        CleanupHandler("88"),
        TpgClose(51),
        CleanupHandler("68680"),
        TpgClose(52),
        CleanupHandler("67965"),
        CleanupStopReset(),
        CleanupFrameReturned(),
    )


def entered_cleanup():
    return replay_outer_stop(
        (FinalCleanupEntry(),),
        runtime=runtime_join(False),
        emergency_stop=False,
        general_stop=False,
    )


class FinalCleanupModelTests(unittest.TestCase):
    def run_cleanup(self, schedule, *, boundary=None, seed=NO_ERROR, outer=None):
        return replay_cleanup(
            schedule,
            outer=entered_cleanup() if outer is None else outer,
            boundary=ScriptedBoundary() if boundary is None else boundary,
            psp_error_seed=seed,
            tpg_sessions=(
                TaskReference("opaque-VISA51"),
                TaskReference("opaque-VISA52"),
            ),
        )

    def test_normal_frame_has_27_psp_two_tpg_three_handlers_and_one_reset(self):
        result = self.run_cleanup(complete_cleanup())
        self.assertTrue(result.frame_returned)
        self.assertEqual(len(result.calls), 32)
        self.assertEqual(result.returned_psp_close_nodes, 27)
        self.assertEqual(result.returned_tpg_close_nodes, (51, 52))
        self.assertEqual(result.returned_handlers, ("67965", "68680", "88"))
        self.assertFalse(result.memory_after.stop)
        self.assertFalse(result.memory_after.tcp_ed)
        self.assertEqual(
            [c.args["variable_uri"] for c in result.calls[:27]], list(FIXED_PSP_TAGS)
        )

    def test_bypass_route_cleanup_does_not_invent_general_or_emergency_reset(self):
        outer = replay_outer_stop(
            (FinalCleanupEntry(),),
            runtime=runtime_join(False),
            emergency_stop=True,
            general_stop=True,
        )
        result = self.run_cleanup(complete_cleanup(), outer=outer)
        self.assertFalse(result.memory_after.stop)
        self.assertTrue(result.memory_after.emergency_stop)
        self.assertTrue(result.memory_after.general_stop)

    def test_controlled_route_preserves_completion_flags_after_cleanup(self):
        outer = replay_outer_stop(
            late_returning_stop(),
            runtime=runtime_join(),
            emergency_stop=False,
            general_stop=True,
        )
        result = self.run_cleanup(complete_cleanup(), outer=outer)
        self.assertFalse(result.memory_after.stop)
        self.assertTrue(result.memory_after.tcp_ed)
        self.assertTrue(result.memory_after.emergency_stop)
        self.assertFalse(result.memory_after.general_stop)

    def test_psp_register_seed_is_explicit_and_not_replaced_by_no_error(self):
        fault = ErrorCluster(True, -201, "supplied uninitialized register value")
        result = self.run_cleanup(complete_cleanup(), seed=fault)
        self.assertTrue(result.frame_returned)
        self.assertEqual(result.psp_error_seed, fault)
        self.assertEqual(result.psp_error_after, fault)
        self.assertTrue(all(c.error_in == fault for c in result.calls[:27]))
        self.assertEqual(result.calls[27].error_in, fault)

    def test_supplied_psp_error_clear_chains_but_handler_return_is_unused(self):
        fault = ErrorCluster(True, -202)
        boundary = ScriptedBoundary(
            errors={
                CallKey(SOURCE.name, "536", 1): fault,
                CallKey(SOURCE.name, "536", 3): NO_ERROR,
                CallKey(SOURCE.name, "88"): ErrorCluster(True, -203),
            }
        )
        result = self.run_cleanup(complete_cleanup(), boundary=boundary)
        self.assertEqual(result.calls[2].error_in, fault)
        self.assertEqual(result.calls[3].error_in, fault)
        self.assertEqual(result.calls[4].error_in, NO_ERROR)
        self.assertEqual(result.psp_error_after, NO_ERROR)
        self.assertEqual(result.calls[27].returned.error, ErrorCluster(True, -203))
        self.assertTrue(result.frame_returned)
        boundary.assert_all_fixtures_used()

    def test_each_call_fault_does_not_create_a_controller_retry_or_daq_shutdown(self):
        baseline = self.run_cleanup(complete_cleanup())
        for call in baseline.calls:
            with self.subTest(key=call.key):
                boundary = ScriptedBoundary(errors={call.key: ErrorCluster(True, -204)})
                result = self.run_cleanup(complete_cleanup(), boundary=boundary)
                self.assertEqual(
                    [c.key for c in result.calls], [c.key for c in baseline.calls]
                )
                self.assertEqual(len(result.calls), 32)
                self.assertTrue(result.frame_returned)
                boundary.assert_all_fixtures_used()

    def test_three_error_branches_are_independent(self):
        psp, a, b = (ErrorCluster(True, code) for code in (-210, -211, -212))
        boundary = ScriptedBoundary(
            errors={
                CallKey(SOURCE.name, "536", 0): psp,
                CallKey(SOURCE.name, "61121"): a,
                CallKey(SOURCE.name, "66474"): b,
            }
        )
        result = self.run_cleanup(complete_cleanup(), boundary=boundary)
        calls = {c.key.node_uid: c for c in result.calls if c.key.iteration is None}
        self.assertEqual(calls["88"].error_in, psp)
        self.assertEqual(calls["68680"].error_in, a)
        self.assertEqual(calls["67965"].error_in, b)
        self.assertIs(calls["61121"].error_in, UNWIRED)
        self.assertIs(calls["66474"].error_in, UNWIRED)
        boundary.assert_all_fixtures_used()

    def test_stop_reset_can_precede_a_blocked_close_without_frame_completion(self):
        result = self.run_cleanup((CleanupStopReset(), PspClose(0)))
        self.assertFalse(result.memory_after.stop)
        self.assertEqual(result.returned_psp_close_nodes, 1)
        self.assertFalse(result.frame_ready)
        self.assertFalse(result.frame_returned)
        with self.assertRaisesRegex(ValueError, "all cleanup branches"):
            self.run_cleanup((CleanupStopReset(), PspClose(0), CleanupFrameReturned()))

    def test_unreturned_handler_keeps_frame_incomplete_after_all_close_returns(self):
        prefix = tuple(PspClose(i) for i in range(27)) + (
            TpgClose(51),
            CleanupHandler("68680"),
            TpgClose(52),
            CleanupHandler("67965"),
            CleanupStopReset(),
        )
        result = self.run_cleanup(prefix)
        self.assertEqual(result.returned_psp_close_nodes, 27)
        self.assertEqual(result.returned_tpg_close_nodes, (51, 52))
        self.assertFalse(result.frame_ready)
        self.assertFalse(result.memory_after.stop)
        with self.assertRaisesRegex(ValueError, "all cleanup branches"):
            self.run_cleanup(prefix + (CleanupFrameReturned(),))

    def test_cleanup_and_postinit_do_not_clear_supplied_stale_general_level(self):
        bypass = replay_outer_stop(
            (FinalCleanupEntry(),),
            runtime=runtime_join(False),
            emergency_stop=True,
            general_stop=True,
        )
        cleaned = self.run_cleanup(complete_cleanup(), outer=bypass)
        initialized = project_stop_reset("post_init", cleaned.memory_after).after
        self.assertFalse(initialized.stop)
        self.assertFalse(initialized.tcp_ed)
        self.assertFalse(initialized.emergency_stop)
        self.assertTrue(initialized.general_stop)
        runtime = runtime_join(
            initialized.tcp_ed,
            runtime_fault("40346"),
            initialized.stop,
        )
        later = replay_outer_stop(
            (GeneralStopRead(),),
            runtime=runtime,
            emergency_stop=initialized.emergency_stop,
            general_stop=initialized.general_stop,
        )
        self.assertEqual(later.choices[0].sequence_uid, "51954")
        # Explicit retained fixture, not evidence of native restart retention.

    def test_cross_branch_interleaving_is_permitted_but_psp_order_is_fixed(self):
        interleaved = (
            (
                CleanupStopReset(),
                TpgClose(52),
                PspClose(0),
                CleanupHandler("67965"),
                TpgClose(51),
                PspClose(1),
                CleanupHandler("68680"),
            )
            + tuple(PspClose(i) for i in range(2, 27))
            + (
                CleanupHandler("88"),
                CleanupFrameReturned(),
            )
        )
        first = self.run_cleanup(complete_cleanup())
        second = self.run_cleanup(interleaved)
        self.assertEqual(second.memory_after, first.memory_after)
        self.assertEqual(second.psp_error_after, first.psp_error_after)
        self.assertEqual({c.key for c in second.calls}, {c.key for c in first.calls})
        self.assertNotEqual([c.key for c in second.calls], [c.key for c in first.calls])

    def test_closing_resources_does_not_zero_outputs_or_deinitialize_ni_tasks(self):
        result = self.run_cleanup(complete_cleanup())
        self.assertEqual(
            {c.operation for c in result.calls},
            {"close_variable_reference", "tpg300_close", "simple_error_handler"},
        )
        self.assertFalse(hasattr(result, "analog_outputs"))
        self.assertFalse(hasattr(result, "digital_outputs"))
        self.assertTrue(
            all(
                c.args.get("reference_source") == "fixed_uri_tag"
                for c in result.calls
                if c.operation == "close_variable_reference"
            )
        )

    def test_handler_and_frame_tokens_need_their_wired_predecessors(self):
        for schedule in (
            (CleanupHandler("88"),),
            (CleanupHandler("68680"),),
            (CleanupHandler("unknown"),),
            (CleanupFrameReturned(),),
            (PspClose(1),),
            (PspClose(True),),
            (TpgClose(50),),
            (TpgClose(51), TpgClose(51)),
            (CleanupStopReset(), CleanupStopReset()),
            (TpgClose(51), CleanupHandler("68680"), CleanupHandler("68680")),
            tuple(PspClose(i) for i in range(27)) + (PspClose(27),),
        ):
            with self.subTest(schedule=schedule), self.assertRaises(ValueError):
                self.run_cleanup(schedule)

    def test_terminal_trace_and_unknown_tokens_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "ends at frame return"):
            self.run_cleanup(complete_cleanup() + (CleanupStopReset(),))
        with self.assertRaises(TypeError):
            self.run_cleanup((object(),))

    def test_cleanup_cannot_start_before_outer_join_and_explicit_entry(self):
        for schedule in ((),):
            outer = replay_outer_stop(
                schedule,
                runtime=runtime_join(False),
                emergency_stop=False,
                general_stop=False,
            )
            with self.assertRaisesRegex(ValueError, "cleanup entry"):
                self.run_cleanup((), outer=outer)
        waiting = replay_outer_stop(
            (),
            runtime=runtime_join(),
            emergency_stop=False,
            general_stop=False,
        )
        with self.assertRaises(ValueError):
            self.run_cleanup((), outer=waiting)

    def test_missing_or_nonfixture_values_do_not_gain_native_defaults(self):
        with self.assertRaises(TypeError):
            self.run_cleanup((), seed=None)
        with self.assertRaises(TypeError):
            self.run_cleanup((), boundary=object())
        with self.assertRaises(TypeError):
            replay_cleanup(
                (),
                outer=entered_cleanup(),
                boundary=ScriptedBoundary(),
                psp_error_seed=NO_ERROR,
                tpg_sessions=("COM1", "COM2"),
            )

    def test_no_socket_sleep_adapter_or_physical_handle_is_accepted(self):
        with (
            patch("socket.socket.connect", side_effect=AssertionError("network")),
            patch("time.sleep", side_effect=AssertionError("sleep")),
        ):
            result = self.run_cleanup(complete_cleanup())
        self.assertTrue(result.frame_returned)


if __name__ == "__main__":
    unittest.main()
