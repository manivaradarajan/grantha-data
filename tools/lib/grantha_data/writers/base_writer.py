"""Abstract base for grantha writers.

This module defines BaseWriter, the abstract interface for serializing
grantha content to different formats.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from grantha_data.base import BaseGrantha


class BaseWriter(ABC):
    """Abstract base for grantha serialization.

    Writers take any BaseGrantha instance and serialize to a specific format.
    """

    @abstractmethod
    def write(
        self,
        grantha: BaseGrantha,
        output_path: Path,
        scripts: Optional[List[str]] = None,
        commentaries: Optional[List[str]] = None,
        **options
    ) -> None:
        """Writes grantha to file in specific format.

        Args:
            grantha: Grantha to serialize.
            output_path: Output file path.
            scripts: Scripts to include (None = all available).
            commentaries: Commentary IDs to include (None = all).
            **options: Format-specific options.

        Raises:
            IOError: If write fails.
        """

    @abstractmethod
    def write_to_string(
        self,
        grantha: BaseGrantha,
        scripts: Optional[List[str]] = None,
        commentaries: Optional[List[str]] = None,
        **options
    ) -> str:
        """Serializes grantha to string.

        Args:
            grantha: Grantha to serialize.
            scripts: Scripts to include (None = all available).
            commentaries: Commentary IDs to include (None = all).
            **options: Format-specific options.

        Returns:
            Serialized string representation.
        """
