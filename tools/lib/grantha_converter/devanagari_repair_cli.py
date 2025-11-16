#!/usr/bin/env python3
"""Command-line interface for repairing Devanagari mismatches.

This tool repairs small Devanagari differences between input and output files
by performing word-by-word comparison and correction.
"""

import argparse
import sys
from pathlib import Path

from grantha_converter.devanagari_repair import extract_devanagari, repair_file
from grantha_converter.hasher import hash_text


def recalculate_hash(file_path: str, verbose: bool = False) -> bool:
    """Recalculate and update the validation hash in a file's frontmatter.

    Args:
        file_path: Path to the file
        verbose: Print status messages

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract body (skip frontmatter)
        frontmatter_end = content.find("---\n\n", 4)
        if frontmatter_end == -1:
            if verbose:
                print("Warning: Could not find end of frontmatter", file=sys.stderr)
            return False

        body = content[frontmatter_end + 5:]

        # Calculate hash
        validation_hash = hash_text(body)

        # Replace in frontmatter (match both formats)
        # Format 1: validation_hash: existing_hash
        # Format 2: validation_hash: TO_BE_CALCULATED
        content = re.sub(
            r'validation_hash:\s*\S+',
            f'validation_hash: {validation_hash}',
            content,
            count=1
        )

        # Write back
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        if verbose:
            print(f"Updated validation hash: {validation_hash[:16]}...")

        return True

    except Exception as e:
        print(f"Error recalculating hash: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Repair Devanagari mismatches between input and output files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Repair a single file
  %(prog)s -i input.md -o output.md

  # Repair with verbose output
  %(prog)s -i input.md -o output.md -v

  # Dry run - see what would be changed without modifying files
  %(prog)s -i input.md -o output.md --dry-run

  # Repair and recalculate validation hash
  %(prog)s -i input.md -o output.md --recalculate-hash

  # Custom maximum difference threshold
  %(prog)s -i input.md -o output.md --max-diff 1000

  # Don't skip frontmatter in output
  %(prog)s -i input.md -o output.md --no-skip-frontmatter
        """
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Input file (source of truth for Devanagari)"
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output file to repair"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed repair information"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be repaired without modifying files"
    )
    parser.add_argument(
        "--max-diff",
        type=int,
        default=500,
        help="Maximum character difference to attempt repair (default: 500)"
    )
    parser.add_argument(
        "--no-skip-frontmatter",
        action="store_true",
        help="Don't skip YAML frontmatter in output (default: skip it)"
    )
    parser.add_argument(
        "--recalculate-hash",
        action="store_true",
        help="Recalculate validation hash after successful repair"
    )

    args = parser.parse_args()

    # Check files exist
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    if not output_path.exists():
        print(f"Error: Output file not found: {args.output}", file=sys.stderr)
        return 1

    # Show initial status
    print(f"Input file:  {args.input}")
    print(f"Output file: {args.output}")

    if args.verbose:
        # Show Devanagari character counts
        with open(args.input, "r", encoding="utf-8") as f:
            input_text = f.read()
        with open(args.output, "r", encoding="utf-8") as f:
            output_text = f.read()

        input_devanagari = extract_devanagari(input_text)
        output_devanagari = extract_devanagari(output_text)

        print(f"\nDevanagari character count:")
        print(f"  Input:  {len(input_devanagari)}")
        print(f"  Output: {len(output_devanagari)}")
        print(f"  Diff:   {abs(len(input_devanagari) - len(output_devanagari))}")

    print()

    # Attempt repair
    success, message = repair_file(
        input_file=str(input_path),
        output_file=str(output_path),
        max_diff_size=args.max_diff,
        skip_frontmatter=not args.no_skip_frontmatter,
        verbose=args.verbose,
        dry_run=args.dry_run
    )

    # Print result
    print(message)

    if success and not args.dry_run and args.recalculate_hash:
        print("\nRecalculating validation hash...")
        # Import re here since we need it
        import re
        if recalculate_hash(str(output_path), verbose=args.verbose):
            print("✓ Validation hash updated")
        else:
            print("Warning: Could not update validation hash", file=sys.stderr)

    if success:
        print("\n✅ Repair successful!")
        return 0
    else:
        print("\n❌ Repair failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
