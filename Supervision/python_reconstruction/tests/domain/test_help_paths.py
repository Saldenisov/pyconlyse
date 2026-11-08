import unittest

from supervision_reconstruction.domain.help_paths import (
    HELP_PATH_PLATFORM_BLOCKED,
    HelpPathOperation,
    plan_build_help_path,
    plan_get_help_dir,
)


class HelpPathPlanTests(unittest.TestCase):
    def test_get_help_dir_preserves_only_wired_operation_sequence(self) -> None:
        plan = plan_get_help_dir()
        self.assertEqual(plan.help_directory_name, "help")
        self.assertEqual(
            plan.operations,
            (HelpPathOperation.STRIP_VI_LIBRARY_PATH, HelpPathOperation.APPEND_HELP_DIRECTORY),
        )
        self.assertIsNone(plan.resolved_path)

    def test_build_help_path_uses_default_and_accepts_only_a_string_name(self) -> None:
        default = plan_build_help_path()
        custom = plan_build_help_path("custom.chm")
        self.assertEqual(default.help_file_name, "lvhelp.chm")
        self.assertEqual(custom.help_file_name, "custom.chm")
        self.assertEqual(
            custom.operations,
            (
                HelpPathOperation.STRIP_VI_LIBRARY_PATH,
                HelpPathOperation.APPEND_HELP_DIRECTORY,
                HelpPathOperation.APPEND_HELP_FILE_NAME,
            ),
        )
        self.assertIsNone(custom.resolved_path)
        with self.assertRaises(TypeError):
            plan_build_help_path(None)  # type: ignore[arg-type]

    def test_platform_path_execution_is_explicitly_blocked(self) -> None:
        self.assertFalse(HELP_PATH_PLATFORM_BLOCKED.implementation_allowed)
        self.assertIn("BuildHelpPath.vi", HELP_PATH_PLATFORM_BLOCKED.vi_names)
        self.assertIn("GetHelpDir.vi", HELP_PATH_PLATFORM_BLOCKED.vi_names)
