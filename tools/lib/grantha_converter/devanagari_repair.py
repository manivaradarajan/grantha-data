"""Repair Devanagari mismatches between input and output files.

This module provides functionality to automatically repair small differences in
Devanagari text between source files and converted output files. It performs
word-by-word comparison and correction while preserving all other content.
"""

import shutil
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple

from grantha_converter.devanagari_extractor import (
    extract_devanagari,
    extract_devanagari_words,
    extract_devanagari_words_with_positions,
)


def repair_devanagari_simple(
    input_text: str,
    output_text: str,
    max_diff_size: int = 500,
    skip_frontmatter: bool = True,
    verbose: bool = False,
    min_similarity: float = 0.85,
    conservative: bool = True,
) -> Tuple[bool, Optional[str], str]:
    """Simplified repair using direct substring replacement.

    This version uses a simpler, more reliable approach:
    1. Extract all Devanagari sequences from both texts
    2. Find sequences that don't match
    3. Replace them directly in the output

    Args:
        input_text: The source text (ground truth)
        output_text: The output text to repair
        max_diff_size: Maximum character difference to attempt repair
        skip_frontmatter: Whether to skip YAML frontmatter in output
        verbose: Print detailed repair information
        min_similarity: Minimum SequenceMatcher similarity ratio (0.0-1.0)
        conservative: Only apply simple replacements, skip insert/delete

    Returns:
        Tuple of (success: bool, repaired_text: Optional[str], message: str)
    """
    # Extract Devanagari with positions
    input_words_with_pos = extract_devanagari_words_with_positions(input_text)

    # Handle frontmatter in output
    frontmatter_end = -1
    output_body = output_text
    frontmatter_prefix = ""

    if skip_frontmatter:
        frontmatter_end = output_text.find("---\n\n", 4)
        if frontmatter_end > 0:
            frontmatter_prefix = output_text[: frontmatter_end + 5]
            output_body = output_text[frontmatter_end + 5 :]

    output_words_with_pos = extract_devanagari_words_with_positions(output_body)

    # Extract just the words for comparison
    input_words = [w for w, _, _ in input_words_with_pos]
    output_words = [w for w, _, _ in output_words_with_pos]

    # Quick check if they're already the same
    if input_words == output_words:
        return True, output_text, "No repair needed - Devanagari already matches"

    # Check total difference
    input_chars = sum(len(w) for w in input_words)
    output_chars = sum(len(w) for w in output_words)
    diff_size = abs(input_chars - output_chars)

    if diff_size >= max_diff_size:
        return (
            False,
            None,
            f"Difference too large to repair: {diff_size} characters (max: {max_diff_size})",
        )

    if verbose:
        print(f"\n🔧 Attempting simple repair:")
        print(f"   Input words: {len(input_words)}")
        print(f"   Output words: {len(output_words)}")
        print(f"   Character difference: {diff_size}")

    # Use SequenceMatcher to align the sequences
    matcher = SequenceMatcher(None, input_words, output_words)

    # Check similarity ratio - abort if sequences are too different
    similarity = matcher.ratio()
    if similarity < min_similarity:
        return (
            False,
            None,
            f"Sequences too different for safe repair (similarity: {similarity:.2%}, minimum: {min_similarity:.2%})",
        )

    if verbose:
        print(f"   ✓ Similarity ratio: {similarity:.2%} (threshold: {min_similarity:.2%})")

    # Collect all changes to apply (work backwards to preserve positions)
    changes = []  # List of (position, old_word, new_word, change_type)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        elif tag == "replace":
            # Replace output words with input words
            for j_idx, i_idx in zip(range(j1, j2), range(i1, i2)):
                if j_idx < len(output_words_with_pos):
                    word, start, end = output_words_with_pos[j_idx]
                    new_word = input_words[i_idx] if i_idx < len(input_words) else ""
                    changes.append((start, end, word, new_word, "replace"))
        elif tag == "delete":
            # Words in input but not in output - need to INSERT into output
            if conservative:
                # Skip insertions in conservative mode
                if verbose:
                    missing = " ".join(input_words[i1:i2])
                    print(f"   ⚠️  Skipping insertion in conservative mode: '{missing}'")
                continue
            # Find best insertion point
            if j1 < len(output_words_with_pos):
                # Insert before position j1
                _, insert_pos, _ = output_words_with_pos[j1]
                for i_idx in range(i1, i2):
                    changes.append((insert_pos, insert_pos, "", input_words[i_idx], "insert"))
            elif j1 > 0 and j1 <= len(output_words_with_pos):
                # Insert after last word
                _, _, insert_pos = output_words_with_pos[j1 - 1]
                for i_idx in range(i1, i2):
                    changes.append((insert_pos, insert_pos, "", input_words[i_idx], "insert"))
        elif tag == "insert":
            # Words in output but not in input - need to DELETE from output
            if conservative:
                # Skip deletions in conservative mode
                if verbose:
                    extra = " ".join(output_words[j1:j2])
                    print(f"   ⚠️  Skipping deletion in conservative mode: '{extra}'")
                continue
            for j_idx in range(j1, j2):
                if j_idx < len(output_words_with_pos):
                    word, start, end = output_words_with_pos[j_idx]
                    changes.append((start, end, word, "", "delete"))

    if not changes:
        return False, None, "No repairable differences found"

    # Sort changes by position (reverse order so we can apply from end to start)
    changes.sort(key=lambda x: x[0], reverse=True)

    if verbose:
        print(f"\n📋 Found {len(changes)} changes to apply:")

    # Apply changes (working backwards from end to start preserves earlier positions)
    repaired_body = output_body
    repair_count = 0
    failed_repairs = []

    for start, end, old_word, new_word, change_type in changes:
        if change_type == "replace":
            # Direct replacement - check that the text at this position matches
            actual_text = repaired_body[start:end]
            if old_word and actual_text == old_word:
                repaired_body = repaired_body[:start] + new_word + repaired_body[end:]
                repair_count += 1
                if verbose:
                    print(f"   ✓ Replaced '{old_word}' → '{new_word}' at pos {start}")
            else:
                failed_repairs.append(f"Replace '{old_word}' at pos {start} (found '{actual_text}')")
                if verbose:
                    print(f"   ✗ Could not replace '{old_word}' at pos {start} (found '{actual_text}')")
        elif change_type == "delete":
            # Delete the word
            actual_text = repaired_body[start:end]
            if old_word and actual_text == old_word:
                repaired_body = repaired_body[:start] + repaired_body[end:]
                repair_count += 1
                if verbose:
                    print(f"   ✓ Deleted '{old_word}' at pos {start}")
            else:
                failed_repairs.append(f"Delete '{old_word}' at pos {start} (found '{actual_text}')")
                if verbose:
                    print(f"   ✗ Could not delete '{old_word}' at pos {start} (found '{actual_text}')")
        elif change_type == "insert":
            # Insert the word - just insert it at the position
            repaired_body = repaired_body[:start] + " " + new_word + repaired_body[start:]
            repair_count += 1
            if verbose:
                print(f"   ✓ Inserted '{new_word}' at pos {start}")

    if repair_count == 0:
        return False, None, "Could not apply any repairs"

    # Reconstruct full output
    if frontmatter_prefix:
        repaired_output = frontmatter_prefix + repaired_body
    else:
        repaired_output = repaired_body

    # Validate
    repaired_words = extract_devanagari_words(repaired_body)
    if input_words == repaired_words:
        msg = f"✅ Successfully repaired {repair_count} change(s)"
        if failed_repairs and verbose:
            msg += f"\n⚠️  {len(failed_repairs)} operations skipped (positions shifted during repair)"
        return True, repaired_output, msg
    else:
        # Show what's still different
        matcher_final = SequenceMatcher(None, input_words, repaired_words)
        still_different = sum(1 for tag, _, _, _, _ in matcher_final.get_opcodes() if tag != "equal")
        msg = f"⚠️ Repair incomplete: {still_different} differences remaining after {repair_count} repairs"
        if failed_repairs:
            msg += f"\n   Failed operations: {len(failed_repairs)}"
            if verbose:
                for failure in failed_repairs[:5]:  # Show first 5 failures
                    msg += f"\n   - {failure}"
                if len(failed_repairs) > 5:
                    msg += f"\n   ... and {len(failed_repairs) - 5} more"
        return False, None, msg


def repair_devanagari(
    input_text: str,
    output_text: str,
    max_diff_size: int = 500,
    skip_frontmatter: bool = True,
    verbose: bool = False,
    min_similarity: float = 0.85,
    conservative: bool = True,
) -> Tuple[bool, Optional[str], str]:
    """Attempt to repair Devanagari mismatches in output text.

    Uses a simple position-based approach to directly replace/insert/delete
    Devanagari words that don't match between input and output.

    Args:
        input_text: The source text (ground truth)
        output_text: The output text to repair
        max_diff_size: Maximum character difference to attempt repair (default: 500)
        skip_frontmatter: Whether to skip YAML frontmatter in output (default: True)
        verbose: Print detailed repair information (default: False)
        min_similarity: Minimum SequenceMatcher similarity ratio (default: 0.85)
        conservative: Only apply simple replacements, skip insert/delete (default: True)

    Returns:
        Tuple of (success: bool, repaired_text: Optional[str], message: str)
        - success: True if repair was successful
        - repaired_text: The repaired text if successful, None otherwise
        - message: Status message describing what happened
    """
    # Use the simpler, more reliable repair function
    return repair_devanagari_simple(
        input_text=input_text,
        output_text=output_text,
        max_diff_size=max_diff_size,
        skip_frontmatter=skip_frontmatter,
        verbose=verbose,
        min_similarity=min_similarity,
        conservative=conservative,
    )


def repair_file(
    input_file: str,
    output_file: str,
    max_diff_size: int = 500,
    skip_frontmatter: bool = True,
    verbose: bool = False,
    dry_run: bool = False,
    min_similarity: float = 0.85,
    conservative: bool = True,
    create_backup: bool = True,
) -> Tuple[bool, str]:
    """Repair Devanagari mismatches between input and output files.

    This function implements a safe repair strategy:
    1. Test repair with dry_run first (unless already in dry_run mode)
    2. Create backup of output file before writing
    3. Apply repair
    4. Validate result
    5. Restore backup if validation fails

    Args:
        input_file: Path to input file (source of truth)
        output_file: Path to output file to repair
        max_diff_size: Maximum character difference to attempt repair
        skip_frontmatter: Whether to skip YAML frontmatter in output
        verbose: Print detailed repair information
        dry_run: Don't write changes, just report what would be done
        min_similarity: Minimum SequenceMatcher similarity ratio (default: 0.85)
        conservative: Only apply simple replacements, skip insert/delete (default: True)
        create_backup: Create backup before modifying file (default: True)

    Returns:
        Tuple of (success: bool, message: str)
    """
    # Read both files
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read()
    except Exception as e:
        return False, f"Error reading input file: {e}"

    try:
        with open(output_file, "r", encoding="utf-8") as f:
            output_text = f.read()
    except Exception as e:
        return False, f"Error reading output file: {e}"

    # STEP 1: Test repair with dry-run first (unless we're already in dry-run mode)
    if not dry_run and verbose:
        print("🧪 Testing repair in dry-run mode first...")

    success, repaired_text, message = repair_devanagari(
        input_text=input_text,
        output_text=output_text,
        max_diff_size=max_diff_size,
        skip_frontmatter=skip_frontmatter,
        verbose=verbose,
        min_similarity=min_similarity,
        conservative=conservative,
    )

    if not success or repaired_text is None:
        return False, f"Dry-run test failed: {message}"

    if dry_run:
        # Just report what would be done
        message += f"\n✓ Dry run - no changes written to {output_file}"
        return True, message

    # STEP 2: Create backup before writing
    backup_path = None
    if create_backup:
        try:
            # Create backup with .backup extension
            backup_path = Path(output_file).with_suffix(Path(output_file).suffix + '.backup')
            shutil.copy2(output_file, backup_path)
            if verbose:
                print(f"💾 Created backup: {backup_path}")
        except Exception as e:
            return False, f"Error creating backup: {e}"

    # STEP 3: Write repaired output
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(repaired_text)
        if verbose:
            print(f"✍️  Wrote repaired content to {output_file}")
    except Exception as e:
        # Restore backup if write failed
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, output_file)
            if verbose:
                print(f"↩️  Restored backup after write failure")
        return False, f"Error writing output file: {e}"

    # STEP 4: Validate the written file
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            written_text = f.read()

        # Quick validation: compare Devanagari words
        input_words = extract_devanagari_words(input_text)
        written_words = extract_devanagari_words(written_text)

        if input_words != written_words:
            # STEP 5: Restore backup if validation failed
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, output_file)
                if verbose:
                    print(f"↩️  Restored backup - written file failed validation")
                return False, f"Repair validation failed after writing. Backup restored. Expected {len(input_words)} words, got {len(written_words)}"

    except Exception as e:
        # Restore backup if validation failed
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, output_file)
            if verbose:
                print(f"↩️  Restored backup after validation error")
        return False, f"Error validating written file: {e}"

    # Success! Clean up backup if desired
    message += f"\n✅ Wrote and validated repaired content to {output_file}"
    if backup_path:
        message += f"\n💾 Backup saved at: {backup_path}"

    return True, message
