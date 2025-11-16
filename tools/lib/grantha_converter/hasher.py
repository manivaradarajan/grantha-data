"""Content hashing for validation of lossless conversion.

This module provides utilities to hash grantha content based on Devanagari text only.
The validation hash extracts and hashes ONLY Devanagari characters (U+0900-U+097F),
ignoring all other scripts, translations, markdown formatting, and whitespace.

This ensures consistency with devanagari_diff.py and provides a canonical,
testable approach to content validation.
"""

import hashlib
from typing import Any, Dict, List, Optional

from grantha_converter.devanagari_extractor import extract_devanagari


def hash_text(text: str) -> str:
    """Generates a SHA256 hash of Devanagari-only text.

    This function extracts ONLY Devanagari characters (U+0900-U+097F) from the
    input text, ignoring all other scripts, translations, formatting, and whitespace.
    This is the canonical hashing function used for validation_hash fields.

    Args:
        text: The text to hash (may contain multiple scripts, markdown, etc.)

    Returns:
        The hex digest of the SHA256 hash of the extracted Devanagari text.

    Example:
        >>> hash_text("अग्नि agni")  # Only "अग्नि" is hashed
        >>> hash_text("# Title\\n\\nअग्नि")  # Only "अग्नि" is hashed
    """
    # Extract only Devanagari characters (consistent with devanagari_diff.py)
    devanagari_only = extract_devanagari(text)
    return hashlib.sha256(devanagari_only.encode('utf-8')).hexdigest()


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
