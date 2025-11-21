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

import yaml
from grantha_converter.devanagari_extractor import extract_devanagari
from grantha_converter.visual_diff import print_visual_diff


def _remove_yaml_header(input: str) -> str:
    """
    Parses the YAML header using the yaml library and returns
    the cleaned body content (as a string).
    """
    # Split the string by the '---' delimiter. This is a simple, effective
    # way to separate the components, though it's less robust than pure parsing.
    parts = input.split("---", 2)

    # Check for the expected structure: ['\n', yaml_header, body_content]
    if len(parts) < 3 or parts[0].strip() != "":
        # If no standard YAML front matter is found, assume no header.
        return input

    # 1. Extract the header string (the middle part)
    header_string = parts[1].strip()

    # 2. Extract the body content (the last part)
    body_content = parts[2].lstrip("\n")  # lstrip to clean up initial newlines

    # 3. Use yaml.safe_load to parse the header data
    try:
        header_data = yaml.safe_load(header_string)
        # Ensure header_data is a dictionary, as expected for a front matter
        if isinstance(header_data, dict):
            return body_content
        else:
            # Handle cases where the header is empty or malformed but still delimited
            return input  # Return original content if header isn't a dict

    except yaml.YAMLError as e:
        print(f"Error parsing YAML header: {e}")
        return input


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

    # Extract ONLY Devanagari characters (ignoring markdown, YAML, etc.)
    devanagari1 = extract_devanagari(_remove_yaml_header(full_text1))
    devanagari2 = extract_devanagari(_remove_yaml_header(full_text2))

    # Show info about extraction
    print(f"\n📊 Extracted Devanagari characters:")
    print(f"   {file1_path.name}: {len(devanagari1)} characters")
    print(f"   {file2_path.name}: {len(devanagari2)} characters")

    # Show colored diff with transliteration
    print_visual_diff(
        devanagari1,
        devanagari2,
        context_chars=args.context,
        max_diffs=args.max_diffs,
    )


if __name__ == "__main__":
    main()
