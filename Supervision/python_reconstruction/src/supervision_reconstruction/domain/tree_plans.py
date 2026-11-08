"""Immutable traversal/effect plans for Add Item.vi and Directory to Tree.vi."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TreeEvidenceBlock:
    vi_names: tuple[str, ...]
    implementation_allowed: bool
    unresolved_contracts: tuple[str, ...]


TREE_TRAVERSAL_BLOCKED = TreeEvidenceBlock(
    vi_names=("Add Item.vi", "Directory to Tree.vi"),
    implementation_allowed=False,
    unresolved_contracts=(
        "List Folder enumeration, ordering, pattern, and error semantics",
        "LabVIEW Path comparison/string/build semantics",
        "Tree control Invoke Node method/property and error propagation semantics",
        "recursive traversal termination under filesystem changes/cycles",
    ),
)


@dataclass(frozen=True)
class AddItemPlan:
    tree_identity: str
    parent_tag: str
    search_root: str
    path: str
    pattern: str
    operations: tuple[str, ...]
    blocked: TreeEvidenceBlock


@dataclass(frozen=True)
class DirectoryToTreePlan:
    tree_identity: str
    search_root: str
    pattern: str
    parent_tag: str
    files_found_input: int
    files_found_connector_is_disconnected: bool
    parent_tag_source: str
    operations: tuple[str, ...]
    blocked: TreeEvidenceBlock


def _require_string(value: str, *, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str")


def plan_add_item(tree_identity: str, parent_tag: str, search_root: str, path: str, pattern: str) -> AddItemPlan:
    """Capture Add Item's two List Folder/Build Path/tree-invoke phases."""

    for name, value in (("tree_identity", tree_identity), ("parent_tag", parent_tag), ("search_root", search_root), ("path", path), ("pattern", pattern)):
        _require_string(value, name=name)
    return AddItemPlan(
        tree_identity, parent_tag, search_root, path, pattern,
        (
            "List Folder(path, no pattern) for files",
            "for each file: Build Path; parent is Parent Tag only when path == search root; invoke tree node",
            "List Folder(path, pattern) for folders",
            "for each folder: Build Path; parent is Parent Tag only when path == search root; invoke tree node",
        ),
        TREE_TRAVERSAL_BLOCKED,
    )


def plan_directory_to_tree(
    tree_identity: str,
    search_root: str,
    pattern: str,
    files_found_input: int = 1,
    *,
    parent_tag: str = "",
) -> DirectoryToTreePlan:
    """Capture initialization, validate/add-item loop, accumulation, and Working effects.

    ``Files found`` is connector metadata with default 1 but is disconnected
    from the body; changing it has no behavioral influence. ``Parent Tag`` has
    no connector index and is retained explicitly as front-panel/local state.
    """

    for name, value in (("tree_identity", tree_identity), ("search_root", search_root), ("pattern", pattern), ("parent_tag", parent_tag)):
        _require_string(value, name=name)
    if type(files_found_input) is not int or not -(2**31) <= files_found_input <= 2**31 - 1:
        raise TypeError("files_found_input must be signed I32 int")
    return DirectoryToTreePlan(
        tree_identity,
        search_root,
        pattern,
        parent_tag,
        files_found_input,
        True,
        "front_panel_or_local_state",
        (
            "Initialize search paths and Working Visible=True/Blinking=True plan",
            "repeat candidate batches until folder worklist size == 0",
            "for each candidate: Validate; only True invokes Add Item",
            "append returned folders to next worklist and files to accumulated array",
            "Working Visible=False/Blinking=False plan after loop",
        ),
        TREE_TRAVERSAL_BLOCKED,
    )
