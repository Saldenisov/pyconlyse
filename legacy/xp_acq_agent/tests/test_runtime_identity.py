"""Identity fixtures only; no process, network or NI access."""
import os
import tempfile
import unittest
from unittest.mock import patch

from legacy.xp_acq_agent.elyse_agent import runtime_identity as identity


class RuntimeIdentityTests(unittest.TestCase):
    def test_source_hash_is_path_independent_and_changes_with_any_pinned_bytes(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for root in (first, second):
                with open(os.path.join(root, "core.py"), "wb") as target:
                    target.write(b"reviewed source\n")
                with open(os.path.join(root, "table.csv"), "wb") as target:
                    target.write(b"a,b\n1,2\n")
            with patch.object(identity, "SOURCE_PATHS", ("core.py", "table.csv")):
                baseline = identity.source_fingerprint(first)
                self.assertEqual(baseline, identity.source_fingerprint(second))
                self.assertTrue(identity.valid_hex(baseline, 64))
                with open(os.path.join(second, "table.csv"), "ab") as target:
                    target.write(b"3,4\n")
                self.assertNotEqual(baseline, identity.source_fingerprint(second))

    def test_missing_pinned_source_fails_instead_of_unknown_build_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(identity, "SOURCE_PATHS", ("missing.py",)):
                with self.assertRaises(OSError):
                    identity.source_fingerprint(folder)

    def test_new_session_is_unique_even_for_identical_source(self):
        with patch.object(identity, "source_fingerprint", return_value="b" * 64):
            first, second = identity.new_runtime_identity(), identity.new_runtime_identity()
        self.assertEqual(first["runtime_protocol_version"], 2)
        self.assertEqual(first["build_id"], second["build_id"])
        self.assertNotEqual(first["session_id"], second["session_id"])
        self.assertTrue(identity.valid_hex(first["session_id"], 32))

    def test_fingerprint_scope_excludes_configs_keys_journals_and_telemetry(self):
        self.assertEqual(len(identity.SOURCE_PATHS), len(set(identity.SOURCE_PATHS)))
        self.assertIn("elyse_agent/runtime_identity.py", identity.SOURCE_PATHS)
        self.assertIn("elyse_agent/acquisition_recovery.py", identity.SOURCE_PATHS)
        for name in identity.SOURCE_PATHS:
            self.assertFalse(any(word in name for word in (".key", ".ownership", "config.", ".sqlite")))


if __name__ == "__main__":
    unittest.main()
