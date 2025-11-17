"""Domain models for grantha content representation.

This module defines immutable domain objects returned by grantha interfaces.
All classes use frozen dataclasses for immutability.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from grantha_data.exceptions import ScriptNotAvailableError


@dataclass(frozen=True)
class Passage:
    """Represents a single passage from a grantha.

    Immutable. Use GranthaBuilder to create modified versions.

    Attributes:
        ref: Hierarchical reference (e.g., "1.1.1").
        passage_type: Type ("main", "prefatory", "concluding").
        content: Content by script {'devanagari': '...', 'roman': '...'}.
        label: Optional labels by script (for prefatory/concluding).
    """

    ref: str
    passage_type: str
    content: Dict[str, str]
    label: Optional[Dict[str, str]] = None

    def get_content(
        self,
        scripts: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Returns content in requested scripts.

        Args:
            scripts: Script names. Defaults to ['devanagari'].

        Returns:
            Filtered content dict.

        Raises:
            ScriptNotAvailableError: If script not available.
        """
        if scripts is None:
            scripts = ['devanagari']
        return self._filter_content_by_scripts(scripts)

    def _filter_content_by_scripts(
        self,
        scripts: List[str]
    ) -> Dict[str, str]:
        """Filters content dictionary to requested scripts."""
        filtered = {}
        for script in scripts:
            if script in self.content:
                filtered[script] = self.content[script]
        return filtered

    def get_all_available_scripts(self) -> List[str]:
        """Returns all available script names."""
        return list(self.content.keys())

    @property
    def has_label(self) -> bool:
        """Returns True if passage has a label."""
        return self.label is not None

    @property
    def is_main(self) -> bool:
        """Returns True if this is a main passage."""
        return self.passage_type == 'main'

    @property
    def is_prefatory(self) -> bool:
        """Returns True if this is prefatory material."""
        return self.passage_type == 'prefatory'

    @property
    def is_concluding(self) -> bool:
        """Returns True if this is concluding material."""
        return self.passage_type == 'concluding'


@dataclass(frozen=True)
class Commentary:
    """Represents commentary on passage(s).

    Attributes:
        commentary_id: Unique commentary identifier.
        ref: Passage reference or range (e.g., "1" or "1.1.1-5").
        content: Content by script.
        prefatory_material: Optional nested prefatory content.
    """

    commentary_id: str
    ref: str
    content: Dict[str, str]
    prefatory_material: Optional[List[Dict[str, Any]]] = None

    def get_content(
        self,
        scripts: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Returns content in requested scripts."""
        if scripts is None:
            scripts = ['devanagari']
        return self._filter_content_by_scripts(scripts)

    def _filter_content_by_scripts(
        self,
        scripts: List[str]
    ) -> Dict[str, str]:
        """Filters content dictionary to requested scripts."""
        filtered = {}
        for script in scripts:
            if script in self.content:
                filtered[script] = self.content[script]
        return filtered

    @property
    def has_prefatory_material(self) -> bool:
        """Returns True if commentary has prefatory material."""
        return (
            self.prefatory_material is not None
            and len(self.prefatory_material) > 0
        )


@dataclass(frozen=True)
class Structure:
    """Hierarchical structure definition.

    Encapsulates structure_levels and provides navigation methods.

    Attributes:
        levels: structure_levels array from JSON/YAML.
    """

    levels: List[Dict[str, Any]] = field(default_factory=list)

    def get_depth(self) -> int:
        """Returns maximum depth of hierarchy."""
        return self._calculate_depth(self.levels)

    def _calculate_depth(self, levels: List[Dict[str, Any]]) -> int:
        """Recursively calculates maximum depth."""
        if not levels:
            return 0

        max_child_depth = 0
        for level in levels:
            children = level.get('children', [])
            max_child_depth = max(max_child_depth, self._calculate_depth(children))

        return 1 + max_child_depth

    def get_level_name(
        self,
        depth: int,
        script: str = 'devanagari'
    ) -> str:
        """Returns level name at depth in specified script.

        Args:
            depth: Zero-indexed depth (0 = root level).
            script: Script name for level name.

        Returns:
            Level name in requested script.

        Raises:
            IndexError: If depth exceeds structure depth.
            ScriptNotAvailableError: If script not available.
        """
        if depth >= self.get_depth():
            return "Mantra" # Default for leaf level if depth exceeds defined structure
        level = self._get_level_at_depth(depth)
        return self._extract_script_name(level, script)

    def _validate_depth(self, depth: int) -> None:
        """Validates depth is within bounds."""
        max_depth = self.get_depth()
        if depth >= max_depth:
            raise IndexError(
                f"Depth {depth} exceeds maximum depth {max_depth}"
            )

    def _get_level_at_depth(
        self,
        depth: int
    ) -> Dict[str, Any]:
        """Returns structure level at given depth."""
        current_levels = self.levels
        for i in range(depth):
            if not current_levels or 'children' not in current_levels[0]:
                # This means the structure is not as deep as 'depth'
                # We can return a default or raise a more specific error
                raise IndexError(f"Structure does not have a level at depth {depth}")
            current_levels = current_levels[0].get('children', [])

        if not current_levels:
            raise IndexError(f"No level found at depth {depth}")

        return current_levels[0]

    def _extract_script_name(
        self,
        level: Dict[str, Any],
        script: str
    ) -> str:
        """Extracts script name from level dictionary."""
        script_names = level.get('scriptNames', {})
        if script not in script_names:
            return level.get('name', '')
        return script_names[script]

    def get_leaf_level_key(self) -> str:
        """Returns key of deepest (leaf) level."""
        leaf_level = self._get_level_at_depth(self.get_depth() - 1)
        return leaf_level.get('key', '')

    def get_all_level_keys(self) -> List[str]:
        """Returns all level keys from root to leaf."""
        keys = []
        current = self.levels
        while current:
            keys.append(current[0]['key'])
            current = current[0].get('children', [])
        return keys


@dataclass(frozen=True)
class GranthaMetadata:
    """Grantha metadata.

    Attributes:
        grantha_id: Unique identifier.
        canonical_title: Title by script.
        text_type: Type ("upanishad", "commentary", etc.).
        language: Primary language.
        structure: Hierarchical structure.
        part_num: Part number (1 for single-part).
        part_title: Optional part title.
        commentaries_metadata: Commentary metadata by ID.
        validation_hash: Optional SHA256 hash.
        scripts: Available scripts.
    """

    grantha_id: str
    canonical_title: Dict[str, str]
    text_type: str
    language: str
    structure: Structure
    part_num: int = 1
    part_title: Optional[str] = None
    commentaries_metadata: Optional[Dict[str, Any]] = None
    validation_hash: Optional[str] = None
    scripts: List[str] = field(default_factory=lambda: ['devanagari'])

    def get_title(self, script: str = 'devanagari') -> str:
        """Returns canonical title in specified script."""
        if script not in self.canonical_title:
            raise ScriptNotAvailableError(
                f"Title not available in script '{script}'"
            )
        return self.canonical_title[script]

    def has_commentary(self, commentary_id: str) -> bool:
        """Returns True if commentary metadata exists."""
        if self.commentaries_metadata is None:
            return False
        return commentary_id in self.commentaries_metadata

    @property
    def is_multipart(self) -> bool:
        """Returns True if part of multi-part grantha."""
        return self.part_num > 1
