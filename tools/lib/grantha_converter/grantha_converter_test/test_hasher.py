"""Tests for hasher module.

The hasher module now implements Devanagari-only hashing, where validation_hash
is computed from ONLY the Devanagari characters (U+0900-U+097F) in the text,
ignoring all other scripts, translations, markdown, and whitespace.
"""

import pytest

from grantha_converter.hasher import (
    extract_content_text,
    hash_grantha,
    hash_passage,
    hash_text,
)


class TestHashText:
    """Tests for hash_text function - Devanagari-only hashing."""

    def test_same_devanagari_text_same_hash(self):
        """Test that identical Devanagari text produces identical hash."""
        text = "ॐ शान्तिः शान्तिः शान्तिः"
        hash1 = hash_text(text)
        hash2 = hash_text(text)
        assert hash1 == hash2

    def test_devanagari_whitespace_differences_ignored(self):
        """Test that whitespace differences in Devanagari don't affect hash."""
        text1 = "ॐ शान्तिः"
        text2 = "ॐ   शान्तिः"
        text3 = "ॐ\n\tशान्तिः"
        # All should produce same hash (whitespace is not in Devanagari block)
        assert hash_text(text1) == hash_text(text2) == hash_text(text3)

    def test_non_devanagari_text_ignored(self):
        """Test that non-Devanagari text is completely ignored."""
        text1 = "ॐ शान्तिः"
        text2 = "ॐ शान्तिः with English"
        text3 = "ॐ शान्तिः agnimīḷe purahitam"
        text4 = "agnimīḷe ॐ शान्तिः purahitam"
        # All should produce same hash (only Devanagari is hashed)
        assert hash_text(text1) == hash_text(text2) == hash_text(text3) == hash_text(text4)

    def test_markdown_ignored(self):
        """Test that markdown formatting is ignored."""
        text1 = "ॐ शान्तिः"
        text2 = "# Mantra\n\n**ॐ शान्तिः**"
        text3 = "<!-- sanskrit:devanagari -->\nॐ शान्तिः\n<!-- /sanskrit:devanagari -->"
        # All should produce same hash (markdown is ignored)
        assert hash_text(text1) == hash_text(text2) == hash_text(text3)

    def test_different_devanagari_different_hash(self):
        """Test that different Devanagari content produces different hash."""
        text1 = "ॐ शान्तिः"
        text2 = "ॐ भद्रम्"
        assert hash_text(text1) != hash_text(text2)

    def test_english_only_produces_empty_hash(self):
        """Test that English-only text produces hash of empty string."""
        text = "This is only English text, no Devanagari"
        result = hash_text(text)
        # Should be same as hash of empty string
        empty_hash = hash_text("")
        assert result == empty_hash

    def test_returns_hex_string(self):
        """Test that hash is returned as hex string."""
        text = "ॐ शान्तिः"
        result = hash_text(text)
        assert isinstance(result, str)
        # SHA256 produces 64 hex characters
        assert len(result) == 64
        # Should only contain hex characters
        assert all(c in '0123456789abcdef' for c in result)

    def test_devanagari_numerals_included(self):
        """Test that Devanagari numerals are included in hash."""
        text1 = "मन्त्र १"
        text2 = "मन्त्र २"
        # Different numerals should produce different hashes
        assert hash_text(text1) != hash_text(text2)

    def test_dandas_included(self):
        """Test that Devanagari dandas are included (they're in Devanagari block)."""
        text1 = "ॐ शान्तिः"
        text2 = "ॐ शान्तिः।"
        text3 = "ॐ शान्तिः॥"
        # Dandas are part of Devanagari block, so they affect the hash
        assert hash_text(text1) != hash_text(text2)
        assert hash_text(text2) != hash_text(text3)


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
    """Tests for hash_passage function - Devanagari-only hashing."""

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

    def test_english_translation_ignored(self):
        """Test that English translation doesn't affect hash."""
        passage1 = {
            'ref': '1',
            'content': {
                'sanskrit': {'devanagari': 'ॐ शान्तिः'},
                'english_translation': 'Om peace'
            }
        }
        passage2 = {
            'ref': '1',
            'content': {
                'sanskrit': {'devanagari': 'ॐ शान्तिः'},
                'english_translation': 'Om, peace and tranquility'
            }
        }
        passage3 = {
            'ref': '1',
            'content': {
                'sanskrit': {'devanagari': 'ॐ शान्तिः'},
                # No English translation
            }
        }
        # All should produce same hash (only Devanagari matters)
        assert hash_passage(passage1) == hash_passage(passage2) == hash_passage(passage3)

    def test_roman_script_ignored(self):
        """Test that Roman transliteration doesn't affect hash."""
        passage1 = {
            'ref': '1',
            'content': {
                'sanskrit': {
                    'devanagari': 'ॐ शान्तिः',
                    'roman': 'oṃ śāntiḥ'
                }
            }
        }
        passage2 = {
            'ref': '1',
            'content': {
                'sanskrit': {
                    'devanagari': 'ॐ शान्तिः',
                    # No Roman transliteration
                }
            }
        }
        # Should produce same hash (Roman is ignored)
        assert hash_passage(passage1) == hash_passage(passage2)

    def test_script_parameter_ignored(self):
        """Test that script parameter no longer affects hash (always Devanagari-only)."""
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
        # Both should produce SAME hash now (only Devanagari is ever hashed)
        assert hash_dev_only == hash_both


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

    def test_script_parameter_ignored(self):
        """Test that script parameter no longer affects hash (always Devanagari-only)."""
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
        # Both should produce SAME hash now (only Devanagari is ever hashed)
        assert hash_dev == hash_both

    def test_only_devanagari_affects_hash(self):
        """Test that only Devanagari content affects the hash."""
        data1 = {
            'passages': [
                {
                    'ref': '1',
                    'content': {
                        'sanskrit': {'devanagari': 'पाठः'},
                        'english_translation': 'Passage'
                    }
                }
            ]
        }
        data2 = {
            'passages': [
                {
                    'ref': '1',
                    'content': {
                        'sanskrit': {
                            'devanagari': 'पाठः',
                            'roman': 'pāṭhaḥ'
                        },
                        'english_translation': 'Different translation of the passage'
                    }
                }
            ]
        }
        # Should produce same hash (only Devanagari matters)
        assert hash_grantha(data1) == hash_grantha(data2)
