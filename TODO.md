# TODO

## Inconsistency in Devanagari Handling for Commentaries vs. Mantras

**Description:**
During the `md2json` conversion process, an inconsistency was identified in how Devanagari text is expected to be structured within Markdown files, specifically concerning "mantra" passages and "commentary" passages.

-   **Mantra Passages:** Devanagari text within mantra sections is explicitly wrapped with `<!-- sanskrit:devanagari -->` and `<!-- /sanskrit:devanagari -->` tags. The `parse_sanskrit_content` function in `md_to_json.py` correctly identifies and extracts content based on these tags.

-   **Commentary Passages:** Devanagari text within commentary sections is *not* explicitly tagged with `<!-- sanskrit:devanagari -->` tags. Instead, it appears as raw text within the commentary block, often alongside other non-content-related HTML-style comments (e.g., `<!-- hide ... -->`).

**Problem:**
The original `parse_sanskrit_content` function was designed to look for explicit tags. Consequently, when processing commentary blocks, it would not find any `sanskrit:devanagari` tags and would therefore fail to extract the Devanagari content, leading to its omission in the generated JSON output. Other HTML-style comments within the commentary blocks further complicated the parsing logic.

**Implemented Fix (Temporary "Hack"):**
To address this, a modification was made to the `parse_sanskrit_content` function in `tools/lib/grantha_converter/md_to_json.py`. The updated logic now includes a fallback mechanism:

1.  The function first attempts to find explicit content tags (like `sanskrit:devanagari`, `sanskrit:roman`, etc.).
2.  If *no* such explicit content tags are found within a given content block (which is characteristic of commentary blocks), the function now assumes that the *entire* content of that block (after stripping out all HTML-style comments) is Devanagari text. This cleaned content is then assigned to `sanskrit_data['devanagari']`.

This approach ensures that Devanagari text from commentary sections is no longer ignored.

**Future Improvement:**
The current fix is a pragmatic solution to ensure data is not lost. A more robust and consistent long-term solution would involve:

-   **Standardizing Markdown Structure:** Define a clear standard for how Devanagari and other language content should be marked up within *all* sections (mantras, commentaries, prefatory material, etc.). This might involve explicitly tagging Devanagari in commentaries or introducing a new, more flexible parsing mechanism that doesn't rely solely on explicit tags for commentary content.
-   **Refining `parse_sanskrit_content`:** Develop a more sophisticated parser that can differentiate between content-bearing tags and other metadata/formatting tags (like `<!-- hide -->`) and handle nested or implicit content structures more gracefully.
