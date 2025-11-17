"""Tests for JsonGrantha implementation."""

from pathlib import Path

import pytest

from grantha_data.json_grantha import JsonGrantha
from grantha_data.exceptions import PassageNotFoundError


class TestJsonGrantha:
    """Tests for JsonGrantha class."""

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

    def test_can_load_json_grantha(self, isavasya_grantha):
        """Tests that JsonGrantha can be instantiated."""
        assert isavasya_grantha is not None

    def test_grantha_id(self, isavasya_grantha):
        """Tests grantha_id property."""
        assert isavasya_grantha.grantha_id == 'isavasya-upanishad'

    def test_get_metadata(self, isavasya_grantha):
        """Tests get_metadata method."""
        metadata = isavasya_grantha.get_metadata()
        assert metadata.grantha_id == 'isavasya-upanishad'
        assert metadata.text_type == 'upanishad'
        assert metadata.language == 'sanskrit'

    def test_get_passage(self, isavasya_grantha):
        """Tests get_passage method."""
        passage = isavasya_grantha.get_passage('1')
        assert passage.ref == '1'
        assert passage.passage_type == 'main'
        assert 'devanagari' in passage.content

    def test_passage_content_contains_expected_text(self, isavasya_grantha):
        """Tests passage content has expected Sanskrit text."""
        passage = isavasya_grantha.get_passage('1')
        content = passage.content['devanagari']
        assert 'ईशावास्यमिदँ सर्वं' in content

    def test_get_all_refs(self, isavasya_grantha):
        """Tests get_all_refs method."""
        refs = isavasya_grantha.get_all_refs()
        assert len(refs) > 0
        assert '1' in refs
        assert '2' in refs

    def test_iter_passages(self, isavasya_grantha):
        """Tests iter_passages method."""
        passages = list(isavasya_grantha.iter_passages())
        assert len(passages) > 0
        assert passages[0].ref == '1'

    def test_get_nonexistent_passage_raises_error(self, isavasya_grantha):
        """Tests that getting nonexistent passage raises error."""
        with pytest.raises(PassageNotFoundError):
            isavasya_grantha.get_passage('999')

    def test_list_commentaries(self, isavasya_grantha):
        """Tests list_commentaries method."""
        commentaries = isavasya_grantha.list_commentaries()
        assert 'isavasya-vedantadesika' in commentaries

    def test_get_commentary(self, isavasya_grantha):
        """Tests get_commentary method."""
        commentary = isavasya_grantha.get_commentary(
            '1',
            'isavasya-vedantadesika'
        )
        assert commentary.commentary_id == 'isavasya-vedantadesika'
        assert commentary.ref == '1'
        assert 'devanagari' in commentary.content

    def test_get_structure(self, isavasya_grantha):
        """Tests get_structure method."""
        structure = isavasya_grantha.get_structure()
        assert structure.get_depth() > 0
        level_keys = structure.get_all_level_keys()
        assert 'Mantra' in level_keys
