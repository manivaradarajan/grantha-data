"""Split large meghamala markdown files into manageable chunks.

This module provides functionality to intelligently split large Sanskrit text files
at natural boundaries (khanda, valli, anuvaka) for parallel processing.
"""

import re
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Boundary:
    """Represents a structural boundary in the text."""
    type: str  # 'khanda', 'valli', 'anuvaka', 'prapathaka'
    position: int  # Character position in text
    line_number: int  # Line number in file
    marker_text: str  # The actual marker text found
    ordinal: Optional[str] = None  # Sanskrit ordinal (प्रथम, द्वितीय, etc.)


# Sanskrit ordinal patterns (nominative masculine/feminine forms)
ORDINALS = [
    'प्रथम',  # 1st
    'द्वितीय', 'द्वितीया',  # 2nd
    'तृतीय', 'तृतीया',  # 3rd
    'चतुर्थ', 'चतुर्थी',  # 4th
    'पञ्चम', 'पञ्चमी',  # 5th
    'षष्ठ', 'षष्ठी',  # 6th
    'सप्तम', 'सप्तमी',  # 7th
    'अष्टम', 'अष्टमी',  # 8th
    'नवम', 'नवमी',  # 9th
    'दशम', 'दशमी',  # 10th
    'एकादश',  # 11th
    'द्वादश',  # 12th
    'त्रयोदश',  # 13th
    'चतुर्दश',  # 14th
    'पञ्चदश',  # 15th
    'षोडश',  # 16th
]

# Boundary patterns for different structural levels
BOUNDARY_PATTERNS = {
    'khanda': [
        # Two separate bold blocks: **प्रथमः** **खण्डः**
        r'\*\*(' + '|'.join(ORDINALS) + r')[ःोम]?\*\*\s+\*\*खण्ड[ःम]\*\*',
        # Single bold block: **प्रथमः खण्डः**
        r'\*\*(' + '|'.join(ORDINALS) + r')[ःोम]?\s*खण्ड[ःम]\*\*',
        r'\*\*खण्ड[ःम]\s*\d+\*\*',  # खण्डः 1, खण्डः 2, etc.
    ],
    'valli': [
        # Two separate bold blocks: **प्रथमा** **वल्ली**
        r'\*\*(' + '|'.join(ORDINALS) + r')[ाी]?\*\*\s+\*\*वल्ली\*\*',
        # Single bold block: **प्रथमा वल्ली**
        r'\*\*(' + '|'.join(ORDINALS) + r')[ाी]?\s*वल्ली\*\*',
        r'\*\*वल्ली\s*\d+\*\*',
    ],
    'anuvaka': [
        # Two separate bold blocks: **प्रथमोऽनुवाकः** (note: typically one word)
        r'\*\*(' + '|'.join(ORDINALS) + r')ोऽनुवाक[ःम]\*\*',
        r'\*\*अनुवाक[ःम]\s*\d+\*\*',
    ],
    'prapathaka': [
        # Two separate bold blocks: **प्रथमः** **प्रपाठकः**
        r'\*\*(' + '|'.join(ORDINALS) + r')[ःोम]?\*\*\s+\*\*प्रपाठक[ःम]\*\*',
        # Single bold block: **प्रथमः प्रपाठकः**
        r'\*\*(' + '|'.join(ORDINALS) + r')[ःोम]?\s*प्रपाठक[ःम]\*\*',
        r'\*\*प्रपाठक[ःम]\s*\d+\*\*',
    ],
}


def detect_structure_boundaries(text: str, verbose: bool = False) -> List[Boundary]:
    """Detect all structural boundaries in meghamala markdown text.

    Args:
        text: The meghamala markdown content
        verbose: Print detection details

    Returns:
        List of Boundary objects in order of appearance
    """
    boundaries = []
    lines = text.split('\n')

    # Track position in text
    char_position = 0

    for line_num, line in enumerate(lines, start=1):
        # Check each boundary type
        for boundary_type, patterns in BOUNDARY_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    # Extract ordinal if present
                    ordinal = None
                    for ord_pattern in ORDINALS:
                        if ord_pattern in match.group(0):
                            ordinal = ord_pattern
                            break

                    boundary = Boundary(
                        type=boundary_type,
                        position=char_position,
                        line_number=line_num,
                        marker_text=match.group(0),
                        ordinal=ordinal
                    )
                    boundaries.append(boundary)

                    if verbose:
                        print(f"Found {boundary_type} at line {line_num}: {match.group(0)}")

                    break  # Only match first pattern per line

        # Update position
        char_position += len(line) + 1  # +1 for newline

    return boundaries


def should_chunk(file_path: str, threshold: int = 200000) -> Tuple[bool, int, str]:
    """Determine if a file should be chunked.

    Args:
        file_path: Path to the file
        threshold: Size threshold in bytes (default: 200KB)

    Returns:
        Tuple of (should_chunk: bool, file_size: int, reason: str)
    """
    path = Path(file_path)

    if not path.exists():
        return False, 0, f"File not found: {file_path}"

    file_size = path.stat().st_size

    if file_size < threshold:
        return False, file_size, f"File size ({file_size} bytes) below threshold ({threshold} bytes)"

    return True, file_size, f"File size ({file_size} bytes) exceeds threshold ({threshold} bytes)"


def split_at_boundaries(
    text: str,
    max_size: int = 200000,
    preferred_boundary: Optional[str] = None,
    verbose: bool = False
) -> List[Tuple[str, Dict]]:
    """Split text at natural boundaries into chunks.

    Args:
        text: The meghamala markdown content
        max_size: Maximum chunk size in bytes (default: 200KB)
        preferred_boundary: Preferred boundary type ('khanda', 'valli', etc.)
        verbose: Print splitting details

    Returns:
        List of (chunk_text, metadata) tuples
        metadata contains: {
            'chunk_index': int,
            'total_chunks': int,
            'boundary_type': str,
            'starts_at_line': int,
            'ends_at_line': int,
            'size': int
        }
    """
    # Detect all boundaries
    boundaries = detect_structure_boundaries(text, verbose=verbose)

    if not boundaries:
        if verbose:
            print("No boundaries found - returning entire text as single chunk")
        return [(text, {
            'chunk_index': 0,
            'total_chunks': 1,
            'boundary_type': 'none',
            'starts_at_line': 1,
            'ends_at_line': len(text.split('\n')),
            'size': len(text)
        })]

    # Determine which boundary type to use
    if preferred_boundary:
        selected_boundaries = [b for b in boundaries if b.type == preferred_boundary]
        if not selected_boundaries:
            if verbose:
                print(f"No {preferred_boundary} boundaries found, using all boundaries")
            selected_boundaries = boundaries
    else:
        # Auto-select: prefer khanda > valli > anuvaka > prapathaka
        for boundary_type in ['khanda', 'valli', 'anuvaka', 'prapathaka']:
            selected_boundaries = [b for b in boundaries if b.type == boundary_type]
            if selected_boundaries:
                if verbose:
                    print(f"Auto-selected boundary type: {boundary_type}")
                break
        else:
            selected_boundaries = boundaries

    # Sort by position
    selected_boundaries.sort(key=lambda b: b.position)

    # Determine chunk split points
    chunks = []
    lines = text.split('\n')
    current_start = 0
    current_start_line = 1

    for i, boundary in enumerate(selected_boundaries):
        # Calculate size if we split here
        chunk_size = boundary.position - current_start

        # Split if we exceed max_size (or it's the last boundary and we need to split)
        if chunk_size >= max_size or i == len(selected_boundaries) - 1:
            # Get chunk text
            chunk_text = text[current_start:boundary.position].strip()

            if chunk_text:  # Only add non-empty chunks
                metadata = {
                    'chunk_index': len(chunks),
                    'total_chunks': -1,  # Will update later
                    'boundary_type': boundary.type,
                    'starts_at_line': current_start_line,
                    'ends_at_line': boundary.line_number - 1,
                    'size': len(chunk_text)
                }
                chunks.append((chunk_text, metadata))

                if verbose:
                    print(f"Chunk {len(chunks)}: lines {current_start_line}-{boundary.line_number-1}, "
                          f"size {len(chunk_text)} bytes")

            # Update start position for next chunk
            current_start = boundary.position
            current_start_line = boundary.line_number

    # Add final chunk (from last boundary to end)
    final_chunk = text[current_start:].strip()
    if final_chunk:
        metadata = {
            'chunk_index': len(chunks),
            'total_chunks': -1,  # Will update later
            'boundary_type': selected_boundaries[-1].type if selected_boundaries else 'none',
            'starts_at_line': current_start_line,
            'ends_at_line': len(lines),
            'size': len(final_chunk)
        }
        chunks.append((final_chunk, metadata))

        if verbose:
            print(f"Final chunk {len(chunks)}: lines {current_start_line}-{len(lines)}, "
                  f"size {len(final_chunk)} bytes")

    # Update total_chunks in all metadata
    total = len(chunks)
    for _, metadata in chunks:
        metadata['total_chunks'] = total

    if verbose:
        print(f"\nTotal chunks: {total}")
        total_size = sum(len(chunk) for chunk, _ in chunks)
        print(f"Total size: {total_size} bytes")

    return chunks


def estimate_chunk_count(file_path: str, max_size: int = 200000) -> Tuple[int, str]:
    """Estimate how many chunks a file would be split into.

    Args:
        file_path: Path to the file
        max_size: Maximum chunk size in bytes

    Returns:
        Tuple of (estimated_chunks: int, boundary_type: str)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        boundaries = detect_structure_boundaries(text)

        if not boundaries:
            return 1, 'none'

        # Find most common boundary type
        from collections import Counter
        boundary_counts = Counter(b.type for b in boundaries)
        most_common_type = boundary_counts.most_common(1)[0][0]

        # Estimate chunks based on file size and boundary count
        file_size = len(text)
        boundaries_of_type = [b for b in boundaries if b.type == most_common_type]

        if not boundaries_of_type:
            return 1, 'none'

        # Rough estimate: file_size / max_size, bounded by boundary count
        estimated = max(1, min(len(boundaries_of_type), (file_size // max_size) + 1))

        return estimated, most_common_type

    except Exception as e:
        return 1, f'error: {e}'
