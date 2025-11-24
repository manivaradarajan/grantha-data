"""Envelope generation for multi-part grantha files.

This module provides functions to generate envelope.json files for multi-part
granthas, combining metadata from multiple part files.
"""

import json
from pathlib import Path
from typing import Any, Dict, List


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
        ValueError: If markdown files are missing required frontmatter or have
                   inconsistent grantha_ids or invalid part numbering
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
        frontmatters.append((md_file, frontmatter))

    # Verify all parts have the same grantha_id
    grantha_ids = set()
    for md_file, fm in frontmatters:
        file_grantha_id = fm.get('grantha_id')
        if not file_grantha_id:
            raise ValueError(f"Missing grantha_id in {md_file}")
        grantha_ids.add(file_grantha_id)

    if len(grantha_ids) > 1:
        # Build detailed error message showing which files have which IDs
        id_to_files = {}
        for md_file, fm in frontmatters:
            file_id = fm.get('grantha_id')
            if file_id not in id_to_files:
                id_to_files[file_id] = []
            id_to_files[file_id].append(md_file.name)

        error_lines = ["Inconsistent grantha_id values found:"]
        for gid, files in sorted(id_to_files.items()):
            error_lines.append(f"  '{gid}': {', '.join(files)}")
        raise ValueError('\n'.join(error_lines))

    # Verify the grantha_id matches what was expected
    actual_grantha_id = list(grantha_ids)[0]
    if actual_grantha_id != grantha_id:
        raise ValueError(
            f"Grantha ID mismatch: expected '{grantha_id}' but files have '{actual_grantha_id}'"
        )

    # Verify part numbers are consecutive starting from 1
    part_nums = []
    for md_file, fm in frontmatters:
        part_num = fm.get('part_num')
        if part_num is None:
            raise ValueError(f"Missing part_num in {md_file}")
        part_nums.append((part_num, md_file))

    # Sort by part number
    part_nums.sort(key=lambda x: x[0])

    # Check for duplicates and non-consecutive parts
    seen_parts = {}  # maps part_num to list of files
    for part_num, md_file in part_nums:
        if part_num not in seen_parts:
            seen_parts[part_num] = []
        seen_parts[part_num].append(md_file)

    # Report duplicates
    duplicates = {pn: files for pn, files in seen_parts.items() if len(files) > 1}
    if duplicates:
        error_lines = ["Duplicate part_num values found:"]
        for pn, files in sorted(duplicates.items()):
            error_lines.append(f"  part_num {pn}: {', '.join(f.name for f in files)}")
        raise ValueError('\n'.join(error_lines))

    # Check that parts are consecutive starting from 1
    expected_parts = set(range(1, len(markdown_files) + 1))
    actual_parts = set(pn for pn, _ in part_nums)

    if actual_parts != expected_parts:
        missing = expected_parts - actual_parts
        extra = actual_parts - expected_parts
        error_msg = "Part numbers are not consecutive 1-N:"
        if missing:
            error_msg += f"\n  Missing parts: {sorted(missing)}"
        if extra:
            error_msg += f"\n  Unexpected parts: {sorted(extra)}"
        raise ValueError(error_msg)

    # Extract frontmatter objects in part order
    file_to_fm = {md_file: fm for md_file, fm in frontmatters}
    frontmatters_sorted = [file_to_fm[md_file] for _, md_file in part_nums]

    # Read metadata from first file (in part order)
    first_fm = frontmatters_sorted[0]

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
