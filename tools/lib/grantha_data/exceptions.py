"""Custom exceptions for grantha_data library.

This module defines all custom exceptions used throughout the grantha_data
library.
"""


class GranthaDataError(Exception):
    """Base exception for all grantha_data errors."""


class PassageNotFoundError(GranthaDataError):
    """Raised when a passage reference is not found."""


class ScriptNotAvailableError(GranthaDataError):
    """Raised when requested script is not available for a passage."""


class CommentaryNotFoundError(GranthaDataError):
    """Raised when commentary is not found for a passage."""


class InvalidRefError(GranthaDataError):
    """Raised when a passage reference has invalid format."""


class ValidationError(GranthaDataError):
    """Raised when grantha validation fails."""
