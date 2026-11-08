"""Qualification restricted to pure generated arithmetic, with network denied."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from qualify_acq_beamline_adjustment import audit_fragment, qualify  # noqa: E402


class BeamlineAdjustmentQualificationTests(unittest.TestCase):
    def test_updated_shared_lvkit_matches_all24_original_scalar_chains(self):
        with (
            patch(
                "socket.socket.connect", side_effect=AssertionError("network forbidden")
            ),
            patch(
                "socket.create_connection",
                side_effect=AssertionError("network forbidden"),
            ),
        ):
            receipt = qualify()
        self.assertEqual(receipt["scalar_fragments"], 24)
        self.assertEqual(receipt["scalar_cases"], 9600)
        self.assertEqual(receipt["frame0_direct_nets_checked"], 424)
        for key in (
            "outer_default_independently_verified",
            "property_failures_qualified",
            "nonfinite_inputs_qualified",
            "whole_events_qualified",
            "whole_acquisition_qualified",
            "hardware_executed",
            "vi_executed",
            "deployable",
        ):
            self.assertFalse(receipt[key])

    def test_unresolved_names_imports_side_effects_and_other_syntax_are_rejected(self):
        for source in (
            "import socket\nresult = current",
            "result = open('x')",
            "current = 1.0\nresult = current",
            "result = current.__class__",
            "result = missing",
            "result = max(current, 1.0, key=missing)",
            "while True: pass",
            "result = -current",
            "result = current * 2.0",
        ):
            with self.subTest(source=source), self.assertRaises(AssertionError):
                audit_fragment(source)

    def test_pure_select_arithmetic_and_scalar_coercion_are_accepted(self):
        audit_fragment(
            "value = current - (1.0 if x1_x10 else 0.1)\n"
            "result = max(-16.0, min(value, 16.0))\n"
        )


if __name__ == "__main__":
    unittest.main()
