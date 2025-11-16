"""Integration tests using actual library files."""

import json
import tempfile
from pathlib import Path

import pytest

from grantha_converter.json_to_md import json_file_to_markdown_file
from grantha_converter.md_to_json import convert_to_json

# Get all library JSON files
LIBRARY_DIR = Path('public/data/library')
LIBRARY_FILES = list(LIBRARY_DIR.glob('*.json')) if LIBRARY_DIR.exists() else []


class TestLibraryRoundtrip:
    """Test round-trip conversion with actual library files."""

    @pytest.mark.parametrize('json_file', LIBRARY_FILES, ids=lambda p: p.stem)
    def test_roundtrip_core_text(self, json_file):
        """Test round-trip conversion of core text (no commentaries)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / f"{json_file.stem}.md"
            roundtrip_path = Path(tmpdir) / f"{json_file.stem}_roundtrip.json"

            # Convert JSON → MD
            json_file_to_markdown_file(
                str(json_file),
                str(md_path),
                scripts=['devanagari'],
                commentaries=None
            )

            assert md_path.exists()

            # Convert MD → JSON
            with open(md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            print(f"Generated Markdown for {json_file.stem}:\n{md_content}")
            json_data = convert_to_json(md_content)
            with open(roundtrip_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

            assert roundtrip_path.exists()

            # Load both files
            with open(json_file, 'r') as f:
                original = json.load(f)

            with open(roundtrip_path, 'r') as f:
                roundtrip = json.load(f)

            # Verify key fields match
            assert roundtrip['grantha_id'] == original['grantha_id']
            assert roundtrip['canonical_title'] == original['canonical_title']
            assert len(roundtrip['passages']) == len(original['passages'])

            # Verify passage refs match
            for orig_p, rt_p in zip(original['passages'], roundtrip['passages']):
                assert rt_p['ref'] == orig_p['ref']

    @pytest.mark.parametrize('json_file', LIBRARY_FILES, ids=lambda p: p.stem)
    def test_markdown_generation(self, json_file):
        """Test that markdown is generated without errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / f"{json_file.stem}.md"

            # Convert JSON → MD
            json_file_to_markdown_file(
                str(json_file),
                str(md_path),
                scripts=['devanagari'],
                commentaries=None
            )

            assert md_path.exists()

            # Read and verify basic structure
            content = md_path.read_text(encoding='utf-8')

            # Should have frontmatter
            assert content.startswith('---\n')
            assert 'grantha_id:' in content
            assert 'validation_hash: sha256:' in content

            # Should have at least one header
            assert '\n# ' in content


@pytest.mark.skipif(not LIBRARY_FILES, reason="No library files found")
def test_all_library_files_exist():
    """Verify we found library files to test."""
    assert len(LIBRARY_FILES) > 0
    print(f"\nFound {len(LIBRARY_FILES)} library files:")
    for f in LIBRARY_FILES:
        print(f"  - {f.name}")
