"""Reference string parsing utilities.

This module provides utilities for parsing and validating passage references.
"""

from typing import List, Tuple

from grantha_data.exceptions import InvalidRefError


def parse_ref(ref: str) -> List[int]:
    """Parses hierarchical reference into integer components.

    Args:
        ref: Reference string like "1.2.3".

    Returns:
        List of integers [1, 2, 3].

    Raises:
        InvalidRefError: If ref format is invalid.
    """
    _validate_ref_not_empty(ref)
    return _split_and_convert_to_ints(ref)


def _validate_ref_not_empty(ref: str) -> None:
    """Validates reference is not empty."""
    if not ref or not ref.strip():
        raise InvalidRefError("Reference cannot be empty")


def _split_and_convert_to_ints(ref: str) -> List[int]:
    """Splits ref by dots and converts to integers."""
    try:
        return [int(part) for part in ref.split('.')]
    except ValueError as e:
        raise InvalidRefError(
            f"Invalid reference format: {ref}"
        ) from e


def is_ref_in_range(
    ref: str,
    range_start: str,
    range_end: str
) -> bool:
    """Checks if ref falls within range.

    Args:
        ref: Reference to check.
        range_start: Start of range (inclusive).
        range_end: End of range (inclusive).

    Returns:
        True if ref is in range.

    Raises:
        InvalidRefError: If any ref has invalid format.
    """
    ref_parts = parse_ref(ref)
    start_parts = parse_ref(range_start)
    end_parts = parse_ref(range_end)
    return start_parts <= ref_parts <= end_parts


def parse_ref_range(ref_range: str) -> Tuple[str, str]:
    """Parses reference range like "1.1.1-5".

    Args:
        ref_range: Range string.

    Returns:
        Tuple of (start_ref, end_ref).

    Raises:
        InvalidRefError: If range format is invalid.
    """
    if '-' not in ref_range:
        return (ref_range, ref_range)

    return _split_range_string(ref_range)


def _split_range_string(ref_range: str) -> Tuple[str, str]:
    """Splits range string into start and end."""
    parts = ref_range.split('-')
    if len(parts) != 2:
        raise InvalidRefError(f"Invalid range format: {ref_range}")

    return (parts[0].strip(), parts[1].strip())


def compare_refs(ref1: str, ref2: str) -> int:
    """Compares two references hierarchically.

    Args:
        ref1: First reference.
        ref2: Second reference.

    Returns:
        -1 if ref1 < ref2, 0 if equal, 1 if ref1 > ref2.

    Raises:
        InvalidRefError: If either ref has invalid format.
    """
    parts1 = parse_ref(ref1)
    parts2 = parse_ref(ref2)

    if parts1 < parts2:
        return -1
    elif parts1 > parts2:
        return 1
    else:
        return 0
