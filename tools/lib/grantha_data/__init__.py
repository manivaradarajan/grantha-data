"""Grantha data access library.

This library provides a unified interface for accessing grantha content
from different formats (JSON, Markdown, etc.) with validation and
multi-part support.

Typical usage example:

    from grantha_data import MarkdownGrantha

    grantha = MarkdownGrantha('path/to/file.md')
    passage = grantha.get_passage('1.1.1', scripts=['devanagari'])
    print(passage.get_content()['devanagari'])
"""

# Public API exports
__all__ = [
    # Exceptions
    'GranthaDataError',
    'PassageNotFoundError',
    'ScriptNotAvailableError',
    'CommentaryNotFoundError',
    'InvalidRefError',
    'ValidationError',
    # Models
    'Passage',
    'Commentary',
    'Structure',
    'GranthaMetadata',
    # Base
    'BaseGrantha',
    # Implementations
    'JsonGrantha',
    'MarkdownGrantha',
    'MultiPartGrantha',
    # Writers
    'JsonWriter',
    'MarkdownWriter',
    # Validation
    'ValidationResult',
    # Builder
    'GranthaBuilder',
]

from grantha_data.exceptions import (
    GranthaDataError,
    PassageNotFoundError,
    ScriptNotAvailableError,
    CommentaryNotFoundError,
    InvalidRefError,
    ValidationError,
)

from grantha_data.models import (
    Passage,
    Commentary,
    Structure,
    GranthaMetadata,
)

from grantha_data.base import BaseGrantha
from grantha_data.builder import GranthaBuilder
from grantha_data.json_grantha import JsonGrantha
from grantha_data.markdown_grantha import MarkdownGrantha
from grantha_data.multi_part_grantha import MultiPartGrantha
from grantha_data.writers import JsonWriter, MarkdownWriter
from grantha_data.validator import ValidationResult
