"""Tests for response_parser module."""

import json
import unittest

from gemini_processor.response_parser import (
    ResponseParseError,
    extract_json_from_mixed_response,
    parse_json_response,
    parse_markdown_response,
)


class TestParseJsonResponse(unittest.TestCase):
    """Test suite for parse_json_response function."""

    def test_valid_json(self):
        """Should parse valid JSON successfully."""
        json_text = '{"key": "value", "number": 42}'
        result = parse_json_response(json_text)
        self.assertEqual(result, {"key": "value", "number": 42})

    def test_json_with_code_fences(self):
        """Should remove markdown code fences before parsing."""
        json_text = '```json\n{"key": "value"}\n```'
        result = parse_json_response(json_text)
        self.assertEqual(result, {"key": "value"})

    def test_json_with_plain_code_fences(self):
        """Should handle code fences without language specifier."""
        json_text = '```\n{"key": "value"}\n```'
        result = parse_json_response(json_text)
        self.assertEqual(result, {"key": "value"})

    def test_whitespace_handling(self):
        """Should handle leading/trailing whitespace."""
        json_text = '\n  \n{"key": "value"}\n  \n'
        result = parse_json_response(json_text)
        self.assertEqual(result, {"key": "value"})

    def test_empty_response_raises_error(self):
        """Should raise ValueError for empty response."""
        with self.assertRaises(ValueError) as context:
            parse_json_response("")
        self.assertIn("Empty", str(context.exception))

    def test_invalid_json_without_repair(self):
        """Should raise ResponseParseError for invalid JSON when repair disabled."""
        invalid_json = '{"key": "value"'  # Missing closing brace
        with self.assertRaises(ResponseParseError):
            parse_json_response(invalid_json, allow_repair=False)

    def test_regex_escape_repair(self):
        """Should repair regex escape sequences."""
        # Gemini sometimes returns regex with single backslashes
        json_with_bad_escapes = '{"regex": "\\d+", "key": "value"}'
        result = parse_json_response(json_with_bad_escapes, allow_repair=True)
        # Should successfully parse after repair
        self.assertIn("regex", result)

    def test_complex_json(self):
        """Should handle complex nested JSON."""
        complex_json = json.dumps({
            "metadata": {"title": "Test", "author": "Alice"},
            "items": [1, 2, 3],
            "nested": {"deep": {"value": "found"}},
        })
        result = parse_json_response(complex_json)
        self.assertEqual(result["metadata"]["author"], "Alice")
        self.assertEqual(result["nested"]["deep"]["value"], "found")

    def test_unicode_in_json(self):
        """Should handle Unicode characters in JSON."""
        unicode_json = '{"sanskrit": "ॐ नमः शिवाय", "chinese": "你好"}'
        result = parse_json_response(unicode_json)
        self.assertEqual(result["sanskrit"], "ॐ नमः शिवाय")
        self.assertEqual(result["chinese"], "你好")

    def test_multiline_json(self):
        """Should handle multiline JSON strings."""
        multiline_json = """{
            "key1": "value1",
            "key2": "value2",
            "key3": "value3"
        }"""
        result = parse_json_response(multiline_json)
        self.assertEqual(len(result), 3)


class TestParseMarkdownResponse(unittest.TestCase):
    """Test suite for parse_markdown_response function."""

    def test_plain_markdown(self):
        """Should return plain markdown unchanged."""
        markdown = "# Heading\n\nSome **bold** text."
        result = parse_markdown_response(markdown)
        self.assertEqual(result, markdown)

    def test_markdown_with_code_fences(self):
        """Should remove outer markdown code fences."""
        markdown = "```markdown\n# Heading\n\nContent\n```"
        result = parse_markdown_response(markdown)
        self.assertEqual(result, "# Heading\n\nContent")

    def test_markdown_with_md_language_tag(self):
        """Should handle ```md code fences."""
        markdown = "```md\n# Heading\n```"
        result = parse_markdown_response(markdown)
        self.assertEqual(result, "# Heading")

    def test_whitespace_handling(self):
        """Should handle leading/trailing whitespace."""
        markdown = "\n\n# Heading\n\n"
        result = parse_markdown_response(markdown)
        self.assertEqual(result, "# Heading")

    def test_empty_response_raises_error(self):
        """Should raise ValueError for empty response."""
        with self.assertRaises(ValueError) as context:
            parse_markdown_response("")
        self.assertIn("Empty", str(context.exception))

    def test_internal_code_blocks_preserved(self):
        """Should preserve internal code blocks in markdown."""
        markdown = "# Heading\n\n```python\nprint('hello')\n```\n\nText after."
        result = parse_markdown_response(markdown)
        # Should preserve the internal code block
        self.assertIn("```python", result)
        self.assertIn("print('hello')", result)

    def test_unicode_markdown(self):
        """Should handle Unicode in markdown."""
        markdown = "# शीर्षक\n\nसंस्कृत text with Devanagari."
        result = parse_markdown_response(markdown)
        self.assertEqual(result, markdown)


class TestExtractJsonFromMixedResponse(unittest.TestCase):
    """Test suite for extract_json_from_mixed_response function."""

    def test_json_in_code_fence(self):
        """Should extract JSON from code fence in mixed content."""
        mixed = 'Here is the data:\n```json\n{"key": "value"}\n```\nMore text.'
        result = extract_json_from_mixed_response(mixed)
        self.assertEqual(result, {"key": "value"})

    def test_pure_json_response(self):
        """Should parse pure JSON response."""
        json_text = '{"key": "value"}'
        result = extract_json_from_mixed_response(json_text)
        self.assertEqual(result, {"key": "value"})

    def test_no_json_returns_none(self):
        """Should return None if no JSON found."""
        text = "Just some plain text without any JSON."
        result = extract_json_from_mixed_response(text)
        self.assertIsNone(result)

    def test_empty_response_returns_none(self):
        """Should return None for empty response."""
        result = extract_json_from_mixed_response("")
        self.assertIsNone(result)

    def test_multiple_json_blocks_returns_first(self):
        """Should return first JSON block if multiple present."""
        mixed = '```json\n{"first": 1}\n```\nText\n```json\n{"second": 2}\n```'
        result = extract_json_from_mixed_response(mixed)
        self.assertEqual(result, {"first": 1})

    def test_malformed_json_in_fence_returns_none(self):
        """Should return None if JSON in fence is malformed."""
        mixed = '```json\n{"key": invalid}\n```'
        result = extract_json_from_mixed_response(mixed)
        self.assertIsNone(result)


class TestResponseParseError(unittest.TestCase):
    """Test suite for ResponseParseError exception."""

    def test_exception_message(self):
        """Should preserve error message."""
        msg = "Test error message"
        error = ResponseParseError(msg)
        self.assertEqual(str(error), msg)

    def test_exception_inheritance(self):
        """Should be a subclass of Exception."""
        self.assertTrue(issubclass(ResponseParseError, Exception))


if __name__ == "__main__":
    unittest.main()
