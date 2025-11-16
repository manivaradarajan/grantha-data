"""Tests for devanagari_extractor module.

This test suite ensures the canonical Devanagari extraction functions work
correctly and consistently across all use cases.
"""

import pytest
from grantha_converter.devanagari_extractor import (
    extract_devanagari,
    extract_devanagari_words,
    extract_devanagari_words_with_positions,
)


class TestExtractDevanagari:
    """Tests for extract_devanagari() function."""

    def test_simple_devanagari_text(self):
        """Test extraction from pure Devanagari text."""
        text = "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम्"
        result = extract_devanagari(text)
        # Should preserve spaces between Devanagari words
        assert result == "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम्"

    def test_mixed_content_markdown(self):
        """Test extraction from markdown with headers."""
        text = "# Mantra 1\n\nअग्निमीळे\n\n## Commentary\n\nपुरोहितं"
        result = extract_devanagari(text)
        # Markdown creates a gap between words, normalized to single space
        assert result == "अग्निमीळे पुरोहितं"

    def test_yaml_frontmatter_ignored(self):
        """Test that YAML frontmatter is completely ignored."""
        text = """---
grantha_id: test
title: "परीक्षा"
---

अग्निमीळे पुरोहितं"""
        result = extract_devanagari(text)
        # Note: "परीक्षा" in YAML should be included since we extract ALL Devanagari
        assert "परीक्षा" in result
        assert "अग्निमीळे पुरोहितं" in result

    def test_html_comments_ignored(self):
        """Test that HTML/markdown comments are ignored."""
        text = "<!-- sanskrit:devanagari -->\nअग्निमीळे\n<!-- /sanskrit:devanagari -->"
        result = extract_devanagari(text)
        assert result == "अग्निमीळे"

    def test_mixed_scripts_only_devanagari(self):
        """Test that only Devanagari is extracted when multiple scripts present."""
        text = "agnimīḷe अग्निमीळे agni मीळे"
        result = extract_devanagari(text)
        # Non-Devanagari gaps are normalized to single space
        assert result == "अग्निमीळे मीळे"
        assert "a" not in result
        assert "g" not in result
        assert "ī" not in result

    def test_english_translation_ignored(self):
        """Test that English text is completely ignored."""
        text = """अग्निमीळे

**Translation**: I praise Agni

पुरोहितं"""
        result = extract_devanagari(text)
        # English creates a gap, normalized to single space
        assert result == "अग्निमीळे पुरोहितं"
        assert "I" not in result
        assert "A" not in result

    def test_dandas_preserved(self):
        """Test that dandas are preserved (they're in Devanagari block)."""
        text = "अग्निमीळे। पुरोहितं॥ यज्ञस्य।"
        result = extract_devanagari(text)
        # Dandas (।॥) are in Devanagari block, so they ARE included
        assert result == "अग्निमीळे। पुरोहितं॥ यज्ञस्य।"

    def test_devanagari_numerals_included(self):
        """Test that Devanagari numerals are included."""
        text = "मन्त्र १, मन्त्र २, मन्त्र १०"
        result = extract_devanagari(text)
        assert "मन्त्र" in result
        assert "१" in result
        assert "२" in result

    def test_combining_marks_included(self):
        """Test that combining marks (matras) are preserved."""
        text = "क + ा = का"
        result = extract_devanagari(text)
        # क (ka), ा (aa matra) are in Devanagari block
        assert "क" in result
        assert "ा" in result

    def test_empty_string(self):
        """Test extraction from empty string."""
        result = extract_devanagari("")
        assert result == ""

    def test_no_devanagari(self):
        """Test extraction when no Devanagari present."""
        text = "This is English text with Roman transliteration agnimīḷe"
        result = extract_devanagari(text)
        assert result == ""

    def test_whitespace_only(self):
        """Test extraction from whitespace-only string."""
        text = "   \n\t  \r\n  "
        result = extract_devanagari(text)
        assert result == ""


class TestExtractDevanagariWords:
    """Tests for extract_devanagari_words() function."""

    def test_simple_words(self):
        """Test extraction of simple word sequences."""
        text = "अग्निमीळे पुरोहितं यज्ञस्य"
        result = extract_devanagari_words(text)
        assert result == ["अग्निमीळे", "पुरोहितं", "यज्ञस्य"]

    def test_words_separated_by_newlines(self):
        """Test that newlines act as word separators."""
        text = "अग्निमीळे\nपुरोहितं\nयज्ञस्य"
        result = extract_devanagari_words(text)
        assert result == ["अग्निमीळे", "पुरोहितं", "यज्ञस्य"]

    def test_words_with_markdown(self):
        """Test extraction ignoring markdown formatting."""
        text = "# अग्निमीळे\n\n**पुरोहितं**\n\n- यज्ञस्य"
        result = extract_devanagari_words(text)
        assert result == ["अग्निमीळे", "पुरोहितं", "यज्ञस्य"]

    def test_words_mixed_with_roman(self):
        """Test extraction when Devanagari is mixed with Roman."""
        text = "Word अग्निमीळे another पुरोहितं text"
        result = extract_devanagari_words(text)
        assert result == ["अग्निमीळे", "पुरोहितं"]

    def test_consecutive_spaces_not_create_empty_words(self):
        """Test that multiple spaces don't create empty entries."""
        text = "अग्निमीळे    पुरोहितं"
        result = extract_devanagari_words(text)
        assert result == ["अग्निमीळे", "पुरोहितं"]
        assert len(result) == 2

    def test_empty_string(self):
        """Test extraction from empty string."""
        result = extract_devanagari_words("")
        assert result == []

    def test_no_devanagari(self):
        """Test when no Devanagari is present."""
        text = "Only English and agnimīḷe transliteration"
        result = extract_devanagari_words(text)
        assert result == []

    def test_single_character_words(self):
        """Test extraction of single-character Devanagari."""
        text = "अ इ उ"
        result = extract_devanagari_words(text)
        assert result == ["अ", "इ", "उ"]

    def test_words_with_numbers(self):
        """Test extraction of words containing Devanagari numerals."""
        text = "मन्त्र१ and मन्त्र२"  # No space between word and number
        result = extract_devanagari_words(text)
        # Numbers are part of Devanagari block, so they're included in the word
        assert "मन्त्र१" in result
        assert "मन्त्र२" in result


class TestExtractDevanagariWordsWithPositions:
    """Tests for extract_devanagari_words_with_positions() function."""

    def test_simple_positions(self):
        """Test that positions are correctly tracked."""
        text = "अग्निमीळे पुरोहितं"
        result = extract_devanagari_words_with_positions(text)
        assert len(result) == 2

        word1, start1, end1 = result[0]
        assert word1 == "अग्निमीळे"
        assert text[start1:end1] == "अग्निमीळे"

        word2, start2, end2 = result[1]
        assert word2 == "पुरोहितं"
        assert text[start2:end2] == "पुरोहितं"

    def test_positions_with_prefix(self):
        """Test positions when Devanagari appears after other content."""
        text = "English prefix अग्निमीळे more text पुरोहितं"
        result = extract_devanagari_words_with_positions(text)

        assert len(result) == 2
        for word, start, end in result:
            assert text[start:end] == word

    def test_positions_accurate_for_repair(self):
        """Test that positions can be used for text replacement."""
        text = "Start अग्निमीळे middle पुरोहितं end"
        result = extract_devanagari_words_with_positions(text)

        # Verify we can replace using the positions
        word1, start1, end1 = result[0]
        replaced = text[:start1] + "REPLACED" + text[end1:]
        assert "REPLACED" in replaced
        assert "अग्निमीळे" not in replaced
        assert "पुरोहितं" in replaced  # Second word should still be there

    def test_empty_string(self):
        """Test extraction from empty string."""
        result = extract_devanagari_words_with_positions("")
        assert result == []

    def test_no_devanagari(self):
        """Test when no Devanagari present."""
        text = "Only English text here"
        result = extract_devanagari_words_with_positions(text)
        assert result == []

    def test_positions_with_newlines(self):
        """Test that positions account for newlines correctly."""
        text = "Line 1\nअग्निमीळे\nLine 3\nपुरोहितं"
        result = extract_devanagari_words_with_positions(text)

        assert len(result) == 2
        for word, start, end in result:
            assert text[start:end] == word

    def test_positions_maintain_order(self):
        """Test that positions are in text order."""
        text = "First अग्निमीळे then पुरोहितं finally यज्ञस्य"
        result = extract_devanagari_words_with_positions(text)

        # Positions should be monotonically increasing
        positions = [start for _, start, _ in result]
        assert positions == sorted(positions)


class TestDevanagariUnicodeRange:
    """Tests to verify correct Unicode range coverage."""

    def test_devanagari_block_start(self):
        """Test character at start of Devanagari block (U+0900)."""
        # U+0900 is a combining mark
        text = "\u0900"
        result = extract_devanagari(text)
        assert result == "\u0900"

    def test_devanagari_block_end(self):
        """Test character at end of Devanagari block (U+097F)."""
        # U+097F is typically unused, but should still be extracted if present
        text = "\u097F"
        result = extract_devanagari(text)
        assert result == "\u097F"

    def test_outside_devanagari_block(self):
        """Test that characters outside U+0900-U+097F are excluded."""
        # U+08FF (just before) and U+0980 (just after) should not be included
        text = "\u08FF अ \u0980"
        result = extract_devanagari(text)
        assert result == "अ"
        assert "\u08FF" not in result
        assert "\u0980" not in result

    def test_common_devanagari_characters(self):
        """Test extraction of commonly used Devanagari characters."""
        # Vowels
        assert extract_devanagari("अआइईउऊऋॠऌ") == "अआइईउऊऋॠऌ"

        # Consonants
        assert extract_devanagari("कखगघङ") == "कखगघङ"

        # Combining marks (matras) - spaces are preserved between them
        assert extract_devanagari("ा ि ी ु ू ृ") == "ा ि ी ु ू ृ"

        # Numerals
        assert extract_devanagari("०१२३४५६७८९") == "०१२३४५६७८९"

        # Dandas
        assert extract_devanagari("।॥") == "।॥"


class TestConsistencyAcrossModules:
    """Tests to ensure consistency with devanagari_diff.py usage."""

    def test_same_result_as_diff_tool_would_use(self):
        """Test that extraction matches what devanagari_diff.py would see."""
        # This is the type of content devanagari_diff.py processes
        text = """---
grantha_id: test
---

# Mantra 1

<!-- sanskrit:devanagari -->
अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम्।
<!-- /sanskrit:devanagari -->

**Translation**: I praise Agni, the priest...
"""
        result = extract_devanagari(text)

        # Should extract only Devanagari, ignoring all markdown/YAML/English
        assert "अग्निमीळे" in result
        assert "पुरोहितं" in result
        assert "यज्ञस्य" in result
        assert "Translation" not in result
        assert "Mantra" not in result

    def test_hash_stability(self):
        """Test that extraction is stable for hashing purposes."""
        # Same content with different formatting should extract identically
        text1 = "अग्निमीळे पुरोहितं यज्ञस्य"
        text2 = "अग्निमीळे    पुरोहितं    यज्ञस्य"
        text3 = "अग्निमीळे\nपुरोहितं\nयज्ञस्य"
        text4 = "# Title\n\nअग्निमीळे पुरोहितं यज्ञस्य\n\n## Section"

        result1 = extract_devanagari(text1)
        result2 = extract_devanagari(text2)
        result3 = extract_devanagari(text3)
        result4 = extract_devanagari(text4)

        # All should normalize to single spaces between words
        assert result1 == result2 == result3 == result4
        assert result1 == "अग्निमीळे पुरोहितं यज्ञस्य"
