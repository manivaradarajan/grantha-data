#!/usr/bin/env python3
"""
Standalone tool to show colored Devanagari diff between two files.

Usage:
    python devanagari_diff.py file1.md file2.md
    python devanagari_diff.py file1.md file2.md --max-diff-lines 50
    python devanagari_diff.py file1.md file2.md --extract-only
"""

import sys
import argparse
from pathlib import Path
import os
from datetime import datetime

# Import from grantha_converter for Devanagari extraction
try:
    from grantha_converter.devanagari_repair import extract_devanagari
    from grantha_converter.diff_utils import show_devanagari_diff, show_transliteration_diff
except ImportError as e:
    print(f"Error: Required grantha_converter modules not found: {e}", file=sys.stderr)
    print("Install with: pip install -e .", file=sys.stderr)
    sys.exit(1)

LOGS_DIR = Path(__file__).parent / "logs"
_current_log_dir = None

def create_log_directory() -> Path:
    global _current_log_dir
    if _current_log_dir is not None:
        return _current_log_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = LOGS_DIR / f"devanagari_diff_run_{timestamp}"
    log_dir.mkdir(parents=True, exist_ok=True)
    _current_log_dir = log_dir
    print(f"📁 Logging to: {log_dir}")
    return log_dir

def save_to_log(filename: str, content: str, subdir: str = None):
    log_dir = create_log_directory()
    if subdir:
        save_dir = log_dir / subdir
        save_dir.mkdir(parents=True, exist_ok=True)
    else:
        save_dir = log_dir
    file_path = save_dir / filename
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  💾 Saved: {file_path.relative_to(LOGS_DIR)}")
    except Exception as e:
        print(f"  ⚠️  Warning: Could not save log file {filename}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Show colored diff of Devanagari text between two files",
        epilog="""
Examples:
  # Compare two markdown files
  %(prog)s input.md output.md

  # Show more diff lines
  %(prog)s input.md output.md --max-diff-lines 100

  # Only extract and compare Devanagari (ignore markdown structure)
  %(prog)s input.md output.md --extract-only

  # Compare with context
  %(prog)s input.md output.md --context 5
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("file1", help="First file to compare")
    parser.add_argument("file2", help="Second file to compare")
    parser.add_argument(
        "--max-diff-lines",
        type=int,
        default=30,
        help="Maximum number of differences to show (default: 30)",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=3,
        help="Number of context lines around each change (default: 3)",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Extract only Devanagari characters before comparing (ignores markdown/formatting)",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Show only statistics, not the diff",
    )
    parser.add_argument(
        "--transliterate-diff",
        action="store_true",
        help="Also show a Harvard-Kyoto transliteration diff",
    )

    args = parser.parse_args()

    # Read files
    file1_path = Path(args.file1)
    file2_path = Path(args.file2)

    if not file1_path.exists():
        print(f"Error: File not found: {args.file1}", file=sys.stderr)
        return 1

    if not file2_path.exists():
        print(f"Error: File not found: {args.file2}", file=sys.stderr)
        return 1

    with open(file1_path, "r", encoding="utf-8") as f:
        text1 = f.read()

    with open(file2_path, "r", encoding="utf-8") as f:
        text2 = f.read()

    # Extract Devanagari if requested
    if args.extract_only:
        print(f"📄 Extracting Devanagari from {file1_path.name}...")
        text1 = extract_devanagari(text1)
        print(f"   Found {len(text1)} Devanagari characters")

        print(f"📄 Extracting Devanagari from {file2_path.name}...")
        text2 = extract_devanagari(text2)
        print(f"   Found {len(text2)} Devanagari characters")
        print()

    # Show statistics
    print(f"📊 Comparison Statistics:")
    print(f"   File 1: {len(text1):,} characters ({file1_path.name})")
    print(f"   File 2: {len(text2):,} characters ({file2_path.name})")
    diff = abs(len(text1) - len(text2))
    print(f"   Difference: {diff:,} characters")
    print()

    if text1 == text2:
        print("✓ Files are identical!")
        return 0

    if args.stats_only:
        return 0

    # Show diff
    show_devanagari_diff(
        text1, text2, context_lines=args.context, max_diff_lines=args.max_diff_lines
    )

    if args.transliterate_diff:
        # For devanagari_diff tool, we don't have a chunk_num, so use 0 as a generic ID
        show_transliteration_diff(text1, text2, chunk_num=0, save_to_log_func=save_to_log)

    return 0


if __name__ == "__main__":
    sys.exit(main())
