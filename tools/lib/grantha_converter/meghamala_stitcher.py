"""Merge chunked meghamala markdown conversions back together.

This module provides functionality to intelligently merge multiple converted chunks
into a single cohesive Grantha Markdown file.
"""

import re
from typing import List, Tuple, Dict, Optional
import yaml


def extract_frontmatter_and_body(text: str) -> Tuple[Optional[Dict], str, int]:
    """Extract YAML frontmatter and body from markdown.

    Args:
        text: Markdown content with frontmatter

    Returns:
        Tuple of (frontmatter_dict, body, frontmatter_end_position)
        Returns (None, text, 0) if no frontmatter found
    """
    # Check for frontmatter
    if not text.startswith('---'):
        return None, text, 0

    # Find end of frontmatter
    frontmatter_end = text.find('\n---\n', 4)
    if frontmatter_end == -1:
        # Try alternate ending pattern
        frontmatter_end = text.find('\n---', 4)
        if frontmatter_end == -1:
            return None, text, 0
        frontmatter_end += 4  # Include the ---
    else:
        frontmatter_end += 5  # Include \n---\n

    # Extract and parse frontmatter
    frontmatter_text = text[3:frontmatter_end-4].strip()  # Remove --- markers

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return None, text, 0

    # Extract body (skip frontmatter and following blank line if present)
    body_start = frontmatter_end
    if text[body_start:body_start+1] == '\n':
        body_start += 1

    body = text[body_start:]

    return frontmatter, body, frontmatter_end


def merge_frontmatter(chunk_frontmatters: List[Dict]) -> Dict:
    """Merge frontmatter from multiple chunks.

    Strategy:
    - Use first chunk for most fields
    - Combine structure_levels if they differ
    - Keep single validation_hash (will recalculate later)
    - Merge commentaries_metadata

    Args:
        chunk_frontmatters: List of frontmatter dictionaries

    Returns:
        Merged frontmatter dictionary
    """
    if not chunk_frontmatters:
        return {}

    # Start with first chunk's frontmatter
    merged = chunk_frontmatters[0].copy()

    # Collect all structure_levels
    all_structure_levels = []
    for fm in chunk_frontmatters:
        if 'structure_levels' in fm and fm['structure_levels']:
            if isinstance(fm['structure_levels'], dict):
                # Convert to list format if needed
                for key, value in fm['structure_levels'].items():
                    if key not in [item.get('key') if isinstance(item, dict) else item for item in all_structure_levels]:
                        all_structure_levels.append({key: value} if isinstance(value, dict) else value)
            elif isinstance(fm['structure_levels'], list):
                for level in fm['structure_levels']:
                    if level not in all_structure_levels:
                        all_structure_levels.append(level)

    # Use combined structure_levels if we found any
    if all_structure_levels and len(all_structure_levels) > len(merged.get('structure_levels', [])):
        merged['structure_levels'] = all_structure_levels

    # Merge commentaries_metadata
    all_commentaries = []
    seen_ids = set()
    for fm in chunk_frontmatters:
        if 'commentaries_metadata' in fm and fm['commentaries_metadata']:
            if isinstance(fm['commentaries_metadata'], list):
                for commentary in fm['commentaries_metadata']:
                    if isinstance(commentary, dict) and 'commentary_id' in commentary:
                        if commentary['commentary_id'] not in seen_ids:
                            all_commentaries.append(commentary)
                            seen_ids.add(commentary['commentary_id'])

    if all_commentaries:
        merged['commentaries_metadata'] = all_commentaries

    # Clear validation_hash - will recalculate after merging
    if 'validation_hash' in merged:
        merged['validation_hash'] = 'TO_BE_CALCULATED'

    return merged


def merge_bodies(chunk_bodies: List[str], spacing: str = '\n\n') -> str:
    """Merge body content from multiple chunks.

    Args:
        chunk_bodies: List of markdown body content
        spacing: Spacing between chunks (default: two newlines)

    Returns:
        Merged body content
    """
    # Strip trailing/leading whitespace from each chunk
    cleaned_chunks = [body.strip() for body in chunk_bodies if body.strip()]

    # Join with spacing
    return spacing.join(cleaned_chunks)


def recalculate_references(body: str) -> str:
    """Ensure references are sequentially numbered across merged content.

    This function scans for reference patterns and renumbers them sequentially.
    Common patterns:
    - ## Mantra 1.1, ## Mantra 1.2, etc.
    - ### Commentary: 1.1, ### Commentary: 1.2, etc.
    - # Prefatory: 0.1, # Prefatory: 0.2, etc.

    Args:
        body: Merged body content

    Returns:
        Body with renumbered references
    """
    # For now, we'll preserve the references as-is since they're context-dependent
    # In the future, could implement smart renumbering based on structure_levels
    # This would require understanding the hierarchical context

    return body


def merge_chunks(
    chunk_files: List[str],
    verbose: bool = False
) -> Tuple[bool, Optional[str], str]:
    """Merge multiple converted chunk files into a single output.

    Args:
        chunk_files: List of paths to chunk files (in order)
        verbose: Print merging details

    Returns:
        Tuple of (success: bool, merged_content: Optional[str], message: str)
    """
    if not chunk_files:
        return False, None, "No chunk files provided"

    if len(chunk_files) == 1:
        # Single chunk - just return it
        try:
            with open(chunk_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
            return True, content, "Single chunk - no merging needed"
        except Exception as e:
            return False, None, f"Error reading chunk file: {e}"

    # Read all chunks
    chunks_data = []
    for i, chunk_file in enumerate(chunk_files):
        try:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                content = f.read()

            frontmatter, body, _ = extract_frontmatter_and_body(content)

            chunks_data.append({
                'index': i,
                'file': chunk_file,
                'frontmatter': frontmatter,
                'body': body,
                'full_content': content
            })

            if verbose:
                print(f"Read chunk {i+1}/{len(chunk_files)}: {chunk_file}")
                if frontmatter:
                    print(f"  Frontmatter keys: {list(frontmatter.keys())}")
                print(f"  Body size: {len(body)} bytes")

        except Exception as e:
            return False, None, f"Error reading chunk {i} ({chunk_file}): {e}"

    # Extract frontmatter and bodies
    frontmatters = [c['frontmatter'] for c in chunks_data if c['frontmatter']]
    bodies = [c['body'] for c in chunks_data]

    # Merge frontmatter
    if frontmatters:
        merged_frontmatter = merge_frontmatter(frontmatters)
        if verbose:
            print(f"\nMerged frontmatter:")
            print(f"  grantha_id: {merged_frontmatter.get('grantha_id')}")
            print(f"  part_num: {merged_frontmatter.get('part_num')}")
            print(f"  structure_levels: {len(merged_frontmatter.get('structure_levels', []))} levels")
    else:
        merged_frontmatter = None

    # Merge bodies
    merged_body = merge_bodies(bodies)

    if verbose:
        print(f"\nMerged body: {len(merged_body)} bytes")

    # Reconstruct full document
    if merged_frontmatter:
        # Convert frontmatter back to YAML
        frontmatter_yaml = yaml.dump(merged_frontmatter, allow_unicode=True, sort_keys=False)
        merged_content = f"---\n{frontmatter_yaml}---\n\n{merged_body}"
    else:
        merged_content = merged_body

    if verbose:
        print(f"\nFinal merged content: {len(merged_content)} bytes")

    return True, merged_content, f"Successfully merged {len(chunk_files)} chunks"


def validate_merged_output(
    original_input: str,
    merged_output: str
) -> Tuple[bool, str]:
    """Validate that merged output preserves all Devanagari from original input.

    Args:
        original_input: Original meghamala markdown input
        merged_output: Merged converted output

    Returns:
        Tuple of (is_valid: bool, message: str)
    """
    from grantha_converter.devanagari_repair import extract_devanagari

    # Extract Devanagari from input
    input_devanagari = extract_devanagari(original_input)

    # Extract Devanagari from output (skip frontmatter)
    frontmatter, body, _ = extract_frontmatter_and_body(merged_output)
    if frontmatter:
        output_devanagari = extract_devanagari(body)
    else:
        output_devanagari = extract_devanagari(merged_output)

    # Compare
    if input_devanagari == output_devanagari:
        return True, f"Validation passed: {len(input_devanagari)} Devanagari characters preserved"

    # Calculate difference
    diff = abs(len(input_devanagari) - len(output_devanagari))
    return False, f"Validation failed: {diff} character difference (input: {len(input_devanagari)}, output: {len(output_devanagari)})"


def cleanup_temp_chunks(chunk_files: List[str], verbose: bool = False) -> int:
    """Delete temporary chunk files.

    Args:
        chunk_files: List of chunk file paths to delete
        verbose: Print deletion details

    Returns:
        Number of files successfully deleted
    """
    import os

    deleted = 0
    for chunk_file in chunk_files:
        try:
            if os.path.exists(chunk_file):
                os.remove(chunk_file)
                deleted += 1
                if verbose:
                    print(f"Deleted: {chunk_file}")
        except Exception as e:
            if verbose:
                print(f"Failed to delete {chunk_file}: {e}")

    return deleted
