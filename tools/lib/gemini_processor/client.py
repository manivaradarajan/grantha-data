# Standard library imports
import os
from pathlib import Path
from typing import Optional

# Third-party imports
from google import genai
from google.genai.types import (
    GenerateContentConfig,
    SafetySetting,
    HarmCategory,
    HarmBlockThreshold,
)

# Local imports
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


class GeminiClient:
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
        self, file_path: Path, use_upload_cache: bool = True, verbose: bool = False
    ):
        """Uploads a file to the Gemini API, using a cache if available."""
        cache_manager = self.upload_cache_manager if use_upload_cache else None
        return upload_file_with_cache(
            client=self.client,
            file_path=file_path,
            cache_manager=cache_manager,
            verbose=verbose,
        )

    def generate_content(
        self,
        model: str,
        prompt: str,
        uploaded_file=None,
    ):
        """Calls the Gemini API with the given prompt and optional uploaded file."""
        contents = [prompt]
        if uploaded_file:
            contents.append(uploaded_file)

        response = self.client.models.generate_content(
            model=model, contents=contents, config=GEMINI_CONTENT_CONFIG
        )

        if not response.text:
            raise ValueError("Empty response from Gemini API")

        return response.text
