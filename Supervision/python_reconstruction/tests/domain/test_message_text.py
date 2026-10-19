import itertools
import unittest

from supervision_reconstruction.domain.message_text import (
    LABVIEW_REGEX_DIALECT_BLOCKED,
    TagFound,
    check_special_tags,
    find_tag,
    format_message_string,
    search_and_replace_pattern,
)


class CheckSpecialTagsTests(unittest.TestCase):
    def test_error_accepts_only_eight_wired_ascii_case_variants(self) -> None:
        for letters in itertools.product(*(("E", "e"), ("R", "r"), ("R", "r"))):
            tag = "<" + "".join(letters) + ">"
            result = check_special_tags(f"before{tag}after")
            self.assertEqual(result.tag_found, TagFound.ERROR)
            self.assertEqual(result.before_tag_source, "before")
            self.assertEqual(result.after_tag_special_data, "after")

    def test_append_accepts_only_64_wired_ascii_case_variants(self) -> None:
        variants = (("A", "a"), ("P", "p"), ("P", "p"), ("E", "e"), ("N", "n"), ("D", "d"))
        for letters in itertools.product(*variants):
            tag = "<" + "".join(letters) + ">"
            result = check_special_tags(f"before{tag}after")
            self.assertEqual(result.tag_found, TagFound.APPEND)
            self.assertEqual(result.before_tag_source, "before")
            self.assertEqual(result.after_tag_special_data, "after")

    def test_error_has_priority_and_non_exact_forms_are_not_tags(self) -> None:
        result = check_special_tags("x<append>y<ERR>z")
        self.assertEqual(result.tag_found, TagFound.ERROR)
        self.assertEqual(result.before_tag_source, "x<append>y")
        self.assertEqual(result.after_tag_special_data, "z")

        for source in ("ERR", "<ERR/>", "< ERr>", "<APPEND/>", "<append >"):
            result = check_special_tags(source)
            self.assertEqual(result.tag_found, TagFound.NO_TAG)
            self.assertEqual(result.before_tag_source, source)
            self.assertEqual(result.after_tag_special_data, "")


class SearchAndReplacePatternTests(unittest.TestCase):
    def test_one_and_all_replacements_follow_offset_feedback(self) -> None:
        one = search_and_replace_pattern(
            "a-a-a", "-", "X", replace_all=False, allow_python_regex_model=True
        )
        self.assertEqual(one.result_string, "aXa-a")
        self.assertEqual(one.offset_past_match, 2)

        all_matches = search_and_replace_pattern(
            "a-a-a", "-", "X", replace_all=True, allow_python_regex_model=True
        )
        self.assertEqual(all_matches.result_string, "aXaXa")
        self.assertEqual(all_matches.offset_past_match, 4)

        later = search_and_replace_pattern(
            "a1a1", "a", "X", offset=2, replace_all=True, allow_python_regex_model=True
        )
        self.assertEqual(later.result_string, "a1X1")
        self.assertEqual(later.offset_past_match, 3)

    def test_missing_and_zero_length_matches_terminate_without_replacement(self) -> None:
        missing = search_and_replace_pattern(
            "abc", "z", "X", replace_all=True, allow_python_regex_model=True
        )
        self.assertEqual(missing.result_string, "abc")
        self.assertEqual(missing.offset_past_match, -1)

        zero_all = search_and_replace_pattern(
            "a", "(?=a)", "X", replace_all=True, allow_python_regex_model=True
        )
        zero_one = search_and_replace_pattern(
            "a", "(?=a)", "X", replace_all=False, allow_python_regex_model=True
        )
        self.assertEqual(zero_all.result_string, "a")
        self.assertEqual(zero_one.result_string, "a")
        self.assertEqual(zero_all.offset_past_match, 0)
        self.assertEqual(zero_one.offset_past_match, 0)

    def test_rejects_unproven_offset_and_regex_inputs(self) -> None:
        with self.assertRaises(ValueError):
            search_and_replace_pattern("abc", "a", offset=-1, allow_python_regex_model=True)
        with self.assertRaises(ValueError):
            search_and_replace_pattern("abc", "[", allow_python_regex_model=True)
        with self.assertRaises(TypeError):
            search_and_replace_pattern(
                "abc", "a", replace_all=1, allow_python_regex_model=True
            )  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            search_and_replace_pattern("abc", "a")
        with self.assertRaises(ValueError):
            search_and_replace_pattern("café", "a", allow_python_regex_model=True)
        self.assertFalse(LABVIEW_REGEX_DIALECT_BLOCKED.implementation_allowed)


class FindTagTests(unittest.TestCase):
    def test_removes_bold_tags_and_keeps_termination_indexing_entry(self) -> None:
        result = find_tag("x<B>bold</B>y", "<[Bb]>", "</[Bb]>")
        self.assertEqual(result.string_out, "xboldy")
        self.assertEqual(result.starts, (1, 6))
        self.assertEqual(result.lengths, (4, 0))

    def test_missing_and_malformed_tags_follow_wired_loop(self) -> None:
        no_tags = find_tag("plain", "<[Bb]>", "</[Bb]>")
        self.assertEqual(no_tags.string_out, "plain")
        self.assertEqual(no_tags.starts, (5,))
        self.assertEqual(no_tags.lengths, (0,))

        open_only = find_tag("a<b>c", "<[Bb]>", "</[Bb]>")
        close_only = find_tag("a</B>c", "<[Bb]>", "</[Bb]>")
        self.assertEqual(open_only.string_out, "ac")
        self.assertEqual(close_only.string_out, "ac")

    def test_only_evidenced_bold_case_forms_match_and_empty_tag_patterns_fail_closed(self) -> None:
        self.assertEqual(find_tag("<B>x</b>", "<[Bb]>", "</[Bb]>").string_out, "x")
        self.assertEqual(find_tag("<b>x</B>", "<[Bb]>", "</[Bb]>").string_out, "x")
        self.assertEqual(find_tag("<BB>x</BB>", "<[Bb]>", "</[Bb]>").string_out, "<BB>x</BB>")
        with self.assertRaises(ValueError):
            find_tag("x", "a*", "</[Bb]>", allow_python_regex_model=True)
        with self.assertRaises(ValueError):
            find_tag("x", "<x>", "</x>")
        with self.assertRaises(ValueError):
            find_tag("café<B>x</B>", "<[Bb]>", "</[Bb]>")


class FormatMessageStringTests(unittest.TestCase):
    def test_changed_message_returns_nonexecuting_write_and_bold_plans(self) -> None:
        result = format_message_string(
            "Source", "x<B>bold</B>y", target_identity="message-ref", current_control_value=""
        )
        self.assertEqual(result.source_out, "Source\r\n\r\n")
        self.assertEqual(result.details_out, "xboldy")
        self.assertEqual(result.message, "Source\r\n\r\nxboldy")
        self.assertEqual(result.bold_start, (1, 6))
        self.assertEqual(result.bold_length, (4, 0))
        self.assertEqual(result.value_write.property_name, "Valeur")
        self.assertEqual(result.value_write.value, result.message)
        self.assertEqual(result.bold_effect.prefix_adjustment, len(result.source_out))
        self.assertEqual(result.bold_effect.starts, result.bold_start)
        self.assertTrue(result.bold_effect.requires_successful_value_write)
        self.assertEqual(result.ordered_effects, (result.value_write, result.bold_effect))

    def test_equal_message_takes_no_property_write_branch(self) -> None:
        result = format_message_string(
            "S", "plain", target_identity="message-ref", current_control_value="S\r\n\r\nplain"
        )
        self.assertIsNone(result.value_write)
        self.assertIsNone(result.bold_effect)
        self.assertEqual(result.ordered_effects, ())
        self.assertEqual(result.bold_start, (5,))
        self.assertEqual(result.bold_length, (0,))

    def test_non_ascii_offsets_fail_closed_until_labview_encoding_is_proven(self) -> None:
        with self.assertRaises(ValueError):
            format_message_string(
                "Source", "détail", target_identity="message-ref", current_control_value=""
            )
