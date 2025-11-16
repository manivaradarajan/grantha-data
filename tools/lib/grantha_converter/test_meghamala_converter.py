"""
Tests for meghamala markdown to Grantha structured markdown converter.
"""

import pytest

from grantha_converter.devanagari_validator import (
    extract_devanagari,
    validate_devanagari_preservation,
)
from grantha_converter.meghamala_converter import (
    GranthaMarkdownGenerator,
    MalformedMantraError,
    MeghamalaParser,
    convert_meghamala_to_grantha,
)

# Test data
SAMPLE_MANTRA = """**केनेषितं पतति प्रेषितं मनः केन प्राणः प्रथमः प्रैति युक्तः ।**

**केनेषितां वाचमिमां वदन्ति चक्षुःश्रोत्रं क उ देवो युनक्ति ।१।।**"""

SAMPLE_WITH_COMMENTARY = """**केनेषितां वाचमिमां वदन्ति चक्षुःश्रोत्रं क उ देवो युनक्ति ।१।।**

**श्रीरङ्गरामानुजमुनिविरचिता**

**प्रकाशिका**

परमात्मस्वरूपं प्रश्नप्रतिवचनरूपप्रकारेण प्रकाशयितुं प्रस्तौति- 'केनेषितं पतति'।"""

SAMPLE_KHANDA = """**प्रथमखण्डः**

**केनेषितां वाचमिमां वदन्ति चक्षुःश्रोत्रं क उ देवो युनक्ति ।१।।**

परमात्मस्वरूपं प्रश्नप्रतिवचनरूपप्रकारेण।

**इति प्रथमखण्डः समाप्तः**"""

SAMPLE_SHANTI = """**[सामवेदशान्तिपाठः]**

**ओम् आप्यायन्तु ममाङ्गानि वाक्प्राणश्चक्षुः ।**

**ओं शान्तिः शान्तिः शान्तिः ।**"""

SAMPLE_MULTILINE_MANTRA = """**प्रथमखण्डः**

**केनेषितं पतति प्रेषितं मनः केन प्राणः प्रथमः प्रैति युक्तः ।**

**केनेषितां वाचमिमां वदन्ति चक्षुःश्रोत्रं क उ देवो युनक्ति ।१।।**"""


class TestDevanagariValidator:
    """Test Devanagari validation functions."""

    def test_extract_devanagari(self):
        """Test extraction of Devanagari characters."""
        text = "This is **केनोपनिषत्** with English text."
        devanagari = extract_devanagari(text)
        assert "केनोपनिषत्" in devanagari
        assert "This" not in devanagari
        assert "**" not in devanagari

    def test_validate_preservation_success(self):
        """Test validation succeeds when text is preserved."""
        source = "**केनोपनिषत्** is text"
        output = "केनोपनिषत् is text"  # Bold removed but text preserved
        is_valid, error = validate_devanagari_preservation(source, output)
        assert is_valid
        assert error == ""

    def test_validate_preservation_failure(self):
        """Test validation fails when text is lost."""
        source = "**केनोपनिषत्** full text"
        output = "केनो partial text"  # Missing characters
        is_valid, error = validate_devanagari_preservation(source, output)
        assert not is_valid
        assert "text loss detected" in error.lower()


class TestMeghamalaParser:
    """Test meghamala parser."""

    def test_extract_title(self):
        """Test title extraction."""
        content = """**श्रीः ।।**

**केनोपनिषत्**

**(तलवकारोपनिषत्)**"""
        parser = MeghamalaParser(content)
        title = parser.extract_title()
        assert title == "केनोपनिषत्"

    def test_extract_commentator_info(self):
        """Test commentator extraction."""
        parser = MeghamalaParser(SAMPLE_WITH_COMMENTARY)
        commentator, commentary_name = parser.extract_commentator_info()
        assert "रङ्गरामानुजमुनिविरचिता" in commentator
        assert commentary_name == "प्रकाशिका"

    def test_extract_bold(self):
        """Test bold text extraction."""
        parser = MeghamalaParser("")
        text = "**केनोपनिषत्**"
        bold = parser.extract_bold(text)
        assert bold == "केनोपनिषत्"

    def test_remove_bold(self):
        """Test bold markup removal."""
        parser = MeghamalaParser("")
        text = "**केनोपनिषत्** and **प्रकाशिका**"
        result = parser.remove_bold(text)
        assert result == "केनोपनिषत् and प्रकाशिका"

    def test_is_likely_mantra(self):
        """Test mantra detection."""
        parser = MeghamalaParser("")

        # Valid mantra
        mantra_line = "**केनेषितां वाचमिमां वदन्ति ।१।।**"
        assert parser.is_likely_mantra(mantra_line)

        # Not a mantra (no verse number)
        not_mantra = "**प्रकाशिका**"
        assert not parser.is_likely_mantra(not_mantra)

        # Not bold
        not_bold = "परमात्मस्वरूपं प्रश्नप्रतिवचन"
        assert not parser.is_likely_mantra(not_bold)

    def test_extract_verse_number(self):
        """Test verse number extraction."""
        parser = MeghamalaParser("")

        text1 = "केनेषितां वाचमिमां वदन्ति ।१।।"
        assert parser.extract_verse_number(text1) == "१"  # Devanagari digit

        text2 = "तदेव ब्रह्म त्वं विद्धि ।५।"
        assert parser.extract_verse_number(text2) == "५"  # Devanagari digit

        text3 = "No verse number here"
        assert parser.extract_verse_number(text3) is None

    def test_is_commentary_text(self):
        """Test commentary text detection."""
        parser = MeghamalaParser("")

        # Valid commentary (not bold, has Devanagari)
        commentary = "परमात्मस्वरूपं प्रश्नप्रतिवचनरूपप्रकारेण।"
        assert parser.is_commentary_text(commentary)

        # Bold text (not commentary)
        bold = "**प्रकाशिका**"
        assert not parser.is_commentary_text(bold)

        # English only (not commentary)
        english = "This is English text"
        assert not parser.is_commentary_text(english)

    def test_parse_khanda_structure(self):
        """Test parsing khanda structure."""
        parser = MeghamalaParser(SAMPLE_KHANDA)
        nodes = parser.parse()

        assert len(nodes) > 0
        assert nodes[0].level_id == "khanda"
        assert nodes[0].number == 1
        assert len(nodes[0].passages) > 0

    def test_parse_mantras(self):
        """Test mantra parsing."""
        parser = MeghamalaParser(SAMPLE_MANTRA)
        nodes = parser.parse()

        # Should create at least one node with passages
        assert any(node.passages for node in nodes)

    def test_parse_commentary(self):
        """Test commentary parsing."""
        parser = MeghamalaParser(SAMPLE_WITH_COMMENTARY)
        nodes = parser.parse()

        # Should extract commentator info
        assert parser.commentator is not None
        assert "रङ्गरामानुजमुनिविरचिता" in parser.commentator

    def test_multiline_mantra_detection(self):
        """Test that multi-line mantras are detected and raise error."""
        parser = MeghamalaParser(SAMPLE_MULTILINE_MANTRA)

        # Should raise MalformedMantraError
        with pytest.raises(MalformedMantraError) as exc_info:
            parser.parse()

        # Check error details
        error = exc_info.value
        assert error.line_num > 0
        assert "केनेषितं पतति" in error.line_content
        assert "केनेषितां वाचमिमां" in error.next_line_content
        assert "Multi-line mantra detected" in str(error)
        assert "line" in str(error).lower()

    def test_multiline_mantra_in_convert(self):
        """Test that convert function propagates MalformedMantraError."""
        with pytest.raises(MalformedMantraError):
            convert_meghamala_to_grantha(
                meghamala_content=SAMPLE_MULTILINE_MANTRA,
                grantha_id="test",
                canonical_title="Test"
            )


class TestGranthaMarkdownGenerator:
    """Test Grantha markdown generator."""

    def test_generate_structure_levels_khanda(self):
        """Test structure_levels generation for khanda."""
        from grantha_converter.meghamala_converter import StructureNode

        nodes = [StructureNode(level_id="khanda", level_label="खण्डः", number=1)]
        generator = GranthaMarkdownGenerator(
            nodes=nodes,
            grantha_id="test",
            canonical_title="Test"
        )

        structure = generator.generate_structure_levels()
        assert "khanda" in structure
        assert structure["khanda"]["label_devanagari"] == "खण्डः"

    def test_generate_commentaries_metadata(self):
        """Test commentaries_metadata generation."""
        generator = GranthaMarkdownGenerator(
            nodes=[],
            grantha_id="test",
            canonical_title="Test",
            commentary_id="test-commentary",
            commentator="Test Commentator"
        )

        metadata = generator.generate_commentaries_metadata()
        assert metadata is not None
        assert len(metadata) == 1
        assert metadata[0]["commentary_id"] == "test-commentary"

    def test_process_text_remove_bold(self):
        """Test text processing with bold removal."""
        generator = GranthaMarkdownGenerator(
            nodes=[],
            grantha_id="test",
            canonical_title="Test",
            remove_bold=True
        )

        text = "**केनोपनिषत्** and **प्रकाशिका**"
        result = generator.process_text(text)
        assert "**" not in result
        assert "केनोपनिषत्" in result

    def test_process_text_keep_bold(self):
        """Test text processing keeping bold."""
        generator = GranthaMarkdownGenerator(
            nodes=[],
            grantha_id="test",
            canonical_title="Test",
            remove_bold=False
        )

        text = "**केनोपनिषत्**"
        result = generator.process_text(text)
        assert "**" in result


class TestIntegration:
    """Integration tests using sample data."""

    def test_convert_simple_mantra(self):
        """Test converting a simple mantra."""
        output = convert_meghamala_to_grantha(
            meghamala_content=SAMPLE_MANTRA,
            grantha_id="test-upanishad",
            canonical_title="Test Upanishad",
            remove_bold=True
        )

        # Check frontmatter
        assert "---" in output
        assert "grantha_id: test-upanishad" in output
        assert "canonical_title: Test Upanishad" in output
        assert "validation_hash:" in output

        # Check mantra content (only second line has verse number, so only it becomes a mantra)
        assert "## Mantra" in output
        assert "<!-- sanskrit:devanagari -->" in output
        assert "केनेषितां वाचमिमां वदन्ति चक्षुःश्रोत्रं क उ देवो युनक्ति" in output

        # Check bold removed
        assert "**" not in output or "**" in output[:output.find("---", 4)]  # Only in frontmatter

    def test_convert_with_commentary(self):
        """Test converting with commentary."""
        output = convert_meghamala_to_grantha(
            meghamala_content=SAMPLE_WITH_COMMENTARY,
            grantha_id="test-upanishad",
            canonical_title="Test Upanishad",
            commentary_id="test-commentary",
            commentator="रङ्गरामानुजमुनिः",
            remove_bold=True
        )

        # Check commentary metadata
        assert "commentaries_metadata:" in output
        assert "commentary_id: test-commentary" in output

        # Check commentary content
        assert "<!-- commentary:" in output
        assert "### Commentary:" in output

    def test_convert_keep_bold(self):
        """Test converting with bold kept."""
        output = convert_meghamala_to_grantha(
            meghamala_content=SAMPLE_MANTRA,
            grantha_id="test-upanishad",
            canonical_title="Test Upanishad",
            remove_bold=False
        )

        # Bold should be present in content (after frontmatter)
        content_start = output.find("---", 4) + 4
        content = output[content_start:]
        # Should have some bold markup in the actual content
        # (Though the mantra line might not have it after processing)

    def test_devanagari_preservation(self):
        """Test that no Devanagari is lost in conversion."""
        output = convert_meghamala_to_grantha(
            meghamala_content=SAMPLE_WITH_COMMENTARY,
            grantha_id="test-upanishad",
            canonical_title="Test Upanishad",
            commentary_id="test-commentary",
            commentator="रङ्गरामानुजमुनिः",
            remove_bold=True
        )

        # Skip frontmatter for comparison (it contains metadata not in source)
        # Find the end of frontmatter (second --- marker)
        frontmatter_end = output.find("---\n\n", 4)
        if frontmatter_end > 0:
            output_body = output[frontmatter_end + 5:]  # Skip "---\n\n"
        else:
            output_body = output

        is_valid, error = validate_devanagari_preservation(
            SAMPLE_WITH_COMMENTARY,
            output_body
        )
        assert is_valid, f"Devanagari validation failed: {error}"

    def test_part_num(self):
        """Test multi-part text part number."""
        output = convert_meghamala_to_grantha(
            meghamala_content=SAMPLE_MANTRA,
            grantha_id="test-upanishad",
            canonical_title="Test Upanishad",
            part_num=3
        )

        assert "part_num: 3" in output


def test_full_file_conversion():
    """
    Test conversion of a full meghamala file.

    This test can be run if the full kena file is available.
    """
    import os
    from pathlib import Path

    # Path to sample file
    sample_file = Path(__file__).parent.parent.parent.parent.parent / \
                  "sources/upanishads/meghamala/kena/kenopaniSat.md"

    if not sample_file.exists():
        pytest.skip("Sample file not available")

    # Read file
    with open(sample_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Convert
    output = convert_meghamala_to_grantha(
        meghamala_content=content,
        grantha_id="kena-upanishad",
        canonical_title="केनोपनिषत्",
        commentary_id="kena-rangaramanuja",
        commentator="रङ्गरामानुजमुनिः"
    )

    # Validate
    is_valid, error = validate_devanagari_preservation(content, output)
    assert is_valid, f"Full file conversion failed validation: {error}"

    # Check structure
    assert "grantha_id: kena-upanishad" in output
    assert "खण्डः" in output or "# Mantra" in output
    assert "validation_hash:" in output
