import shutil
from difflib import SequenceMatcher
from rapidfuzz import fuzz
from pathlib import Path
from typing import Optional, Tuple

from grantha_converter.devanagari_extractor import (
    extract_devanagari_words_with_positions,
    extract_devanagari,
    clean_text_for_devanagari_comparison,
)


def _repair_spacing(
    text: str,
    target_chars: str,
    current_chars: str,
    verbose: bool = False,
) -> Optional[str]:
    """Repairs spacing differences in Devanagari text.

    Uses character-level diffing on cleaned text to find spacing differences,
    then applies corrections to the full text while preserving markdown structure.

    Args:
        text: The text to repair (with markdown structure intact).
        target_chars: The target Devanagari sequence (from cleaned input).
        current_chars: The current Devanagari sequence (from cleaned text).
        verbose: If True, print detailed repair information.

    Returns:
        Repaired text with corrected spacing, or None if repair is not feasible.
    """
    import re
    from difflib import SequenceMatcher

    # First check if differences are only spacing (insertions/deletions, no replacements)
    matcher = SequenceMatcher(None, target_chars, current_chars, autojunk=False)
    has_replacements = any(tag == 'replace' for tag, _, _, _, _ in matcher.get_opcodes())

    if has_replacements:
        if verbose:
            print(f"   ⚠ Differences include character replacements, not just spacing")
        return None

    # Clean the text the same way to build position mapping
    cleaned_text = clean_text_for_devanagari_comparison(text, skip_headings=True)

    # Build mapping: current_chars index -> original text position
    # We need to track where each character in current_chars appears in the original text
    devanagari_pattern = r'[\u0900-\u097F\u1CD0-\u1CFF\u200C\u200D\u0951\u0952]'

    # Step 1: Map current_chars indices to cleaned_text positions
    current_char_to_cleaned_pos = []
    for match in re.finditer(devanagari_pattern, cleaned_text):
        for i, char in enumerate(match.group()):
            current_char_to_cleaned_pos.append(match.start() + i)

    if len(current_char_to_cleaned_pos) != len(current_chars):
        if verbose:
            print(f"   ⚠ Char count mismatch: {len(current_char_to_cleaned_pos)} != {len(current_chars)}")
        return None

    # Step 2: Map cleaned_text positions to original text positions
    cleaned_to_original = []
    original_idx = 0
    for i, char in enumerate(cleaned_text):
        if char in '\u0900-\u097F\u1CD0-\u1CFF\u200C\u200D\u0951\u0952':
            # This is a Devanagari character, find it in original text
            found_pos = text.find(char, original_idx)
            if found_pos != -1:
                cleaned_to_original.append(found_pos)
                original_idx = found_pos + 1
            else:
                cleaned_to_original.append(-1)
        else:
            cleaned_to_original.append(-1)

    # Now apply spacing fixes based on opcodes
    opcodes = matcher.get_opcodes()
    changes = []  # List of (original_text_pos, operation, content)

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == 'equal':
            continue
        elif tag == 'insert':
            # current_chars[j1:j2] should be deleted (extra spaces in output)
            # j1 is an index into current_chars
            # Map it to position in cleaned_text, then to position in original text
            if j1 < len(current_char_to_cleaned_pos):
                cleaned_pos = current_char_to_cleaned_pos[j1]
                if cleaned_pos < len(cleaned_to_original):
                    orig_pos = cleaned_to_original[cleaned_pos]
                    if orig_pos != -1:
                        # The extra characters in current_chars are at j1:j2
                        # In the original text, there might be a space right before this position
                        # Check if there's a space before orig_pos
                        if orig_pos > 0 and text[orig_pos - 1] == ' ':
                            changes.append((orig_pos - 1, 'delete', 1))

        elif tag == 'delete':
            # target_chars[i1:i2] should be inserted (missing in output)
            # j1 is where to insert in current_chars sequence
            if j1 < len(current_char_to_cleaned_pos):
                cleaned_pos = current_char_to_cleaned_pos[j1]
                if cleaned_pos < len(cleaned_to_original):
                    orig_pos = cleaned_to_original[cleaned_pos]
                    if orig_pos != -1:
                        chars_to_insert = target_chars[i1:i2]
                        changes.append((orig_pos, 'insert', chars_to_insert))
            elif j1 == len(current_char_to_cleaned_pos) and current_char_to_cleaned_pos:
                # Insert at the end
                last_cleaned_pos = current_char_to_cleaned_pos[-1]
                if last_cleaned_pos < len(cleaned_to_original):
                    orig_pos = cleaned_to_original[last_cleaned_pos]
                    if orig_pos != -1:
                        chars_to_insert = target_chars[i1:i2]
                        changes.append((orig_pos + 1, 'insert', chars_to_insert))

    if not changes:
        if verbose:
            print(f"   ⚠ No actionable spacing changes found")
        return None

    # Apply changes in reverse order to preserve positions
    changes.sort(key=lambda x: x[0], reverse=True)
    repaired = text

    for pos, operation, content in changes:
        if operation == 'delete':
            repaired = repaired[:pos] + repaired[pos+content:]
        elif operation == 'insert':
            repaired = repaired[:pos] + content + repaired[pos:]

    if verbose:
        char_diff = abs(len(target_chars) - len(current_chars))
        print(f"   ✓ Applied {len(changes)} spacing correction(s) ({char_diff} character difference)")

    return repaired


def repair_devanagari_simple(
    input_text: str,
    output_text: str,
    max_diff_size: int = 500,
    skip_frontmatter: bool = True,
    verbose: bool = False,
    min_similarity: float = 0.85,
) -> Tuple[bool, Optional[str], str]:
    """
    Repairs Devanagari text by surgically replacing Devanagari words in the output file
    to match the input file, while preserving all markdown structure, comments, and formatting.

    The algorithm:
    1. Extract Devanagari words with positions from BOTH input and output (original texts)
    2. Skip frontmatter and comments, but KEEP headings (we repair those too)
    3. Compare word sequences and identify differences
    4. Apply surgical edits to output text at the identified positions
    """
    # 1. Extract Devanagari words WITH POSITIONS from BOTH texts
    #    Use same filtering for both: skip frontmatter/comments/headings
    #    NOTE: We skip headings to match devanagari-diff behavior and ensure
    #    we're comparing actual content, not structural heading attributes
    input_words_with_pos = extract_devanagari_words_with_positions(
        input_text,
        skip_frontmatter=True,
        skip_comments=True,
        skip_headings=True
    )
    input_words = [w for w, _, _ in input_words_with_pos]

    output_words_with_pos = extract_devanagari_words_with_positions(
        output_text,
        skip_frontmatter=True,
        skip_comments=True,
        skip_headings=True
    )
    output_words = [w for w, _, _ in output_words_with_pos]

    if input_words == output_words:
        # Word-level matches, but check character-level (spacing) too
        if verbose:
            print(f"   ✓ Word-level Devanagari matches ({len(input_words)} words)")
            print(f"   ✓ Checking character-level (spacing)...")

        # Extract character-level Devanagari from both texts
        cleaned_input = clean_text_for_devanagari_comparison(input_text, skip_headings=True)
        input_chars = extract_devanagari(cleaned_input)

        cleaned_output = clean_text_for_devanagari_comparison(output_text, skip_headings=True)
        output_chars = extract_devanagari(cleaned_output)

        if input_chars == output_chars:
            return True, output_text, "No repair needed - Devanagari already matches."
        else:
            # Character-level mismatch (spacing issues)
            char_diff = abs(len(input_chars) - len(output_chars))
            if verbose:
                print(f"   ⚠ Character-level mismatch: {char_diff} character difference")
                print(f"      Input: {len(input_chars)} chars, Output: {len(output_chars)} chars")
                print(f"   ✓ Attempting spacing repair...")

            # Perform character-level spacing repair
            spacing_repaired_text = _repair_spacing(
                output_text,
                input_chars,
                output_chars,
                verbose=verbose
            )

            if spacing_repaired_text is None:
                if verbose:
                    print(f"   ⚠ Spacing repair not feasible, minor differences remain")
                return True, output_text, f"No word-level repair needed (minor {char_diff}-char spacing differences remain)."

            # Validate the spacing repair
            cleaned_final = clean_text_for_devanagari_comparison(spacing_repaired_text, skip_headings=True)
            final_chars = extract_devanagari(cleaned_final)

            if final_chars == input_chars:
                return True, spacing_repaired_text, f"Successfully applied {char_diff} spacing corrections."
            else:
                remaining_diff = abs(len(final_chars) - len(input_chars))
                return True, output_text, f"Partial spacing repair ({char_diff - remaining_diff} of {char_diff} corrections applied)."

    # 2. Safety Check: Similarity
    similarity = fuzz.ratio(" ".join(input_words), " ".join(output_words)) / 100.0
    if similarity < min_similarity:
        return False, None, f"Sequences too different for safe repair (similarity: {similarity:.2%}, minimum: {min_similarity:.2%})."

    if verbose:
        print(f"   ✓ Similarity ratio: {similarity:.2%} (threshold: {min_similarity:.2%})")
        print(f"   ✓ Input has {len(input_words)} Devanagari words")
        print(f"   ✓ Output has {len(output_words)} Devanagari words")

    # 3. Align word sequences to find differences
    matcher = SequenceMatcher(None, input_words, output_words, autojunk=False)
    changes = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        elif tag == 'replace':
            # Replace words in output[j1:j2] with words from input[i1:i2]
            replacement_text = " ".join(input_words[i1:i2])
            # Get positions in ORIGINAL output text
            start = output_words_with_pos[j1][1]
            end = output_words_with_pos[j2 - 1][2]
            old_block_text = " ".join(output_words[j1:j2])
            changes.append((start, end, replacement_text, f"replace '{old_block_text}' with '{replacement_text}'"))
        elif tag == 'delete': # Words in input but not output -> Insert into output
            # Insert at the position where j1 would be
            if j1 < len(output_words_with_pos):
                insert_pos = output_words_with_pos[j1][1]
                # Add space after insertion to separate from following word
                text_to_insert = " ".join(input_words[i1:i2]) + " "
            elif j1 > 0 and len(output_words_with_pos) > 0:
                # Insert after the last word - add space before
                insert_pos = output_words_with_pos[-1][2]
                text_to_insert = " " + " ".join(input_words[i1:i2])
            else:
                # No words in output, can't determine position
                if verbose:
                    print(f"   ⚠ Cannot determine insertion position for missing words: {' '.join(input_words[i1:i2])}")
                continue
            changes.append((insert_pos, insert_pos, text_to_insert, f"insert '{text_to_insert.strip()}'"))
        elif tag == 'insert': # Words in output but not input -> Delete from output
            # Delete each word individually to handle spacing correctly
            for j in range(j1, j2):
                old_word, start, end = output_words_with_pos[j]
                # Also delete trailing space if present
                if end < len(output_text) and output_text[end] == ' ':
                    end += 1
                changes.append((start, end, "", f"delete '{old_word}'"))

    if not changes:
        return False, None, "Repair failed: No actionable changes found."

    # 4. Apply changes in reverse order to the ORIGINAL output text
    changes.sort(key=lambda x: x[0], reverse=True)
    repaired_text = output_text

    if verbose:
        print(f"\n📋 Found {len(changes)} changes to apply:")

    for start, end, new_text, desc in changes:
        if verbose:
            print(f"   ✓ Applying change at {start}-{end}: {desc}")
        repaired_text = repaired_text[:start] + new_text + repaired_text[end:]

    # 5. Final validation: extract Devanagari from repaired text using SAME filtering as input
    final_repaired_words_with_pos = extract_devanagari_words_with_positions(
        repaired_text,
        skip_frontmatter=True,
        skip_comments=True,
        skip_headings=True
    )
    final_repaired_words = [w for w, _, _ in final_repaired_words_with_pos]

    if final_repaired_words == input_words:
        # Word-level repair succeeded, now check character-level (spacing)
        if verbose:
            print(f"\n📋 Word-level repair complete. Checking character-level (spacing)...")

        # Extract character-level Devanagari from both texts
        cleaned_input = clean_text_for_devanagari_comparison(input_text, skip_headings=True)
        input_chars = extract_devanagari(cleaned_input)

        cleaned_repaired = clean_text_for_devanagari_comparison(repaired_text, skip_headings=True)
        repaired_chars = extract_devanagari(cleaned_repaired)

        if input_chars == repaired_chars:
            return True, repaired_text, f"Successfully applied {len(changes)} corrections."
        else:
            # Character-level mismatch (likely spacing) - perform character-level repair
            char_diff = abs(len(input_chars) - len(repaired_chars))
            if verbose:
                print(f"   ⚠ Character-level mismatch detected: {char_diff} character difference")
                print(f"   ✓ Attempting character-level repair...")

            # Perform character-level repair by replacing Devanagari in repaired text
            # with exact character-level Devanagari from input
            spacing_repaired_text = _repair_spacing(
                repaired_text,
                input_chars,
                repaired_chars,
                verbose=verbose
            )

            if spacing_repaired_text is None:
                return True, repaired_text, f"Successfully applied {len(changes)} corrections (minor spacing differences remain)."

            # Validate the spacing repair
            cleaned_final = clean_text_for_devanagari_comparison(spacing_repaired_text, skip_headings=True)
            final_chars = extract_devanagari(cleaned_final)

            if final_chars == input_chars:
                total_corrections = len(changes) + char_diff
                return True, spacing_repaired_text, f"Successfully applied {total_corrections} corrections (including {char_diff} spacing fixes)."
            else:
                # Spacing repair failed, return word-level repair result
                return True, repaired_text, f"Successfully applied {len(changes)} corrections (minor spacing differences remain)."
    else:
        if verbose:
            Path("/tmp/final_repaired_words.txt").write_text("\n".join(final_repaired_words), encoding="utf-8")
            Path("/tmp/final_input_words.txt").write_text("\n".join(input_words), encoding="utf-8")
            print("   - Final validation failed. Word lists saved to /tmp/ for diffing.")
            print(f"   - Expected {len(input_words)} words, got {len(final_repaired_words)} words")
        return False, None, "Repair validation failed: Repaired text does not match source."


def repair_file(
    input_file: str,
    output_file: str,
    max_diff_size: int = 500,
    skip_frontmatter: bool = True,
    verbose: bool = False,
    dry_run: bool = False,
    min_similarity: float = 0.85,
    create_backup: bool = True,
) -> Tuple[bool, str]:
    """Repair Devanagari mismatches between input and output files."""
    try:
        input_text = Path(input_file).read_text(encoding="utf-8")
        output_text = Path(output_file).read_text(encoding="utf-8")
    except Exception as e:
        return False, f"Error reading files: {e}"

    if verbose and not dry_run:
        print("🧪 Testing repair in dry-run mode first...")

    success, repaired_text, message = repair_devanagari_simple(
        input_text=input_text,
        output_text=output_text,
        max_diff_size=max_diff_size,
        skip_frontmatter=skip_frontmatter,
        verbose=verbose,
        min_similarity=min_similarity,
    )

    if not success:
        return False, f"Repair pre-check failed: {message}"

    if dry_run:
        return True, f"Dry run successful: {message}"

    # --- Create backup and write file ---
    backup_path = None
    if create_backup:
        try:
            backup_path = Path(output_file).with_suffix(Path(output_file).suffix + '.backup')
            shutil.copy2(output_file, backup_path)
            if verbose:
                print(f"💾 Created backup: {backup_path}")
        except Exception as e:
            return False, f"Error creating backup: {e}"

    try:
        Path(output_file).write_text(repaired_text, encoding="utf-8")
        if verbose:
            print(f"✍️  Wrote repaired content to {output_file}")
    except Exception as e:
        if backup_path:
            shutil.copy2(backup_path, output_file)
        return False, f"Error writing output file: {e}"

    return True, message
