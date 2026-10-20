"""Data fixtures only; native handles, dialogs and devices remain inaccessible."""

import copy
import json
import unittest

from legacy.xp_acq_agent.elyse_agent.acquisition_counter_native_preview import (
    plan_simple_error_dialog,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_counter_native_preview import (
    preview_counter_native_flow as inspect_flow,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime


def bank(selector=2.9, offset=0.0):
    return tuple(float(index) + offset for index in range(32)) + (selector,)


def error(status=False, code=0, source=""):
    return dict(status=status, code=code, source=source)


def preview_counter_native_flow(*args, **kwargs):
    # Every test explicitly selects the clean incoming fixture unless overridden.
    kwargs.setdefault("error_in", error())
    return inspect_flow(*args, **kwargs)


def fixtures():
    rows = []
    for stage in (
        "read_co_pulse_done",
        "wait_ms",
        "stop_task",
        "clear_errors",
        "write_co_timing_properties",
        "start_task",
    ):
        row = dict(
            stage=stage,
            task_token=None
            if stage in ("wait_ms", "clear_errors")
            else "fixture:" + stage,
            error=error(),
        )
        if stage == "read_co_pulse_done":
            row["data"] = [True]
        rows.append(row)
    # Explicit supplied native return, not a thrown Python exception.
    rows[-1]["error"] = error(True, -100, "supplied Start error")
    return rows


class NativePreviewTests(unittest.TestCase):
    def test_returned_error_does_not_gate_independent_reset_and_publication(self):
        source, rows = bank(), fixtures()
        reset, publication = bank(3.1, 10.0), bank(16.9, 20.0)
        original = copy.deepcopy(rows)
        result = preview_counter_native_flow(
            source,
            rows,
            dict(disposition="RETURNED", error_out=error(True, -100)),
            reset,
            publication,
        )
        self.assertEqual(result["request"]["counter"], 0)
        self.assertEqual(result["request"]["selector"], 2.9)
        self.assertEqual(
            result["fixture_effects"],
            [
                dict(kind="fixture_reset", snapshot=list(reset[:32] + (-1.0,))),
                dict(kind="fixture_publication", snapshot=list(publication)),
            ],
        )
        self.assertTrue(result["caller"]["completed"])
        self.assertEqual(result["dialog"]["buttons"], ["Continue"])
        self.assertFalse(result["automatic_continue"])
        self.assertFalse(result["hardware_execution"])
        self.assertFalse(result["native_execution"])
        self.assertFalse(result["resource_release_requested"])
        self.assertFalse(result["caller"]["deployed_xp_handler_binary_qualified"])
        self.assertEqual(rows, original)
        json.dumps(result, allow_nan=False)

    def test_no_response_suspends_before_banks(self):
        result = preview_counter_native_flow(
            bank(), fixtures(), dict(disposition="NO_RESPONSE")
        )
        self.assertEqual(result["caller"]["suspended_at"], "handler_response")
        self.assertEqual(result["fixture_effects"], [])

    def test_no_response_requires_dialog_in_saved_default_profile(self):
        for incoming in (error(), error(False, 1, "warning")):
            rows = fixtures()
            rows[-1]["error"] = incoming
            with self.assertRaises(ValueError):
                preview_counter_native_flow(
                    bank(), rows, dict(disposition="NO_RESPONSE")
                )
            result = preview_counter_native_flow(
                bank(),
                rows,
                dict(disposition="RETURNED", error_out=incoming),
                bank(),
                bank(),
            )
            self.assertTrue(result["caller"]["completed"])
            self.assertEqual(result["dialog"]["buttons"], [])

    def test_source_default_profile_does_not_invent_a_stop_button(self):
        with self.assertRaises(ValueError):
            preview_counter_native_flow(
                bank(), fixtures(), dict(disposition="ABORT_TOP_LEVEL")
            )

    def test_runtime_inspection_leaves_state_revision_and_ownership_unchanged(self):
        def forbidden():
            self.fail("Backend factory must not be accessed")

        runtime = AcquisitionRuntime(forbidden, clock=lambda: 100.0)
        before = runtime.snapshot()
        result = runtime.inspect_counter_error_flow(
            bank(), fixtures(), dict(disposition="NO_RESPONSE"), error_in=error()
        )
        self.assertEqual(runtime.snapshot(), before)
        self.assertEqual(result["mode"], "STATIC_SUPPLIED_RETURN_PREVIEW")

    def test_explicit_original_error_is_reused_each_poll_not_shifted(self):
        rows = fixtures()
        first = copy.deepcopy(rows[0])
        first["data"] = [False]
        first["error"] = error(True, -2, "first poll")
        rows = [first, copy.deepcopy(rows[1])] + rows
        incoming = error(True, -1, "original")
        result = preview_counter_native_flow(
            bank(), rows, dict(disposition="NO_RESPONSE"), error_in=incoming
        )
        polls = [
            item["call"]
            for item in result["caller"]["helper"]["calls"]
            if item["call"]["stage"] == "read_co_pulse_done"
        ]
        self.assertEqual(len(polls), 2)
        self.assertEqual([item["error_in"] for item in polls], [incoming, incoming])
        self.assertEqual(polls[0]["task_in"], polls[1]["task_in"])
        with self.assertRaises(ValueError):
            inspect_flow(bank(), fixtures(), dict(disposition="NO_RESPONSE"))

    def test_rejects_missing_extra_or_reordered_returns(self):
        rows = fixtures()
        cases = [rows[:-1], rows + [rows[-1]], list(reversed(rows))]
        for supplied in cases:
            with self.assertRaises(ValueError):
                preview_counter_native_flow(
                    bank(), supplied, dict(disposition="NO_RESPONSE")
                )

    def test_rejects_callback_or_mutable_payload_smuggling(self):
        for replacement in (lambda: None, (), {}, None):
            with self.assertRaises(ValueError):
                preview_counter_native_flow(
                    bank(), replacement, dict(disposition="NO_RESPONSE")
                )
        for name, value in (
            ("extra", True),
            ("error", error(True, True)),
            ("task_token", lambda: None),
            ("data", [float("nan")]),
        ):
            rows = fixtures()
            rows[0][name] = value
            with self.assertRaises((ValueError, TypeError)):
                preview_counter_native_flow(
                    bank(), rows, dict(disposition="NO_RESPONSE")
                )

    def test_rejects_incomplete_or_unreturned_handler_bank_fixtures(self):
        for handler in (
            {},
            dict(disposition="RETURNED"),
            dict(disposition="CONTINUE_AUTOMATICALLY"),
            dict(disposition="NO_RESPONSE", error_out=error()),
            dict(disposition="NO_RESPONSE", callback=lambda: None),
        ):
            with self.assertRaises((ValueError, TypeError)):
                preview_counter_native_flow(bank(), fixtures(), handler)
        with self.assertRaises(ValueError):
            preview_counter_native_flow(
                bank(), fixtures(), dict(disposition="NO_RESPONSE"), bank()
            )
        with self.assertRaises(ValueError):
            preview_counter_native_flow(
                bank(),
                fixtures(),
                dict(disposition="RETURNED", error_out=error()),
                bank(),
                None,
            )

    def test_invalid_task_projection_never_runs_replay(self):
        for selector in (0.1, 0.9999999999999999, 17.0, -1.0):
            with self.assertRaises(ValueError):
                preview_counter_native_flow(
                    bank(selector), fixtures(), dict(disposition="NO_RESPONSE")
                )


class DialogProfileTests(unittest.TestCase):
    def test_public_mode_remapping_and_error_buttons(self):
        for mode, core, buttons in (
            (0, 0, []),
            (1, 1, ["Continue"]),
            (2, 2, ["Continue", "Stop"]),
            (3, 4, ["Continue"]),
            (4, 5, ["Continue", "Stop"]),
        ):
            plan = plan_simple_error_dialog(error(True, -1, "fixture"), mode)
            self.assertEqual(plan["core_mode"], core)
            self.assertEqual(plan["buttons"], buttons)
            self.assertFalse(plan["actual_dialog_opened"])
            self.assertFalse(plan["orderly_cleanup_guaranteed"])
            self.assertFalse(plan["continue_clears_error"])
            self.assertFalse(plan["continue_retries_operation"])
            self.assertFalse(plan["deployed_xp_handler_binary_qualified"])

    def test_warning_and_no_error_visibility(self):
        for mode in range(5):
            self.assertFalse(
                plan_simple_error_dialog(error(), mode)["dialog_required_by_profile"]
            )
            self.assertEqual(
                plan_simple_error_dialog(error(False, 1), mode)[
                    "dialog_required_by_profile"
                ],
                mode in (3, 4),
            )

    def test_rejects_non_public_or_coerced_modes(self):
        for mode in (-1, 5, True, 1.0, "1"):
            with self.assertRaises(ValueError):
                plan_simple_error_dialog(error(), mode)


if __name__ == "__main__":
    unittest.main()
