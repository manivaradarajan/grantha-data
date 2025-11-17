"""Lazy content loading utilities.

This module provides utilities for lazy-loading passage content from
source data.
"""

from typing import Any, Dict, Optional


class LazyContentLoader:
    """Lazy loader for passage content.

    Loads content on first access, caches for subsequent calls.
    """

    def __init__(self, source_data: Dict[str, Any]):
        """Initializes loader with source data.

        Args:
            source_data: Raw content dictionary.
        """
        self._source_data = source_data
        self._cached_content: Optional[Dict[str, str]] = None

    def load(self) -> Dict[str, str]:
        """Loads and returns content.

        Returns:
            Content dictionary by script.
        """
        if self._cached_content is None:
            self._cached_content = self._extract_content()
        return self._cached_content

    def _extract_content(self) -> Dict[str, str]:
        """Extracts content from source data."""
        content = self._source_data.get('content', {})
        sanskrit = content.get('sanskrit', {})
        return self._extract_sanskrit_scripts(sanskrit)

    def _extract_sanskrit_scripts(
        self,
        sanskrit: Dict[str, Any]
    ) -> Dict[str, str]:
        """Extracts all available scripts from sanskrit content."""
        result = {}
        for script in ['devanagari', 'roman', 'kannada']:
            if self._script_has_content(sanskrit, script):
                result[script] = sanskrit[script]
        return result

    def _script_has_content(
        self,
        sanskrit: Dict[str, Any],
        script: str
    ) -> bool:
        """Checks if script has non-empty content."""
        return script in sanskrit and sanskrit[script]
