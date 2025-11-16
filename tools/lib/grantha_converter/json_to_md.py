"""JSON to Markdown converter for grantha data.

This module converts grantha JSON files to a structured Markdown format.
Key features include:
- Generation of a YAML frontmatter containing all metadata for lossless
  reconstruction.
- A validation hash to ensure content integrity.
- Hierarchical rendering of passages based on `structure_levels`.
- Interleaving of commentaries directly following the passages they reference.
- Selective inclusion of scripts (e.g., Devanagari, Roman) and commentaries.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .devanagari_extractor import HASH_VERSION
from .hasher import extract_content_text, hash_grantha


def get_lowest_level_key(structure_levels: List[Dict[str, Any]]) -> str:
    """Recursively finds the 'key' of the deepest level in a structure definition.

    This is used to determine which passages are the primary, lowest-level
    content units (e.g., "Mantra").

    Args:
        structure_levels: The `structure_levels` list from the grantha JSON.

    Returns:
        The string key of the lowest structural level (e.g., "Mantra").
    """
    if not structure_levels:
        return 'Mantra'  # Default if none

    last_level = structure_levels[-1]
    if 'children' in last_level and last_level['children']:
        return get_lowest_level_key(last_level['children'])
    else:
        return last_level['key']


def build_hierarchy_tree(structure_levels: List[Dict[str, Any]],
                         passages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Builds a hierarchical tree from a flat list of passages.

    This function transforms a simple list of passages into a nested dictionary
    that mirrors the grantha's structure (e.g., Adhyaya > Brahmana > Mantra).
    The tree is built based on the dot-separated `ref` field of each passage.

    Args:
        structure_levels: The structure definition from the JSON.
        passages: A flat list of passage dictionaries.

    Returns:
        A nested dictionary representing the hierarchical structure, with
        passages stored in `_passages` keys at each node.
    """
    tree: Dict[str, Any] = {}

    for passage in passages:
        ref = passage['ref']
        parts = ref.split('.')

        # Navigate or create tree structure
        current = tree
        for i, part in enumerate(parts):
            # The `_children` key holds sub-nodes.
            if part not in current:
                current[part] = {'_passages': [], '_children': {}}
            if i == len(parts) - 1:
                # This is a leaf node for this passage, so add it.
                current[part]['_passages'].append(passage)
            else:
                # This is an intermediate node, so traverse deeper.
                current = current[part]['_children']

    return tree


def get_header_level_name(structure_levels: List[Dict[str, Any]], depth: int) -> str:
    """Gets the name for a header at a given depth in the structure.

    Args:
        structure_levels: The structure definition from the JSON.
        depth: The 0-indexed depth level.

    Returns:
        The name of the level (e.g., "Mundaka", "Khanda", "Mantra").
    """
    if not structure_levels:
        return "Mantra"

    # Start at the root level
    current = structure_levels[0]

    # Navigate down the hierarchy to the target depth
    for i in range(depth):
        if 'children' in current and current['children']:
            current = current['children'][0]
        else:
            # Reached a leaf before target depth
            return current['key']

    return current['key']


def format_content(content: Dict[str, Any],
                   scripts: List[str],
                   indent: str = "") -> str:
    """Formats a content dictionary into a Markdown string.

    This function creates the body of a passage, including script tags
    as HTML comments for machine readability.

    Args:
        content: A content dictionary with fields like 'sanskrit' and 'english'.
        scripts: A list of scripts to include in the output.
        indent: An indentation prefix for each line.

    Returns:
        A formatted Markdown string for the content block.
    """
    lines = []

    # Add Sanskrit text in requested scripts
    if 'sanskrit' in content:
        sanskrit = content['sanskrit']
        for script_name in ['devanagari', 'roman', 'kannada']:
            if script_name in scripts and sanskrit.get(script_name):
                lines.append(f"{indent}<!-- sanskrit:{script_name} -->")
                lines.append(f"{indent}{sanskrit[script_name]}")

    # Add English translation
    if 'english_translation' in content and content['english_translation']:
        lines.append(f"{indent}<!-- english_translation -->")
        lines.append(f"{indent}{content['english_translation']}")

    # Add English (for commentary)
    if 'english' in content and content['english']:
        lines.append(f"{indent}<!-- english -->")
        lines.append(f"{indent}{content['english']}")

    return '\n'.join(lines)


def write_tree_to_markdown(tree: Dict[str, Any],
                           structure_levels: List[Dict[str, Any]],
                           scripts: List[str],
                           commentary_map: Dict[str, List[Dict[str, Any]]] = None,
                           depth: int = 0,
                           ref_prefix: str = "") -> str:
    """Recursively writes the hierarchical passage tree to a Markdown string.

    This function traverses the nested dictionary tree, generating Markdown
    headers for each level and interleaving commentaries directly after the
    passages they reference.

    Args:
        tree: The hierarchical tree of passages from `build_hierarchy_tree`.
        structure_levels: The structure definition from the JSON.
        scripts: A list of scripts to include in the output.
        commentary_map: A dictionary mapping passage refs to their commentaries.
        depth: The current recursion depth (used for header levels).
        ref_prefix: The reference prefix for the current level (e.g., "1.2.").

    Returns:
        A Markdown string representing this subtree.
    """
    lines = []
    if commentary_map is None:
        commentary_map = {}

    # Get level name for headers
    level_name = get_header_level_name(structure_levels, depth)
    lowest_level_key = get_lowest_level_key(structure_levels)

    # Sort keys numerically to ensure correct order
    sorted_keys = sorted(tree.keys(), key=lambda x: int(x) if x.isdigit() else x)

    for key in sorted_keys:
        node = tree[key]
        current_ref = f"{ref_prefix}{key}" if ref_prefix else key

        # Write header for this level
        header_level = 1 if level_name == lowest_level_key else depth + 1
        header_prefix = '#' * header_level
        header_text = f"{level_name} {current_ref}"
        lines.append(f"{header_prefix} {header_text}\n")

        # Write passages at this level
        for passage in node.get('_passages', []):
            content_md = format_content(passage['content'], scripts)
            if content_md:
                lines.append(content_md)
                lines.append("")  # Blank line after passage

            # Write commentaries for this passage (interleaved)
            passage_ref = passage['ref']
            if passage_ref in commentary_map:
                for comm_data in commentary_map[passage_ref]:
                    # Add metadata comment for reconstruction
                    comm_metadata = {'commentary_id': comm_data['commentary_id']}
                    lines.append(f"<!-- commentary: {json.dumps(comm_metadata, ensure_ascii=False)} -->")

                    # Commentary header (one level deeper than passage)
                    comm_header_level = header_level + 1
                    comm_header_prefix = '#' * comm_header_level
                    commentator_name = comm_data['commentator_name']
                    lines.append(f"{comm_header_prefix} Commentary: {commentator_name}\n")

                    # Prefatory material in commentary
                    if 'prefatory_material' in comm_data:
                        for i, item in enumerate(comm_data['prefatory_material']):
                            pref_meta = {
                                'type': item.get('type', ''),
                                'label': item.get('label', '')
                            }
                            lines.append(f"<!-- commentary_prefatory_{passage_ref}_{i}: {json.dumps(pref_meta, ensure_ascii=False)} -->")
                            label = item.get('label', item.get('type', ''))
                            lines.append(f"{'#' * (comm_header_level + 1)} {label}\n")
                            content_md = format_content(item['content'], scripts)
                            if content_md:
                                lines.append(content_md)
                                lines.append("")

                    # Main commentary content
                    if 'content' in comm_data:
                        content_md = format_content(comm_data['content'], scripts)
                        if content_md:
                            lines.append(content_md)
                            lines.append("")

        # Recursively write children
        children = node.get('_children', {})
        if children:
            child_md = write_tree_to_markdown(
                children,
                structure_levels,
                scripts,
                commentary_map,
                depth + 1,
                f"{current_ref}."
            )
            lines.append(child_md)

    return '\n'.join(lines)


def convert_to_markdown(data: Dict[str, Any],
                        scripts: Optional[List[str]] = None,
                        commentaries: Optional[List[str]] = None) -> str:
    """Converts a grantha JSON dictionary to a structured Markdown string.

    This is the main function for the JSON to Markdown conversion. It orchestrates
    the creation of the frontmatter, the building of the hierarchical passage
    tree, and the final rendering to a Markdown string.

    Args:
        data: The full grantha JSON data as a dictionary.
        scripts: A list of scripts to include (e.g., ['devanagari']).
            Defaults to ['devanagari'].
        commentaries: A list of commentary IDs to include. Defaults to None,
            which includes no commentaries.

    Returns:
        A single string containing the full Markdown output with YAML frontmatter.
    """
    if scripts is None:
        scripts = ['devanagari']

    # Build frontmatter with all necessary metadata for reconstruction
    frontmatter = {
        'grantha_id': data.get('grantha_id'),
        'canonical_title': data.get('canonical_title'),
        'text_type': data.get('text_type'),
        'language': data.get('language'),
        'scripts': scripts,
        'structure_levels': data.get('structure_levels', []),
    }

    # Add optional top-level fields if they exist
    for key in ['aliases', 'variants_available', 'metadata']:
        if key in data:
            frontmatter[key] = data[key]

    if commentaries:
        frontmatter['commentaries'] = commentaries
        # Store full commentary metadata for reconstruction
        commentaries_metadata = []
        for commentary_data in data.get('commentaries', []):
            if commentary_data['commentary_id'] in commentaries:
                comm_meta = {
                    'commentary_id': commentary_data['commentary_id'],
                    'commentator': commentary_data.get('commentator', {}),
                }
                for key in ['commentary_title', 'metadata']:
                    if key in commentary_data:
                        comm_meta[key] = commentary_data[key]
                commentaries_metadata.append(comm_meta)
        frontmatter['commentaries_metadata'] = commentaries_metadata

    # Generate validation hash
    validation_hash = hash_grantha(data, scripts=scripts, commentaries=commentaries)
    frontmatter['hash_version'] = HASH_VERSION
    frontmatter['validation_hash'] = f"sha256:{validation_hash}"

    # --- Build Markdown Content ---
    content_lines = []

    # Add prefatory material
    if 'prefatory_material' in data and data['prefatory_material']:
        for item in data['prefatory_material']:
            ref = item.get('ref')
            label_info = item.get('label', {})
            label_text = label_info.get('devanagari', '')
            if ref and label_text:
                header = f'# Prefatory: {ref} (devanagari: "{label_text}")'
                content_lines.append(header)
                content_md = format_content(item['content'], scripts)
                if content_md:
                    content_lines.append(content_md)
                    content_lines.append("")

    # Build a map of passage references to their commentaries for easy lookup
    commentary_map: Dict[str, List[Dict[str, Any]]] = {}
    if commentaries and 'commentaries' in data:
        for commentary_data in data['commentaries']:
            commentary_id = commentary_data['commentary_id']
            if commentary_id not in commentaries:
                continue

            commentator = commentary_data.get('commentator', {})
            commentator_name = commentator.get('devanagari', commentator.get('latin', commentary_id))

            for passage in commentary_data.get('passages', []):
                ref = passage['ref']
                if ref not in commentary_map:
                    commentary_map[ref] = []
                comm_entry = {
                    'commentary_id': commentary_id,
                    'commentator_name': commentator_name,
                    'content': passage.get('content'),
                }
                if 'prefatory_material' in passage:
                    comm_entry['prefatory_material'] = passage['prefatory_material']
                commentary_map[ref].append(comm_entry)

    # Add main passages with interleaved commentaries
    if 'passages' in data and data['passages']:
        tree = build_hierarchy_tree(data.get('structure_levels', []), data['passages'])
        tree_md = write_tree_to_markdown(
            tree,
            data.get('structure_levels', []),
            scripts,
            commentary_map
        )
        content_lines.append(tree_md)

    # Add concluding material
    if 'concluding_material' in data and data['concluding_material']:
        for item in data['concluding_material']:
            ref = item.get('ref')
            label_info = item.get('label', {})
            label_text = label_info.get('devanagari', '')
            if ref and label_text:
                header = f'# Concluding: {ref} (devanagari: "{label_text}")'
                content_lines.append(header)
                content_md = format_content(item['content'], scripts)
                if content_md:
                    content_lines.append(content_md)
                    content_lines.append("")

    # Combine frontmatter and content
    yaml_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    markdown = f"---\n{yaml_str}---\n\n" + '\n'.join(content_lines)

    return markdown


def json_file_to_markdown_file(input_path: str,
                                 output_path: str,
                                 scripts: Optional[List[str]] = None,
                                 commentaries: Optional[List[str]] = None) -> None:
    """Reads a grantha JSON file and writes it to a structured Markdown file.

    Args:
        input_path: The path to the input JSON file.
        output_path: The path to the output Markdown file.
        scripts: A list of scripts to include.
        commentaries: A list of commentary IDs to include.
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    markdown = convert_to_markdown(data, scripts=scripts, commentaries=commentaries)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)
