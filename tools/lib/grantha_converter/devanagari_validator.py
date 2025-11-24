"""
Devanagari text validator to ensure zero text loss during conversion.

This module extracts Devanagari Unicode characters from text and validates
that no characters are lost during markdown format conversion.
"""

import re
from typing import Tuple


def extract_devanagari(text: str) -> str:
    """
    Extract all Devanagari Unicode characters from text.

    Devanagari block: U+0900 to U+097F
    Additional Devanagari extensions: U+A8E0 to U+A8FF

    Args:
        text: Input text that may contain Devanagari characters

    Returns:
        String containing only Devanagari characters in order
    """
    # Match Devanagari Unicode ranges
    devanagari_pattern = r'[\u0900-\u097F\uA8E0-\uA8FF]+'
    matches = re.findall(devanagari_pattern, text)
    return ''.join(matches)


def normalize_devanagari(text: str) -> str:
    """
    Normalize Devanagari text for comparison by removing:
    - Whitespace (spaces, tabs, newlines)
    - Zero-width characters (ZWNJ, ZWJ, zero-width space)
    - Common punctuation marks (।, ॥, ।।, digits like १ २ ३)

    This allows formatting changes while detecting actual text modifications.

    Args:
        text: Devanagari text to normalize

    Returns:
        Normalized text for comparison
    """
    # Remove whitespace
    normalized = re.sub(r'\s+', '', text)

    # Remove zero-width characters
    normalized = normalized.replace('\u200B', '')  # Zero-width space
    normalized = normalized.replace('\u200C', '')  # ZWNJ
    normalized = normalized.replace('\u200D', '')  # ZWJ

    # Remove Devanagari punctuation and digits
    normalized = normalized.replace('।', '')  # Danda
    normalized = normalized.replace('॥', '')  # Double danda

    # Remove Devanagari digits (०-९)
    normalized = re.sub(r'[\u0966-\u096F]', '', normalized)

    return normalized


def validate_devanagari_preservation(source_text: str, output_text: str) -> Tuple[bool, str]:
    """
    Validate that all Devanagari text from source is preserved in output.

    Args:
        source_text: Original text (e.g., meghamala markdown)
        output_text: Converted text (e.g., structured Grantha markdown)

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if all Devanagari text preserved, False otherwise
        - error_message: Empty string if valid, detailed error message otherwise
    """
    # Extract Devanagari from both texts
    source_devanagari = extract_devanagari(source_text)
    output_devanagari = extract_devanagari(output_text)

    # Normalize for comparison
    source_normalized = normalize_devanagari(source_devanagari)
    output_normalized = normalize_devanagari(output_devanagari)

    # Compare
    if source_normalized == output_normalized:
        return True, ""

    # Build detailed error message
    error_lines = [
        "❌ Devanagari text loss detected!",
        f"Source length: {len(source_normalized)} characters",
        f"Output length: {len(output_normalized)} characters",
        f"Difference: {len(source_normalized) - len(output_normalized)} characters",
        ""
    ]

    # Find first difference
    min_len = min(len(source_normalized), len(output_normalized))
    first_diff_idx = None
    for i in range(min_len):
        if source_normalized[i] != output_normalized[i]:
            first_diff_idx = i
            break

    if first_diff_idx is not None:
        context_start = max(0, first_diff_idx - 20)
        context_end = min(len(source_normalized), first_diff_idx + 20)
        error_lines.extend([
            f"First difference at position {first_diff_idx}:",
            f"Source context: ...{source_normalized[context_start:context_end]}...",
            f"Output context: ...{output_normalized[context_start:context_end]}...",
        ])
    elif len(source_normalized) > len(output_normalized):
        error_lines.append("Output is truncated or missing text at the end")
        missing_start = len(output_normalized)
        error_lines.append(f"Missing text starts: {source_normalized[missing_start:missing_start+50]}...")
    else:
        error_lines.append("Output has extra text at the end")
        extra_start = len(source_normalized)
        error_lines.append(f"Extra text starts: {output_normalized[extra_start:extra_start+50]}...")

    return False, "\n".join(error_lines)


def get_devanagari_stats(text: str) -> dict:
    """
    Get statistics about Devanagari content in text.

    Args:
        text: Input text

    Returns:
        Dictionary with statistics:
        - total_chars: Total Devanagari characters
        - unique_chars: Number of unique Devanagari characters
        - char_list: List of unique characters
    """
    devanagari = extract_devanagari(text)
    normalized = normalize_devanagari(devanagari)
    unique_chars = sorted(set(normalized))

    return {
        'total_chars': len(normalized),
        'unique_chars': len(unique_chars),
        'char_list': unique_chars
    }


def validate_file_conversion(source_file: str, output_file: str) -> bool:
    """
    Validate that Devanagari text is preserved between two files.

    Args:
        source_file: Path to source markdown file
        output_file: Path to output markdown file

    Returns:
        True if validation passes, False otherwise

    Raises:
        FileNotFoundError: If either file doesn't exist
        ValueError: If validation fails (with detailed error message)
    """
    with open(source_file, 'r', encoding='utf-8') as f:
        source_text = f.read()

    with open(output_file, 'r', encoding='utf-8') as f:
        output_text = f.read()

    is_valid, error_msg = validate_devanagari_preservation(source_text, output_text)

    if not is_valid:
        raise ValueError(f"Validation failed:\n{error_msg}")

    return True
