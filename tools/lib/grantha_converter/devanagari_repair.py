import shutil
import re
from difflib import SequenceMatcher
from rapidfuzz import fuzz
from pathlib import Path
from typing import List, Optional, Tuple

from grantha_converter.devanagari_extractor import (
    extract_devanagari_words,
    extract_devanagari_words_with_positions,
)


def _clean_text_for_comparison(text: str) -> str:
    """
    Cleans text by removing frontmatter, HTML comments, and markdown bold markers
    to prepare it for Devanagari word extraction and comparison.
    """
    # 1. Remove YAML frontmatter
    if text.strip().startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]

    # 2. Replace HTML comments with a space to avoid merging words
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)

    # 3. Remove markdown bold markers
    text = re.sub(r"\*\*", "", text)
    
    # 4. (Optional but good practice) Normalize whitespace to a single space
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def repair_devanagari_simple(
    input_text: str,
    output_text: str,
    max_diff_size: int = 500,
    skip_frontmatter: bool = True,
    verbose: bool = False,
    min_similarity: float = 0.85,
) -> Tuple[bool, Optional[str], str]:
    """
    Repairs Devanagari text by aligning word lists from cleaned text and
    applying changes back to a similarly cleaned version of the original text.
    """
    # 1. Preserve original frontmatter from the output file if requested
    frontmatter_prefix = ""
    if skip_frontmatter:
        output_parts = output_text.split('---', 2)
        if len(output_parts) > 2 and output_text.startswith('---'):
            frontmatter_prefix = f"---{output_parts[1]}---"

    # 2. Create consistently cleaned versions of both texts for all operations
    input_body_cleaned = _clean_text_for_comparison(input_text)
    output_body_cleaned = _clean_text_for_comparison(output_text)

    # 3. Extract words AND positions from the CLEANED texts.
    #    Positions are now relative to the cleaned bodies, ensuring consistency.
    input_words_with_pos = extract_devanagari_words_with_positions(input_body_cleaned)
    output_words_with_pos = extract_devanagari_words_with_positions(output_body_cleaned)
    
    input_words = [w for w, _, _ in input_words_with_pos]
    output_words = [w for w, _, _ in output_words_with_pos]

    if input_words == output_words:
        return True, output_text, "No repair needed - Devanagari already matches."

    # 4. Safety Check: Similarity
    similarity = fuzz.ratio(" ".join(input_words), " ".join(output_words)) / 100.0
    if similarity < min_similarity:
        return False, None, f"Sequences too different for safe repair (similarity: {similarity:.2%}, minimum: {min_similarity:.2%})."

    if verbose:
        print(f"   ✓ Similarity ratio: {similarity:.2%} (threshold: {min_similarity:.2%})")

    # 5. Align word sequences to find differences
    matcher = SequenceMatcher(None, input_words, output_words, autojunk=False)
    changes = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        elif tag == 'replace':
            # Join all the words from the input that should replace the output block
            replacement_text = " ".join(input_words[i1:i2])
            # Get the start position of the first word to be replaced and the end of the last
            start = output_words_with_pos[j1][1]
            end = output_words_with_pos[j2 - 1][2]
            old_block_text = " ".join(output_words[j1:j2])
            changes.append((start, end, replacement_text, f"replace '{old_block_text}' with '{replacement_text}'"))
        elif tag == 'delete': # Words in input but not output -> Insert into output
            # Get position from the word before or after the insertion point
            insert_pos = output_words_with_pos[j1][1] if j1 < len(output_words_with_pos) else len(output_body_cleaned)
            text_to_insert = " ".join(input_words[i1:i2]) + " "
            changes.append((insert_pos, insert_pos, text_to_insert, f"insert '{text_to_insert.strip()}'"))
        elif tag == 'insert': # Words in output but not input -> Delete from output
            for j in range(j1, j2):
                old_word, start, end = output_words_with_pos[j]
                changes.append((start, end, "", f"delete '{old_word}'"))

    if not changes:
        return False, None, "Repair failed: No actionable changes found."

    # 6. Apply changes in reverse to the CLEANED output body
    changes.sort(key=lambda x: x[0], reverse=True)
    repaired_body = output_body_cleaned
    
    if verbose:
        print(f"\n📋 Found {len(changes)} changes to apply:")

    for start, end, new_text, desc in changes:
        if verbose:
            print(f"   ✓ Applying change at {start}-{end}: {desc}")
        repaired_body = repaired_body[:start] + new_text + repaired_body[end:]

    # 7. Final validation against the CLEANED input body
    final_repaired_words = extract_devanagari_words(repaired_body)
    
    if final_repaired_words == input_words:
        # Success! Re-attach the original frontmatter to the repaired clean body.
        final_content = frontmatter_prefix + "\n" + repaired_body if frontmatter_prefix else repaired_body
        return True, final_content, f"Successfully applied {len(changes)} corrections."
    else:
        if verbose:
            Path("/tmp/final_repaired_words.txt").write_text("\n".join(final_repaired_words), encoding="utf-8")
            Path("/tmp/final_input_words.txt").write_text("\n".join(input_words), encoding="utf-8")
            print("   - Final validation failed. Word lists saved to /tmp/ for diffing.")
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
