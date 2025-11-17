"""Hierarchy tree building utilities.

This module provides utilities for building hierarchical trees from flat
passage lists, used by MarkdownWriter.
"""

from typing import Any, Dict, List


def build_hierarchy_tree(passages: List[Any]) -> Dict[str, Any]:
    """Builds a hierarchical tree from flat list of passages.

    Args:
        passages: Flat list of Passage objects.

    Returns:
        Nested dictionary with _passages and _children keys.
    """
    tree: Dict[str, Any] = {}

    for passage in passages:
        ref = passage.ref
        _add_passage_to_tree(tree, ref, passage)

    return tree


def _add_passage_to_tree(
    tree: Dict[str, Any],
    ref: str,
    passage: Any
) -> None:
    """Adds a single passage to the hierarchy tree."""
    parts = ref.split('.')
    current = tree

    for i, part in enumerate(parts):
        if part not in current:
            current[part] = {'_passages': [], '_children': {}}

        if i == len(parts) - 1:
            current[part]['_passages'].append(passage)
        else:
            current = current[part]['_children']


def sort_tree_keys(tree: Dict[str, Any]) -> List[str]:
    """Sorts tree keys numerically.

    Args:
        tree: Hierarchy tree dictionary.

    Returns:
        Sorted list of keys.
    """
    return sorted(
        tree.keys(),
        key=lambda x: int(x) if x.isdigit() else x
    )
