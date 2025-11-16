"""Gemini API processing utilities for text conversion.

This library provides generic utilities for working with Google's Gemini API,
including file upload/caching, smart sampling, prompt template management,
response parsing, and analysis result caching.
"""

from gemini_processor.cache_manager import AnalysisCache
from gemini_processor.file_manager import (
    clear_upload_cache,
    get_cached_upload,
    upload_file_with_cache,
)
from gemini_processor.prompt_manager import PromptManager
from gemini_processor.response_parser import (
    parse_json_response,
    parse_markdown_response,
)
from gemini_processor.sampler import create_custom_sample, create_smart_sample

__all__ = [
    # File management
    "upload_file_with_cache",
    "get_cached_upload",
    "clear_upload_cache",
    # Sampling
    "create_smart_sample",
    "create_custom_sample",
    # Prompt management
    "PromptManager",
    # Response parsing
    "parse_json_response",
    "parse_markdown_response",
    # Caching
    "AnalysisCache",
]

__version__ = "0.1.0"
