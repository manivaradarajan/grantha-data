"""Converter for HTML details-based Markdown to Grantha Markdown format.

This module provides functionality to convert Markdown files that use HTML <details>
tags for organizing Sanskrit texts into the standardized Grantha Markdown format.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import yaml


@dataclass
class DetailsBlock:
    """Represents a parsed <details> block."""

    summary: str
    content: str
    is_open: bool
    start_line: int


@dataclass
class PassageData:
    """Represents a passage (mantra or commentary) with metadata."""

    ref: str
    content: str
    passage_type: str  # 'mantra', 'prefatory', 'concluding', 'commentary'
    summary: str  # Original summary text


def parse_toml_frontmatter(content: str) -> Tuple[Optional[Dict], str]:
    """Parse TOML frontmatter (enclosed in +++) from content.

    Returns:
        Tuple of (frontmatter_dict, remaining_content)
    """
    toml_pattern = r"^\+\+\+\s*\n(.*?)\n\+\+\+\s*\n"
    match = re.match(toml_pattern, content, re.DOTALL)

    if not match:
        return None, content

    # Simple TOML parsing for basic key = "value" format
    frontmatter = {}
    toml_content = match.group(1)
    for line in toml_content.split("\n"):
        line = line.strip()
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            frontmatter[key] = value

    remaining = content[match.end() :]
    return frontmatter, remaining


def parse_details_blocks(content: str) -> List[DetailsBlock]:
    """Extract all <details> blocks from content.

    Handles both <details> and <details open> tags.

    Returns:
        List of DetailsBlock objects
    """
    blocks = []

    # Pattern to match <details> or <details open> with summary and content
    pattern = r"<details(\s+open)?>\s*<summary>(.*?)</summary>\s*(.*?)</details>"

    for match in re.finditer(pattern, content, re.DOTALL):
        is_open = match.group(1) is not None
        summary = match.group(2).strip()
        block_content = match.group(3).strip()

        blocks.append(
            DetailsBlock(
                summary=summary,
                content=block_content,
                is_open=is_open,
                start_line=content[: match.start()].count("\n") + 1,
            )
        )

    return blocks


def extract_mantra_number(text: str) -> Optional[int]:
    """Extract mantra number from Sanskrit text containing ॥ N pattern.

    Handles variations like:
    - ॥ १ ॥
    - ॥१॥
    - ॥ १ (without closing ॥)
    - ॥ 1 ॥

    Returns:
        Integer mantra number or None if not found
    """
    # Pattern for Devanagari numbers or Arabic numerals
    # Make the closing ॥ optional
    pattern = r"॥\s*([०-९\d]+)(?:\s*॥)?"

    match = re.search(pattern, text)
    if not match:
        return None

    num_str = match.group(1).strip()

    # Convert Devanagari digits to Arabic
    devanagari_to_arabic = {
        "०": "0",
        "१": "1",
        "२": "2",
        "३": "3",
        "४": "4",
        "५": "5",
        "६": "6",
        "७": "7",
        "८": "8",
        "९": "9",
    }

    arabic_num = ""
    for char in num_str:
        arabic_num += devanagari_to_arabic.get(char, char)

    try:
        return int(arabic_num)
    except ValueError:
        return None


def clean_sanskrit_content(text: str) -> str:
    """Clean Sanskrit content by removing HTML tags and normalizing whitespace.

    Preserves all Devanagari characters and meaningful punctuation.
    """
    # Remove any remaining HTML tags
    cleaned = re.sub(r"<[^>]+>", "", text)

    # Normalize multiple newlines to at most 2 (paragraph breaks)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Strip leading/trailing whitespace but preserve internal formatting
    cleaned = cleaned.strip()

    return cleaned


def detect_prefatory_material(blocks: List[DetailsBlock]) -> Tuple[List[int], int]:
    """Detect which blocks are prefatory material (before first numbered mantra).

    Returns:
        Tuple of (list of prefatory block indices, index where mantras start)
    """
    first_mantra_idx = None

    # Find the first मूलम् block that contains ॥ १ ॥
    for idx, block in enumerate(blocks):
        if block.summary == "मूलम्" and block.is_open:
            mantra_num = extract_mantra_number(block.content)
            if mantra_num == 1:
                first_mantra_idx = idx
                break

    # If found, everything before it is prefatory
    if first_mantra_idx is not None:
        prefatory_indices = list(range(first_mantra_idx))
    else:
        # No mantra 1 found, assume no prefatory material
        prefatory_indices = []
        first_mantra_idx = 0

    return prefatory_indices, first_mantra_idx


def pair_mantras_with_commentaries(
    blocks: List[DetailsBlock],
) -> List[Tuple[int, Optional[int]]]:
    """Pair mantra blocks with their corresponding commentary blocks.

    Returns:
        List of tuples (mantra_block_idx, commentary_block_idx or None)
    """
    pairs = []

    i = 0
    while i < len(blocks):
        block = blocks[i]

        # Check if this is a मूलम् (mantra) block
        if block.summary == "मूलम्" and block.is_open:
            mantra_idx = i
            commentary_idx = None

            # Check if next block is a टीका (commentary)
            if i + 1 < len(blocks):
                next_block = blocks[i + 1]
                if next_block.summary == "टीका":
                    commentary_idx = i + 1
                    i += 1  # Skip the commentary in next iteration

            pairs.append((mantra_idx, commentary_idx))

        i += 1

    return pairs


def build_grantha_frontmatter(
    grantha_id: str,
    canonical_title: str,
    commentary_id: str,
    commentator: Optional[str] = None,
    commentary_title: Optional[str] = None,
    part_num: int = 1,
    text_type: str = "upanishad",
    language: str = "sanskrit",
    structure_key: str = "Mantra",
    structure_name_devanagari: str = "मन्त्रः",
) -> str:
    """Build YAML frontmatter for Grantha Markdown format.

    Returns:
        YAML frontmatter as string (including --- delimiters)
    """
    frontmatter = {
        "grantha_id": grantha_id,
        "part_num": part_num,
        "canonical_title": canonical_title,
        "text_type": text_type,
        "language": language,
        "structure_levels": [
            {
                "key": structure_key,
                "scriptNames": {"devanagari": structure_name_devanagari},
            }
        ],
        "commentaries_metadata": {
            commentary_id: {
                "commentary_title": commentary_title or canonical_title,
                "commentator": {"devanagari": commentator or "Unknown"},
            }
        },
    }

    yaml_str = yaml.dump(
        frontmatter, allow_unicode=True, sort_keys=False, default_flow_style=False
    )
    return f"---\n{yaml_str}---\n"


def format_passage(passage_data: PassageData, structure_key: str = "Mantra") -> str:
    """Format a passage in Grantha Markdown format.

    Returns:
        Formatted passage as string
    """
    lines = []

    # Add heading based on passage type
    if passage_data.passage_type == "mantra":
        lines.append(f"# {structure_key} {passage_data.ref}")
    elif passage_data.passage_type == "prefatory":
        lines.append(f'# Prefatory: {passage_data.ref} (devanagari: "शान्तिपाठः")')
    elif passage_data.passage_type == "concluding":
        lines.append(f'# Concluding: {passage_data.ref} (devanagari: "समापनम्")')
    else:
        raise ValueError(f"Unknown passage type: {passage_data.passage_type}")

    lines.append("")
    lines.append("<!-- sanskrit:devanagari -->")
    lines.append("")
    lines.append(passage_data.content)
    lines.append("")
    lines.append("<!-- /sanskrit:devanagari -->")

    return "\n".join(lines)


def format_commentary(ref: str, content: str, commentary_id: str) -> str:
    """Format a commentary in Grantha Markdown format.

    Returns:
        Formatted commentary as string
    """
    lines = []

    lines.append(f'<!-- commentary: {{"commentary_id": "{commentary_id}"}} -->')
    lines.append(f"# Commentary: {ref}")
    lines.append("")
    lines.append("<!-- sanskrit:devanagari -->")
    lines.append("")
    lines.append(content)
    lines.append("")
    lines.append("<!-- /sanskrit:devanagari -->")

    return "\n".join(lines)


def convert_file(
    input_path: str,
    output_path: str,
    grantha_id: str,
    canonical_title: str,
    commentary_id: str,
    commentator: Optional[str] = None,
    commentary_title: Optional[str] = None,
    structure_key: str = "Mantra",
    structure_name_devanagari: str = "मन्त्रः",
) -> None:
    """Convert an HTML details-based Markdown file to Grantha Markdown format.

    Args:
        input_path: Path to input file
        output_path: Path to output file
        grantha_id: Grantha identifier
        canonical_title: Title in Devanagari
        commentary_id: ID for the commentary
        commentator: Commentator name in Devanagari (optional)
        commentary_title: Commentary title (optional, defaults to canonical_title)
        structure_key: Structure level key (default: 'Mantra')
        structure_name_devanagari: Structure level name in Devanagari
    """
    # Read input file
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse frontmatter
    source_frontmatter, content = parse_toml_frontmatter(content)

    # Extract commentator from source if not provided
    if commentator is None and source_frontmatter:
        commentator = source_frontmatter.get("title", "Unknown")

    # Parse details blocks
    blocks = parse_details_blocks(content)

    if not blocks:
        raise ValueError("No <details> blocks found in input file")

    # Detect prefatory material
    prefatory_indices, first_mantra_idx = detect_prefatory_material(blocks)

    # Build output content
    output_lines = []

    # Add frontmatter
    frontmatter = build_grantha_frontmatter(
        grantha_id=grantha_id,
        canonical_title=canonical_title,
        commentary_id=commentary_id,
        commentator=commentator,
        commentary_title=commentary_title,
        structure_key=structure_key,
        structure_name_devanagari=structure_name_devanagari,
    )
    output_lines.append(frontmatter)

    # Process prefatory material first
    prefatory_ref = "0"
    prefatory_passages = []
    prefatory_commentaries = []

    # Collect prefatory materials
    for idx in prefatory_indices:
        block = blocks[idx]
        if block.summary == "मूलम्" and block.is_open:
            # Prefatory mantra/passage
            content = clean_sanskrit_content(block.content)
            passage_data = PassageData(
                ref=prefatory_ref,
                content=content,
                passage_type="prefatory",
                summary=block.summary,
            )
            prefatory_passages.append(passage_data)
        elif block.summary == "टीका":
            # Prefatory commentary
            content = clean_sanskrit_content(block.content)
            prefatory_commentaries.append(content)

    # If we have prefatory commentaries but no prefatory passages, create a minimal passage
    if prefatory_commentaries and not prefatory_passages:
        # Create a minimal prefatory passage
        minimal_passage = PassageData(
            ref=prefatory_ref,
            content="",  # Empty content
            passage_type="prefatory",
            summary="Prefatory Material",
        )
        prefatory_passages.append(minimal_passage)

    # Output prefatory passages
    for passage in prefatory_passages:
        output_lines.append(format_passage(passage, structure_key))
        output_lines.append("")

    # Output prefatory commentaries
    for commentary_content in prefatory_commentaries:
        output_lines.append(
            format_commentary(prefatory_ref, commentary_content, commentary_id)
        )
        output_lines.append("")

    # Process main mantras and commentaries
    i = first_mantra_idx
    while i < len(blocks):
        block = blocks[i]

        if block.summary == "मूलम्" and block.is_open:
            # This is a mantra
            mantra_content = clean_sanskrit_content(block.content)
            mantra_num = extract_mantra_number(block.content)

            if mantra_num is None:
                raise ValueError(
                    f"Could not extract mantra number from block at line {block.start_line}"
                )

            ref = str(mantra_num)

            # Format mantra
            passage_data = PassageData(
                ref=ref,
                content=mantra_content,
                passage_type="mantra",
                summary=block.summary,
            )
            output_lines.append(format_passage(passage_data, structure_key))
            output_lines.append("")

            # Check if next block is commentary
            if i + 1 < len(blocks) and blocks[i + 1].summary == "टीका":
                commentary_content = clean_sanskrit_content(blocks[i + 1].content)
                output_lines.append(
                    format_commentary(ref, commentary_content, commentary_id)
                )
                output_lines.append("")
                i += 1  # Skip the commentary block in next iteration

        i += 1

    # Write output file
    output_text = "\n".join(output_lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output_text)
