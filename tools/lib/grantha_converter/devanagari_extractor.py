"""Extract Devanagari text from strings.

This module provides the canonical implementation for extracting Devanagari
characters and words from text. It serves as the single source of truth for
Devanagari extraction across the entire codebase.

The extraction functions:
- Remove all non-Devanagari content (markdown, YAML, whitespace, etc.)
- Extract only characters in the Devanagari Unicode block (U+0900-U+097F)
- Are used for validation hashing, diff comparison, and text repair

## Hash Algorithm Version

HASH_VERSION tracks breaking changes to the extraction algorithm.
Increment this when making changes that would produce different hashes
for the same input text.

Version History:
- v3 (current): Added markdown heading removal to cleaning function.
  Headings (lines starting with #) are now excluded from extraction, so
  structural metadata like "# Mantra 1" doesn't affect content hash.
- v2: Word-boundary-preserving extraction. Devanagari word sequences
  are joined with single spaces, normalizing gaps from non-Devanagari content.
- v1 (legacy): No-space extraction. All Devanagari characters concatenated
  without spaces. (Pre-versioning era)
"""

import re
from typing import List, Tuple

# IMPORTANT: Increment this version number when making breaking changes
# to the extraction or hashing algorithm.
HASH_VERSION = 3


def clean_text_for_devanagari_comparison(
    text: str,
    skip_headings: bool = True
) -> str:
    """Cleans text by removing structural elements for Devanagari comparison.

    This is the canonical cleaning function used across the codebase for:
    - Devanagari diff comparison (devanagari_diff.py)
    - Validation hash computation (hasher.py)
    - Text repair operations (devanagari_repair.py) when skip_headings=False

    Removes:
        - YAML frontmatter (enclosed in --- or +++)
        - HTML comments (<!-- ... -->)
        - Markdown headings (lines starting with #) - only if skip_headings=True
        - Markdown bold markers (**)

    Preserves:
        - All body content (Sanskrit text, commentary, etc.)
        - Devanagari characters for extraction
        - Markdown headings when skip_headings=False (for repair operations)

    Args:
        text: Input text that may contain YAML frontmatter, HTML comments,
              markdown headings, bold markers, and other non-Devanagari content.
        skip_headings: If True (default), remove markdown headings from output.
                      Set to False for repair operations that need to preserve
                      heading Devanagari.

    Returns:
        Cleaned text with structural elements removed, ready for Devanagari
        extraction. Whitespace is normalized to single spaces.

    Examples:
        >>> text = "---\\ntitle: Test\\n---\\n# मन्त्रः 1\\n**अग्निमीळे** <!-- comment --> पुरोहितं"
        >>> clean_text_for_devanagari_comparison(text)
        'अग्निमीळे पुरोहितं'
        >>> clean_text_for_devanagari_comparison(text, skip_headings=False)
        '# मन्त्रः 1 अग्निमीळे पुरोहितं'
    """
    # 1. Remove YAML/TOML frontmatter (--- or +++ delimiters)
    stripped = text.strip()
    if stripped.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    elif stripped.startswith("+++"):
        parts = text.split("+++", 2)
        if len(parts) == 3:
            text = parts[2]

    # 2. Remove markdown headings (lines starting with #)
    # This removes structural headings like "# Mantra 1" or "## Commentary: 1"
    # so that heading text doesn't affect the content hash.
    # Skip this step for repair operations where headings need to be preserved.
    if skip_headings:
        text = re.sub(r'^#+\s+.*$', '', text, flags=re.MULTILINE)

    # 3. Replace HTML comments with a space to avoid merging words
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)

    # 4. Remove markdown bold markers
    text = re.sub(r"\*\*", "", text)

    # 5. Normalize whitespace to a single space
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def extract_devanagari(text: str) -> str:
    """Extracts all Devanagari characters from a string, preserving word boundaries.

    This is the canonical extraction function used across the codebase for:
    - Validation hash computation (hasher.py)
    - Devanagari diff comparison (devanagari_diff.py)
    - Text repair operations (devanagari_repair.py)

    This function extracts Devanagari word sequences and joins them with single
    spaces. This preserves word boundaries while normalizing non-Devanagari gaps
    caused by non-Devanagari content (markdown, English, etc.).

    Args:
        text: The input string (may contain markdown, YAML, multiple scripts, etc.)

    Returns:
        A string containing only the Devanagari text from the input, with
        word boundaries preserved. Non-Devanagari content is removed, and
        the resulting gaps are normalized to single spaces.

    Examples:
        >>> extract_devanagari("# Sanskrit\\n\\nअग्निमीळे पुरोहितं")
        'अग्निमीळे पुरोहितं'

        >>> extract_devanagari("अग्निमीळे। पुरोहितं")
        'अग्निमीळे। पुरोहितं'

        >>> extract_devanagari("अग्निमीळे English पुरोहितं")
        'अग्निमीळे पुरोहितं'
    """
    # Extract Devanagari word sequences and join with single spaces
    # This preserves word boundaries while normalizing non-Devanagari gaps
    words = extract_devanagari_words(text)
    return " ".join(words)


def extract_devanagari_words(text: str) -> List[str]:
    """Extracts Devanagari words (sequences) from text.

    A "word" is defined as any contiguous sequence of Devanagari characters.
    This function splits the text by any non-Devanagari characters, ensuring
    that all Devanagari words are correctly isolated.

    Args:
        text: Input text (may contain mixed content)

    Returns:
        List of Devanagari words.
    """
    # Split the text by any sequence of one or more non-Devanagari characters.
    # The pattern [^\u0900-\u097F]+ matches any character that is NOT in the
    # Devanagari Unicode range.
    words = re.split(r"[^\u0900-\u097F]+", text)
    # Filter out any empty strings that result from the split (e.g., if the
    # text starts or ends with a non-Devanagari character).
    return [word for word in words if word]


def extract_devanagari_words_with_positions(
    text: str,
    skip_frontmatter: bool = True,
    skip_comments: bool = True,
    skip_headings: bool = False,
) -> List[Tuple[str, int, int]]:
    """Extracts Devanagari words with their positions in the ORIGINAL text.

    This function is designed for surgical repair operations. It extracts
    Devanagari character sequences and their exact positions in the input text,
    with optional filtering to skip Devanagari content in frontmatter, HTML
    comments, and markdown headings.

    Args:
        text: Input text (completely unmodified)
        skip_frontmatter: If True, skip Devanagari in YAML frontmatter (default: True)
        skip_comments: If True, skip Devanagari in HTML comments (default: True)
        skip_headings: If True, skip Devanagari in markdown heading lines (default: False)

    Returns:
        List of tuples (word, start_pos, end_pos) where:
        - word: The Devanagari text sequence
        - start_pos: Character index where word starts in ORIGINAL text
        - end_pos: Character index where word ends in ORIGINAL text

    Example:
        >>> extract_devanagari_words_with_positions("Hello अग्नि world मीळे")
        [('अग्नि', 6, 10), ('मीळे', 17, 21)]

        >>> extract_devanagari_words_with_positions("**अग्नि** <!-- मीळे --> पुरोहितं")
        [('अग्नि', 2, 6), ('पुरोहितं', 25, 33)]

    Note:
        The positions returned are in the ORIGINAL text, including all markdown
        and other formatting. This is crucial for surgical repair that preserves
        document structure.
    """
    # Build list of excluded ranges
    excluded_ranges = []

    # 1. Find frontmatter range (--- or +++ delimiters)
    if skip_frontmatter:
        stripped = text.strip()
        delimiter = None
        if stripped.startswith("---"):
            delimiter = "---"
        elif stripped.startswith("+++"):
            delimiter = "+++"

        if delimiter:
            parts = text.split(delimiter, 2)
            if len(parts) == 3:
                # Find the end of the second delimiter
                first_delim_end = text.find(delimiter) + len(delimiter)
                second_delim_start = text.find(delimiter, first_delim_end)
                second_delim_end = second_delim_start + len(delimiter)
                excluded_ranges.append((0, second_delim_end))

    # 2. Find all HTML comment ranges
    if skip_comments:
        for match in re.finditer(r"<!--.*?-->", text, flags=re.DOTALL):
            excluded_ranges.append((match.start(), match.end()))

    # 3. Find markdown heading line ranges
    if skip_headings:
        lines_processed = 0
        for line in text.split("\n"):
            line_start = lines_processed
            line_end = lines_processed + len(line)
            if line.strip().startswith("#"):
                excluded_ranges.append((line_start, line_end))
            lines_processed = line_end + 1  # +1 for the newline

    # Extract all Devanagari words with positions
    pattern = r"[\u0900-\u097F]+"
    all_matches = []
    for match in re.finditer(pattern, text):
        word_start = match.start()
        word_end = match.end()

        # Check if this word is in any excluded range
        is_excluded = False
        for excl_start, excl_end in excluded_ranges:
            if word_start >= excl_start and word_end <= excl_end:
                is_excluded = True
                break

        if not is_excluded:
            all_matches.append((match.group(), word_start, word_end))

    return all_matches
