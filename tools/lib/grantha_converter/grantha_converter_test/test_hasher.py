"""Tests for hasher module."""

import pytest
from grantha_converter.hasher import (
    normalize_text,
    hash_text,
    extract_content_text,
    hash_passage,
    hash_grantha,
)


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_removes_whitespace(self):
        """Test that all whitespace is removed."""
        text = "Hello   World\n\tTest"
        result = normalize_text(text)
        assert result == "HelloWorldTest"

    def test_removes_devanagari_dandas(self):
        """Test that devanagari dandas are removed."""
        text = "ॐ। शान्तिः॥"
        result = normalize_text(text)
        assert '।' not in result
        assert '॥' not in result

    def test_removes_zero_width_characters(self):
        """Test that zero-width characters are removed."""
        text = "test\u200bword\u200c\u200d"
        result = normalize_text(text)
        assert '\u200b' not in result
        assert '\u200c' not in result
        assert '\u200d' not in result

    def test_removes_punctuation(self):
        """Test that punctuation is removed."""
        text = "Hello, World! How are you?"
        result = normalize_text(text)
        assert ',' not in result
        assert '!' not in result
        assert '?' not in result

    def test_preserves_devanagari_text(self):
        """Test that actual Devanagari characters are preserved."""
        text = "ॐ शान्तिः"
        result = normalize_text(text)
        # Should contain devanagari characters (without spaces)
        assert 'ॐ' in result
        assert 'श' in result
        assert ' ' not in result

    def test_empty_string(self):
        """Test handling of empty string."""
        assert normalize_text("") == ""

    def test_none_input(self):
        """Test handling of None input."""
        assert normalize_text(None) == ""

    def test_unicode_normalization(self):
        """Test that Unicode is normalized to NFC form."""
        # Using combining characters vs precomposed
        text1 = "café"  # with combining acute
        text2 = "café"  # with precomposed é
        # Both should normalize to same form
        assert normalize_text(text1) == normalize_text(text2)


class TestHashText:
    """Tests for hash_text function."""

    def test_same_text_same_hash(self):
        """Test that identical text produces identical hash."""
        text = "ॐ शान्तिः शान्तिः शान्तिः"
        hash1 = hash_text(text)
        hash2 = hash_text(text)
        assert hash1 == hash2

    def test_whitespace_differences_ignored(self):
        """Test that whitespace differences don't affect hash."""
        text1 = "Hello World"
        text2 = "Hello   World"
        text3 = "Hello\n\tWorld"
        assert hash_text(text1) == hash_text(text2) == hash_text(text3)

    def test_punctuation_differences_ignored(self):
        """Test that punctuation differences don't affect hash."""
        text1 = "Hello World"
        text2 = "Hello, World!"
        text3 = "Hello। World॥"
        assert hash_text(text1) == hash_text(text2) == hash_text(text3)

    def test_different_content_different_hash(self):
        """Test that different content produces different hash."""
        text1 = "ॐ शान्तिः"
        text2 = "ॐ भद्रम्"
        assert hash_text(text1) != hash_text(text2)

    def test_returns_hex_string(self):
        """Test that hash is returned as hex string."""
        text = "test"
        result = hash_text(text)
        assert isinstance(result, str)
        # SHA256 produces 64 hex characters
        assert len(result) == 64
        # Should only contain hex characters
        assert all(c in '0123456789abcdef' for c in result)


class TestExtractContentText:
    """Tests for extract_content_text function."""

    def test_extracts_devanagari_only(self):
        """Test extracting only devanagari script."""
        content = {
            'sanskrit': {
                'devanagari': 'देवनागरी',
                'roman': 'romanized',
                'kannada': None
            }
        }
        result = extract_content_text(content, scripts=['devanagari'])
        assert 'देवनागरी' in result
        assert 'romanized' not in result

    def test_extracts_multiple_scripts(self):
        """Test extracting multiple scripts."""
        content = {
            'sanskrit': {
                'devanagari': 'देवनागरी',
                'roman': 'romanized',
                'kannada': None
            }
        }
        result = extract_content_text(content, scripts=['devanagari', 'roman'])
        assert 'देवनागरी' in result
        assert 'romanized' in result

    def test_extracts_all_scripts_when_none(self):
        """Test extracting all scripts when scripts=None."""
        content = {
            'sanskrit': {
                'devanagari': 'देवनागरी',
                'roman': 'romanized',
                'kannada': 'ಕನ್ನಡ'
            }
        }
        result = extract_content_text(content, scripts=None)
        assert 'देवनागरी' in result
        assert 'romanized' in result
        assert 'ಕನ್ನಡ' in result

    def test_includes_english_translation(self):
        """Test that English translation is included."""
        content = {
            'sanskrit': {'devanagari': 'संस्कृत'},
            'english_translation': 'English text'
        }
        result = extract_content_text(content, scripts=['devanagari'])
        assert 'संस्कृत' in result
        assert 'English text' in result

    def test_includes_english_commentary(self):
        """Test that English commentary is included."""
        content = {
            'sanskrit': {'devanagari': 'संस्कृत'},
            'english': 'Commentary in English'
        }
        result = extract_content_text(content, scripts=['devanagari'])
        assert 'संस्कृत' in result
        assert 'Commentary in English' in result

    def test_handles_null_fields(self):
        """Test handling of null fields."""
        content = {
            'sanskrit': {
                'devanagari': 'देवनागरी',
                'roman': None,
                'kannada': None
            },
            'english_translation': None
        }
        result = extract_content_text(content, scripts=['devanagari'])
        assert 'देवनागरी' in result


class TestHashPassage:
    """Tests for hash_passage function."""

    def test_hashes_passage_content(self):
        """Test hashing a single passage."""
        passage = {
            'ref': '1',
            'content': {
                'sanskrit': {'devanagari': 'ॐ शान्तिः'},
                'english_translation': 'Om peace'
            }
        }
        result = hash_passage(passage)
        assert isinstance(result, str)
        assert len(result) == 64

    def test_respects_script_selection(self):
        """Test that script selection affects hash."""
        passage = {
            'ref': '1',
            'content': {
                'sanskrit': {
                    'devanagari': 'देवनागरी',
                    'roman': 'romanized'
                }
            }
        }
        hash_dev_only = hash_passage(passage, scripts=['devanagari'])
        hash_both = hash_passage(passage, scripts=['devanagari', 'roman'])
        # Different content selected should produce different hash
        assert hash_dev_only != hash_both


class TestHashGrantha:
    """Tests for hash_grantha function."""

    def test_hashes_simple_grantha(self):
        """Test hashing a simple grantha with main passages."""
        data = {
            'grantha_id': 'test',
            'passages': [
                {
                    'ref': '1',
                    'content': {
                        'sanskrit': {'devanagari': 'पाठः १'},
                        'english_translation': 'Passage 1'
                    }
                },
                {
                    'ref': '2',
                    'content': {
                        'sanskrit': {'devanagari': 'पाठः २'},
                        'english_translation': 'Passage 2'
                    }
                }
            ]
        }
        result = hash_grantha(data)
        assert isinstance(result, str)
        assert len(result) == 64

    def test_includes_prefatory_material(self):
        """Test that prefatory material is included in hash."""
        data_without = {
            'passages': [
                {'ref': '1', 'content': {'sanskrit': {'devanagari': 'पाठः'}}}
            ]
        }
        data_with = {
            'prefatory_material': [
                {
                    'label': 'शान्तिः',
                    'content': {'sanskrit': {'devanagari': 'ॐ शान्तिः'}}
                }
            ],
            'passages': [
                {'ref': '1', 'content': {'sanskrit': {'devanagari': 'पाठः'}}}
            ]
        }
        hash_without = hash_grantha(data_without)
        hash_with = hash_grantha(data_with)
        assert hash_without != hash_with

    def test_includes_concluding_material(self):
        """Test that concluding material is included in hash."""
        data_without = {
            'passages': [
                {'ref': '1', 'content': {'sanskrit': {'devanagari': 'पाठः'}}}
            ]
        }
        data_with = {
            'passages': [
                {'ref': '1', 'content': {'sanskrit': {'devanagari': 'पाठः'}}}
            ],
            'concluding_material': [
                {
                    'label': 'समाप्तिः',
                    'content': {'sanskrit': {'devanagari': 'इति समाप्तम्'}}
                }
            ]
        }
        hash_without = hash_grantha(data_without)
        hash_with = hash_grantha(data_with)
        assert hash_without != hash_with

    def test_includes_commentaries_when_specified(self):
        """Test that commentaries are included when specified."""
        data = {
            'passages': [
                {'ref': '1', 'content': {'sanskrit': {'devanagari': 'पाठः'}}}
            ],
            'commentaries': [
                {
                    'commentary_id': 'test-commentary',
                    'passages': [
                        {
                            'ref': '1',
                            'content': {
                                'sanskrit': {'devanagari': 'व्याख्या'}
                            }
                        }
                    ]
                }
            ]
        }
        hash_no_commentary = hash_grantha(data, commentaries=None)
        hash_with_commentary = hash_grantha(data, commentaries=['test-commentary'])
        assert hash_no_commentary != hash_with_commentary

    def test_excludes_unspecified_commentaries(self):
        """Test that only specified commentaries are included."""
        data = {
            'passages': [
                {'ref': '1', 'content': {'sanskrit': {'devanagari': 'पाठः'}}}
            ],
            'commentaries': [
                {
                    'commentary_id': 'commentary-1',
                    'passages': [
                        {
                            'ref': '1',
                            'content': {'sanskrit': {'devanagari': 'व्याख्या १'}}
                        }
                    ]
                },
                {
                    'commentary_id': 'commentary-2',
                    'passages': [
                        {
                            'ref': '1',
                            'content': {'sanskrit': {'devanagari': 'व्याख्या २'}}
                        }
                    ]
                }
            ]
        }
        hash_commentary1 = hash_grantha(data, commentaries=['commentary-1'])
        hash_commentary2 = hash_grantha(data, commentaries=['commentary-2'])
        hash_both = hash_grantha(data, commentaries=['commentary-1', 'commentary-2'])

        # Different commentaries should produce different hashes
        assert hash_commentary1 != hash_commentary2
        assert hash_commentary1 != hash_both
        assert hash_commentary2 != hash_both

    def test_respects_script_parameter(self):
        """Test that script parameter affects hash."""
        data = {
            'passages': [
                {
                    'ref': '1',
                    'content': {
                        'sanskrit': {
                            'devanagari': 'देवनागरी',
                            'roman': 'romanized'
                        }
                    }
                }
            ]
        }
        hash_dev = hash_grantha(data, scripts=['devanagari'])
        hash_both = hash_grantha(data, scripts=['devanagari', 'roman'])
        assert hash_dev != hash_both
