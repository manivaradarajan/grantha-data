"""Markdown grantha writer.

This module provides MarkdownWriter for serializing grantha content to
structured Markdown format conforming to GRANTHA_MARKDOWN.md specification.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from grantha_data.base import BaseGrantha
from grantha_data.models import Passage
from grantha_data.writers.base_writer import BaseWriter
from grantha_data._internal.hierarchy_builder import (
    build_hierarchy_tree,
    sort_tree_keys,
)


class MarkdownWriter(BaseWriter):
    """Serializes grantha to structured markdown format.

    Produces markdown conforming to GRANTHA_MARKDOWN.md spec.
    """

    def write(
        self,
        grantha: BaseGrantha,
        output_path: Path,
        scripts: Optional[List[str]] = None,
        commentaries: Optional[List[str]] = None,
        **_options
    ) -> None:
        """Writes grantha to markdown file.

        Args:
            grantha: Grantha to serialize.
            output_path: Output .md file path.
            scripts: Scripts to include (None = all).
            commentaries: Commentary IDs to include (None = all).
            **_options: Additional options (ignored).
        """
        markdown_string = self.write_to_string(
            grantha,
            scripts,
            commentaries
        )
        self._write_string_to_file(markdown_string, output_path)

    def _write_string_to_file(
        self,
        content: str,
        output_path: Path
    ) -> None:
        """Writes string content to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as f:
            f.write(content)

    def write_to_string(
        self,
        grantha: BaseGrantha,
        scripts: Optional[List[str]] = None,
        commentaries: Optional[List[str]] = None,
        **_options
    ) -> str:
        """Serializes grantha to markdown string.

        Args:
            grantha: Grantha to serialize.
            scripts: Scripts to include (None = all).
            commentaries: Commentary IDs to include (None = all).
            **_options: Additional options (ignored).

        Returns:
            Markdown string representation.
        """
        parts = []
        parts.append(self._build_frontmatter(grantha, scripts))
        parts.append(self._build_body(grantha, scripts, commentaries))
        return '\n'.join(parts)

    def _build_frontmatter(
        self,
        grantha: BaseGrantha,
        scripts: Optional[List[str]]
    ) -> str:
        """Builds YAML frontmatter."""
        metadata = grantha.get_metadata()

        frontmatter_dict = {
            'grantha_id': metadata.grantha_id,
            'part_num': metadata.part_num,
            'canonical_title': metadata.get_title('devanagari'),
            'text_type': metadata.text_type,
            'language': metadata.language,
            'scripts': scripts if scripts else metadata.scripts,
            'structure_levels': metadata.structure.levels,
        }

        self._add_commentaries_metadata_to_frontmatter(
            frontmatter_dict,
            grantha
        )

        frontmatter_yaml = yaml.dump(
            frontmatter_dict,
            allow_unicode=True,
            default_flow_style=False
        )

        return f"---\n{frontmatter_yaml}---\n"

    def _add_commentaries_metadata_to_frontmatter(
        self,
        frontmatter_dict: Dict[str, Any],
        grantha: BaseGrantha
    ) -> None:
        """Adds commentaries_metadata to frontmatter if present."""
        commentary_ids = grantha.list_commentaries()
        if not commentary_ids:
            return

        commentaries_metadata = []
        for cid in commentary_ids:
            metadata = grantha.get_commentary_metadata(cid)
            commentaries_metadata.append({
                'commentary_id': cid,
                **metadata
            })

        frontmatter_dict['commentaries_metadata'] = commentaries_metadata

    def _build_body(
        self,
        grantha: BaseGrantha,
        scripts: Optional[List[str]],
        commentaries: Optional[List[str]]
    ) -> str:
        """Builds markdown body with passages and commentaries."""
        parts = []

        # Prefatory material
        prefatory = grantha.get_prefatory_material(scripts)
        if prefatory:
            parts.append(self._format_prefatory_material(prefatory))

        # Main passages
        parts.append(
            self._format_main_passages(grantha, scripts, commentaries)
        )

        # Concluding material
        concluding = grantha.get_concluding_material(scripts)
        if concluding:
            parts.append(self._format_concluding_material(concluding))

        return '\n'.join(parts)

    def _format_prefatory_material(
        self,
        prefatory: List[Passage]
    ) -> str:
        """Formats prefatory material passages."""
        lines = []
        for passage in prefatory:
            lines.append(self._format_passage_header(passage))
            lines.append(self._format_passage_content(passage))
            lines.append("")
        return '\n'.join(lines)

    def _format_concluding_material(
        self,
        concluding: List[Passage]
    ) -> str:
        """Formats concluding material passages."""
        lines = []
        for passage in concluding:
            lines.append(self._format_passage_header(passage))
            lines.append(self._format_passage_content(passage))
            lines.append("")
        return '\n'.join(lines)

    def _format_passage_header(self, passage: Passage) -> str:
        """Formats passage header based on type."""
        if passage.is_prefatory:
            label = passage.label.get('devanagari', '') if passage.label else ''
            return f'# Prefatory: {passage.ref} (devanagari: "{label}")'
        elif passage.is_concluding:
            label = passage.label.get('devanagari', '') if passage.label else ''
            return f'# Concluding: {passage.ref} (devanagari: "{label}")'
        else:
            # Main passage - headers are handled by _write_tree_to_markdown
            return ""

    def _format_passage_content(self, passage: Passage) -> str:
        """Formats passage content with script tags."""
        lines = []
        content = passage.content

        for script in ['devanagari', 'roman', 'kannada']:
            if script in content and content[script]:
                lines.append(f"<!-- sanskrit:{script} -->")
                lines.append("")
                lines.append(content[script])
                lines.append("")
                lines.append(f"<!-- /sanskrit:{script} -->")

        return '\n'.join(lines)

    def _format_main_passages(
        self,
        grantha: BaseGrantha,
        scripts: Optional[List[str]],
        commentaries: Optional[List[str]]
    ) -> str:
        """Formats main passages in hierarchical structure."""
        passages = list(grantha.iter_passages('main'))
        if not passages:
            return ""

        tree = build_hierarchy_tree(passages)
        commentary_map = self._build_commentary_map(
            grantha,
            commentaries,
            scripts
        )

        return self._write_tree_to_markdown(
            tree,
            grantha.get_structure(),
            commentary_map
        )

    def _build_commentary_map(
        self,
        grantha: BaseGrantha,
        commentary_ids: Optional[List[str]],
        scripts: Optional[List[str]]
    ) -> Dict[str, List[Any]]:
        """Builds map of ref to commentary passages."""
        if commentary_ids is None:
            commentary_ids = grantha.list_commentaries()

        if not commentary_ids:
            return {}

        commentary_map: Dict[str, List[Any]] = {}

        for ref in grantha.get_all_refs():
            for cid in commentary_ids:
                try:
                    commentary = grantha.get_commentary(ref, cid, scripts)
                    if ref not in commentary_map:
                        commentary_map[ref] = []
                    commentary_map[ref].append(commentary)
                except Exception:
                    # Commentary may not exist for all refs
                    continue

        return commentary_map

    def _write_tree_to_markdown(
        self,
        tree: Dict[str, Any],
        structure: Any,
        commentary_map: Dict[str, List[Any]],
        depth: int = 0,
        ref_prefix: str = ""
    ) -> str:
        """Recursively writes hierarchy tree to markdown."""
        lines = []

        # Get the current level's name and key from the structure
        # Handle cases where depth might exceed explicitly defined structure levels
        if depth < structure.get_depth():
            current_level_dict = structure._get_level_at_depth(depth)
            level_name = structure._extract_script_name(current_level_dict, 'devanagari')
            current_level_key = current_level_dict.get('key', '')
        else:
            # If depth exceeds defined structure, use leaf level's name and key
            level_name = structure.get_level_name(depth, 'devanagari') # This will return "Mantra"
            current_level_key = structure.get_leaf_level_key() # This will return the key of the leaf level

        leaf_level_key = structure.get_leaf_level_key()

        for key in sort_tree_keys(tree):
            node = tree[key]
            current_ref = f"{ref_prefix}{key}" if ref_prefix else key

            # Write header using the current_level_key
            header_level = depth + 1
            header_prefix = '#' * header_level
            lines.append(f"{header_prefix} {level_name} {current_ref}\n")

            # Write passages at this level if it's the leaf level
            if current_level_key == leaf_level_key:
                for passage in node.get('_passages', []):
                    lines.append(self._format_passage_content(passage))
                    lines.append("")

                    # Write commentaries for this passage
                    if current_ref in commentary_map:
                        for commentary in commentary_map[current_ref]:
                            lines.append(
                                self._format_commentary(
                                    commentary,
                                    header_level
                                )
                            )

            # Recursively write children
            children = node.get('_children', {})
            if children:
                child_md = self._write_tree_to_markdown(
                    children,
                    structure,
                    commentary_map,
                    depth + 1,
                    f"{current_ref}."
                )
                lines.append(child_md)

        return '\n'.join(lines)

    def _format_commentary(
        self,
        commentary: Any,
        header_level: int
    ) -> str:
        """Formats a single commentary passage."""
        lines = []

        # Commentary metadata comment
        lines.append(
            f'<!-- commentary: {{"commentary_id": "{commentary.commentary_id}"}} -->'
        )
        lines.append("")

        # Commentary header
        comm_header_level = header_level + 1
        comm_header_prefix = '#' * comm_header_level
        lines.append(f"{comm_header_prefix} Commentary: {commentary.ref}")
        lines.append("")

        # Commentary content
        content = commentary.content
        for script in ['devanagari', 'roman', 'kannada']:
            if script in content and content[script]:
                lines.append(f"<!-- sanskrit:{script} -->")
                lines.append("")
                lines.append(content[script])
                lines.append("")
                lines.append(f"<!-- /sanskrit:{script} -->")

        lines.append(
            f'<!-- /commentary: {{"commentary_id": "{commentary.commentary_id}"}} -->'
        )
        lines.append("")

        return '\n'.join(lines)
