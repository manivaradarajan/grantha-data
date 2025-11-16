"""Tests for json_to_md module."""

import pytest
import yaml

from grantha_converter.json_to_md import (
    build_hierarchy_tree,
    convert_to_markdown,
    format_content,
    get_header_level_name,
    write_tree_to_markdown,
)


class TestBuildHierarchyTree:
    """Tests for build_hierarchy_tree function."""

    def test_single_level_hierarchy(self):
        """Test building tree from single-level hierarchy."""
        structure_levels = [{'key': 'Mantra', 'scriptNames': {'devanagari': 'मन्त्रः'}}]
        passages = [
            {'ref': '1', 'content': {}},
            {'ref': '2', 'content': {}},
        ]
        tree = build_hierarchy_tree(structure_levels, passages)

        assert '1' in tree
        assert '2' in tree
        assert len(tree['1']['_passages']) == 1
        assert len(tree['2']['_passages']) == 1

    def test_two_level_hierarchy(self):
        """Test building tree from two-level hierarchy."""
        structure_levels = [
            {
                'key': 'Valli',
                'children': [{'key': 'Mantra'}]
            }
        ]
        passages = [
            {'ref': '1.1', 'content': {}},
            {'ref': '1.2', 'content': {}},
            {'ref': '2.1', 'content': {}},
        ]
        tree = build_hierarchy_tree(structure_levels, passages)

        assert '1' in tree
        assert '2' in tree
        assert '1' in tree['1']['_children']
        assert '2' in tree['1']['_children']
        assert '1' in tree['2']['_children']

    def test_three_level_hierarchy(self):
        """Test building tree from three-level hierarchy."""
        structure_levels = [
            {
                'key': 'Mundaka',
                'children': [
                    {
                        'key': 'Khanda',
                        'children': [{'key': 'Mantra'}]
                    }
                ]
            }
        ]
        passages = [
            {'ref': '1.1.1', 'content': {}},
            {'ref': '1.1.2', 'content': {}},
            {'ref': '1.2.1', 'content': {}},
            {'ref': '2.1.1', 'content': {}},
        ]
        tree = build_hierarchy_tree(structure_levels, passages)

        assert '1' in tree
        assert '2' in tree
        assert '1' in tree['1']['_children']
        assert '2' in tree['1']['_children']
        assert '1' in tree['1']['_children']['1']['_children']

    def test_four_level_hierarchy(self):
        """Test building tree from four-level hierarchy."""
        structure_levels = [
            {
                'key': 'Book',
                'children': [
                    {
                        'key': 'Chapter',
                        'children': [
                            {
                                'key': 'Section',
                                'children': [{'key': 'Verse'}]
                            }
                        ]
                    }
                ]
            }
        ]
        passages = [
            {'ref': '1.1.1.1', 'content': {}},
            {'ref': '1.1.1.2', 'content': {}},
            {'ref': '1.2.1.1', 'content': {}},
            {'ref': '2.1.1.1', 'content': {}},
        ]
        tree = build_hierarchy_tree(structure_levels, passages)

        assert '1' in tree
        assert '2' in tree
        # Navigate to deepest level
        level1 = tree['1']['_children']
        assert '1' in level1
        level2 = level1['1']['_children']
        assert '1' in level2
        level3 = level2['1']['_children']
        assert '1' in level3
        assert len(level3['1']['_passages']) == 1


class TestGetHeaderLevelName:
    """Tests for get_header_level_name function."""

    def test_single_level(self):
        """Test getting name at depth 0 in single-level structure."""
        structure_levels = [{'key': 'Mantra'}]
        assert get_header_level_name(structure_levels, 0) == 'Mantra'

    def test_two_levels_depth_0(self):
        """Test getting name at depth 0 in two-level structure."""
        structure_levels = [
            {'key': 'Valli', 'children': [{'key': 'Mantra'}]}
        ]
        assert get_header_level_name(structure_levels, 0) == 'Valli'

    def test_two_levels_depth_1(self):
        """Test getting name at depth 1 in two-level structure."""
        structure_levels = [
            {'key': 'Valli', 'children': [{'key': 'Mantra'}]}
        ]
        assert get_header_level_name(structure_levels, 1) == 'Mantra'

    def test_three_levels(self):
        """Test getting names at all depths in three-level structure."""
        structure_levels = [
            {
                'key': 'Mundaka',
                'children': [
                    {
                        'key': 'Khanda',
                        'children': [{'key': 'Mantra'}]
                    }
                ]
            }
        ]
        assert get_header_level_name(structure_levels, 0) == 'Mundaka'
        assert get_header_level_name(structure_levels, 1) == 'Khanda'
        assert get_header_level_name(structure_levels, 2) == 'Mantra'


class TestFormatContent:
    """Tests for format_content function."""

    def test_formats_devanagari_only(self):
        """Test formatting with only devanagari script."""
        content = {
            'sanskrit': {
                'devanagari': 'देवनागरी',
                'roman': 'romanized'
            }
        }
        result = format_content(content, scripts=['devanagari'])
        assert 'देवनागरी' in result
        assert 'romanized' not in result

    def test_formats_multiple_scripts(self):
        """Test formatting with multiple scripts."""
        content = {
            'sanskrit': {
                'devanagari': 'देवनागरी',
                'roman': 'romanized'
            }
        }
        result = format_content(content, scripts=['devanagari', 'roman'])
        assert 'देवनागरी' in result
        assert 'romanized' in result

    def test_includes_english_translation(self):
        """Test that English translation is included."""
        content = {
            'sanskrit': {'devanagari': 'संस्कृत'},
            'english_translation': 'Sanskrit'
        }
        result = format_content(content, scripts=['devanagari'])
        assert 'Sanskrit' in result

    def test_includes_english_commentary(self):
        """Test that English commentary is included."""
        content = {
            'sanskrit': {'devanagari': 'संस्कृत'},
            'english': 'Commentary'
        }
        result = format_content(content, scripts=['devanagari'])
        assert 'Commentary' in result

    def test_handles_null_fields(self):
        """Test handling of null fields."""
        content = {
            'sanskrit': {
                'devanagari': 'देवनागरी',
                'roman': None
            },
            'english_translation': None
        }
        result = format_content(content, scripts=['devanagari', 'roman'])
        assert 'देवनागरी' in result
        assert 'None' not in result


class TestWriteTreeToMarkdown:
    """Tests for write_tree_to_markdown function."""

    def test_single_level(self):
        """Test writing single-level tree."""
        tree = {
            '1': {'_passages': [{'ref': '1', 'content': {'sanskrit': {'devanagari': 'पाठः १'}}}], '_children': {}},
            '2': {'_passages': [{'ref': '2', 'content': {'sanskrit': {'devanagari': 'पाठः २'}}}], '_children': {}}
        }
        structure_levels = [{'key': 'Mantra'}]
        result = write_tree_to_markdown(tree, structure_levels, ['devanagari'])

        assert '# Mantra 1' in result
        assert '# Mantra 2' in result
        assert 'पाठः १' in result
        assert 'पाठः २' in result

    def test_two_levels(self):
        """Test writing two-level tree."""
        tree = {
            '1': {
                '_passages': [],
                '_children': {
                    '1': {'_passages': [{'ref': '1.1', 'content': {'sanskrit': {'devanagari': 'पाठः १.१'}}}], '_children': {}},
                    '2': {'_passages': [{'ref': '1.2', 'content': {'sanskrit': {'devanagari': 'पाठः १.२'}}}], '_children': {}}
                }
            }
        }
        structure_levels = [
            {'key': 'Valli', 'children': [{'key': 'Mantra'}]}
        ]
        result = write_tree_to_markdown(tree, structure_levels, ['devanagari'])

        assert '# Valli 1' in result
        assert '# Mantra 1.1' in result
        assert '# Mantra 1.2' in result
        assert 'पाठः १.१' in result

    def test_three_levels(self):
        """Test writing three-level tree."""
        tree = {
            '1': {
                '_passages': [],
                '_children': {
                    '1': {
                        '_passages': [],
                        '_children': {
                            '1': {'_passages': [{'ref': '1.1.1', 'content': {'sanskrit': {'devanagari': 'पाठः १.१.१'}}}], '_children': {}}
                        }
                    }
                }
            }
        }
        structure_levels = [
            {
                'key': 'Mundaka',
                'children': [
                    {
                        'key': 'Khanda',
                        'children': [{'key': 'Mantra'}]
                    }
                ]
            }
        ]
        result = write_tree_to_markdown(tree, structure_levels, ['devanagari'])

        assert '# Mundaka 1' in result
        assert '## Khanda 1.1' in result
        assert '# Mantra 1.1.1' in result
        assert 'पाठः १.१.१' in result

    def test_four_levels(self):
        """Test writing four-level tree."""
        tree = {
            '1': {
                '_passages': [],
                '_children': {
                    '1': {
                        '_passages': [],
                        '_children': {
                            '1': {
                                '_passages': [],
                                '_children': {
                                    '1': {'_passages': [{'ref': '1.1.1.1', 'content': {'sanskrit': {'devanagari': 'पाठः १.१.१.१'}}}], '_children': {}}
                                }
                            }
                        }
                    }
                }
            }
        }
        structure_levels = [
            {
                'key': 'Book',
                'children': [
                    {
                        'key': 'Chapter',
                        'children': [
                            {
                                'key': 'Section',
                                'children': [{'key': 'Verse'}]
                            }
                        ]
                    }
                ]
            }
        ]
        result = write_tree_to_markdown(tree, structure_levels, ['devanagari'])

        assert '# Book 1' in result
        assert '## Chapter 1.1' in result
        assert '### Section 1.1.1' in result
        assert '# Verse 1.1.1.1' in result


import copy
import unittest


@pytest.fixture
def base_data():
    """Fixture for a base grantha data structure."""
    return {
        'grantha_id': 'test-grantha',
        'canonical_title': 'परीक्षा',
        'text_type': 'upanishad',
        'language': 'sanskrit',
        'structure_levels': [{'key': 'Mantra'}],
        'passages': [
            {
                'ref': '1',
                'content': {
                    'sanskrit': {'devanagari': 'पाठः १'},
                    'english_translation': 'Passage 1'
                }
            }
        ]
    }

class TestConvertToMarkdown(unittest.TestCase):
    """Tests for convert_to_markdown function."""

    def setUp(self):
        """Set up a base grantha data structure for tests."""
        self.base_data = {
            'grantha_id': 'test-grantha',
            'canonical_title': 'परीक्षा',
            'text_type': 'upanishad',
            'language': 'sanskrit',
            'structure_levels': [{'key': 'Mantra'}],
            'passages': [
                {
                    'ref': '1',
                    'content': {
                        'sanskrit': {'devanagari': 'पाठः १'},
                        'english_translation': 'Passage 1'
                    }
                }
            ]
        }

    def test_basic_conversion(self):
        """Test basic conversion with simple grantha."""
        result = convert_to_markdown(self.base_data, scripts=['devanagari'])

        # Check frontmatter
        self.assertIn('---', result)
        self.assertIn('grantha_id: test-grantha', result)
        self.assertIn('validation_hash: sha256:', result)

        # Check content
        self.assertIn('# Mantra 1', result)
        self.assertIn('पाठः १', result)
        self.assertIn('Passage 1', result)

    def test_includes_prefatory_material(self):
        """Test that prefatory material is included."""
        data = copy.deepcopy(self.base_data)
        data['prefatory_material'] = [{
            'ref': '0.1',
            'label': {'devanagari': 'Intro'},
            'content': {'sanskrit': {'devanagari': 'prefatory text'}}
        }]
        result = convert_to_markdown(data)
        self.assertIn('# Prefatory: 0.1 (devanagari: "Intro")', result)
        self.assertIn('prefatory text', result)

    def test_includes_concluding_material(self):
        """Test that concluding material is included."""
        data = copy.deepcopy(self.base_data)
        data['concluding_material'] = [{
            'ref': '99.1',
            'label': {'devanagari': 'Outro'},
            'content': {'sanskrit': {'devanagari': 'concluding text'}}
        }]
        result = convert_to_markdown(data)
        self.assertIn('# Concluding: 99.1 (devanagari: "Outro")', result)
        self.assertIn('concluding text', result)

    def test_includes_commentary(self):
        """Test that commentary is included when requested."""
        data = copy.deepcopy(self.base_data)
        data['commentaries'] = [
            {
                'commentary_id': 'test-commentary',
                'commentary_title': 'परीक्षाभाष्यम्',
                'commentator': {'devanagari': 'टीकाकारः'},
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
        result = convert_to_markdown(data, scripts=['devanagari'], commentaries=['test-commentary'])

        self.assertIn('# Commentary: टीकाकारः', result)
        self.assertIn('व्याख्या', result)

    def test_excludes_commentary_when_not_requested(self):
        """Test that commentary is excluded when not requested."""
        data = copy.deepcopy(self.base_data)
        data['commentaries'] = [
            {
                'commentary_id': 'test-commentary',
                'commentator': {'devanagari': 'टीकाकारः'},
                'passages': [
                    {
                        'ref': '1',
                        'content': {'sanskrit': {'devanagari': 'व्याख्या'}}
                    }
                ]
            }
        ]
        result = convert_to_markdown(data, scripts=['devanagari'], commentaries=None)

        self.assertNotIn('Commentary', result)
        self.assertNotIn('व्याख्या', result)

    def test_yaml_frontmatter_parseable(self):
        """Test that YAML frontmatter is valid and parseable."""
        result = convert_to_markdown(self.base_data, scripts=['devanagari'])

        # Extract frontmatter
        parts = result.split('---\n')
        self.assertTrue(len(parts) >= 3)
        frontmatter_yaml = parts[1]

        # Parse YAML
        frontmatter = yaml.safe_load(frontmatter_yaml)
        self.assertEqual(frontmatter['grantha_id'], 'test-grantha')
        self.assertEqual(frontmatter['canonical_title'], 'परीक्षा')
        self.assertIn('validation_hash', frontmatter)
        self.assertTrue(frontmatter['validation_hash'].startswith('sha256:'))

    def test_multiple_scripts(self):
        """Test conversion with multiple scripts."""
        data = copy.deepcopy(self.base_data)
        data['passages'][0]['content']['sanskrit']['roman'] = 'devanāgarī'
        result = convert_to_markdown(data, scripts=['devanagari', 'roman'])

        self.assertIn('पाठः १', result)
        self.assertIn('devanāgarī', result)
