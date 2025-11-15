"""Tests for HTML details to Grantha Markdown converter."""

import pytest
from .html_details_to_grantha_md import (
    parse_toml_frontmatter,
    parse_details_blocks,
    extract_mantra_number,
    clean_sanskrit_content,
    detect_prefatory_material,
    pair_mantras_with_commentaries,
    build_grantha_frontmatter,
    format_passage,
    format_commentary,
    PassageData,
    DetailsBlock
)


class TestParseTomlFrontmatter:
    """Tests for TOML frontmatter parsing."""

    def test_parse_simple_toml(self):
        content = '''+++
title = "वेङ्कटनाथः"
author = "Vedanta Desika"
+++

Content here'''

        frontmatter, remaining = parse_toml_frontmatter(content)

        assert frontmatter is not None
        assert frontmatter['title'] == 'वेङ्कटनाथः'
        assert frontmatter['author'] == 'Vedanta Desika'
        assert remaining.strip() == 'Content here'

    def test_parse_no_frontmatter(self):
        content = 'Just content, no frontmatter'

        frontmatter, remaining = parse_toml_frontmatter(content)

        assert frontmatter is None
        assert remaining == content

    def test_parse_empty_frontmatter(self):
        content = '''+++
+++

Content'''

        frontmatter, remaining = parse_toml_frontmatter(content)

        # Empty frontmatter is treated as no frontmatter
        assert frontmatter is None
        assert content == remaining


class TestParseDetailsBlocks:
    """Tests for parsing HTML <details> blocks."""

    def test_parse_single_block(self):
        content = '''<details open><summary>मूलम्</summary>

ईशावास्यमिदँ सर्वं ॥ १ ॥

</details>'''

        blocks = parse_details_blocks(content)

        assert len(blocks) == 1
        assert blocks[0].summary == 'मूलम्'
        assert blocks[0].is_open is True
        assert 'ईशावास्यमिदँ सर्वं' in blocks[0].content

    def test_parse_multiple_blocks(self):
        content = '''<details open><summary>मूलम्</summary>
Mantra 1
</details>

<details><summary>टीका</summary>
Commentary 1
</details>

<details open><summary>मूलम्</summary>
Mantra 2
</details>'''

        blocks = parse_details_blocks(content)

        assert len(blocks) == 3
        assert blocks[0].summary == 'मूलम्'
        assert blocks[0].is_open is True
        assert blocks[1].summary == 'टीका'
        assert blocks[1].is_open is False
        assert blocks[2].summary == 'मूलम्'

    def test_parse_nested_content(self):
        content = '''<details open><summary>मूलम्</summary>

Line 1
Line 2

Line 3

</details>'''

        blocks = parse_details_blocks(content)

        assert len(blocks) == 1
        assert 'Line 1\nLine 2\n\nLine 3' in blocks[0].content


class TestExtractMantraNumber:
    """Tests for extracting mantra numbers from Sanskrit text."""

    def test_extract_devanagari_number_with_spaces(self):
        text = 'ईशावास्यमिदँ सर्वं ॥ १ ॥'
        assert extract_mantra_number(text) == 1

    def test_extract_devanagari_number_no_spaces(self):
        text = 'ईशावास्यमिदँ सर्वं॥१॥'
        assert extract_mantra_number(text) == 1

    def test_extract_arabic_number(self):
        text = 'Some text ॥ 5 ॥'
        assert extract_mantra_number(text) == 5

    def test_extract_double_digit_devanagari(self):
        text = 'Some text ॥ १८ ॥'
        assert extract_mantra_number(text) == 18

    def test_extract_no_number(self):
        text = 'Some text without number'
        assert extract_mantra_number(text) is None

    def test_extract_from_longer_text(self):
        text = '''ईशावास्यमिदँ सर्वं यत्किंच जगत्यां जगत् ।
तेन त्यक्तेन भुञ्जीथा मा गृधः कस्यस्विद्धनम् ॥ १ ॥'''
        assert extract_mantra_number(text) == 1


class TestCleanSanskritContent:
    """Tests for cleaning Sanskrit content."""

    def test_remove_html_tags(self):
        text = '<span>ईशावास्यमिदँ</span> <strong>सर्वं</strong>'
        cleaned = clean_sanskrit_content(text)
        assert '<' not in cleaned
        assert '>' not in cleaned
        assert 'ईशावास्यमिदँ' in cleaned
        assert 'सर्वं' in cleaned

    def test_normalize_multiple_newlines(self):
        text = 'Line 1\n\n\n\nLine 2'
        cleaned = clean_sanskrit_content(text)
        assert '\n\n\n' not in cleaned
        assert 'Line 1\n\nLine 2' == cleaned

    def test_strip_whitespace(self):
        text = '  \n  Sanskrit text  \n  '
        cleaned = clean_sanskrit_content(text)
        assert cleaned == 'Sanskrit text'

    def test_preserve_internal_formatting(self):
        text = '''Line 1
Line 2

Paragraph 2'''
        cleaned = clean_sanskrit_content(text)
        assert 'Line 1\nLine 2\n\nParagraph 2' == cleaned


class TestDetectPreformatoryMaterial:
    """Tests for detecting prefatory material."""

    def test_detect_prefatory_before_mantra_1(self):
        blocks = [
            DetailsBlock('मूलम्', 'ॐ शान्ति पाठ', True, 1),
            DetailsBlock('मूलम्', 'Mantra ॥ १ ॥', True, 5),
            DetailsBlock('मूलम्', 'Mantra ॥ २ ॥', True, 10)
        ]

        prefatory, first_idx = detect_prefatory_material(blocks)

        assert 0 in prefatory
        assert first_idx == 1

    def test_no_prefatory_material(self):
        blocks = [
            DetailsBlock('मूलम्', 'Mantra ॥ १ ॥', True, 1),
            DetailsBlock('मूलम्', 'Mantra ॥ २ ॥', True, 5)
        ]

        prefatory, first_idx = detect_prefatory_material(blocks)

        assert len(prefatory) == 0
        assert first_idx == 0

    def test_multiple_prefatory_blocks(self):
        blocks = [
            DetailsBlock('मूलम्', 'Invocation', True, 1),
            DetailsBlock('मूलम्', 'Introduction', True, 3),
            DetailsBlock('मूलम्', 'Mantra ॥ १ ॥', True, 5)
        ]

        prefatory, first_idx = detect_prefatory_material(blocks)

        assert 0 in prefatory
        assert 1 in prefatory
        assert first_idx == 2


class TestPairMantrasWithCommentaries:
    """Tests for pairing mantras with commentaries."""

    def test_pair_alternating_blocks(self):
        blocks = [
            DetailsBlock('मूलम्', 'Mantra 1', True, 1),
            DetailsBlock('टीका', 'Commentary 1', False, 3),
            DetailsBlock('मूलम्', 'Mantra 2', True, 5),
            DetailsBlock('टीका', 'Commentary 2', False, 7)
        ]

        pairs = pair_mantras_with_commentaries(blocks)

        assert len(pairs) == 2
        assert pairs[0] == (0, 1)
        assert pairs[1] == (2, 3)

    def test_pair_mantra_without_commentary(self):
        blocks = [
            DetailsBlock('मूलम्', 'Mantra 1', True, 1),
            DetailsBlock('मूलम्', 'Mantra 2', True, 3)
        ]

        pairs = pair_mantras_with_commentaries(blocks)

        assert len(pairs) == 2
        assert pairs[0] == (0, None)
        assert pairs[1] == (1, None)

    def test_pair_mixed_pattern(self):
        blocks = [
            DetailsBlock('मूलम्', 'Mantra 1', True, 1),
            DetailsBlock('टीका', 'Commentary 1', False, 3),
            DetailsBlock('मूलम्', 'Mantra 2', True, 5)
        ]

        pairs = pair_mantras_with_commentaries(blocks)

        assert len(pairs) == 2
        assert pairs[0] == (0, 1)
        assert pairs[1] == (2, None)


class TestBuildGranthaFrontmatter:
    """Tests for building YAML frontmatter."""

    def test_build_basic_frontmatter(self):
        yaml_str = build_grantha_frontmatter(
            grantha_id='test-upanishad',
            canonical_title='टेस्ट उपनिषत्',
            commentary_id='test-commentary',
            commentator='टेस्टर'
        )

        assert '---' in yaml_str
        assert 'grantha_id: test-upanishad' in yaml_str
        assert 'canonical_title: टेस्ट उपनिषत्' in yaml_str
        assert 'part_num: 1' in yaml_str
        assert 'test-commentary:' in yaml_str
        assert 'commentator:' in yaml_str
        assert 'devanagari: टेस्टर' in yaml_str

    def test_frontmatter_structure_levels(self):
        yaml_str = build_grantha_frontmatter(
            grantha_id='test',
            canonical_title='Test',
            commentary_id='test-comm',
            structure_key='Shloka',
            structure_name_devanagari='श्लोकः'
        )

        assert 'structure_levels:' in yaml_str
        assert 'key: Shloka' in yaml_str
        assert 'devanagari: श्लोकः' in yaml_str


class TestFormatPassage:
    """Tests for formatting passages."""

    def test_format_mantra(self):
        passage = PassageData(
            ref='1',
            content='ईशावास्यमिदँ सर्वं ॥ १ ॥',
            passage_type='mantra',
            summary='मूलम्'
        )

        formatted = format_passage(passage)

        assert '# Mantra 1' in formatted
        assert '<!-- sanskrit:devanagari -->' in formatted
        assert 'ईशावास्यमिदँ सर्वं' in formatted
        assert '<!-- /sanskrit:devanagari -->' in formatted

    def test_format_prefatory(self):
        passage = PassageData(
            ref='0',
            content='ॐ शान्तिः',
            passage_type='prefatory',
            summary='मूलम्'
        )

        formatted = format_passage(passage)

        assert '# Prefatory: 0' in formatted
        assert 'devanagari: "शान्तिपाठः"' in formatted
        assert '<!-- sanskrit:devanagari -->' in formatted

    def test_format_concluding(self):
        passage = PassageData(
            ref='99',
            content='समाप्तः',
            passage_type='concluding',
            summary='मूलम्'
        )

        formatted = format_passage(passage)

        assert '# Concluding: 99' in formatted
        assert 'devanagari: "समापनम्"' in formatted


class TestFormatCommentary:
    """Tests for formatting commentaries."""

    def test_format_basic_commentary(self):
        formatted = format_commentary(
            ref='1',
            content='This is commentary text',
            commentary_id='test-comm'
        )

        assert '<!-- commentary: {"commentary_id": "test-comm"} -->' in formatted
        assert '# Commentary: 1' in formatted
        assert '<!-- sanskrit:devanagari -->' in formatted
        assert 'This is commentary text' in formatted
        assert '<!-- /sanskrit:devanagari -->' in formatted

    def test_commentary_preserves_multiline(self):
        content = '''Line 1
Line 2

Paragraph 2'''

        formatted = format_commentary('1', content, 'test')

        assert 'Line 1\nLine 2\n\nParagraph 2' in formatted
