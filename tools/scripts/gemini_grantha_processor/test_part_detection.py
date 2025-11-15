#!/usr/bin/env python3
"""
Test part number detection from filenames.
"""

import sys
from pathlib import Path

# Add script directory to path
sys.path.insert(0, str(Path(__file__).parent))

from convert_meghamala import extract_part_number_from_filename


def test_part_detection():
    """Test various filename patterns."""

    test_cases = [
        # (filename, expected_part_num)
        ("03-01.md", 1),
        ("03-02.md", 2),
        ("04-01.md", 1),
        ("brihadaranyaka-03.md", 3),
        ("chandogya-05.md", 5),
        ("01.md", 1),
        ("08.md", 8),
        ("part-1.md", 1),
        ("part-3.md", 3),
        ("part_2.md", 2),
        ("kenopanishad.md", 1),  # Default
        ("isavasya.md", 1),  # Default
        ("mANDUkyopaniSat.md", 1),  # Default
    ]

    print("Testing part number detection:")
    print("-" * 60)

    all_passed = True
    for filename, expected in test_cases:
        detected = extract_part_number_from_filename(filename)
        status = "✓" if detected == expected else "✗"

        if detected != expected:
            all_passed = False

        print(f"{status} {filename:30s} → {detected:2d} (expected {expected})")

    print("-" * 60)
    if all_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == '__main__':
    sys.exit(test_part_detection())
