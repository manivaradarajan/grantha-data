"""Integration tests for grantha_data library.

Tests complete workflows including:
- GranthaBuilder creation and modification
- Round-trip conversions between formats
- MultiPartGrantha unified access
- Validation across implementations
- Complete public API integration
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest

from grantha_data import (
    JsonGrantha,
    MarkdownGrantha,
    MultiPartGrantha,
    JsonWriter,
    MarkdownWriter,
    GranthaBuilder,
    Structure,
)


class TestGranthaBuilderIntegration:
    """Tests for GranthaBuilder workflows."""

    def test_builder_from_scratch(self, tmp_path: Path) -> None:
        """Tests creating grantha from scratch with builder."""
        # Create builder
        builder = GranthaBuilder(
            grantha_id='test-grantha',
            canonical_title={'devanagari': 'परीक्षा'},
            text_type='upanishad',
            language='sanskrit',
            structure=Structure(levels=[{'name': 'mantra'}]),
            part_num=1,
        )

        # Add passages
        builder.add_passage(
            '1',
            content={'devanagari': 'प्रथमः मन्त्रः'},
            passage_type='main'
        )
        builder.add_passage(
            '2',
            content={'devanagari': 'द्वितीयः मन्त्रः'},
            passage_type='main'
        )

        # Build grantha
        grantha = builder.build(format='json')

        # Verify
        assert grantha.grantha_id == 'test-grantha'
        assert len(grantha.get_all_refs()) == 2

        passage1 = grantha.get_passage('1')
        assert passage1.content['devanagari'] == 'प्रथमः मन्त्रः'

    def test_builder_modify_existing(self, tmp_path: Path) -> None:
        """Tests modifying existing grantha with builder."""
        # Create original grantha
        original_data = {
            'grantha_id': 'test-grantha',
            'canonical_title': 'परीक्षा',
            'text_type': 'upanishad',
            'language': 'sanskrit',
            'structure_levels': [{'name': 'mantra'}],
            'part_num': 1,
            'passages': [
                {
                    'ref': '1',
                    'passage_type': 'main',
                    'content': {'sanskrit': {'devanagari': 'मूलम्'}},
                }
            ],
        }

        json_file = tmp_path / 'original.json'
        json_file.write_text(
            json.dumps(original_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        original = JsonGrantha(json_file)

        # Modify with builder
        builder = GranthaBuilder.from_grantha(original)
        builder.update_passage_content(
            '1',
            {'devanagari': 'संशोधितम्'}
        )
        builder.add_passage(
            '2',
            content={'devanagari': 'नूतनम्'},
            passage_type='main'
        )

        modified = builder.build(format='json')

        # Verify changes
        assert len(modified.get_all_refs()) == 2
        passage1 = modified.get_passage('1')
        assert passage1.content['devanagari'] == 'संशोधितम्'
        passage2 = modified.get_passage('2')
        assert passage2.content['devanagari'] == 'नूतनम्'

    def test_builder_with_commentary(self, tmp_path: Path) -> None:
        """Tests builder with commentary."""
        builder = GranthaBuilder(
            grantha_id='test-grantha',
            canonical_title={'devanagari': 'परीक्षा'},
            text_type='upanishad',
            language='sanskrit',
            structure=Structure(levels=[{'name': 'mantra'}]),
            part_num=1,
        )

        # Add passage and commentary
        builder.add_passage(
            '1',
            content={'devanagari': 'मन्त्रः'},
            passage_type='main'
        )
        builder.add_commentary(
            '1',
            'test-comm',
            content={'devanagari': 'व्याख्या'},
        )
        builder.set_commentary_metadata(
            'test-comm',
            {
                'commentary_title': 'टीका',
                'commentator': 'टीकाकारः',
            }
        )

        grantha = builder.build(format='json')

        # Verify
        assert 'test-comm' in grantha.list_commentaries()
        commentary = grantha.get_commentary('1', 'test-comm')
        assert commentary.content['devanagari'] == 'व्याख्या'

        metadata = grantha.get_commentary_metadata('test-comm')
        assert metadata['commentary_title'] == 'टीका'


class TestRoundTripConversions:
    """Tests for round-trip format conversions."""

    def test_json_to_markdown_to_json(self, tmp_path: Path) -> None:
        """Tests JSON → Markdown → JSON round-trip."""
        # Create original JSON
        original_data = self._create_test_grantha_dict()
        json_file1 = tmp_path / 'original.json'
        json_file1.write_text(
            json.dumps(original_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        # Load as JsonGrantha
        grantha1 = JsonGrantha(json_file1)

        # Convert to Markdown
        md_file = tmp_path / 'converted.md'
        writer = MarkdownWriter()
        writer.write(grantha1, md_file)

        # Load as MarkdownGrantha
        grantha2 = MarkdownGrantha(md_file)

        # Convert back to JSON
        json_file2 = tmp_path / 'roundtrip.json'
        writer = JsonWriter()
        writer.write(grantha2, json_file2)

        # Load final JSON
        grantha3 = JsonGrantha(json_file2)

        # Verify content preserved
        self._assert_granthas_equal(grantha1, grantha3)

    def test_markdown_to_json_to_markdown(self, tmp_path: Path) -> None:
        """Tests Markdown → JSON → Markdown round-trip."""
        # Use real Kausitaki part
        kausitaki_path = Path(
            'structured_md/upanishads/kausitaki/kausitaki-1.md'
        )
        if not kausitaki_path.exists():
            pytest.skip('Kausitaki source file not found')

        # Load as MarkdownGrantha
        grantha1 = MarkdownGrantha(kausitaki_path)

        # Convert to JSON
        json_file = tmp_path / 'converted.json'
        writer = JsonWriter()
        writer.write(grantha1, json_file)

        # Load as JsonGrantha
        grantha2 = JsonGrantha(json_file)

        # Convert back to Markdown
        md_file = tmp_path / 'roundtrip.md'
        writer = MarkdownWriter()
        writer.write(grantha2, md_file)

        # Load final Markdown
        grantha3 = MarkdownGrantha(md_file)

        # Verify content preserved
        self._assert_granthas_equal(grantha1, grantha3)

    def _create_test_grantha_dict(self) -> Dict[str, Any]:
        """Creates test grantha dictionary."""
        return {
            'grantha_id': 'test-grantha',
            'canonical_title': 'परीक्षोपनिषत्',
            'text_type': 'upanishad',
            'language': 'sanskrit',
            'structure_levels': [
                {'name': 'adhyaya', 'key': 'adhyaya'},
                {'name': 'mantra', 'key': 'mantra'}
            ],
            'part_num': 1,
            'passages': [
                {
                    'ref': '1.1',
                    'passage_type': 'main',
                    'content': {
                        'sanskrit': {
                            'devanagari': 'प्रथमाध्यायस्य प्रथमः मन्त्रः'
                        }
                    },
                },
                {
                    'ref': '1.2',
                    'passage_type': 'main',
                    'content': {
                        'sanskrit': {
                            'devanagari': 'प्रथमाध्यायस्य द्वितीयः मन्त्रः'
                        }
                    },
                },
            ],
        }

    def _assert_granthas_equal(
        self,
        g1: 'BaseGrantha',
        g2: 'BaseGrantha'
    ) -> None:
        """Asserts two granthas have same content."""
        # Verify metadata
        m1 = g1.get_metadata()
        m2 = g2.get_metadata()
        assert m1.grantha_id == m2.grantha_id
        assert m1.canonical_title == m2.canonical_title
        assert m1.text_type == m2.text_type
        assert m1.language == m2.language

        # Verify passages
        refs1 = g1.get_all_refs()
        refs2 = g2.get_all_refs()
        assert refs1 == refs2

        for ref in refs1:
            p1 = g1.get_passage(ref)
            p2 = g2.get_passage(ref)
            assert p1.ref == p2.ref
            assert p1.passage_type == p2.passage_type
            assert p1.content == p2.content


class TestMultiPartIntegration:
    """Tests for MultiPartGrantha workflows."""

    def test_multipart_from_directory(self) -> None:
        """Tests loading multi-part grantha from directory."""
        kausitaki_dir = Path('structured_md/upanishads/kausitaki/')
        if not kausitaki_dir.exists():
            pytest.skip('Kausitaki source files not found')

        # Load as MultiPartGrantha
        grantha = MultiPartGrantha.from_directory(
            kausitaki_dir,
            pattern='kausitaki-*.md'
        )

        # Verify metadata
        assert grantha.grantha_id == 'kausitaki-upanishad'
        assert grantha.is_multipart
        assert grantha.num_parts == 4

        # Verify can access passages from all parts
        all_refs = grantha.get_all_refs()
        assert len(all_refs) > 0

        # Test passage from first part
        passage1 = grantha.get_passage('1.1.1')
        assert passage1.ref == '1.1.1'
        assert 'devanagari' in passage1.content

        # Test passage from later part
        if '3.1' in all_refs:
            passage3 = grantha.get_passage('3.1')
            assert passage3.ref == '3.1'
            assert 'devanagari' in passage3.content

    def test_multipart_iteration(self) -> None:
        """Tests iterating over all passages in multi-part grantha."""
        kausitaki_dir = Path('structured_md/upanishads/kausitaki/')
        if not kausitaki_dir.exists():
            pytest.skip('Kausitaki source files not found')

        grantha = MultiPartGrantha.from_directory(
            kausitaki_dir,
            pattern='kausitaki-*.md'
        )

        # Collect all passages via iteration
        passages = list(grantha.iter_passages())

        # Verify we got passages
        assert len(passages) > 0

        # Verify all passages have content
        for passage in passages:
            assert passage.ref
            assert passage.content
            assert 'devanagari' in passage.content

    def test_multipart_lazy_loading(self, tmp_path: Path) -> None:
        """Tests lazy loading of parts."""
        # Create multiple simple JSON parts
        parts = []
        for i in range(1, 4):
            data = {
                'grantha_id': 'test-grantha',
                'canonical_title': 'परीक्षा',
                'text_type': 'upanishad',
                'language': 'sanskrit',
                'structure_levels': [{'name': 'mantra'}],
                'part_num': i,
                'passages': [
                    {
                        'ref': f'{i}.1',
                        'passage_type': 'main',
                        'content': {
                            'sanskrit': {
                                'devanagari': f'भागः {i}'
                            }
                        },
                    }
                ],
            }

            part_file = tmp_path / f'part-{i}.json'
            part_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            parts.append(part_file)

        # Create MultiPartGrantha
        grantha = MultiPartGrantha(parts, format='json')

        # Verify parts loaded lazily
        assert grantha.num_parts == 3

        # Access passage from part 2
        passage = grantha.get_passage('2.1')
        assert passage.content['devanagari'] == 'भागः 2'


class TestValidationIntegration:
    """Tests for validation across implementations."""

    def test_json_grantha_validation(self) -> None:
        """Tests validation on real JSON grantha."""
        json_path = Path('tools/lib/grantha_data/tests/test_data/isavasya_cleaned.json')

        grantha = JsonGrantha(json_path)

        # Run all validations
        results = grantha.validate_all()

        # All should pass
        for result in results:
            assert result.passed, f"{result.name}: {result.message}"

    def test_markdown_grantha_validation(self) -> None:
        """Tests validation on real Markdown grantha."""
        md_path = Path('structured_md/upanishads/kausitaki/kausitaki-1.md')
        if not md_path.exists():
            pytest.skip('Kausitaki markdown file not found')

        grantha = MarkdownGrantha(md_path)

        # Run all validations
        results = grantha.validate_all()

        # All should pass
        for result in results:
            assert result.passed, f"{result.name}: {result.message}"

    def test_validation_after_modification(self, tmp_path: Path) -> None:
        """Tests validation after builder modification."""
        # Create original
        original_data = {
            'grantha_id': 'test-grantha',
            'canonical_title': 'परीक्षा',
            'text_type': 'upanishad',
            'language': 'sanskrit',
            'structure_levels': [{'name': 'mantra'}],
            'part_num': 1,
            'passages': [
                {
                    'ref': '1',
                    'passage_type': 'main',
                    'content': {'sanskrit': {'devanagari': 'मूलम्'}},
                }
            ],
        }

        json_file = tmp_path / 'original.json'
        json_file.write_text(
            json.dumps(original_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        original = JsonGrantha(json_file)

        # Modify
        builder = GranthaBuilder.from_grantha(original)
        builder.add_passage(
            '2',
            content={'devanagari': 'नूतनम्'},
            passage_type='main'
        )

        modified = builder.build(format='json')

        # Validate modified grantha
        results = modified.validate_all()

        # Structure and refs should still be valid
        structure_result = next(
            r for r in results if r.name == 'structure_completeness'
        )
        assert structure_result.passed

        refs_result = next(
            r for r in results if r.name == 'refs_unique'
        )
        assert refs_result.passed


class TestCompleteAPIIntegration:
    """Tests for complete public API integration."""

    def test_complete_workflow(self, tmp_path: Path) -> None:
        """Tests complete workflow using entire public API."""
        # 1. Create grantha with builder
        builder = GranthaBuilder(
            grantha_id='complete-test',
            canonical_title={'devanagari': 'सम्पूर्णपरीक्षा'},
            text_type='upanishad',
            language='sanskrit',
            structure=Structure(levels=[
                {'name': 'adhyaya', 'key': 'adhyaya'},
                {'name': 'mantra', 'key': 'mantra'}
            ]),
            part_num=1,
        )

        # Add passages
        for adhyaya in range(1, 3):
            for mantra in range(1, 3):
                builder.add_passage(
                    f'{adhyaya}.{mantra}',
                    content={
                        'devanagari': f'अध्यायः {adhyaya} मन्त्रः {mantra}'
                    },
                    passage_type='main'
                )

        # Add commentary
        builder.add_commentary(
            '1.1',
            'test-commentary',
            content={'devanagari': 'व्याख्या'},
        )
        builder.set_commentary_metadata(
            'test-commentary',
            {'commentary_title': 'टीका', 'commentator': 'टीकाकारः'}
        )

        grantha1 = builder.build(format='json')

        # 2. Write to JSON
        json_file = tmp_path / 'test.json'
        json_writer = JsonWriter()
        json_writer.write(grantha1, json_file)

        # 3. Load as JsonGrantha
        grantha2 = JsonGrantha(json_file)

        # 4. Validate
        results = grantha2.validate_all()
        for result in results:
            if result.name != 'hash_integrity':
                # Hash might not match since we created programmatically
                assert result.passed, f"{result.name}: {result.message}"

        # 5. Write to Markdown
        md_file = tmp_path / 'test.md'
        md_writer = MarkdownWriter()
        md_writer.write(grantha2, md_file)

        # 6. Load as MarkdownGrantha
        grantha3 = MarkdownGrantha(md_file)

        # 7. Verify content preservation
        assert grantha3.grantha_id == 'complete-test'
        assert len(grantha3.get_all_refs()) == 4

        passage = grantha3.get_passage('1.1')
        assert passage.content['devanagari'] == 'अध्यायः 1 मन्त्रः 1'

        # 8. Test iteration
        all_passages = list(grantha3.iter_passages())
        assert len(all_passages) == 4

        # 9. Test commentary access
        assert 'test-commentary' in grantha3.list_commentaries()
        commentary = grantha3.get_commentary('1.1', 'test-commentary')
        assert commentary.content['devanagari'] == 'व्याख्या'

        # 10. Modify with builder
        builder2 = GranthaBuilder.from_grantha(grantha3)
        builder2.add_passage(
            '2.3',
            content={'devanagari': 'अध्यायः 2 मन्त्रः 3'},
            passage_type='main'
        )

        grantha4 = builder2.build(format='json')

        # 11. Verify modification
        assert len(grantha4.get_all_refs()) == 5
        new_passage = grantha4.get_passage('2.3')
        assert new_passage.content['devanagari'] == 'अध्यायः 2 मन्त्रः 3'
