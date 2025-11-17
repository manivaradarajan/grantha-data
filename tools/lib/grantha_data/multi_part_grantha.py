"""Multi-part grantha wrapper providing unified access.

This module provides MultiPartGrantha, which wraps multiple grantha parts
and provides unified access across them.
"""

from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from grantha_data.base import BaseGrantha
from grantha_data.exceptions import PassageNotFoundError
from grantha_data.json_grantha import JsonGrantha
from grantha_data.markdown_grantha import MarkdownGrantha
from grantha_data.models import (
    Commentary,
    GranthaMetadata,
    Passage,
    Structure,
)


class MultiPartGrantha(BaseGrantha):
    """Wrapper providing unified access across multiple grantha parts.

    Routes passage requests to appropriate part based on ref.
    Lazy-loads parts on first access and caches them.
    """

    def __init__(
        self,
        parts: List[Union[Path, BaseGrantha]],
        format: str = 'auto'
    ) -> None:
        """Initializes MultiPartGrantha.

        Args:
            parts: List of file paths or BaseGrantha instances.
            format: Format hint ('json', 'markdown', 'auto').
        """
        self._part_paths = self._extract_part_paths(parts)
        self._format = format
        self._part_cache: Dict[int, BaseGrantha] = {}
        self._ref_to_part_index = self._build_ref_index()
        self._metadata = self._build_unified_metadata()

    def _extract_part_paths(
        self,
        parts: List[Union[Path, BaseGrantha]]
    ) -> List[Path]:
        """Extracts file paths from parts list."""
        paths = []
        for part in parts:
            if isinstance(part, Path):
                paths.append(part)
            elif isinstance(part, BaseGrantha):
                # Store the grantha instance directly
                self._part_cache[len(paths)] = part
                paths.append(None)  # Placeholder
            else:
                raise ValueError(f"Invalid part type: {type(part)}")
        return paths

    def _build_ref_index(self) -> Dict[str, int]:
        """Builds index mapping refs to part indices."""
        ref_index = {}

        for i, _path in enumerate(self._part_paths):
            part = self._get_part(i)
            for ref in part.get_all_refs():
                ref_index[ref] = i

        return ref_index

    def _build_unified_metadata(self) -> GranthaMetadata:
        """Builds unified metadata from first part."""
        first_part = self._get_part(0)
        metadata = first_part.get_metadata()

        # Mark as multipart if more than one part
        return GranthaMetadata(
            grantha_id=metadata.grantha_id,
            canonical_title=metadata.canonical_title,
            text_type=metadata.text_type,
            language=metadata.language,
            structure=metadata.structure,
            part_num=len(self._part_paths),  # Total parts
            commentaries_metadata=metadata.commentaries_metadata,
            validation_hash=None,  # No unified hash
            scripts=metadata.scripts,
        )

    def _get_part(self, index: int) -> BaseGrantha:
        """Gets part at index, loading if necessary."""
        if index in self._part_cache:
            return self._part_cache[index]

        part = self._load_part(index)
        self._part_cache[index] = part
        return part

    def _load_part(self, index: int) -> BaseGrantha:
        """Loads part from file."""
        path = self._part_paths[index]
        if path is None:
            raise ValueError(f"No path for part {index}")

        format = self._determine_format(path)

        if format == 'json':
            return JsonGrantha(path)
        elif format == 'markdown':
            return MarkdownGrantha(path)
        else:
            raise ValueError(f"Unknown format: {format}")

    def _determine_format(self, path: Path) -> str:
        """Determines format from path or hint."""
        if self._format != 'auto':
            return self._format

        suffix = path.suffix.lower()
        if suffix == '.json':
            return 'json'
        elif suffix == '.md':
            return 'markdown'
        else:
            raise ValueError(f"Cannot determine format for {path}")

    @classmethod
    def from_directory(
        cls,
        dir_path: Path,
        pattern: str = "*.md"
    ) -> 'MultiPartGrantha':
        """Creates MultiPartGrantha from directory of part files.

        Args:
            dir_path: Directory containing part files.
            pattern: Glob pattern for matching files.

        Returns:
            MultiPartGrantha instance.
        """
        part_files = sorted(dir_path.glob(pattern))
        if not part_files:
            raise ValueError(f"No files matching {pattern} in {dir_path}")

        format = 'markdown' if pattern.endswith('.md') else 'auto'
        return cls(part_files, format=format)

    @classmethod
    def from_envelope(cls, envelope_path: Path) -> 'MultiPartGrantha':
        """Creates MultiPartGrantha from JSON envelope file.

        Args:
            envelope_path: Path to envelope.json.

        Returns:
            MultiPartGrantha instance.
        """
        import json

        with envelope_path.open('r', encoding='utf-8') as f:
            envelope = json.load(f)

        part_files = envelope.get('parts', [])
        envelope_dir = envelope_path.parent

        part_paths = [envelope_dir / f for f in part_files]
        return cls(part_paths, format='json')

    # BaseGrantha interface implementation

    def get_passage(
        self,
        ref: str,
        scripts: Optional[List[str]] = None
    ) -> Passage:
        """Retrieves passage by reference, routing to correct part."""
        part_index = self._get_part_index_for_ref(ref)
        part = self._get_part(part_index)
        return part.get_passage(ref, scripts)

    def _get_part_index_for_ref(self, ref: str) -> int:
        """Gets part index for given ref."""
        if ref not in self._ref_to_part_index:
            raise PassageNotFoundError(
                f"Passage '{ref}' not found in any part"
            )
        return self._ref_to_part_index[ref]

    def get_all_refs(self, passage_type: str = 'main') -> List[str]:
        """Returns all passage refs across all parts."""
        all_refs = []
        for i in range(len(self._part_paths)):
            part = self._get_part(i)
            all_refs.extend(part.get_all_refs(passage_type))
        return all_refs

    def iter_passages(
        self,
        passage_type: str = 'main'
    ) -> Iterator[Passage]:
        """Iterates over passages across all parts."""
        for i in range(len(self._part_paths)):
            part = self._get_part(i)
            for passage in part.iter_passages(passage_type):
                yield passage

    def get_prefatory_material(
        self,
        scripts: Optional[List[str]] = None
    ) -> List[Passage]:
        """Returns prefatory material from all parts."""
        all_prefatory = []
        for i in range(len(self._part_paths)):
            part = self._get_part(i)
            all_prefatory.extend(part.get_prefatory_material(scripts))
        return all_prefatory

    def get_concluding_material(
        self,
        scripts: Optional[List[str]] = None
    ) -> List[Passage]:
        """Returns concluding material from all parts."""
        all_concluding = []
        for i in range(len(self._part_paths)):
            part = self._get_part(i)
            all_concluding.extend(part.get_concluding_material(scripts))
        return all_concluding

    def get_commentary(
        self,
        ref: str,
        commentary_id: str,
        scripts: Optional[List[str]] = None
    ) -> Commentary:
        """Retrieves commentary, routing to correct part."""
        part_index = self._get_part_index_for_ref(ref)
        part = self._get_part(part_index)
        return part.get_commentary(ref, commentary_id, scripts)

    def list_commentaries(self) -> List[str]:
        """Returns list of all available commentary IDs."""
        # Get from first part (should be consistent across parts)
        first_part = self._get_part(0)
        return first_part.list_commentaries()

    def get_commentary_metadata(
        self,
        commentary_id: str
    ) -> Dict[str, Any]:
        """Returns metadata for a specific commentary."""
        first_part = self._get_part(0)
        return first_part.get_commentary_metadata(commentary_id)

    def get_structure(self) -> Structure:
        """Returns hierarchical structure."""
        return self._metadata.structure

    def get_metadata(self) -> GranthaMetadata:
        """Returns unified grantha metadata."""
        return self._metadata

    @property
    def grantha_id(self) -> str:
        """Returns the grantha ID."""
        return self._metadata.grantha_id

    @property
    def is_multipart(self) -> bool:
        """Returns True (always multipart)."""
        return True

    @property
    def num_parts(self) -> int:
        """Returns number of parts."""
        return len(self._part_paths)
