"""JSON-based grantha implementation.

This module provides JsonGrantha, which reads grantha content from JSON files.
"""

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from grantha_data.base import BaseGrantha
from grantha_data.exceptions import (
    CommentaryNotFoundError,
    PassageNotFoundError,
)
from grantha_data.models import (
    Commentary,
    GranthaMetadata,
    Passage,
    Structure,
)
from grantha_data.validator import GranthaValidator


class JsonGrantha(BaseGrantha, GranthaValidator):
    """Immutable grantha reading from JSON files.

    Implements hybrid loading: metadata loaded immediately on init,
    passage content loaded lazily on first access.
    """

    def __init__(self, file_path: Path, data: Optional[Dict[str, Any]] = None) -> None:
        """Initializes JsonGrantha from a JSON file or data dictionary.

        Args:
            file_path: Path to JSON grantha file.
            data: Optional dictionary with grantha data.

        Raises:
            FileNotFoundError: If file does not exist and data is not provided.
            ValidationError: If JSON structure is invalid.
        """
        self._file_path = file_path
        if data:
            self._data = data
        else:
            self._data = self._load_json_file(file_path)
        self._metadata = self._build_metadata()
        self._passage_index = self._build_passage_index()
        self._commentary_index = self._build_commentary_index()

    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Loads and parses JSON file."""
        with file_path.open('r', encoding='utf-8') as f:
            return json.load(f)

    def _build_metadata(self) -> GranthaMetadata:
        """Builds GranthaMetadata from JSON data."""
        structure_levels = (
            self._data['structure']['levels']
            if 'structure' in self._data
            else self._data['structure_levels']
        )
        return GranthaMetadata(
            grantha_id=self._data['grantha_id'],
            canonical_title=self._extract_canonical_title(),
            text_type=self._data['text_type'],
            language=self._data['language'],
            structure=Structure(levels=structure_levels),
            part_num=self._data.get('part_num', 1),
            part_title=self._data.get('part_title'),
            commentaries_metadata=self._extract_commentaries_metadata(),
            validation_hash=self._data.get('validation_hash'),
            scripts=self._extract_available_scripts(),
        )

    def _extract_canonical_title(self) -> Dict[str, str]:
        """Extracts canonical title from JSON."""
        title = self._data['canonical_title']
        if isinstance(title, str):
            return {'devanagari': title}
        return title

    def _extract_commentaries_metadata(self) -> Optional[Dict[str, Any]]:
        """Extracts commentaries metadata if present."""
        commentaries = self._data.get('commentaries', [])
        if not commentaries:
            return None

        metadata = {}
        for commentary in commentaries:
            commentary_id = commentary['commentary_id']
            metadata[commentary_id] = {
                'commentary_title': commentary.get('commentary_title'),
                'commentator': commentary.get('commentator'),
            }
        return metadata

    def _extract_available_scripts(self) -> List[str]:
        """Extracts list of available scripts from first passage."""
        passages = self._data.get('passages', [])
        if not passages:
            return ['devanagari']

        first_passage = passages[0]
        content = first_passage.get('content', {})
        # Handle both nested 'sanskrit' key and direct script keys
        if 'sanskrit' in content and isinstance(content['sanskrit'], dict):
            content = content['sanskrit']
        return [s for s in ['devanagari', 'roman', 'kannada']
                if s in content and content[s]]

    def _build_passage_index(self) -> Dict[str, Dict[str, Any]]:
        """Builds index mapping refs to passage data."""
        index = {}
        for passage_data in self._data.get('passages', []):
            ref = passage_data['ref']
            index[ref] = passage_data
        return index

    def _build_commentary_index(
        self
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Builds index mapping (commentary_id, ref) to commentary data."""
        index: Dict[str, Dict[str, Dict[str, Any]]] = {}

        for commentary in self._data.get('commentaries', []):
            commentary_id = commentary['commentary_id']
            index[commentary_id] = {}

            for passage in commentary.get('passages', []):
                ref = passage['ref']
                index[commentary_id][ref] = passage

        return index

    # Passage access methods

    def get_passage(
        self,
        ref: str,
        scripts: Optional[List[str]] = None
    ) -> Passage:
        """Retrieves passage by reference."""
        if ref not in self._passage_index:
            raise PassageNotFoundError(f"Passage '{ref}' not found")

        passage_data = self._passage_index[ref]
        return self._create_passage_from_data(passage_data, scripts)

    def _create_passage_from_data(
        self,
        passage_data: Dict[str, Any],
        scripts: Optional[List[str]]
    ) -> Passage:
        """Creates Passage object from JSON data."""
        content = self._extract_passage_content(passage_data, scripts)
        return Passage(
            ref=passage_data['ref'],
            passage_type=passage_data.get('passage_type', 'main'),
            content=content,
            label=passage_data.get('label'),
        )

    def _extract_passage_content(
        self,
        passage_data: Dict[str, Any],
        scripts: Optional[List[str]]
    ) -> Dict[str, str]:
        """Extracts content from passage data."""
        content = passage_data.get('content', {})
        # Handle both nested 'sanskrit' key and direct script keys
        if 'sanskrit' in content and isinstance(content['sanskrit'], dict):
            content = content['sanskrit']

        if scripts is None:
            scripts = self._metadata.scripts

        result = {}
        for script in scripts:
            if script in content and content[script]:
                result[script] = content[script]

        return result

    def get_all_refs(self, passage_type: str = 'main') -> List[str]:
        """Returns all passage refs of given type."""
        return [ref for ref in self._passage_index.keys()]

    def iter_passages(
        self,
        passage_type: str = 'main'
    ) -> Iterator[Passage]:
        """Iterates over passages of given type."""
        for ref in self.get_all_refs(passage_type):
            yield self.get_passage(ref)

    def get_prefatory_material(
        self,
        scripts: Optional[List[str]] = None
    ) -> List[Passage]:
        """Returns all prefatory material passages."""
        prefatory_data = self._data.get('prefatory_material', [])
        return [
            self._create_passage_from_data(p, scripts)
            for p in prefatory_data
        ]

    def get_concluding_material(
        self,
        scripts: Optional[List[str]] = None
    ) -> List[Passage]:
        """Returns all concluding material passages."""
        concluding_data = self._data.get('concluding_material', [])
        return [
            self._create_passage_from_data(p, scripts)
            for p in concluding_data
        ]

    # Commentary access methods

    def get_commentary(
        self,
        ref: str,
        commentary_id: str,
        scripts: Optional[List[str]] = None
    ) -> Commentary:
        """Retrieves commentary for a specific passage."""
        if commentary_id not in self._commentary_index:
            raise CommentaryNotFoundError(
                f"Commentary '{commentary_id}' not found"
            )

        if ref not in self._commentary_index[commentary_id]:
            raise CommentaryNotFoundError(
                f"Commentary '{commentary_id}' not found for ref '{ref}'"
            )

        commentary_data = self._commentary_index[commentary_id][ref]
        return self._create_commentary_from_data(
            commentary_data,
            commentary_id,
            scripts
        )

    def _create_commentary_from_data(
        self,
        commentary_data: Dict[str, Any],
        commentary_id: str,
        scripts: Optional[List[str]]
    ) -> Commentary:
        """Creates Commentary object from JSON data."""
        content = self._extract_passage_content(commentary_data, scripts)
        return Commentary(
            commentary_id=commentary_id,
            ref=commentary_data['ref'],
            content=content,
            prefatory_material=commentary_data.get('prefatory_material'),
        )

    def list_commentaries(self) -> List[str]:
        """Returns list of all available commentary IDs."""
        return list(self._commentary_index.keys())

    def get_commentary_metadata(
        self,
        commentary_id: str
    ) -> Dict[str, Any]:
        """Returns metadata for a specific commentary."""
        if commentary_id not in self._commentary_index:
            raise CommentaryNotFoundError(
                f"Commentary '{commentary_id}' not found"
            )

        if self._metadata.commentaries_metadata is None:
            return {}

        return self._metadata.commentaries_metadata.get(commentary_id, {})

    # Structure and metadata access

    def get_structure(self) -> Structure:
        """Returns hierarchical structure of this grantha."""
        return self._metadata.structure

    def get_metadata(self) -> GranthaMetadata:
        """Returns grantha metadata."""
        return self._metadata

    @property
    def grantha_id(self) -> str:
        """Returns the grantha ID."""
        return self._metadata.grantha_id

    @property
    def is_multipart(self) -> bool:
        """Returns True if this is a multi-part grantha."""
        return self._metadata.part_num > 1
