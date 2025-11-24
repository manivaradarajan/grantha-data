#!/usr/bin/env python3
"""
Devanagari Repair Tool (Surgical, Out-of-Place)

This script repairs the Devanagari text in a target file (fileB) based on a
source-of-truth file (fileA), producing a new, repaired file. Both input
files are treated as read-only.

The script first extracts only the Devanagari text from both files, then
computes a diff. This diff is then surgically applied back to the full
content of fileB.
"""

import argparse
import sys
from pathlib import Path
import shutil
from grantha_converter.devanagari_repair import repair_file

def main():
    parser = argparse.ArgumentParser(
        description="Surgically repair Devanagari text in a file based on a source-of-truth file."
    )
    parser.add_argument("fileA", help="The source-of-truth file (ReadOnly).")
    parser.add_argument("fileB", help="The file to repair (ReadOnly).")
    parser.add_argument(
        "--output", "-o",
        help="Optional: Specify the output file path. Defaults to '[fileB].repaired'."
    )
    parser.add_argument(
        "--min-sim", type=float, default=80.0,
        help="Abort if similarity of extracted Devanagari is below this ratio (default: 80.0)."
    )
    parser.add_argument(
        "--max-changes", type=int, default=2000,
        help="Abort if more than this many Devanagari characters are changed (default: 2000)."
    )
    parser.add_argument(
        "--keep-frontmatter", action="store_true",
        help="Preserve frontmatter from fileB, repairing only the body."
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print detailed information about the repair process."
    )

    args = parser.parse_args()

    # --- 1. Validate input files ---
    fileA_path = Path(args.fileA)
    fileB_path = Path(args.fileB)

    if not fileA_path.exists():
        print(f"Error: Source file not found: {args.fileA}", file=sys.stderr)
        sys.exit(1)
    if not fileB_path.exists():
        print(f"Error: File to repair not found: {args.fileB}", file=sys.stderr)
        sys.exit(1)

    # --- 2. Determine output path and create a temporary copy of fileB ---
    output_path = Path(args.output) if args.output else fileB_path.with_suffix(fileB_path.suffix + ".repaired")

    try:
        shutil.copy2(fileB_path, output_path)
    except Exception as e:
        print(f"Error: Could not create a copy for the repaired file: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"🔧 Repairing '{fileB_path.name}' based on '{fileA_path.name}'...")
    print(f"   - Output will be written to: '{output_path.name}'")

    # --- 3. Call the surgical repair utility ---
    repair_successful, repair_message = repair_file(
        input_file=str(fileA_path),
        output_file=str(output_path),
        max_diff_size=args.max_changes,
        skip_frontmatter=args.keep_frontmatter,
        min_similarity=args.min_sim / 100.0, # repair_file expects a 0.0-1.0 float
        verbose=args.verbose,
        dry_run=False,
        create_backup=False,  # We already created a copy
    )

    # --- 4. Report result ---
    if repair_successful:
        print("\n✅ Repair successful.")
        print(f"   - {repair_message}")
        print(f"   - Repaired file saved to: {output_path}")
    else:
        print("\n❌ Repair failed.")
        print(f"   - {repair_message}")
        # Clean up the partially modified file on failure
        if output_path.exists():
            output_path.unlink()
        print(f"   - Incomplete output file '{output_path.name}' has been removed.")

if __name__ == "__main__":
    main()
