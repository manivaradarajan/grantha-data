"""Builder for constructing and modifying grantha content.

This module provides GranthaBuilder for creating new or modified grantha
instances using a fluent interface.
"""

from typing import Any, Dict, List, Optional

from grantha_data.base import BaseGrantha
from grantha_data.models import (
    Commentary,
    Passage,
    Structure,
)


class GranthaBuilder:
    """Builder for creating new or modified grantha instances.

    Provides mutable interface for constructing grantha content.
    Call build() to produce an immutable grantha instance.

    Usage:
        # Create from scratch
        builder = GranthaBuilder(
            grantha_id='my-text',
            canonical_title={'devanagari': 'मम ग्रन्थः'},
            text_type='upanishad',
            language='sanskrit',
            structure=Structure(levels=[...])
        )
        builder.add_passage('1', content={'devanagari': '...'})
        grantha = builder.build()

        # Modify existing
        builder = GranthaBuilder.from_grantha(existing_grantha)
        builder.update_passage_content('1.1', {'devanagari': 'new text'})
        new_grantha = builder.build()
    """

    def __init__(
        self,
        grantha_id: str,
        canonical_title: Dict[str, str],
        text_type: str,
        language: str,
        structure: Structure,
        part_num: int = 1,
        **kwargs
    ) -> None:
        """Initializes empty builder with metadata.

        Args:
            grantha_id: Unique grantha identifier.
            canonical_title: Title by script.
            text_type: Type of text.
            language: Primary language.
            structure: Hierarchical structure.
            part_num: Part number.
            **kwargs: Additional metadata fields.
        """
        self._grantha_id = grantha_id
        self._canonical_title = canonical_title
        self._text_type = text_type
        self._language = language
        self._structure = structure
        self._part_num = part_num
        self._metadata_kwargs = kwargs

        self._passages: Dict[str, Passage] = {}
        self._prefatory: List[Passage] = []
        self._concluding: List[Passage] = []
        self._commentaries: Dict[str, List[Commentary]] = {}
        self._commentary_metadata: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def from_grantha(cls, grantha: BaseGrantha) -> 'GranthaBuilder':
        """Creates builder from existing grantha.

        Args:
            grantha: Existing grantha to copy.

        Returns:
            Builder with all content from grantha.
        """
        metadata = grantha.get_metadata()
        builder = cls(
            grantha_id=metadata.grantha_id,
            canonical_title=metadata.canonical_title,
            text_type=metadata.text_type,
            language=metadata.language,
            structure=metadata.structure,
            part_num=metadata.part_num,
        )

        builder._copy_passages_from_grantha(grantha)
        builder._copy_commentaries_from_grantha(grantha)

        return builder

    def _copy_passages_from_grantha(
        self,
        grantha: BaseGrantha
    ) -> None:
        """Copies all passages from grantha."""
        for passage in grantha.iter_passages('main'):
            self._passages[passage.ref] = passage

        self._prefatory = list(grantha.get_prefatory_material())
        self._concluding = list(grantha.get_concluding_material())

    def _copy_commentaries_from_grantha(
        self,
        grantha: BaseGrantha
    ) -> None:
        """Copies all commentaries from grantha."""
        commentary_ids = grantha.list_commentaries()

        for cid in commentary_ids:
            self._commentary_metadata[cid] = (
                grantha.get_commentary_metadata(cid)
            )
            self._commentaries[cid] = []

            # Copy commentary passages
            for ref in grantha.get_all_refs():
                try:
                    commentary = grantha.get_commentary(ref, cid)
                    self._commentaries[cid].append(commentary)
                except Exception:
                    # Commentary may not exist for all refs
                    continue

    # Passage manipulation (fluent interface)

    def add_passage(
        self,
        ref: str,
        content: Dict[str, str],
        passage_type: str = 'main',
        label: Optional[Dict[str, str]] = None
    ) -> 'GranthaBuilder':
        """Adds a passage.

        Args:
            ref: Hierarchical reference.
            content: Content by script.
            passage_type: Type of passage.
            label: Optional label (for prefatory/concluding).

        Returns:
            Self for method chaining.
        """
        passage = Passage(
            ref=ref,
            passage_type=passage_type,
            content=content,
            label=label
        )
        self._add_passage_to_collection(passage)
        return self

    def _add_passage_to_collection(self, passage: Passage) -> None:
        """Adds passage to appropriate internal collection."""
        if passage.is_main:
            self._passages[passage.ref] = passage
        elif passage.is_prefatory:
            self._prefatory.append(passage)
        elif passage.is_concluding:
            self._concluding.append(passage)

    def update_passage_content(
        self,
        ref: str,
        content: Dict[str, str]
    ) -> 'GranthaBuilder':
        """Updates existing passage content.

        Args:
            ref: Reference of passage to update.
            content: New content by script.

        Returns:
            Self for method chaining.

        Raises:
            KeyError: If ref not found.
        """
        if ref not in self._passages:
            raise KeyError(f"Passage '{ref}' not found")

        existing = self._passages[ref]
        updated = self._create_updated_passage(existing, content)
        self._passages[ref] = updated
        return self

    def _create_updated_passage(
        self,
        existing: Passage,
        new_content: Dict[str, str]
    ) -> Passage:
        """Creates new passage with updated content."""
        return Passage(
            ref=existing.ref,
            passage_type=existing.passage_type,
            content=new_content,
            label=existing.label
        )

    def remove_passage(self, ref: str) -> 'GranthaBuilder':
        """Removes passage by ref.

        Args:
            ref: Reference of passage to remove.

        Returns:
            Self for method chaining.
        """
        if ref in self._passages:
            del self._passages[ref]
        return self

    # Commentary manipulation

    def add_commentary(
        self,
        ref: str,
        commentary_id: str,
        content: Dict[str, str],
        **kwargs
    ) -> 'GranthaBuilder':
        """Adds commentary for passage.

        Args:
            ref: Passage reference.
            commentary_id: Commentary identifier.
            content: Commentary content by script.
            **kwargs: Additional commentary fields.

        Returns:
            Self for method chaining.
        """
        commentary = Commentary(
            commentary_id=commentary_id,
            ref=ref,
            content=content,
            prefatory_material=kwargs.get('prefatory_material'),
        )

        if commentary_id not in self._commentaries:
            self._commentaries[commentary_id] = []

        self._commentaries[commentary_id].append(commentary)
        return self

    def set_commentary_metadata(
        self,
        commentary_id: str,
        metadata: Dict[str, Any]
    ) -> 'GranthaBuilder':
        """Sets metadata for commentary.

        Args:
            commentary_id: Commentary identifier.
            metadata: Commentary metadata.

        Returns:
            Self for method chaining.
        """
        self._commentary_metadata[commentary_id] = metadata
        return self

    # Metadata manipulation

    def set_grantha_id(self, grantha_id: str) -> 'GranthaBuilder':
        """Sets grantha ID."""
        self._grantha_id = grantha_id
        return self

    def set_canonical_title(
        self,
        title: Dict[str, str]
    ) -> 'GranthaBuilder':
        """Sets canonical title."""
        self._canonical_title = title
        return self

    def set_part_num(self, part_num: int) -> 'GranthaBuilder':
        """Sets part number."""
        self._part_num = part_num
        return self

    # Build immutable grantha

    def build(self, format: str = 'json') -> BaseGrantha:
        """Builds immutable grantha instance.

        Args:
            format: Implementation type ('json' or 'markdown').

        Returns:
            Immutable grantha instance.

        Raises:
            ValueError: If format unknown or content invalid.
        """
        self._validate_before_build()

        if format == 'json':
            return self._build_json_grantha()
        elif format == 'markdown':
            # Note: Building markdown grantha requires writing to file first
            raise NotImplementedError(
                "Building MarkdownGrantha from builder requires "
                "writing to file first. Use JsonWriter then load."
            )
        else:
            raise ValueError(f"Unknown format: {format}")

    def _validate_before_build(self) -> None:
        """Validates builder state before building."""
        if not self._grantha_id:
            raise ValueError("grantha_id is required")
        if not self._canonical_title:
            raise ValueError("canonical_title is required")
        if not self._passages:
            raise ValueError("At least one passage is required")

    def _build_json_grantha(self) -> 'JsonGrantha':
        """Builds JsonGrantha instance from builder state."""
        from grantha_data.json_grantha import JsonGrantha

        grantha_dict = self._build_grantha_dict()

        # Create a mock file path since JsonGrantha expects one
        # This is a workaround for the current JsonGrantha implementation
        # which requires a file path for initialization.
        mock_path = f"/tmp/{self._grantha_id}.json"

        return JsonGrantha(mock_path, data=grantha_dict)

    def _build_grantha_dict(self) -> Dict[str, Any]:
        """Builds grantha dictionary from builder state."""
        grantha_dict = {
            'grantha_id': self._grantha_id,
            'canonical_title': self._canonical_title,
            'text_type': self._text_type,
            'language': self._language,
            'part_num': self._part_num,
            'structure': {'levels': self._structure.levels},
            'passages': self._build_passages_list(),
            'prefatory_material': self._build_prefatory_list(),
            'concluding_material': self._build_concluding_list(),
        }

        if self._commentaries:
            grantha_dict['commentaries'] = self._build_commentaries_list()

        return grantha_dict

    def _build_passages_list(self) -> List[Dict[str, Any]]:
        """Builds passages list for JSON."""
        passages = []
        for passage in self._passages.values():
            passages.append({
                'ref': passage.ref,
                'passage_type': passage.passage_type,
                'content': passage.content,
                'label': passage.label,
            })
        return passages

    def _build_prefatory_list(self) -> List[Dict[str, Any]]:
        """Builds prefatory material list for JSON."""
        return [
            {
                'ref': p.ref,
                'passage_type': p.passage_type,
                'content': p.content,
                'label': p.label,
            }
            for p in self._prefatory
        ]

    def _build_concluding_list(self) -> List[Dict[str, Any]]:
        """Builds concluding material list for JSON."""
        return [
            {
                'ref': p.ref,
                'passage_type': p.passage_type,
                'content': p.content,
                'label': p.label,
            }
            for p in self._concluding
        ]

    def _build_commentaries_list(self) -> List[Dict[str, Any]]:
        """Builds commentaries list for JSON."""
        commentaries = []
        for cid, comm_list in self._commentaries.items():
            metadata = self._commentary_metadata.get(cid, {})
            commentary_dict = {
                'commentary_id': cid,
                'commentary_title': metadata.get('commentary_title'),
                'commentator': metadata.get('commentator'),
                'passages': [
                    {
                        'ref': c.ref,
                        'content': c.content,
                    }
                    for c in comm_list
                ]
            }
            commentaries.append(commentary_dict)
        return commentaries
