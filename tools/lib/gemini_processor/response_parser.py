"""Response parsing utilities for Gemini API responses.

Provides robust parsing of JSON and markdown responses from Gemini API,
including error handling, code fence removal, and JSON repair capabilities.
"""

import json
import re
from typing import Any, Dict, Optional


class ResponseParseError(Exception):
    """Raised when a response cannot be parsed."""

    pass


def _remove_code_fences(text: str) -> str:
    """Remove markdown code fences from text.

    Args:
        text: Text potentially wrapped in ```json or ``` markers.

    Returns:
        Text with code fences removed.
    """
    if not text.startswith("```"):
        return text

    lines = text.split("\n")
    json_lines = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            json_lines.append(line)

    return "\n".join(json_lines)


def _repair_json_escapes(text: str) -> str:
    """Attempt to repair common JSON escape sequence issues.

    Gemini sometimes returns regex patterns with single backslashes which are
    invalid in JSON. This function attempts to fix those issues.

    Args:
        text: The JSON text that may have escape issues.

    Returns:
        Repaired JSON text.
    """
    # Find all strings that look like regex patterns in the JSON
    # Pattern: "regex": "..." where ... contains backslashes
    regex_pattern = r'"regex":\s*"([^"]*)"'

    def fix_regex(match: re.Match) -> str:
        regex_value = match.group(1)
        # Double all single backslashes that aren't already doubled
        # This is tricky because we need to handle:
        # \* -> \\*
        # \\ -> \\ (already correct)
        # \S -> \\S
        fixed = regex_value.replace("\\", "\\\\")
        # But if they were already doubled, we just quadrupled them, so fix that
        fixed = fixed.replace("\\\\\\\\", "\\\\")
        return f'"regex": "{fixed}"'

    repaired = re.sub(regex_pattern, fix_regex, text)
    return repaired


def parse_json_response(
    response_text: str, allow_repair: bool = True
) -> Dict[str, Any]:
    """Parse JSON response from Gemini API with robust error handling.

    Handles common issues like markdown code fences and escape sequence problems.
    Provides detailed error messages with context when parsing fails.

    Args:
        response_text: The raw response text from Gemini API.
        allow_repair: If True, attempt to repair JSON escape sequences on parse failure.

    Returns:
        Parsed JSON as a dictionary.

    Raises:
        ResponseParseError: If JSON parsing fails even after repair attempts.
        ValueError: If response_text is empty.
    """
    if not response_text:
        raise ValueError("Empty response text")

    cleaned_text = response_text.strip()

    # Remove markdown code fences if present
    cleaned_text = _remove_code_fences(cleaned_text)

    # Attempt to parse JSON
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as first_error:
        if not allow_repair:
            raise ResponseParseError(
                f"JSON parse failed: {first_error}\n"
                f"At line {first_error.lineno}, column {first_error.colno}"
            ) from first_error

        # First parse failed - try repairing escape sequences
        repaired_text = _repair_json_escapes(cleaned_text)

        try:
            return json.loads(repaired_text)
        except json.JSONDecodeError as e:
            # Even repair didn't work - raise detailed error
            error_context = _get_error_context(cleaned_text, e)
            raise ResponseParseError(
                f"JSON parse failed even after repair:\n"
                f"  Error: {e}\n"
                f"  Location: line {e.lineno}, column {e.colno}\n"
                f"{error_context}"
            ) from e


def _get_error_context(text: str, error: json.JSONDecodeError) -> str:
    """Get contextual lines around a JSON decode error.

    Args:
        text: The full text being parsed.
        error: The JSONDecodeError exception.

    Returns:
        Formatted string showing lines around the error.
    """
    if not error.lineno:
        return f"First 200 chars: {text[:200]}"

    lines = text.split("\n")
    if not (1 <= error.lineno <= len(lines)):
        return f"Invalid line number: {error.lineno}"

    context_lines = []
    context_lines.append(f"Context around line {error.lineno}:")

    start = max(0, error.lineno - 3)
    end = min(len(lines), error.lineno + 2)

    for i in range(start, end):
        marker = ">>>" if i == error.lineno - 1 else "   "
        context_lines.append(f"{marker} {i+1:3d}: {lines[i]}")
        if i == error.lineno - 1 and error.colno:
            pointer = " " * (error.colno + 8) + "^-- Error here"
            context_lines.append(pointer)

    return "\n".join(context_lines)


def parse_markdown_response(response_text: str) -> str:
    """Parse markdown response from Gemini API.

    Handles code fence removal and basic validation.

    Args:
        response_text: The raw response text from Gemini API.

    Returns:
        Cleaned markdown text.

    Raises:
        ValueError: If response_text is empty.
    """
    if not response_text:
        raise ValueError("Empty response text")

    cleaned_text = response_text.strip()

    # Remove markdown code fences if the entire response is wrapped
    # (Don't remove internal code blocks)
    if cleaned_text.startswith("```markdown") or cleaned_text.startswith("```md"):
        lines = cleaned_text.split("\n")
        if len(lines) > 2 and lines[-1].strip() == "```":
            # Remove first and last lines
            cleaned_text = "\n".join(lines[1:-1])

    return cleaned_text


def extract_json_from_mixed_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from a response that may contain both JSON and other content.

    Useful for parsing responses that mix JSON metadata with markdown content.

    Args:
        response_text: The raw response text that may contain JSON.

    Returns:
        Parsed JSON dictionary if found, None otherwise.
    """
    if not response_text:
        return None

    # Look for JSON-like content between code fences
    json_pattern = r"```json\s*\n(.*?)\n```"
    matches = re.findall(json_pattern, response_text, re.DOTALL)

    if matches:
        try:
            return json.loads(matches[0])
        except json.JSONDecodeError:
            pass

    # Try parsing the entire text
    try:
        return parse_json_response(response_text)
    except (ResponseParseError, ValueError):
        return None
