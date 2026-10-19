import unittest

from supervision_reconstruction.domain.tree_plans import (
    TREE_TRAVERSAL_BLOCKED,
    plan_add_item,
    plan_directory_to_tree,
)


class TreePlanTests(unittest.TestCase):
    def test_add_item_plan_records_file_then_patterned_folder_traversal(self) -> None:
        plan = plan_add_item("tree-ref", "root", "C:/root", "C:/root", "*.vi")
        self.assertEqual(
            (plan.tree_identity, plan.parent_tag, plan.search_root, plan.path, plan.pattern),
            ("tree-ref", "root", "C:/root", "C:/root", "*.vi"),
        )
        self.assertEqual(
            plan.operations,
            (
                "List Folder(path, no pattern) for files",
                "for each file: Build Path; parent is Parent Tag only when path == search root; invoke tree node",
                "List Folder(path, pattern) for folders",
                "for each folder: Build Path; parent is Parent Tag only when path == search root; invoke tree node",
            ),
        )
        self.assertIs(plan.blocked, TREE_TRAVERSAL_BLOCKED)

    def test_directory_plan_records_validate_gate_and_working_lifecycle_without_io(self) -> None:
        plan = plan_directory_to_tree(
            "tree-ref", "C:/root", "*.vi", 1, parent_tag="root"
        )
        self.assertEqual(
            (
                plan.tree_identity,
                plan.search_root,
                plan.pattern,
                plan.parent_tag,
                plan.files_found_input,
            ),
            ("tree-ref", "C:/root", "*.vi", "root", 1),
        )
        self.assertTrue(plan.files_found_connector_is_disconnected)
        self.assertEqual(plan.parent_tag_source, "front_panel_or_local_state")
        self.assertEqual(
            plan.operations,
            (
                "Initialize search paths and Working Visible=True/Blinking=True plan",
                "repeat candidate batches until folder worklist size == 0",
                "for each candidate: Validate; only True invokes Add Item",
                "append returned folders to next worklist and files to accumulated array",
                "Working Visible=False/Blinking=False plan after loop",
            ),
        )
        self.assertFalse(plan.blocked.implementation_allowed)
        changed_unwired = plan_directory_to_tree("tree", "root", "*", -(2**31))
        default_unwired = plan_directory_to_tree("tree", "root", "*")
        self.assertEqual(changed_unwired.files_found_input, -(2**31))
        self.assertEqual(default_unwired.files_found_input, 1)
        self.assertEqual(changed_unwired.operations, default_unwired.operations)
        self.assertEqual(default_unwired.parent_tag, "")
        with self.assertRaises(TypeError):
            plan_directory_to_tree("tree", "root", "*", True)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            plan_directory_to_tree("tree", "root", "*", 2**31)
