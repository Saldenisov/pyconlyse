import unittest
from dataclasses import FrozenInstanceError

from supervision_reconstruction.domain.journal import (
    DISPLAY_TIMESTAMP_FORMAT,
    FILE_TIMESTAMP_FORMAT,
    journal_transformation_status,
    plan_journal_file_write,
    project_journal_bytes,
)


class JournalEvidenceTests(unittest.TestCase):
    def test_journal_transform_is_explicitly_blocked_instead_of_guessed(self) -> None:
        status = journal_transformation_status()

        self.assertEqual(status.vi_name, "2_SUP_Journal_des _erreurs.vi")
        self.assertFalse(status.implementation_allowed)
        self.assertEqual(
            status.observed_timestamp_formats,
            ("%Y %d/%m %H:%M:%S   ", "%d/%m %H:%M:%S   "),
        )
        self.assertGreaterEqual(len(status.unresolved_contracts), 4)

    def project(self, message=b"new", journal=b"old"):
        return project_journal_bytes(
            message_input=message,
            journal_in=journal,
            display_timestamp=b"04/10 23:59:59   ",
            file_timestamp=b"2026 05/10 00:00:00   ",
        )

    def test_new_entry_is_prepended_with_crlf_and_message_is_cleared(self):
        result = self.project()
        self.assertEqual(result.journal_out, b"04/10 23:59:59   new\r\nold")
        self.assertEqual(result.message_output, b"")
        self.assertEqual(result.file_row, b"2026 05/10 00:00:00   new")

    def test_independent_timestamp_values_are_not_collapsed_to_one_clock(self):
        result = self.project()
        self.assertNotEqual(result.file_row[:20], result.journal_out[:20])

    def test_empty_message_and_empty_journal_still_produce_timestamp_and_crlf(self):
        result = self.project(message=b"", journal=b"")
        self.assertEqual(result.journal_out, b"04/10 23:59:59   \r\n")
        self.assertEqual(result.file_row, b"2026 05/10 00:00:00   ")

    def test_binary_bytes_nuls_and_embedded_newlines_are_preserved(self):
        for message in (b"\0\xff", b"a\r\nb", b"\n\r", bytes(range(256))):
            result = self.project(message=message, journal=b"\0old\xff")
            self.assertEqual(
                result.journal_out, b"04/10 23:59:59   " + message + b"\r\n\0old\xff"
            )

    def test_no_100_line_truncation_is_invented(self):
        journal = b"old\r\n" * 150
        self.assertEqual(self.project(journal=journal).journal_out.count(b"\r\n"), 151)

    def test_timestamp_format_bytes_keep_three_trailing_spaces(self):
        self.assertEqual(DISPLAY_TIMESTAMP_FORMAT, b"%d/%m %H:%M:%S   ")
        self.assertEqual(FILE_TIMESTAMP_FORMAT, b"%Y %d/%m %H:%M:%S   ")

    def test_implicit_unicode_encoding_is_rejected(self):
        for name in (
            "message_input",
            "journal_in",
            "display_timestamp",
            "file_timestamp",
        ):
            args = dict.fromkeys(
                ("message_input", "journal_in", "display_timestamp", "file_timestamp"),
                b"",
            )
            args[name] = "text"
            with self.assertRaises(TypeError):
                project_journal_bytes(**args)

    def test_empty_path_does_not_skip_direct_append_intent(self):
        for path in (None, "", "legacy-path-token"):
            intent = plan_journal_file_write(self.project(), file_path_token=path)
            self.assertEqual(intent.file_path_token, path)
            self.assertEqual(intent.one_dimensional_data, (self.project().file_row,))
            self.assertTrue(intent.append_to_file)
            self.assertTrue(intent.external_effects_blocked)
            self.assertFalse(intent.file_format_and_delimiter_qualified)

    def test_projection_and_write_intent_are_immutable(self):
        result = self.project()
        with self.assertRaises(FrozenInstanceError):
            result.message_output = b"retained"
        intent = plan_journal_file_write(result, file_path_token="")
        with self.assertRaises(FrozenInstanceError):
            intent.external_effects_blocked = False
