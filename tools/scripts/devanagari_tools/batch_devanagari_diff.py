#!/usr/bin/env python3
"""
Batch Devanagari Diff Tool

Compare Devanagari content between pairs of input/output files and generate
a comprehensive text-editor-friendly diff log.

This script:
- Pairs input and output files lexically
- Extracts only Devanagari characters from both files
- Generates detailed character-level diffs
- Outputs to a timestamped log file (no ANSI color codes)
- Flags whitespace-only changes
- Highlights areas requiring manual review
- Optionally auto-stages files with zero diffs via git

Usage:
    python batch_devanagari_diff.py \\
      --input sources/upanishads/vishvas/chandogya/chandogya-with-rangaramanuja \\
      --output structured_md/upanishads/chandogya \\
      --auto-stage
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import diff_match_patch
from aksharamukha import transliterate
from grantha_converter.devanagari_extractor import (
    clean_text_for_devanagari_comparison,
    extract_devanagari,
)


def discover_and_pair_files(
    input_dir: Path, output_dir: Path
) -> List[Tuple[int, Path, Path]]:
    """
    Discover .md files in both directories and pair them lexically.

    Args:
        input_dir: Input directory path
        output_dir: Output directory path

    Returns:
        List of (file_num, input_path, output_path) tuples
        file_num is 1-based index for easy reference

    Excludes: PROVENANCE.yaml, _index.md, and other non-content files
    """
    # Find all .md files, excluding special files
    input_files = sorted(
        [
            f
            for f in input_dir.glob("*.md")
            if f.name not in ["PROVENANCE.md", "_index.md"]
        ]
    )
    output_files = sorted(
        [
            f
            for f in output_dir.glob("*.md")
            if f.name not in ["PROVENANCE.md", "_index.md"]
        ]
    )

    if len(input_files) != len(output_files):
        print(
            f"Warning: File count mismatch - {len(input_files)} input files, {len(output_files)} output files",
            file=sys.stderr,
        )

    # Pair files by lexical order with 1-based indexing
    pairs = [
        (i + 1, input_f, output_f)
        for i, (input_f, output_f) in enumerate(zip(input_files, output_files))
    ]

    return pairs


def is_whitespace_only(text: str) -> bool:
    """
    Check if text consists only of whitespace characters.

    Returns:
        True if only spaces, tabs, newlines, zero-width chars
    """
    return text.strip() == ""


def format_number(num: int) -> str:
    """Format number with thousands separator."""
    return f"{num:,}"


def calculate_position_range(diffs, diff_index, dmp):
    """Calculate character position range for a diff in the source text."""
    pos = 0
    for i in range(diff_index):
        op, text = diffs[i]
        if op != dmp.DIFF_INSERT:  # Count deletions and equals
            pos += len(text)
    op, text = diffs[diff_index]
    return pos, pos + len(text)


def format_diff_snippet(
    diffs, diff_index, dmp, context_chars, transliteration_scheme
):
    """
    Format a single diff with context for text editor display.

    Returns formatted string with markers like [DELETED: ...], [INSERTED: ...]
    """
    # Get the current diff
    op, text = diffs[diff_index]

    # Collect context before
    pre_context = ""
    if diff_index > 0:
        pre_op, pre_text = diffs[diff_index - 1]
        if pre_op == dmp.DIFF_EQUAL:
            pre_context = pre_text[-context_chars:]

    # Collect the diff snippet (may include consecutive diffs)
    diff_snippet = [(op, text)]
    j = diff_index + 1
    while j < len(diffs) and diffs[j][0] != dmp.DIFF_EQUAL:
        diff_snippet.append(diffs[j])
        j += 1

    # Collect context after
    post_context = ""
    if j < len(diffs):
        post_op, post_text = diffs[j]
        if post_op == dmp.DIFF_EQUAL:
            post_context = post_text[:context_chars]

    # Build text representation
    def format_snippet(snippet_diffs, include_markers=True):
        parts = []
        if pre_context:
            parts.append(f"...{pre_context}")

        for op, txt in snippet_diffs:
            if not include_markers:
                parts.append(txt)
            elif op == dmp.DIFF_DELETE:
                parts.append(f"[DELETED: {txt}]")
            elif op == dmp.DIFF_INSERT:
                parts.append(f"[INSERTED: {txt}]")
            else:
                parts.append(txt)

        if post_context:
            parts.append(f"{post_context}...")

        return "".join(parts)

    # Create formatted output
    context_line = format_snippet(diff_snippet, include_markers=True)

    # Build before/after views
    before_parts = []
    after_parts = []

    if pre_context:
        before_parts.append(f"...{pre_context}")
        after_parts.append(f"...{pre_context}")

    for op, txt in diff_snippet:
        if op == dmp.DIFF_DELETE:
            before_parts.append(txt)
        elif op == dmp.DIFF_INSERT:
            after_parts.append(txt)
        else:
            before_parts.append(txt)
            after_parts.append(txt)

    if post_context:
        before_parts.append(f"{post_context}...")
        after_parts.append(f"{post_context}...")

    before_text = "".join(before_parts)
    after_text = "".join(after_parts)

    # Transliterate
    try:
        before_hk = transliterate.process("Devanagari", transliteration_scheme, before_text)
        after_hk = transliterate.process("Devanagari", transliteration_scheme, after_text)
    except:
        before_hk = "[transliteration error]"
        after_hk = "[transliteration error]"

    # Determine diff type
    has_delete = any(op == dmp.DIFF_DELETE for op, _ in diff_snippet)
    has_insert = any(op == dmp.DIFF_INSERT for op, _ in diff_snippet)

    if has_delete and has_insert:
        diff_type = "[REPLACEMENT]"
    elif has_delete:
        diff_type = "[DELETION]"
    else:
        diff_type = "[INSERTION]"

    # Check if whitespace-only
    all_whitespace = all(
        is_whitespace_only(txt) for op, txt in diff_snippet if op != dmp.DIFF_EQUAL
    )

    return {
        "type": diff_type,
        "whitespace_only": all_whitespace,
        "context": context_line,
        "before": before_text,
        "after": after_text,
        "before_hk": before_hk,
        "after_hk": after_hk,
    }


def compare_files(
    input_path: Path,
    output_path: Path,
    context_chars: int,
    transliteration_scheme: str,
):
    """
    Compare two files and return diff information.

    Returns:
        Dictionary with comparison results
    """
    # Read files
    with open(input_path, "r", encoding="utf-8") as f:
        input_text = f.read()
    with open(output_path, "r", encoding="utf-8") as f:
        output_text = f.read()

    # Extract Devanagari
    input_cleaned = clean_text_for_devanagari_comparison(input_text)
    output_cleaned = clean_text_for_devanagari_comparison(output_text)
    input_devanagari = extract_devanagari(input_cleaned)
    output_devanagari = extract_devanagari(output_cleaned)

    # Compute diff
    dmp = diff_match_patch.diff_match_patch()
    diffs = dmp.diff_main(input_devanagari, output_devanagari)
    dmp.diff_cleanupSemantic(diffs)

    # Analyze diffs
    diff_details = []
    total_diffs = 0
    non_whitespace_diffs = 0
    whitespace_only_diffs = 0

    for i, (op, text) in enumerate(diffs):
        if op == dmp.DIFF_EQUAL:
            continue

        total_diffs += 1
        snippet_info = format_diff_snippet(
            diffs, i, dmp, context_chars, transliteration_scheme
        )

        if snippet_info["whitespace_only"]:
            whitespace_only_diffs += 1
        else:
            non_whitespace_diffs += 1

        diff_details.append(snippet_info)

    return {
        "input_chars": len(input_devanagari),
        "output_chars": len(output_devanagari),
        "total_diffs": total_diffs,
        "non_whitespace_diffs": non_whitespace_diffs,
        "whitespace_only_diffs": whitespace_only_diffs,
        "diff_details": diff_details,
    }


def auto_stage_file(file_path: Path) -> bool:
    """
    Run 'git add' on a file.

    Returns:
        True if successful, False otherwise
    """
    try:
        subprocess.run(
            ["git", "add", str(file_path)], check=True, capture_output=True, text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to git add {file_path}: {e}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("Warning: git command not found", file=sys.stderr)
        return False


def generate_report(
    file_pairs: List[Tuple[int, Path, Path]],
    results: List[dict],
    input_dir: Path,
    output_dir: Path,
    auto_stage: bool,
) -> str:
    """
    Generate comprehensive text report from comparison results.

    Returns:
        Formatted report as string
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    # Header
    lines.append("#" * 80)
    lines.append("DEVANAGARI DIFF BATCH REPORT")
    lines.append(f"Generated: {timestamp}")
    lines.append("#" * 80)
    lines.append("")
    lines.append(f"Input Directory:  {input_dir}")
    lines.append(f"Output Directory: {output_dir}")
    lines.append("")
    lines.append(f"Files Compared: {len(file_pairs)} pairs")
    lines.append("")

    # Summary statistics
    total_input_chars = sum(r["input_chars"] for r in results)
    total_output_chars = sum(r["output_chars"] for r in results)
    char_diff = total_output_chars - total_input_chars
    char_diff_pct = (
        (char_diff / total_input_chars * 100) if total_input_chars > 0 else 0
    )

    total_diffs = sum(r["total_diffs"] for r in results)
    total_non_ws = sum(r["non_whitespace_diffs"] for r in results)
    total_ws = sum(r["whitespace_only_diffs"] for r in results)

    perfect_matches = sum(1 for r in results if r["total_diffs"] == 0)
    files_needing_review = len(file_pairs) - perfect_matches

    auto_staged_count = 0
    if auto_stage:
        for (_, _, output_path), result in zip(file_pairs, results):
            if result["total_diffs"] == 0:
                if auto_stage_file(output_path):
                    auto_staged_count += 1

    lines.append("=" * 80)
    lines.append("SUMMARY STATISTICS")
    lines.append("=" * 80)
    lines.append(f"Total Input Devanagari Characters:   {format_number(total_input_chars)}")
    lines.append(f"Total Output Devanagari Characters:  {format_number(total_output_chars)}")
    lines.append(f"Character Difference:                {char_diff:+,} ({char_diff_pct:+.2f}%)")
    lines.append("")
    lines.append(f"Total Differences Found:             {total_diffs}")
    lines.append(f"  - Non-whitespace changes:          {total_non_ws}")
    lines.append(f"  - Whitespace-only changes:         {total_ws}")
    lines.append("")
    lines.append(f"Perfect Matches (0 diffs):           {perfect_matches} files")
    lines.append(f"Files Needing Review:                {files_needing_review} files")
    if auto_stage:
        lines.append(f"Auto-staged (perfect matches):       {auto_staged_count} files")
    lines.append("")

    # File-by-file details
    for (file_num, input_path, output_path), result in zip(file_pairs, results):
        lines.append("=" * 80)
        lines.append(f"FILE PAIR {file_num}/{len(file_pairs)}")
        lines.append("=" * 80)
        lines.append(f"Input  #{file_num}: {input_path.name}")
        lines.append(f"Output #{file_num}: {output_path.name}")
        lines.append("")
        lines.append("Extracted Devanagari:")
        lines.append(f"  Input:  {format_number(result['input_chars'])} characters")
        lines.append(f"  Output: {format_number(result['output_chars'])} characters")
        delta = result["output_chars"] - result["input_chars"]
        lines.append(f"  Delta:  {delta:+,} characters")
        lines.append("")
        lines.append(f"Differences Found: {result['total_diffs']}")
        lines.append(f"  - Non-whitespace: {result['non_whitespace_diffs']}")
        lines.append(f"  - Whitespace-only: {result['whitespace_only_diffs']}")

        if result["total_diffs"] == 0:
            staged_msg = " (auto-staged)" if auto_stage else ""
            lines.append(f"Auto-staged: YES{staged_msg}")
        else:
            lines.append("Auto-staged: NO (has differences)")

        lines.append("")

        # Individual diffs
        for diff_num, diff_info in enumerate(result["diff_details"], 1):
            lines.append("-" * 80)
            lines.append(f"DIFF {diff_num}/{result['total_diffs']}")
            lines.append("-" * 80)
            lines.append(f"Type: {diff_info['type']}")
            lines.append(f"Whitespace-only: {'YES' if diff_info['whitespace_only'] else 'NO'}")
            lines.append("")
            lines.append("Context:")
            lines.append(diff_info["context"])
            lines.append("")
            lines.append("Devanagari:")
            if diff_info["before"]:
                lines.append(f"  Before: {diff_info['before']}")
            if diff_info["after"]:
                lines.append(f"  After:  {diff_info['after']}")
            lines.append("")
            lines.append("Harvard-Kyoto:")
            if diff_info["before_hk"]:
                lines.append(f"  Before: {diff_info['before_hk']}")
            if diff_info["after_hk"]:
                lines.append(f"  After:  {diff_info['after_hk']}")
            lines.append("")

            if not diff_info["whitespace_only"]:
                lines.append("⚠ REVIEW REQUIRED: Significant text change detected (non-whitespace)")
            else:
                lines.append("⚠ Note: Whitespace-only change (likely formatting)")
            lines.append("")

    # Priority list
    priority_files = sorted(
        [
            (file_num, input_path, output_path, result["non_whitespace_diffs"])
            for (file_num, input_path, output_path), result in zip(file_pairs, results)
            if result["non_whitespace_diffs"] > 0
        ],
        key=lambda x: x[3],
        reverse=True,
    )

    if priority_files:
        lines.append("=" * 80)
        lines.append("FILES REQUIRING IMMEDIATE ATTENTION")
        lines.append("=" * 80)
        for rank, (file_num, input_path, output_path, non_ws_count) in enumerate(
            priority_files, 1
        ):
            lines.append(
                f"{rank}. File pair {file_num}/{len(file_pairs)} "
                f"(Input #{file_num}, Output #{file_num}): "
                f"{non_ws_count} non-whitespace differences"
            )
        lines.append("")

    # Footer
    lines.append("#" * 80)
    lines.append("END OF REPORT")
    lines.append("#" * 80)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Batch compare Devanagari text between input and output file pairs"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Input directory containing source .md files",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Output directory containing converted .md files",
    )
    parser.add_argument(
        "--context",
        "-c",
        type=int,
        default=60,
        help="Number of characters to show before/after each difference (default: 60)",
    )
    parser.add_argument(
        "--transliteration",
        "-t",
        type=str,
        default="HK",
        help="Transliteration scheme to use (default: HK)",
    )
    parser.add_argument(
        "--auto-stage",
        action="store_true",
        help="Automatically run 'git add' on output files with zero diffs",
    )

    args = parser.parse_args()

    # Validate directories
    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        print(f"Error: Input directory not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not output_dir.exists():
        print(f"Error: Output directory not found: {args.output}", file=sys.stderr)
        sys.exit(1)

    # Discover and pair files
    print(f"Discovering files in {input_dir}...")
    print(f"                  and {output_dir}...")
    file_pairs = discover_and_pair_files(input_dir, output_dir)

    if not file_pairs:
        print("Error: No file pairs found to compare", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(file_pairs)} file pairs to compare")
    print()

    # Compare all file pairs
    results = []
    for file_num, input_path, output_path in file_pairs:
        print(f"Comparing pair {file_num}/{len(file_pairs)}: {input_path.name} vs {output_path.name}...")
        try:
            result = compare_files(
                input_path, output_path, args.context, args.transliteration
            )
            results.append(result)
        except Exception as e:
            print(f"Error comparing {input_path.name}: {e}", file=sys.stderr)
            # Add empty result to maintain alignment
            results.append({
                "input_chars": 0,
                "output_chars": 0,
                "total_diffs": 0,
                "non_whitespace_diffs": 0,
                "whitespace_only_diffs": 0,
                "diff_details": [],
            })

    # Generate report
    print()
    print("Generating report...")
    report = generate_report(file_pairs, results, input_dir, output_dir, args.auto_stage)

    # Write to timestamped file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Extract last component of input dir for filename
    input_dir_name = input_dir.name
    output_filename = f"{input_dir_name}_diff_log_{timestamp}.txt"
    output_path = Path.cwd() / output_filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✓ Report written to: {output_path}")
    print()
    print("Summary:")
    total_diffs = sum(r["total_diffs"] for r in results)
    total_non_ws = sum(r["non_whitespace_diffs"] for r in results)
    perfect_matches = sum(1 for r in results if r["total_diffs"] == 0)
    print(f"  Total differences: {total_diffs} ({total_non_ws} non-whitespace)")
    print(f"  Perfect matches: {perfect_matches}/{len(file_pairs)} files")

    if args.auto_stage and perfect_matches > 0:
        print(f"  Auto-staged: {perfect_matches} files")


if __name__ == "__main__":
    main()
