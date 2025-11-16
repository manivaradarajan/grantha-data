"""Smart sampling utilities for large text files.

Provides functions for creating representative samples of large text files
to fit within API token limits while preserving structural information.
"""

from typing import Tuple


def create_smart_sample(text: str, max_size: int = 500000) -> Tuple[str, bool]:
    """Create smart sample for files exceeding max_size.

    For large files, creates a representative sample containing:
    - First 100KB (includes title, initial structure, early content)
    - Middle 50KB (captures mid-document patterns)
    - Last 50KB (includes conclusion markers, final structure)

    Args:
        text: The full text content.
        max_size: Maximum size in bytes before sampling (default: 500KB).

    Returns:
        A tuple of (sample_text, was_sampled):
            - sample_text: Either full text or sampled version
            - was_sampled: True if sampling was applied, False if full text returned
    """
    text_size = len(text)

    if text_size <= max_size:
        return text, False

    # Sample sizes
    first_chunk = 102400  # 100KB
    middle_chunk = 51200  # 50KB
    last_chunk = 51200  # 50KB

    # Calculate middle position
    middle_start = (text_size - middle_chunk) // 2
    middle_end = middle_start + middle_chunk

    # Calculate last chunk position
    last_start = max(0, text_size - last_chunk)

    # Create sample with clear markers
    sample_parts = [
        text[:first_chunk],
        "\n\n--- SAMPLE CONTINUES (MIDDLE SECTION) ---\n\n",
        text[middle_start:middle_end],
        "\n\n--- SAMPLE CONTINUES (END SECTION) ---\n\n",
        text[last_start:],
    ]

    sample = "".join(sample_parts)
    return sample, True


def create_custom_sample(
    text: str,
    max_size: int,
    first_bytes: int,
    middle_bytes: int,
    last_bytes: int,
) -> Tuple[str, bool]:
    """Create custom sample with specified chunk sizes.

    Provides fine-grained control over sampling strategy by allowing custom
    chunk sizes for each section.

    Args:
        text: The full text content.
        max_size: Maximum size in bytes before sampling.
        first_bytes: Bytes to sample from beginning.
        middle_bytes: Bytes to sample from middle.
        last_bytes: Bytes to sample from end.

    Returns:
        A tuple of (sample_text, was_sampled):
            - sample_text: Either full text or sampled version
            - was_sampled: True if sampling was applied, False if full text returned

    Raises:
        ValueError: If chunk sizes are negative or total exceeds max_size.
    """
    if first_bytes < 0 or middle_bytes < 0 or last_bytes < 0:
        raise ValueError("Chunk sizes must be non-negative")

    total_sample_size = first_bytes + middle_bytes + last_bytes
    if total_sample_size > max_size:
        raise ValueError(
            f"Total sample size ({total_sample_size}) exceeds max_size ({max_size})"
        )

    text_size = len(text)

    if text_size <= max_size:
        return text, False

    # Calculate middle position
    middle_start = (text_size - middle_bytes) // 2
    middle_end = middle_start + middle_bytes

    # Calculate last chunk position
    last_start = max(0, text_size - last_bytes)

    # Create sample with clear markers
    sample_parts = [
        text[:first_bytes],
        "\n\n--- SAMPLE CONTINUES (MIDDLE SECTION) ---\n\n",
        text[middle_start:middle_end],
        "\n\n--- SAMPLE CONTINUES (END SECTION) ---\n\n",
        text[last_start:],
    ]

    sample = "".join(sample_parts)
    return sample, True
