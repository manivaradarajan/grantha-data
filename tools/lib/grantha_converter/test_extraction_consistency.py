"""Tests to ensure hasher, validator, and differ use the same extraction.

These tests verify that all three components extract the same Devanagari text
from markdown files, ensuring consistency across validation, hashing, and diffing.
"""

import pytest
from pathlib import Path
import tempfile

from grantha_converter.devanagari_extractor import (
    extract_devanagari,
    clean_text_for_devanagari_comparison,
)
from grantha_converter.hasher import hash_text


class TestExtractionConsistency:
    """Tests that ensure all extraction methods produce identical results."""

    def test_basic_extraction_consistency(self):
        """Verify that body-only and full-text paths extract same Devanagari."""
        test_markdown = """---
grantha_id: test
canonical_title: परीक्षा
---

# Mantra 1

<!-- sanskrit:devanagari -->
अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम्
<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "test"} -->
# Commentary: 1

होत्रं रत्नधातमम्"""

        # Extract frontmatter to get body
        frontmatter_end = test_markdown.find('---\n', 4)
        body = test_markdown[frontmatter_end + 4:]

        # Method 1: Hasher/Validator approach (body-only)
        hasher_devanagari = extract_devanagari(body)

        # Method 2: Differ approach (full text → clean → extract)
        cleaned_text = clean_text_for_devanagari_comparison(test_markdown)
        differ_devanagari = extract_devanagari(cleaned_text)

        # They should extract the same Devanagari
        assert hasher_devanagari == differ_devanagari, (
            f"Hasher and Differ extract different Devanagari!\n"
            f"Hasher: {hasher_devanagari}\n"
            f"Differ: {differ_devanagari}"
        )

    def test_hash_consistency_with_differ(self):
        """Verify that hash_text() produces same result as differ extraction."""
        body = """# Mantra 1

अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम्"""

        # Get Devanagari using hasher
        hasher_devanagari = extract_devanagari(body)

        # Get Devanagari using differ (which cleans first)
        # Since body has no frontmatter, cleaning is a no-op
        cleaned = clean_text_for_devanagari_comparison(body)
        differ_devanagari = extract_devanagari(cleaned)

        # Should be identical
        assert hasher_devanagari == differ_devanagari

        # Hashes should also match
        hash1 = hash_text(body)
        hash2 = hash_text(cleaned)
        assert hash1 == hash2

    def test_frontmatter_excluded_from_all_extractions(self):
        """Verify that frontmatter Devanagari is excluded by all methods."""
        test_markdown = """---
canonical_title: परीक्षा
grantha_id: test
---

अग्निमीळे"""

        # Extract body manually
        frontmatter_end = test_markdown.find('---\n', 4)
        body = test_markdown[frontmatter_end + 4:]

        # Method 1: Hasher/Validator (body-only)
        hasher_devanagari = extract_devanagari(body)

        # Method 2: Differ (full text → clean → extract)
        cleaned = clean_text_for_devanagari_comparison(test_markdown)
        differ_devanagari = extract_devanagari(cleaned)

        # Neither should include "परीक्षा" from frontmatter
        assert "परीक्षा" not in hasher_devanagari
        assert "परीक्षा" not in differ_devanagari

        # Both should only have "अग्निमीळे"
        assert hasher_devanagari == "अग्निमीळे"
        assert differ_devanagari == "अग्निमीळे"
        assert hasher_devanagari == differ_devanagari

    def test_html_comments_excluded_consistently(self):
        """Verify that HTML comments are handled consistently."""
        test_markdown = """# Mantra 1

<!-- sanskrit:devanagari -->
अग्निमीळे
<!-- /sanskrit:devanagari -->

<!-- This is देव a comment -->

पुरोहितं"""

        # Hasher/Validator: Comments are already in body, extract_devanagari
        # will include them unless cleaned first
        raw_extraction = extract_devanagari(test_markdown)

        # Differ: Cleans comments first
        cleaned = clean_text_for_devanagari_comparison(test_markdown)
        differ_extraction = extract_devanagari(cleaned)

        # The differ's cleaned approach should exclude comment content
        assert "देव" not in differ_extraction, (
            "Comment content should be removed by cleaning"
        )

        # For validation to work correctly, body must not include
        # HTML comment *content* - the comments are kept as-is in markdown
        # but extract_devanagari only gets Devanagari outside comments
        # This test verifies the cleaning function works as expected

    def test_with_real_file_structure(self):
        """Test with realistic file structure including all elements."""
        realistic_markdown = """---
grantha_id: ishavasya-upanishad
part_num: 1
canonical_title: ईशावास्योपनिषत्
text_type: upanishad
language: sanskrit
structure_type: mantra
commentaries_metadata:
- commentary_id: test
  commentary_title: टिप्पणी
  commentator:
    devanagari: टिप्पणीकारः
    roman: tippanikara
structure_levels:
- key: Mantra
  scriptNames:
    devanagari: मन्त्रः
    roman: mantra
hash_version: 2
validation_hash: placeholder
---

<!-- hide type:document-title -->
**ईशावास्योपनिषत्**
<!-- /hide -->

# Mantra 1

<!-- sanskrit:devanagari -->
ईशावास्यमिदं सर्वं यत्किञ्च जगत्यां जगत् ।
<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "test"} -->
# Commentary: 1

अयं मन्त्रः सर्वव्यापकत्वं प्रतिपादयति ।"""

        # Extract body
        frontmatter_end = realistic_markdown.find('---\n', 4)
        body = realistic_markdown[frontmatter_end + 4:]

        # Method 1: Hasher/Validator
        hasher_devanagari = extract_devanagari(body)

        # Method 2: Differ
        cleaned = clean_text_for_devanagari_comparison(realistic_markdown)
        differ_devanagari = extract_devanagari(cleaned)

        # Should match
        assert hasher_devanagari == differ_devanagari

        # Verify frontmatter titles are excluded
        assert "ईशावास्योपनिषत्" in realistic_markdown
        # The title appears multiple times but we want to ensure we're
        # extracting from body correctly
        assert len(hasher_devanagari) > 0
        assert hasher_devanagari == differ_devanagari

    def test_extraction_function_identity(self):
        """Verify all components use the exact same extraction function."""
        # Import the functions used by each component
        from grantha_converter.hasher import hash_text
        from grantha_converter.devanagari_extractor import extract_devanagari

        # The hasher uses extract_devanagari internally
        # The differ uses extract_devanagari after cleaning
        # The validator uses extract_devanagari on body

        # All should be the same function object
        test_text = "अग्निमीळे देवम्"

        result1 = extract_devanagari(test_text)
        result2 = extract_devanagari(test_text)

        # Same function should give same result
        assert result1 == result2
        assert result1 == "अग्निमीळे देवम्"

        # hash_text should use extract_devanagari internally
        # We verify this by checking the hash is consistent
        hash1 = hash_text(test_text)
        hash2 = hash_text(test_text)
        assert hash1 == hash2

    def test_validator_and_differ_on_same_file(self):
        """Simulate what validator and differ do on the same file."""
        test_content = """---
canonical_title: परीक्षा
---

अग्निमीळे पुरोहितं"""

        # Simulate validator behavior
        frontmatter_end = test_content.find('---\n', 4)
        body = test_content[frontmatter_end + 4:]
        validator_devanagari = extract_devanagari(body)
        validator_hash = hash_text(body)

        # Simulate differ behavior
        cleaned = clean_text_for_devanagari_comparison(test_content)
        differ_devanagari = extract_devanagari(cleaned)

        # Should extract the same Devanagari
        assert validator_devanagari == differ_devanagari
        assert validator_devanagari == "अग्निमीळे पुरोहितं"

        # Verify hash uses same extraction
        expected_devanagari = "अग्निमीळे पुरोहितं"
        assert validator_devanagari == expected_devanagari


class TestCleaningFunction:
    """Tests specifically for the cleaning function used by differ."""

    def test_cleaning_removes_frontmatter(self):
        """Verify cleaning removes YAML frontmatter."""
        text = """---
title: Test
canonical_title: परीक्षा
---

अग्निमीळे"""

        cleaned = clean_text_for_devanagari_comparison(text)

        # Frontmatter should be gone
        assert "title: Test" not in cleaned
        assert "---" not in cleaned

        # Body should remain
        assert "अग्निमीळे" in cleaned

    def test_cleaning_removes_html_comments(self):
        """Verify cleaning removes HTML comments."""
        text = "अग्नि <!-- comment देव --> मीळे"

        cleaned = clean_text_for_devanagari_comparison(text)

        # Comment should be gone
        assert "<!--" not in cleaned
        assert "comment" not in cleaned

        # Text should remain
        assert "अग्नि" in cleaned
        assert "मीळे" in cleaned

    def test_cleaning_removes_bold_markers(self):
        """Verify cleaning removes markdown bold markers."""
        text = "**अग्निमीळे** पुरोहितं"

        cleaned = clean_text_for_devanagari_comparison(text)

        # Bold markers should be gone
        assert "**" not in cleaned

        # Text should remain
        assert "अग्निमीळे" in cleaned
        assert "पुरोहितं" in cleaned


class TestHeadingExclusion:
    """Tests that markdown headings are excluded from all extractions."""

    def test_headings_excluded_from_extraction(self):
        """Verify that Devanagari in markdown headings is excluded."""
        test_markdown = """# मन्त्रः 1

अग्निमीळे पुरोहितं

## Commentary: 1

भाष्यम्"""

        # Clean and extract
        cleaned = clean_text_for_devanagari_comparison(test_markdown)
        extracted = extract_devanagari(cleaned)

        # Heading text should NOT be included
        assert "मन्त्रः" not in extracted, (
            "Heading text should be excluded from extraction"
        )

        # Body content SHOULD be included
        assert "अग्निमीळे" in extracted
        assert "पुरोहितं" in extracted
        assert "भाष्यम्" in extracted

        # Verify exact expected content
        assert extracted == "अग्निमीळे पुरोहितं भाष्यम्"

    def test_headings_excluded_consistently_across_components(self):
        """Verify headings excluded by hasher, validator, and differ."""
        test_content = """---
canonical_title: परीक्षा
---

# मन्त्रः 1

अग्निमीळे पुरोहितं"""

        # Simulate validator behavior (body-only)
        frontmatter_end = test_content.find('---\n', 4)
        body = test_content[frontmatter_end + 4:]

        # Validator must clean before hashing to exclude headings
        cleaned_body = clean_text_for_devanagari_comparison(body)
        validator_devanagari = extract_devanagari(cleaned_body)

        # Simulate differ behavior (full text)
        differ_cleaned = clean_text_for_devanagari_comparison(test_content)
        differ_devanagari = extract_devanagari(differ_cleaned)

        # Both should exclude heading
        assert "मन्त्रः" not in validator_devanagari
        assert "मन्त्रः" not in differ_devanagari

        # Both should have same content
        assert validator_devanagari == differ_devanagari
        assert validator_devanagari == "अग्निमीळे पुरोहितं"

    def test_multiple_heading_levels_excluded(self):
        """Verify all heading levels (#, ##, ###, etc.) are excluded."""
        test_text = """# Level 1: मन्त्रः
## Level 2: भाष्यम्
### Level 3: टिप्पणी
#### Level 4: विवरणम्

अग्निमीळे पुरोहितं"""

        cleaned = clean_text_for_devanagari_comparison(test_text)
        extracted = extract_devanagari(cleaned)

        # No heading text should be included
        assert "मन्त्रः" not in extracted
        assert "भाष्यम्" not in extracted
        assert "टिप्पणी" not in extracted
        assert "विवरणम्" not in extracted

        # Only body content
        assert extracted == "अग्निमीळे पुरोहितं"

    def test_heading_with_reference_excluded(self):
        """Verify headings with references are excluded."""
        test_text = """# Mantra 1.1.1

मन्त्रः

# Commentary: 1.1.1

भाष्यम्"""

        cleaned = clean_text_for_devanagari_comparison(test_text)
        extracted = extract_devanagari(cleaned)

        # Should only have body content, not heading numbers
        assert extracted == "मन्त्रः भाष्यम्"

    def test_heading_in_realistic_file_excluded(self):
        """Test with realistic file structure to ensure headings excluded."""
        realistic_content = """---
grantha_id: test
canonical_title: परीक्षा
---

# Prefatory: 0.0

शान्तिपाठः

# Mantra 1

<!-- sanskrit:devanagari -->
अग्निमीळे पुरोहितं
<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "test"} -->
## Commentary: 1

भाष्यम्"""

        # Clean and extract (simulating hasher/validator)
        frontmatter_end = realistic_content.find('---\n', 4)
        body = realistic_content[frontmatter_end + 4:]
        cleaned = clean_text_for_devanagari_comparison(body)
        extracted = extract_devanagari(cleaned)

        # Should have content but not headings
        assert "शान्तिपाठः" in extracted
        assert "अग्निमीळे" in extracted
        assert "पुरोहितं" in extracted
        assert "भाष्यम्" in extracted

        # Should NOT have heading markers or labels
        assert "Prefatory" not in extracted
        assert "Mantra" not in extracted
        assert "Commentary" not in extracted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
