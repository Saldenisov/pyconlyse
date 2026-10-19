import unittest

from supervision_reconstruction.domain.file_dialog import (
    initialize_search,
    is_legacy_windows_shortcut_leaf_name,
    strip_windows_path_leaf_name,
    validate_path_signal,
)


class FileDialogTests(unittest.TestCase):
    def test_initialize_returns_single_path_and_nonexecuting_ui_effect_plan(self) -> None:
        result = initialize_search(
            r"C:\ELYSE\search-root", working_control_identity="working-refnum-17"
        )

        self.assertEqual(result.paths, (r"C:\ELYSE\search-root",))
        self.assertEqual(result.working_effect.control_identity, "working-refnum-17")
        self.assertEqual(
            [(write.property_name, write.value) for write in result.working_effect.writes],
            [("Visible", True), ("Blinking", True)],
        )

    def test_validate_rejects_only_the_two_evidenced_shortcut_spellings(self) -> None:
        self.assertTrue(is_legacy_windows_shortcut_leaf_name(".LNK"))
        self.assertTrue(is_legacy_windows_shortcut_leaf_name("item.LNK"))
        self.assertTrue(is_legacy_windows_shortcut_leaf_name("item.lnk"))
        for mixed in (".LNk", ".LnK", ".Lnk", ".lNK", ".lNk", ".lnK"):
            self.assertFalse(is_legacy_windows_shortcut_leaf_name(f"item{mixed}"))
        self.assertFalse(is_legacy_windows_shortcut_leaf_name("LNK"))
        self.assertFalse(is_legacy_windows_shortcut_leaf_name("item.LNK.more"))
        self.assertFalse(is_legacy_windows_shortcut_leaf_name("item.txt"))

    def test_validate_graph_is_valid_path_and_not_exact_legacy_shortcut(self) -> None:
        normal = validate_path_signal(path_ref_is_valid=True, path=r"C:\data\item.txt")
        shortcut = validate_path_signal(path_ref_is_valid=True, path=r"C:\data\item.lnk")
        invalid_ref = validate_path_signal(path_ref_is_valid=False, path=r"C:\data\item.txt")

        self.assertTrue(normal.valid_path)
        self.assertEqual(normal.leaf_name, "item.txt")
        self.assertFalse(normal.is_windows_shortcut)
        self.assertFalse(shortcut.valid_path)
        self.assertTrue(shortcut.is_windows_shortcut)
        self.assertFalse(invalid_ref.valid_path)

        for ref_is_valid in (False, True):
            for suffix, is_shortcut in ((".txt", False), (".LNK", True), (".lnk", True)):
                result = validate_path_signal(
                    path_ref_is_valid=ref_is_valid,
                    path=rf"C:\data\item{suffix}",
                )
                self.assertIs(type(result.valid_path), bool)
                self.assertEqual(result.valid_path, ref_is_valid and not is_shortcut)

    def test_strip_path_and_public_functions_reject_wrong_runtime_types(self) -> None:
        self.assertEqual(strip_windows_path_leaf_name(r"C:\data\item.LNK"), "item.LNK")
        self.assertEqual(strip_windows_path_leaf_name("C:\\data\\"), "data")
        self.assertEqual(strip_windows_path_leaf_name("C:\\"), "")
        self.assertEqual(strip_windows_path_leaf_name(""), "")
        with self.assertRaises(TypeError):
            initialize_search(None, working_control_identity="working")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            initialize_search("C:\\data", working_control_identity=None)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            validate_path_signal(path_ref_is_valid=1, path=r"C:\data\item.txt")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            validate_path_signal(path_ref_is_valid=True, path=None)  # type: ignore[arg-type]
