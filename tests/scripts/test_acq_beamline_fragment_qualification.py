"""Updated shared converter versus reviewed original beam-line tail mappings."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from qualify_acq_beamline_fragments import audit_fragment, qualify  # noqa: E402


class BeamlineFragmentQualificationTests(unittest.TestCase):
    def test_current_shared_lvkit_pure_fragments_match_original_maps(self):
        with (
            patch(
                "socket.socket.connect", side_effect=AssertionError("network forbidden")
            ),
            patch(
                "socket.create_connection",
                side_effect=AssertionError("network forbidden"),
            ),
        ):
            result = qualify()
        self.assertEqual(result["event_cases"], 520)
        self.assertEqual(result["bank_cases"], 1300)
        self.assertEqual(result["scalar_values_compared"], 13000)
        for flag in (
            "full_events_qualified",
            "full_acquisition_qualified",
            "deployable",
            "hardware_executed",
            "vi_executed",
        ):
            self.assertFalse(result[flag])

    def test_nonpure_or_unresolved_code_is_rejected_before_execution(self):
        for source in (
            "import socket\nresult = cells\n",
            "result = open('x')\n",
            "cells = ()\nresult = cells\n",
            "result = cells.__class__\n",
            "result = missing\n",
            "result = replace_fields(cells, (), bad=True)\n",
            "result = cells[-1]\n",
            "result = cells[True]\n",
            "result = bank9[0] + bank10[0]\n",
            "while True: pass\n",
        ):
            with self.subTest(source=source), self.assertRaises(AssertionError):
                audit_fragment(source)

    def test_explicit_indexed_tuple_replacement_is_accepted(self):
        audit_fragment(
            "cluster = replace_fields(bank9, (((0,), cells[3][5]),))\n"
            "result = (cluster,)\n"
        )


if __name__ == "__main__":
    unittest.main()
