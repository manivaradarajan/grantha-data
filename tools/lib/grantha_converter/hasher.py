"""Content hashing for validation of lossless conversion.

This module provides utilities to hash grantha content by normalizing text
and excluding non-significant characters (whitespace, zero-width marks, punctuation)
to verify that the semantic content remains unchanged after conversion.
"""

import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Optional

# Unicode characters to exclude from hash
ZERO_WIDTH_CHARS = [
    '\u200b',  # Zero-width space
    '\u200c',  # Zero-width non-joiner
    '\u200d',  # Zero-width joiner
    '\ufeff',  # Zero-width no-break space (BOM)
]

# Devanagari and common punctuation marks to exclude
PUNCTUATION_CHARS = [
    '\u0964',  # Devanagari danda
    '\u0965',  # Devanagari double danda
    '।',       # Devanagari danda (alternative)
    '॥',       # Devanagari double danda (alternative)
    ',', '.', ';', ':', '!', '?', '-', '—', '–',
    '(', ')', '[', ']', '{', '}', '"', "'", '`',
]


def normalize_text(text: str) -> str:
    """Normalizes text for hashing by removing non-significant characters.

    The normalization process includes:
    - Removing all whitespace (spaces, newlines, tabs, etc.).
    - Removing zero-width Unicode characters (e.g., ZWNJ, ZWJ).
    - Removing punctuation marks (dandas, commas, periods, etc.).
    - Applying NFC Unicode normalization.

    Args:
        text: The input string to normalize.

    Returns:
        A normalized string containing only significant characters.
    """
    if not text:
        return ""

    # Remove zero-width characters
    for char in ZERO_WIDTH_CHARS:
        text = text.replace(char, '')

    # Remove punctuation
    for char in PUNCTUATION_CHARS:
        text = text.replace(char, '')

    # Remove all whitespace characters
    text = re.sub(r'\s+', '', text)

    # Normalize Unicode (NFC form)
    text = unicodedata.normalize('NFC', text)

    return text


def hash_text(text: str) -> str:
    """Generates a SHA256 hash of normalized text.

    Args:
        text: The text to hash.

    Returns:
        The hex digest of the SHA256 hash.
    """
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def extract_content_text(content: Dict[str, Any], scripts: Optional[List[str]] = None) -> str:
    """Extracts all text from a passage's content object.

    This function aggregates text from various fields within a content dictionary,
    such as different Sanskrit scripts and English translations.

    Args:
        content: A content dictionary, which may contain 'sanskrit',
            'english_translation', and 'english' fields.
        scripts: An optional list of scripts to include (e.g., ['devanagari']).
            If None, all available scripts are included.

    Returns:
        A single concatenated string of all requested textual content.
    """
    texts = []

    # Extract Sanskrit text
    if 'sanskrit' in content:
        sanskrit = content['sanskrit']
        script_keys = ['devanagari', 'roman', 'kannada']
        for key in script_keys:
            if scripts is None or key in scripts:
                if sanskrit.get(key):
                    texts.append(sanskrit[key])

    # Extract English translation
    if 'english_translation' in content and content['english_translation']:
        texts.append(content['english_translation'])

    # Extract English (for commentary)
    if 'english' in content and content['english']:
        texts.append(content['english'])

    return ''.join(texts)


def hash_passage(passage: Dict[str, Any], scripts: Optional[List[str]] = None) -> str:
    """Generates a hash for a single passage object.

    Args:
        passage: A passage dictionary containing a 'content' field.
        scripts: An optional list of scripts to include in the hash.

    Returns:
        The SHA256 hash of the passage's content.
    """
    content_text = extract_content_text(passage['content'], scripts)
    return hash_text(content_text)


def hash_grantha(data: Dict[str, Any],
                 scripts: Optional[List[str]] = None,
                 commentaries: Optional[List[str]] = None) -> str:
    """Generates a validation hash for an entire grantha document.

    This function aggregates text from all specified parts of the grantha
    (e.g., main passages, prefatory material, specific commentaries) and
    computes a single hash to represent the state of the content.

    Args:
        data: The full grantha JSON data dictionary.
        scripts: An optional list of scripts to include in the hash.
        commentaries: An optional list of commentary IDs to include. If None,
            only the core text is hashed.

    Returns:
        The SHA256 hash of all specified content in the document.
    """
    all_texts = []
    
    content_sections = ['prefatory_material', 'passages', 'concluding_material']
    for section in content_sections:
        if section in data:
            for item in data[section]:
                text = extract_content_text(item['content'], scripts)
                all_texts.append(text)

    # Hash commentaries if requested
    if commentaries and 'commentaries' in data:
        for commentary in data['commentaries']:
            if commentary['commentary_id'] in commentaries:
                for passage in commentary.get('passages', []):
                    # Handle nested content sections within commentaries
                    if 'prefatory_material' in passage:
                        for item in passage['prefatory_material']:
                            text = extract_content_text(item['content'], scripts)
                            all_texts.append(text)
                    if 'content' in passage:
                        text = extract_content_text(passage['content'], scripts)
                        all_texts.append(text)

    # Combine and hash all text
    combined = ''.join(all_texts)
    return hash_text(combined)
