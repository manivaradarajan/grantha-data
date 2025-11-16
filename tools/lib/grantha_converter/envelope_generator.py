"""Envelope generation for multi-part grantha files.

This module provides functions to generate envelope.json files for multi-part
granthas, combining metadata from multiple part files.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def create_envelope_from_parts(
    grantha_id: str,
    part_files: List[Path],
    output_dir: Path
) -> Dict[str, Any]:
    """Create an envelope.json from multiple part JSON files.

    Args:
        grantha_id: The ID of the grantha
        part_files: List of paths to part JSON files (sorted by part_num)
        output_dir: Directory where envelope.json will be written

    Returns:
        The envelope data dictionary

    Raises:
        ValueError: If part files are missing required fields or have inconsistent metadata
    """
    if not part_files:
        raise ValueError("No part files provided")

    # Load all parts
    parts_data = []
    for part_file in part_files:
        with open(part_file, 'r', encoding='utf-8') as f:
            parts_data.append(json.load(f))

    # Verify all parts belong to the same grantha
    for part_data in parts_data:
        if part_data.get('grantha_id') != grantha_id:
            raise ValueError(
                f"Part file {part_data.get('grantha_id')} does not match "
                f"expected grantha_id {grantha_id}"
            )

    # Read metadata from first part (should be consistent across all parts)
    first_part = parts_data[0]

    # Build envelope structure
    envelope = {
        'grantha_id': grantha_id,
        'canonical_title': first_part.get('canonical_title'),
        'text_type': first_part.get('text_type'),
        'language': first_part.get('language'),
        'structure_levels': first_part.get('structure_levels', []),
        'parts': [part_file.name for part_file in part_files]
    }

    # Add optional fields if present
    if 'metadata' in first_part:
        envelope['metadata'] = first_part['metadata']
    if 'aliases' in first_part:
        envelope['aliases'] = first_part['aliases']
    if 'variants_available' in first_part:
        envelope['variants_available'] = first_part['variants_available']

    return envelope


def create_envelope_from_markdown_files(
    grantha_id: str,
    markdown_files: List[Path],
    output_dir: Path
) -> Dict[str, Any]:
    """Create an envelope.json by reading metadata from markdown files.

    This function reads the frontmatter from markdown files to extract
    metadata without doing a full conversion to JSON.

    Args:
        grantha_id: The ID of the grantha
        markdown_files: List of paths to markdown files (sorted by part_num)
        output_dir: Directory where envelope.json will be written

    Returns:
        The envelope data dictionary

    Raises:
        ValueError: If markdown files are missing required frontmatter
    """
    from .md_to_json import parse_frontmatter

    if not markdown_files:
        raise ValueError("No markdown files provided")

    # Read frontmatter from all files
    frontmatters = []
    for md_file in markdown_files:
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        frontmatter, _ = parse_frontmatter(content)
        frontmatters.append(frontmatter)

    # Verify all parts belong to the same grantha
    for fm in frontmatters:
        if fm.get('grantha_id') != grantha_id:
            raise ValueError(
                f"Markdown file {fm.get('grantha_id')} does not match "
                f"expected grantha_id {grantha_id}"
            )

    # Read metadata from first file
    first_fm = frontmatters[0]

    # Generate part filenames
    part_files = [f"part{i+1}.json" for i in range(len(markdown_files))]

    # Build envelope structure
    envelope = {
        'grantha_id': grantha_id,
        'canonical_title': first_fm.get('canonical_title'),
        'text_type': first_fm.get('text_type'),
        'language': first_fm.get('language'),
        'structure_levels': first_fm.get('structure_levels', []),
        'parts': part_files
    }

    # Add optional fields if present
    if 'metadata' in first_fm:
        envelope['metadata'] = first_fm['metadata']
    if 'aliases' in first_fm:
        envelope['aliases'] = first_fm['aliases']
    if 'variants_available' in first_fm:
        envelope['variants_available'] = first_fm['variants_available']

    return envelope


def write_envelope(envelope: Dict[str, Any], output_path: Path) -> None:
    """Write an envelope dictionary to a JSON file.

    Args:
        envelope: The envelope data dictionary
        output_path: Path where the envelope.json will be written
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)
