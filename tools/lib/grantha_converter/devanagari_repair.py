import shutil
from difflib import SequenceMatcher
from rapidfuzz import fuzz
from pathlib import Path
from typing import Optional, Tuple

from grantha_converter.devanagari_extractor import (
    extract_devanagari_words_with_positions,
)

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
    #    Use same filtering for both: skip frontmatter/comments, keep headings
    input_words_with_pos = extract_devanagari_words_with_positions(
        input_text,
        skip_frontmatter=True,
        skip_comments=True,
        skip_headings=False
    )
    input_words = [w for w, _, _ in input_words_with_pos]

    output_words_with_pos = extract_devanagari_words_with_positions(
        output_text,
        skip_frontmatter=True,
        skip_comments=True,
        skip_headings=False
    )
    output_words = [w for w, _, _ in output_words_with_pos]

    if input_words == output_words:
        return True, output_text, "No repair needed - Devanagari already matches."

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
        skip_headings=False
    )
    final_repaired_words = [w for w, _, _ in final_repaired_words_with_pos]

    if final_repaired_words == input_words:
        return True, repaired_text, f"Successfully applied {len(changes)} corrections."
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
