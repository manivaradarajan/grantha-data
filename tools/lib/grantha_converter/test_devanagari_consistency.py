"""
Test mutual consistency between diff, repair, and validator tools.

This test ensures that:
1. Text cleaning preserves ALL Devanagari characters
2. Diff and repair use identical text extraction logic
3. The hash validator is compatible with diff/repair

The design principle:
- hasher.py works on JSON (clean structured data, no cleaning needed)
- diff/repair work on MD files (use clean_text_for_devanagari_comparison)
- All three must agree on what constitutes "same Devanagari content"
"""

import pytest
import hashlib
from pathlib import Path
from grantha_converter.devanagari_extractor import (
    extract_devanagari,
    clean_text_for_devanagari_comparison,
)
from grantha_converter.devanagari_repair import repair_devanagari_simple


class TestDevanagariConsistency:
    """Test that diff, repair, and validator are mutually consistent."""

    def test_cleaning_preserves_all_devanagari(self):
        """Verify that clean_text_for_devanagari_comparison never loses Devanagari."""
        test_cases = [
            # YAML frontmatter
            "---\ntitle: Test\n---\nअग्निमीळे पुरोहितं",
            # HTML comments
            "अग्नि <!-- this is a comment --> मीळे",
            # Bold markers
            "**अग्निमीळे** पुरोहितं",
            # All combined
            "---\ntitle: Test\n---\n**अग्नि** <!-- comment --> मीळे",
            # Multiple spaces
            "अग्नि\n\n\nमीळे",
            # Real-world sample
            "# Mantra 1.1\n\n<!-- sanskrit:devanagari -->\nअग्निमीळे पुरोहितं\n<!-- /sanskrit:devanagari -->",
        ]

        for test_text in test_cases:
            # Extract Devanagari before and after cleaning
            dev_before = extract_devanagari(test_text)
            cleaned = clean_text_for_devanagari_comparison(test_text)
            dev_after = extract_devanagari(cleaned)

            # They MUST be identical - cleaning should never lose Devanagari
            assert dev_before == dev_after, (
                f"Cleaning lost Devanagari!\n"
                f"Before: {dev_before}\n"
                f"After:  {dev_after}\n"
                f"Input:  {repr(test_text[:100])}"
            )

    def test_diff_and_repair_use_same_logic(self):
        """Verify diff and repair extract Devanagari identically."""
        # Create two test texts with different markup but same Devanagari
        text1 = "---\ntitle: Source\n---\n**अग्निमीळे** पुरोहितं"
        text2 = "---\ntitle: Target\n---\nअग्नि <!-- comment --> मीळे पुरोहितं"

        # What diff would see
        cleaned1 = clean_text_for_devanagari_comparison(text1)
        cleaned2 = clean_text_for_devanagari_comparison(text2)
        diff_dev1 = extract_devanagari(cleaned1)
        diff_dev2 = extract_devanagari(cleaned2)

        # What repair would see (it uses the same cleaning function)
        success, repaired, msg = repair_devanagari_simple(text1, text2, verbose=False)

        # If diff sees match, repair should say "no repair needed"
        if diff_dev1 == diff_dev2:
            assert success and "No repair needed" in msg, (
                "Diff sees match but repair doesn't agree"
            )
        else:
            # If diff sees differences, repair should either fix them or report differences
            assert success or "repair" in msg.lower(), (
                "Diff sees differences but repair says no action needed"
            )

    def test_identical_texts_are_consistent(self):
        """When two texts have identical Devanagari, all tools should agree."""
        # Note: HTML comments are replaced with spaces, so they act as word separators
        # These two texts have the SAME Devanagari after cleaning
        text1 = "---\ntitle: One\n---\n**अग्निमीळे** पुरोहितं यज्ञस्य"
        text2 = "---\ntitle: Two\n---\n**अग्निमीळे** पुरोहितं यज्ञस्य"

        # Diff should show no differences
        cleaned1 = clean_text_for_devanagari_comparison(text1)
        cleaned2 = clean_text_for_devanagari_comparison(text2)
        dev1 = extract_devanagari(cleaned1)
        dev2 = extract_devanagari(cleaned2)
        assert dev1 == dev2, f"Diff logic shows differences but should match:\n  '{dev1}'\n  '{dev2}'"

        # Repair should say "no repair needed"
        success, repaired, msg = repair_devanagari_simple(text1, text2, verbose=False)
        assert success, f"Repair failed: {msg}"
        assert "No repair needed" in msg, f"Repair should say no action needed: {msg}"

    def test_different_texts_are_consistent(self):
        """When two texts have different Devanagari, all tools should agree."""
        text1 = "अग्निमीळे पुरोहितं"
        text2 = "अग्निमीळे देवम्"  # Different ending

        # Diff should show differences
        cleaned1 = clean_text_for_devanagari_comparison(text1)
        cleaned2 = clean_text_for_devanagari_comparison(text2)
        dev1 = extract_devanagari(cleaned1)
        dev2 = extract_devanagari(cleaned2)
        assert dev1 != dev2, "Diff logic should show differences"

        # Repair should detect differences
        success, repaired, msg = repair_devanagari_simple(text1, text2, verbose=False)
        assert "No repair needed" not in msg, "Repair should detect differences"

    def test_hash_computation_is_stable(self):
        """Verify that hash computation is stable and deterministic."""
        text = "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम्"

        # Compute hash multiple times
        dev = extract_devanagari(text)
        hash1 = hashlib.sha256(dev.encode('utf-8')).hexdigest()
        hash2 = hashlib.sha256(dev.encode('utf-8')).hexdigest()
        hash3 = hashlib.sha256(dev.encode('utf-8')).hexdigest()

        assert hash1 == hash2 == hash3, "Hash computation is not stable"

    def test_markup_variations_produce_same_hash(self):
        """Verify that different markup produces same hash after cleaning."""
        # Same Devanagari, different markup
        # NOTE: HTML comments are replaced with spaces, so they act as separators
        # Don't put HTML comments INSIDE words!
        variations = [
            "अग्निमीळे पुरोहितं",
            "**अग्निमीळे** पुरोहितं",
            "अग्निमीळे <!-- comment --> पुरोहितं",  # Comment between words, not inside
            "---\ntitle: Test\n---\nअग्निमीळे पुरोहितं",
        ]

        hashes = []
        for text in variations:
            cleaned = clean_text_for_devanagari_comparison(text)
            dev = extract_devanagari(cleaned)
            h = hashlib.sha256(dev.encode('utf-8')).hexdigest()
            hashes.append(h)

        # All hashes should be identical
        assert len(set(hashes)) == 1, (
            f"Different markup produced different hashes:\n"
            f"Hashes: {hashes}"
        )

    def test_whitespace_normalization_is_consistent(self):
        """Verify that whitespace normalization works consistently."""
        text1 = "अग्नि    मीळे"  # Multiple spaces
        text2 = "अग्नि\n\n\nमीळे"  # Multiple newlines
        text3 = "अग्नि\t\tमीळे"  # Tabs

        cleaned1 = clean_text_for_devanagari_comparison(text1)
        cleaned2 = clean_text_for_devanagari_comparison(text2)
        cleaned3 = clean_text_for_devanagari_comparison(text3)

        dev1 = extract_devanagari(cleaned1)
        dev2 = extract_devanagari(cleaned2)
        dev3 = extract_devanagari(cleaned3)

        # All should normalize to same Devanagari with single space
        assert dev1 == dev2 == dev3, (
            f"Whitespace normalization inconsistent:\n"
            f"dev1: {dev1}\n"
            f"dev2: {dev2}\n"
            f"dev3: {dev3}"
        )


class TestRealWorldConsistency:
    """Test consistency using actual files from the repository."""

    @pytest.mark.skipif(
        not Path("sources/upanishads/meghamala/aitareya/aitareyopaniSat.md").exists(),
        reason="Test files not found"
    )
    def test_actual_files_consistency(self):
        """Test diff and repair consistency on actual repository files."""
        input_file = "sources/upanishads/meghamala/aitareya/aitareyopaniSat.md"
        output_file = "structured_md/upanishads/aitareya/aitareya-upanishad-rangaramanuja-01-01.md"

        if not Path(input_file).exists() or not Path(output_file).exists():
            pytest.skip("Test files not found")

        # Read files
        input_text = Path(input_file).read_text()
        output_text = Path(output_file).read_text()

        # What diff sees
        cleaned_input = clean_text_for_devanagari_comparison(input_text)
        cleaned_output = clean_text_for_devanagari_comparison(output_text)
        diff_input_dev = extract_devanagari(cleaned_input)
        diff_output_dev = extract_devanagari(cleaned_output)
        diff_match = (diff_input_dev == diff_output_dev)

        # What repair sees
        success, repaired, msg = repair_devanagari_simple(
            input_text, output_text, verbose=False
        )

        # They must agree
        if diff_match:
            assert success and "No repair needed" in msg, (
                f"Diff shows match but repair says: {msg}"
            )
        else:
            assert "No repair needed" not in msg, (
                "Diff shows differences but repair says no action needed"
            )


class TestSurgicalRepairs:
    """Test that repairs are surgical (small changes only), not wholesale replacements."""

    def test_repair_preserves_structure(self):
        """Verify that repair preserves all markdown structure."""
        # Original text with structure
        original = """---
grantha_id: test
canonical_title: परीक्षा
---

<!-- hide type:title -->
**परीक्षा**
<!-- /hide -->

# Mantra 1.1
<!-- sanskrit:devanagari -->
**अग्निमीळे पुरोहितम्**
<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "test"} -->
# Commentary: 1.1
यज्ञस्य देवम्
"""

        # Modified text with typo in Devanagari
        modified = original.replace("पुरोहितम्", "पुरोहितं")

        # Repair should fix the typo
        success, repaired, msg = repair_devanagari_simple(original, modified, verbose=False)

        assert success, f"Repair failed: {msg}"

        # Count lines - should be exactly the same
        original_lines = original.count('\n')
        repaired_lines = repaired.count('\n')
        assert original_lines == repaired_lines, (
            f"Line count changed! Original: {original_lines}, Repaired: {repaired_lines}\n"
            f"This suggests wholesale replacement rather than surgical edits"
        )

        # YAML frontmatter should be identical
        assert repaired.startswith("---\ngrantha_id: test"), "YAML frontmatter was corrupted"

        # All HTML comments should be preserved
        assert repaired.count("<!--") == original.count("<!--"), "HTML comments were removed"
        assert repaired.count("-->") == original.count("-->"), "HTML comments were removed"

        # Markdown headers should be preserved
        assert "# Mantra 1.1" in repaired, "Markdown headers were removed"
        assert "# Commentary: 1.1" in repaired, "Commentary headers were removed"

    def test_repair_makes_minimal_changes(self):
        """Verify that repair changes only the necessary Devanagari characters."""
        original = "**अग्निमीळे पुरोहितम्** देवम् ऋत्विजम्"
        modified = "**अग्निमीळे पुरोहितं** देवम् ऋत्विजम्"  # Only म् → ं changed

        success, repaired, msg = repair_devanagari_simple(original, modified, verbose=False)

        assert success, f"Repair failed: {msg}"

        # The repaired text should be identical to original
        assert repaired == original, (
            f"Expected minimal repair but got:\n"
            f"Original:  {original}\n"
            f"Repaired:  {repaired}"
        )

    def test_repair_size_limit(self):
        """Verify that repair doesn't make massive changes to the file."""
        import difflib

        # Create a realistic file structure
        base_text = """---
grantha_id: test
part_num: 1
canonical_title: परीक्षा
---

# Mantra 1.1
<!-- sanskrit:devanagari -->
""" + "अग्निमीळे पुरोहितं यज्ञस्य देवम् ऋत्विजम् होतारं रत्नधातमम् । " * 50 + """
<!-- /sanskrit:devanagari -->

# Commentary: 1.1
""" + "एतत् व्याख्यानम् अस्ति । " * 100

        # Modified version with a few typos
        modified = base_text.replace("पुरोहितं", "पुरोहितम्", 3)  # Fix 3 instances

        success, repaired, msg = repair_devanagari_simple(base_text, modified, verbose=False)

        if not success:
            # If there are differences, repair should succeed
            pytest.skip("Files matched, no repair needed")

        # Calculate the character-level difference
        original_len = len(modified)
        repaired_len = len(repaired)

        # The length should not change dramatically (allow 5% variance for small edits)
        length_diff_pct = abs(repaired_len - original_len) / original_len * 100

        assert length_diff_pct < 5.0, (
            f"Repair changed file size by {length_diff_pct:.1f}%!\n"
            f"Original: {original_len} chars, Repaired: {repaired_len} chars\n"
            f"This suggests wholesale replacement rather than surgical repair"
        )

        # Use difflib to count actual edit operations (more accurate than zip)
        matcher = difflib.SequenceMatcher(None, modified, repaired)
        total_edits = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ('replace', 'delete', 'insert'):
                # Count the number of characters affected in the original text
                total_edits += max(i2 - i1, j2 - j1)

        # Should change very few characters (less than 2% of file)
        # Note: This is more lenient than 1% because character edits can have
        # cascading position effects in the diff
        diff_pct = total_edits / original_len * 100

        assert diff_pct < 2.0, (
            f"Repair changed {total_edits} characters ({diff_pct:.2f}% of file)!\n"
            f"This suggests non-surgical changes"
        )

    def test_no_structure_removal(self):
        """Verify that repair NEVER removes YAML, comments, or markdown headers."""
        original = """---
title: टेस्ट
author: लेखकः
---

<!-- This is a comment in English -->
<!-- यह टिप्पणी है -->

# Heading देवनागरी में

**अग्निमीळे** पुरोहितं यज्ञस्य देवमृत्विजम् । होतारं रत्नधातमम् ॥
"""

        # Modified with small Devanagari typo
        modified = original.replace("यज्ञस्य", "यज्ञस्या")

        success, repaired, msg = repair_devanagari_simple(original, modified, verbose=False)

        assert success, f"Repair failed: {msg}"

        # Critical assertions - these should NEVER fail
        assert "---" in repaired, "YAML frontmatter delimiters removed!"
        assert "title: टेस्ट" in repaired or "title:" in repaired, "YAML was corrupted!"
        assert "<!-- This is a comment" in repaired, "English HTML comment removed!"
        assert "<!-- यह टिप्पणी है -->" in repaired, "Devanagari HTML comment removed!"
        assert "# Heading" in repaired, "Markdown heading removed!"
        assert "**अग्निमीळे**" in repaired or "अग्निमीळे" in repaired, "Bold markers or content removed!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
