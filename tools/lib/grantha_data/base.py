"""Abstract base class for grantha data access.

This module defines BaseGrantha, the abstract interface that all grantha
implementations must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional

from grantha_data.models import (
    Commentary,
    GranthaMetadata,
    Passage,
    Structure,
)


class BaseGrantha(ABC):
    """Abstract base for immutable grantha access.

    All grantha objects are read-only. Use GranthaBuilder to create
    modified versions or construct new granthas.
    """

    # Passage access methods

    @abstractmethod
    def get_passage(
        self,
        ref: str,
        scripts: Optional[List[str]] = None
    ) -> Passage:
        """Retrieves passage by reference.

        Args:
            ref: Hierarchical reference (e.g., "1.1.1").
            scripts: Scripts to include. Defaults to ['devanagari'].

        Returns:
            Passage object with requested content.

        Raises:
            PassageNotFoundError: If ref does not exist.
            ScriptNotAvailableError: If requested script unavailable.
        """

    @abstractmethod
    def get_all_refs(self, passage_type: str = 'main') -> List[str]:
        """Returns all passage refs of given type.

        Args:
            passage_type: Type filter ("main", "prefatory", "concluding").

        Returns:
            List of refs in hierarchical order.
        """

    @abstractmethod
    def iter_passages(
        self,
        passage_type: str = 'main'
    ) -> Iterator[Passage]:
        """Iterates over passages of given type.

        Args:
            passage_type: Type filter ("main", "prefatory", "concluding").

        Yields:
            Passage objects in hierarchical order.
        """

    # Prefatory/concluding material access

    @abstractmethod
    def get_prefatory_material(
        self,
        scripts: Optional[List[str]] = None
    ) -> List[Passage]:
        """Returns all prefatory material passages.

        Args:
            scripts: Scripts to include. Defaults to ['devanagari'].

        Returns:
            List of prefatory passages.
        """

    @abstractmethod
    def get_concluding_material(
        self,
        scripts: Optional[List[str]] = None
    ) -> List[Passage]:
        """Returns all concluding material passages.

        Args:
            scripts: Scripts to include. Defaults to ['devanagari'].

        Returns:
            List of concluding passages.
        """

    # Commentary access methods

    @abstractmethod
    def get_commentary(
        self,
        ref: str,
        commentary_id: str,
        scripts: Optional[List[str]] = None
    ) -> Commentary:
        """Retrieves commentary for a specific passage.

        Args:
            ref: Passage reference.
            commentary_id: Identifier for commentary.
            scripts: Scripts to include. Defaults to ['devanagari'].

        Returns:
            Commentary object.

        Raises:
            CommentaryNotFoundError: If commentary not found for ref.
        """

    @abstractmethod
    def list_commentaries(self) -> List[str]:
        """Returns list of all available commentary IDs.

        Returns:
            List of commentary IDs.
        """

    @abstractmethod
    def get_commentary_metadata(
        self,
        commentary_id: str
    ) -> Dict[str, Any]:
        """Returns metadata for a specific commentary.

        Args:
            commentary_id: Commentary identifier.

        Returns:
            Commentary metadata dictionary.

        Raises:
            CommentaryNotFoundError: If commentary_id not found.
        """

    # Structure and metadata access

    @abstractmethod
    def get_structure(self) -> Structure:
        """Returns hierarchical structure of this grantha.

        Returns:
            Structure object.
        """

    @abstractmethod
    def get_metadata(self) -> GranthaMetadata:
        """Returns grantha metadata.

        Returns:
            GranthaMetadata object.
        """

    # Properties (using @property decorator per Google style)

    @property
    @abstractmethod
    def grantha_id(self) -> str:
        """Returns the grantha ID."""

    @property
    @abstractmethod
    def is_multipart(self) -> bool:
        """Returns True if this is a multi-part grantha."""
