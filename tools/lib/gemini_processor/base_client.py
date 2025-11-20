"""
Base abstract class for Gemini clients.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class BaseGeminiClient(ABC):
    """Abstract base class for Gemini API clients."""

    @abstractmethod
    def upload_file(
        self, file_path: Path, use_upload_cache: bool = True, verbose: bool = False
    ):
        """
        Uploads a file to the Gemini API.

        Args:
            file_path: Path to the file to upload
            use_upload_cache: Whether to use upload caching
            verbose: Whether to print verbose output

        Returns:
            An uploaded file object or None
        """
        pass

    @abstractmethod
    def generate_content(
        self,
        model: str,
        prompt: str,
        uploaded_file=None,
    ) -> str:
        """
        Generates content using the Gemini API.

        Args:
            model: The model name to use
            prompt: The prompt text
            uploaded_file: Optional uploaded file object

        Returns:
            The generated content as a string
        """
        pass
