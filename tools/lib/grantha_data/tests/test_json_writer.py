"""Tests for JsonWriter implementation."""

import json
from pathlib import Path
import tempfile

import pytest

from grantha_data.json_grantha import JsonGrantha
from grantha_data.writers.json_writer import JsonWriter


class TestJsonWriter:
    """Tests for JsonWriter class."""

    @pytest.fixture
    def isavasya_path(self):
        """Returns path to Isavasya JSON file."""
        return Path(
            'sources/upanishads/vishvas/isavasya/'
            'isa-vedantadesika/isavasya-vedantadesika.json'
        )

    @pytest.fixture
    def isavasya_grantha(self, isavasya_path):
        """Returns JsonGrantha instance for Isavasya."""
        return JsonGrantha(isavasya_path)

    @pytest.fixture
    def writer(self):
        """Returns JsonWriter instance."""
        return JsonWriter()

    def test_write_to_string(self, isavasya_grantha, writer):
        """Tests write_to_string produces valid JSON."""
        json_string = writer.write_to_string(isavasya_grantha)
        # Should be valid JSON
        data = json.loads(json_string)
        assert data['grantha_id'] == 'isavasya-upanishad'

    def test_write_to_file(self, isavasya_grantha, writer):
        """Tests write creates valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'output.json'
            writer.write(isavasya_grantha, output_path)

            # File should exist
            assert output_path.exists()

            # Should be valid JSON
            with output_path.open('r') as f:
                data = json.load(f)
            assert data['grantha_id'] == 'isavasya-upanishad'

    def test_roundtrip_preserves_passages(self, isavasya_grantha, writer):
        """Tests roundtrip preserves passage content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'output.json'
            writer.write(isavasya_grantha, output_path)

            # Read back
            new_grantha = JsonGrantha(output_path)

            # Compare passage content
            original_passage = isavasya_grantha.get_passage('1')
            new_passage = new_grantha.get_passage('1')

            assert original_passage.ref == new_passage.ref
            assert (
                original_passage.content['devanagari'] ==
                new_passage.content['devanagari']
            )

    def test_write_with_script_filter(self, isavasya_grantha, writer):
        """Tests writing with script filter."""
        json_string = writer.write_to_string(
            isavasya_grantha,
            scripts=['devanagari']
        )
        data = json.loads(json_string)

        # Should only have devanagari
        first_passage = data['passages'][0]
        content = first_passage['content']['sanskrit']
        assert 'devanagari' in content
        # Should not have roman if it existed in original
        assert 'roman' not in content

    def test_write_includes_commentaries(self, isavasya_grantha, writer):
        """Tests that commentaries are included."""
        json_string = writer.write_to_string(isavasya_grantha)
        data = json.loads(json_string)

        assert 'commentaries' in data
        assert len(data['commentaries']) > 0
        assert (
            data['commentaries'][0]['commentary_id'] ==
            'isavasya-vedantadesika'
        )
