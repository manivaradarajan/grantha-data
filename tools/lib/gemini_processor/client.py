# Standard library imports
import os
from pathlib import Path
from typing import Optional

# Third-party imports
from google import genai
from google.genai import types
from google.genai.types import (
    GenerateContentConfig,
    SafetySetting,
    HarmCategory,
    HarmBlockThreshold,
)

# Local imports
from .base_client import BaseGeminiClient
from .file_manager import (
    FileUploadCache,
    upload_file_with_cache,
)

# Reusable config used for Gemini generate_content calls.
GEMINI_CONTENT_CONFIG = GenerateContentConfig(
    safety_settings=[
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
    ],
)


class GeminiClient(BaseGeminiClient):
    """A client for interacting with the Gemini API."""

    def __init__(self, api_key: Optional[str] = None, upload_cache_file: Optional[Path] = None):
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Error: GEMINI_API_KEY environment variable not set.")
        self.client = genai.Client(api_key=api_key)
        self.upload_cache_manager = (
            FileUploadCache(upload_cache_file) if upload_cache_file else None
        )

    def upload_file(
        self,
        file_path: Path,
        use_upload_cache: bool = True,
        verbose: bool = False,
        mime_type: str = "text/markdown",
    ):
        """Uploads a file to the Gemini API, using a cache if available.

        Args:
            file_path: Path to the file to upload.
            use_upload_cache: Whether to use upload caching.
            verbose: Enable verbose logging.
            mime_type: MIME type of the file (e.g., "application/pdf", "text/markdown").

        Returns:
            Uploaded file object from Gemini API.
        """
        cache_manager = self.upload_cache_manager if use_upload_cache else None
        return upload_file_with_cache(
            client=self.client,
            file_path=file_path,
            cache_manager=cache_manager,
            mime_type=mime_type,
            verbose=verbose,
        )

    def generate_content(
        self,
        model: str,
        prompt: str,
        uploaded_file=None,
        config: Optional[GenerateContentConfig] = None,
    ):
        """Calls the Gemini API with the given prompt and optional uploaded file.

        Args:
            model: Gemini model name.
            prompt: Text prompt for the model.
            uploaded_file: Optional uploaded file object from upload_file().
            config: Optional GenerateContentConfig. If None, uses default safety settings.

        Returns:
            Generated text response.

        Raises:
            ValueError: If response is empty.
        """
        # Build Content with proper Part structure
        parts = [types.Part.from_text(text=prompt)]
        if uploaded_file:
            # Convert uploaded file to URI-based Part
            parts.append(types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type))

        contents = [
            types.Content(
                role="user",
                parts=parts,
            ),
        ]

        # Use provided config or default
        generation_config = config if config is not None else GEMINI_CONTENT_CONFIG

        response = self.client.models.generate_content(
            model=model, contents=contents, config=generation_config
        )

        if not response.text:
            raise ValueError("Empty response from Gemini API")

        return response.text
