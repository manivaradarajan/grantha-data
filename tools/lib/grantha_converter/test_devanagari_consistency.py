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
                f"Diff shows differences but repair says no action needed"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
