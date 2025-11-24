#!/usr/bin/env python3
"""
Devanagari Diff Tool

Compare Devanagari text between two files and show character-level differences.
This script extracts ONLY Devanagari characters from both files (ignoring markdown,
YAML frontmatter, etc.) and shows a colored diff with three colors:
  - RED background: text deleted from file1
  - GREEN background: text inserted in file2
  - YELLOW background: text replaced/changed

Both Devanagari and Harvard-Kyoto transliteration are shown for each difference.

Usage:
    python devanagari_diff.py <file1> <file2>
    python devanagari_diff.py <file1> <file2> -c 60 -m 20
"""

import argparse
import sys
from pathlib import Path

from grantha_converter.devanagari_extractor import (
    extract_devanagari,
    clean_text_for_devanagari_comparison,
)
from grantha_converter.visual_diff import print_visual_diff


def main():
    parser = argparse.ArgumentParser(
        description="Compare Devanagari text between two files (extracts only Devanagari characters)"
    )
    parser.add_argument("file1", help="First file to compare")
    parser.add_argument("file2", help="Second file to compare")
    parser.add_argument(
        "--context",
        "-c",
        type=int,
        default=40,
        help="Number of characters to show before/after each difference (default: 40)",
    )
    parser.add_argument(
        "--max-diffs",
        "-m",
        type=int,
        default=10,
        help="Maximum number of differences to show (default: 10)",
    )
    parser.add_argument(
        "--output-style",
        type=str,
        choices=["rich", "colorama"],
        default="colorama",
        help="Output style for the diff (default: colorama)",
    )
    parser.add_argument(
        "--transliteration-scheme",
        type=str,
        default="HK",
        help="Transliteration scheme to use (default: HK)",
    )

    args = parser.parse_args()

    # Check if files exist
    file1_path = Path(args.file1)
    file2_path = Path(args.file2)

    if not file1_path.exists():
        print(f"Error: File not found: {args.file1}", file=sys.stderr)
        sys.exit(1)

    if not file2_path.exists():
        print(f"Error: File not found: {args.file2}", file=sys.stderr)
        sys.exit(1)

    # Read files
    try:
        with open(file1_path, "r", encoding="utf-8") as f:
            full_text1 = f.read()
    except Exception as e:
        print(f"Error reading {args.file1}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file2_path, "r", encoding="utf-8") as f:
            full_text2 = f.read()
    except Exception as e:
        print(f"Error reading {args.file2}: {e}", file=sys.stderr)
        sys.exit(1)

    # Clean text first (remove YAML, HTML comments, bold markers)
    # Then extract ONLY Devanagari characters
    cleaned_text1 = clean_text_for_devanagari_comparison(full_text1)
    cleaned_text2 = clean_text_for_devanagari_comparison(full_text2)
    devanagari1 = extract_devanagari(cleaned_text1)
    devanagari2 = extract_devanagari(cleaned_text2)

    # Show info about extraction
    print("\n📊 Extracted Devanagari characters:")
    print(f"   {file1_path.name}: {len(devanagari1)} characters")
    print(f"   {file2_path.name}: {len(devanagari2)} characters")

    # Show colored diff with transliteration
    print_visual_diff(
        devanagari1,
        devanagari2,
        context_chars=args.context,
        max_diffs=args.max_diffs,
        output_style=args.output_style,
        transliteration_scheme=args.transliteration_scheme,
    )

if __name__ == "__main__":
    main()
