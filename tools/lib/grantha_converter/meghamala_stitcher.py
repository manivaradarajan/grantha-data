"""Merges chunked meghamala markdown conversions into a single document.

This module provides functionality to intelligently merge multiple converted
chunks into a single cohesive Grantha Markdown file with proper frontmatter,
validation hashing, and Devanagari content preservation checks.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from grantha_converter.devanagari_extractor import HASH_VERSION, extract_devanagari
from grantha_converter.hasher import hash_text


def extract_frontmatter_and_body(text: str) -> Tuple[Optional[Dict], str, int]:
    """Extracts YAML frontmatter and body content from markdown.

    Parses markdown text to separate YAML frontmatter (enclosed in ---
    delimiters) from the body content. Returns None for frontmatter if
    no valid frontmatter is found.

    Args:
        text: Markdown content potentially containing YAML frontmatter.

    Returns:
        A tuple containing:
            - frontmatter_dict: Parsed YAML as dict, or None if not found.
            - body: The markdown body content after frontmatter.
            - frontmatter_end_position: Character position where frontmatter ends.
    """
    if not text.startswith('---'):
        return None, text, 0

    # Find the closing --- delimiter
    frontmatter_end = _find_frontmatter_end(text)
    if frontmatter_end == -1:
        return None, text, 0

    # Parse the YAML content between delimiters
    frontmatter_text = text[3:frontmatter_end - 4].strip()
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return None, text, 0

    # Extract body, skipping frontmatter and any following blank line
    body_start = frontmatter_end
    if text[body_start:body_start + 1] == '\n':
        body_start += 1

    return frontmatter, text[body_start:], frontmatter_end


def _find_frontmatter_end(text: str) -> int:
    """Finds the ending position of YAML frontmatter.

    Looks for the closing --- delimiter. Handles both '\n---\n' and '\n---'
    patterns.

    Args:
        text: Text starting with '---' delimiter.

    Returns:
        Character position of frontmatter end, or -1 if not found.
    """
    # Try standard ending pattern first
    pos = text.find('\n---\n', 4)
    if pos != -1:
        return pos + 5  # Include '\n---\n'

    # Try alternate ending pattern (no trailing newline)
    pos = text.find('\n---', 4)
    if pos != -1:
        return pos + 4  # Include '\n---'

    return -1


def merge_frontmatter(chunk_frontmatters: List[Dict]) -> Dict:
    """Merges frontmatter from multiple chunks into a single frontmatter.

    Strategy:
        - Uses first chunk as the base for most fields
        - Merges commentaries_metadata lists, deduplicating by commentary_id
        - Structure_levels assumed identical across chunks (uses first)
        - validation_hash placeholder set (recalculated after body merge)

    Args:
        chunk_frontmatters: List of frontmatter dictionaries from chunks.

    Returns:
        Merged frontmatter dictionary ready for recalculating hash.
    """
    if not chunk_frontmatters:
        return {}

    # Start with first chunk's frontmatter as base
    merged = chunk_frontmatters[0].copy()

    # Merge commentary metadata, avoiding duplicates
    merged['commentaries_metadata'] = _merge_commentaries(chunk_frontmatters)

    # Clear validation_hash - will be recalculated after body merge
    if 'validation_hash' in merged:
        merged['validation_hash'] = 'TO_BE_CALCULATED'

    return merged


def _merge_commentaries(frontmatters: List[Dict]) -> List[Dict]:
    """Merges commentaries_metadata lists from multiple frontmatters.

    Deduplicates commentaries by commentary_id, preserving first occurrence.

    Args:
        frontmatters: List of frontmatter dicts potentially containing
            commentaries_metadata.

    Returns:
        Deduplicated list of commentary metadata entries.
    """
    all_commentaries = []
    seen_ids = set()

    for frontmatter in frontmatters:
        commentaries = frontmatter.get('commentaries_metadata')
        if not commentaries or not isinstance(commentaries, list):
            continue

        for commentary in commentaries:
            if not isinstance(commentary, dict):
                continue

            commentary_id = commentary.get('commentary_id')
            if commentary_id and commentary_id not in seen_ids:
                all_commentaries.append(commentary)
                seen_ids.add(commentary_id)

    return all_commentaries


def merge_bodies(chunk_bodies: List[str], spacing: str = '\n\n') -> str:
    """Merges body content from multiple chunks.

    Strips whitespace from each chunk and joins them with specified spacing.

    Args:
        chunk_bodies: List of markdown body content strings.
        spacing: String to insert between chunks. Defaults to two newlines.

    Returns:
        Merged body content as a single string.
    """
    cleaned_chunks = [body.strip() for body in chunk_bodies if body.strip()]
    return spacing.join(cleaned_chunks)


def recalculate_references(body: str) -> str:
    """Ensures references are sequentially numbered across merged content.

    Currently a placeholder for future smart renumbering based on
    structure_levels. For now, preserves references as-is since they
    are context-dependent and generated correctly by the conversion.

    Args:
        body: Merged body content.

    Returns:
        Body with renumbered references (currently unchanged).
    """
    # Future enhancement: Implement smart renumbering based on hierarchical
    # context (e.g., ## Mantra 1.1, ## Mantra 1.2, etc.)
    return body


def merge_chunks(
    chunk_files: List[str],
    verbose: bool = False
) -> Tuple[bool, Optional[str], str]:
    """Merges multiple converted chunk files into a single output file.

    Reads all chunk files, extracts their frontmatter and bodies, merges them,
    recalculates the validation hash, and assembles the final document.

    Args:
        chunk_files: List of file paths to chunk files, in order.
        verbose: If True, print detailed merging information.

    Returns:
        A tuple containing:
            - success: True if merge succeeded, False otherwise.
            - merged_content: Complete merged markdown, or None if failed.
            - message: Description of result or error message.
    """
    if not chunk_files:
        return False, None, "No chunk files provided"

    # Handle single chunk case (no merging needed)
    if len(chunk_files) == 1:
        return _handle_single_chunk(chunk_files[0])

    # Read and parse all chunks
    chunks_data = _read_all_chunks(chunk_files, verbose)
    if chunks_data is None:
        return False, None, "Error reading chunk files"

    # Extract frontmatter and bodies
    frontmatters = [c['frontmatter'] for c in chunks_data if c['frontmatter']]
    bodies = [c['body'] for c in chunks_data]

    # Merge components
    merged_frontmatter = merge_frontmatter(frontmatters) if frontmatters else None
    merged_body = merge_bodies(bodies)

    if verbose:
        _print_merge_summary(merged_frontmatter, merged_body, len(chunk_files))

    # Assemble final document
    merged_content = _assemble_document(merged_frontmatter, merged_body)

    return True, merged_content, f"Successfully merged {len(chunk_files)} chunks"


def _handle_single_chunk(chunk_file: str) -> Tuple[bool, Optional[str], str]:
    """Handles the case where only one chunk exists (no merging needed).

    Args:
        chunk_file: Path to the single chunk file.

    Returns:
        Tuple of (success, content, message).
    """
    try:
        with open(chunk_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return True, content, "Single chunk - no merging needed"
    except Exception as e:
        return False, None, f"Error reading chunk file: {e}"


def _read_all_chunks(
    chunk_files: List[str],
    verbose: bool
) -> Optional[List[Dict]]:
    """Reads and parses all chunk files.

    Args:
        chunk_files: List of paths to chunk files.
        verbose: If True, print information about each chunk.

    Returns:
        List of dicts containing parsed chunk data, or None if error occurs.
    """
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
                _print_chunk_info(i, len(chunk_files), chunk_file, frontmatter, body)

        except Exception as e:
            print(f"Error reading chunk {i} ({chunk_file}): {e}")
            return None

    return chunks_data


def _print_chunk_info(
    index: int,
    total: int,
    filename: str,
    frontmatter: Optional[Dict],
    body: str
) -> None:
    """Prints information about a chunk being read.

    Args:
        index: Zero-based index of this chunk.
        total: Total number of chunks.
        filename: Path to chunk file.
        frontmatter: Parsed frontmatter dict or None.
        body: Body content string.
    """
    print(f"Read chunk {index + 1}/{total}: {filename}")
    if frontmatter:
        print(f"  Frontmatter keys: {list(frontmatter.keys())}")
    print(f"  Body size: {len(body)} bytes")


def _print_merge_summary(
    frontmatter: Optional[Dict],
    body: str,
    num_chunks: int
) -> None:
    """Prints summary of merge operation.

    Args:
        frontmatter: Merged frontmatter dict or None.
        body: Merged body content.
        num_chunks: Number of chunks merged.
    """
    if frontmatter:
        print("\nMerged frontmatter:")
        print(f"  grantha_id: {frontmatter.get('grantha_id')}")
        print(f"  part_num: {frontmatter.get('part_num')}")
        levels = frontmatter.get('structure_levels', [])
        print(f"  structure_levels: {len(levels)} levels")

    print(f"\nMerged body: {len(body)} bytes")


def _assemble_document(frontmatter: Optional[Dict], body: str) -> str:
    """Assembles the final document with frontmatter and body.

    Ensures required fields are present, recalculates validation hash,
    and formats frontmatter as YAML.

    Args:
        frontmatter: Merged frontmatter dict, or None.
        body: Merged body content.

    Returns:
        Complete markdown document as string.
    """
    if not frontmatter:
        return body

    # Ensure required fields have defaults
    _add_required_field_defaults(frontmatter)

    # Recalculate validation hash from merged body
    frontmatter['hash_version'] = HASH_VERSION
    frontmatter['validation_hash'] = hash_text(body)

    # Convert to YAML with proper formatting
    frontmatter_yaml = yaml.dump(
        frontmatter,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )

    return f"---\n{frontmatter_yaml}---\n\n{body}"


def _add_required_field_defaults(frontmatter: Dict) -> None:
    """Adds default values for required fields if missing.

    Modifies frontmatter dict in-place.

    Args:
        frontmatter: Frontmatter dict to update.
    """
    if 'text_type' not in frontmatter:
        frontmatter['text_type'] = 'upanishad'
    if 'language' not in frontmatter:
        frontmatter['language'] = 'sanskrit'


def validate_merged_output(
    original_input: str,
    merged_output: str
) -> Tuple[bool, str]:
    """Validates that merged output preserves all Devanagari from input.

    Extracts Devanagari characters from both input and output (excluding
    output frontmatter) and compares them. This ensures the Sanskrit
    content was preserved through the conversion and merging process.

    Args:
        original_input: Original meghamala markdown input text.
        merged_output: Merged converted output text.

    Returns:
        Tuple of:
            - is_valid: True if all Devanagari preserved, False otherwise.
            - message: Descriptive message about validation result.
    """
    # Extract Devanagari from original input
    input_devanagari = extract_devanagari(original_input)

    # Extract Devanagari from output body (skip frontmatter)
    frontmatter, body, _ = extract_frontmatter_and_body(merged_output)
    output_devanagari = extract_devanagari(body if frontmatter else merged_output)

    # Compare character counts
    if input_devanagari == output_devanagari:
        char_count = len(input_devanagari)
        return True, f"Validation passed: {char_count} Devanagari characters preserved"

    # Calculate and report difference
    diff = abs(len(input_devanagari) - len(output_devanagari))
    input_count = len(input_devanagari)
    output_count = len(output_devanagari)

    return (
        False,
        f"Validation failed: {diff} character difference "
        f"(input: {input_count}, output: {output_count})"
    )


def cleanup_temp_chunks(chunk_files: List[str], verbose: bool = False) -> int:
    """Deletes temporary chunk files.

    Args:
        chunk_files: List of chunk file paths to delete.
        verbose: If True, print information about each deletion.

    Returns:
        Number of files successfully deleted.
    """
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
