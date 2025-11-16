#!/usr/bin/env python3
"""
Tests for convert_meghamala.py using Gemini API mocks.

This test suite uses unittest.mock to mock all Gemini API calls,
allowing us to test the conversion logic without making actual API requests.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

# Import the module under test
from convert_meghamala import (
    call_gemini_api,
    create_chunk_conversion_prompt,
    create_conversion_prompt,
    create_first_chunk_prompt,
    extract_part_number_from_filename,
    get_directory_parts,
    hide_editor_comments_in_content,
    infer_metadata_with_gemini,
    parse_first_chunk_response,
    strip_code_fences,
    validate_devanagari_unchanged,
)

# Import library functions that were moved
from gemini_processor.prompt_manager import PromptManager
from gemini_processor.sampler import create_smart_sample

# TestPromptLoading removed - PromptManager is tested in gemini_processor library


class TestPromptCreation(unittest.TestCase):
    """Test prompt creation functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_input = "**श्रीः**\n\nSome Sanskrit text"
        self.grantha_id = "test-upanishad"
        self.canonical_title = "परीक्षोपनिषत्"
        self.commentary_id = "test-commentary"
        self.commentator = "परीक्षाचार्यः"

    @patch("convert_meghamala.prompt_manager.load_template")
    def test_create_conversion_prompt_without_commentary(self, mock_load):
        """Test creating conversion prompt without commentary."""
        mock_template = "Prompt for {grantha_id}: {input_text}"
        mock_load.return_value = mock_template

        # Mock the template to expect all the variables we pass
        mock_template = """
        {grantha_id}
        {canonical_title}
        {part_num}
        {commentary_metadata}
        {commentaries_frontmatter}
        {commentary_instructions}
        {commentary_example}
        {input_text}
        """
        mock_load.return_value = mock_template

        result = create_conversion_prompt(
            input_text=self.test_input,
            grantha_id=self.grantha_id,
            canonical_title=self.canonical_title,
            part_num=1,
        )

        self.assertIn(self.grantha_id, result)
        self.assertIn(self.test_input, result)

    @patch("convert_meghamala.prompt_manager.load_template")
    def test_create_conversion_prompt_with_commentary(self, mock_load):
        """Test creating conversion prompt with commentary metadata."""
        mock_template = """
        {grantha_id}
        {canonical_title}
        {part_num}
        {commentary_metadata}
        {commentaries_frontmatter}
        {commentary_instructions}
        {commentary_example}
        {input_text}
        """
        mock_load.return_value = mock_template

        result = create_conversion_prompt(
            input_text=self.test_input,
            grantha_id=self.grantha_id,
            canonical_title=self.canonical_title,
            commentary_id=self.commentary_id,
            commentator=self.commentator,
            part_num=1,
        )

        self.assertIn(self.grantha_id, result)
        self.assertIn(self.commentary_id, result)
        self.assertIn(self.commentator, result)

    @patch("convert_meghamala.prompt_manager.load_template")
    def test_create_first_chunk_prompt(self, mock_load):
        """Test creating first chunk prompt."""
        mock_template = "Extract metadata from: {chunk_text}"
        mock_load.return_value = mock_template

        result = create_first_chunk_prompt(self.test_input, part_num=1)

        self.assertIn(self.test_input, result)
        mock_load.assert_called_once_with("first_chunk_prompt.txt")

    @patch("convert_meghamala.prompt_manager.load_template")
    def test_create_chunk_conversion_prompt(self, mock_load):
        """Test creating chunk continuation prompt."""
        mock_template = "Continue converting: {chunk_text}"
        mock_load.return_value = mock_template

        result = create_chunk_conversion_prompt(self.test_input)

        self.assertIn(self.test_input, result)
        mock_load.assert_called_once_with("chunk_continuation_prompt.txt")


class TestGeminiAPIWithMocks(unittest.TestCase):
    """Test Gemini API calls with mocked responses."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_input_file = os.path.join(self.temp_dir, "test_input.md")
        self.test_output_file = os.path.join(self.temp_dir, "test_output.md")

        # Create test input file
        with open(self.test_input_file, "w", encoding="utf-8") as f:
            f.write("**परीक्षोपनिषत्**\n\nTest content")

    def tearDown(self):
        """Clean up test files."""
        import shutil

        shutil.rmtree(self.temp_dir)

    @patch("convert_meghamala.genai.Client")
    @patch("convert_meghamala.prompt_manager.load_template")
    def test_infer_metadata_success(self, mock_load_template, mock_client_class):
        """Test successful metadata inference with mocked Gemini API."""
        # Set up environment
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            # Mock the template loading
            mock_load_template.return_value = "Extract metadata: {excerpt}"

            # Mock the Gemini client and response
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.text = json.dumps(
                {
                    "canonical_title": "परीक्षोपनिषत्",
                    "grantha_id": "test-upanishad",
                    "commentary_id": None,
                    "commentator": None,
                    "structure_type": "khanda",
                }
            )
            mock_client.models.generate_content.return_value = mock_response

            # Call the function
            result = infer_metadata_with_gemini(self.test_input_file, verbose=False)

            # Verify results
            self.assertEqual(result["canonical_title"], "परीक्षोपनिषत्")
            self.assertEqual(result["grantha_id"], "test-upanishad")
            self.assertEqual(result["structure_type"], "khanda")
            self.assertIsNone(result["commentary_id"])

            # Verify API was called
            mock_client.models.generate_content.assert_called_once()

    def test_infer_metadata_no_api_key(self):
        """Test metadata inference fails gracefully without API key."""
        # Ensure GEMINI_API_KEY is not set
        with patch.dict(os.environ, {}, clear=True):
            result = infer_metadata_with_gemini(self.test_input_file, verbose=False)

            # Should return empty dict
            self.assertEqual(result, {})

    @patch("convert_meghamala.genai.Client")
    @patch("convert_meghamala.prompt_manager.load_template")
    def test_infer_metadata_api_error(self, mock_load_template, mock_client_class):
        """Test metadata inference handles API errors gracefully."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            mock_load_template.return_value = "Extract metadata: {excerpt}"

            # Mock client to raise an exception
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.side_effect = Exception("API Error")

            # Call should return empty dict on error
            result = infer_metadata_with_gemini(self.test_input_file, verbose=False)

            self.assertEqual(result, {})

    @patch("convert_meghamala.genai.Client")
    def test_call_gemini_api_success(self, mock_client_class):
        """Test successful Gemini API call with mocked response."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            # Mock the client and response
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.text = "---\ngrantha_id: test\n---\n\nConverted content"
            mock_client.models.generate_content.return_value = mock_response

            # Call the function
            result = call_gemini_api(
                prompt="Test prompt", output_file=self.test_output_file, verbose=False
            )

            # Should succeed
            self.assertTrue(result)

            # Check output file was created
            self.assertTrue(os.path.exists(self.test_output_file))

            # Check content
            with open(self.test_output_file, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("Converted content", content)

    @patch("convert_meghamala.genai.Client")
    def test_call_gemini_api_removes_code_fences(self, mock_client_class):
        """Test that code fences are removed from Gemini response."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Response with code fences
            mock_response = MagicMock()
            mock_response.text = "```markdown\n---\ngrantha_id: test\n---\n\nContent\n```"
            mock_client.models.generate_content.return_value = mock_response

            result = call_gemini_api(
                prompt="Test", output_file=self.test_output_file, verbose=False
            )

            self.assertTrue(result)

            # Check code fences were removed
            with open(self.test_output_file, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn("```", content)
                self.assertIn("grantha_id: test", content)

    def test_call_gemini_api_no_api_key(self):
        """Test API call fails gracefully without API key."""
        with patch.dict(os.environ, {}, clear=True):
            result = call_gemini_api(
                prompt="Test", output_file=self.test_output_file, verbose=False
            )

            self.assertFalse(result)

    @patch("convert_meghamala.genai.Client")
    def test_call_gemini_api_handles_exceptions(self, mock_client_class):
        """Test API call handles exceptions gracefully."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.side_effect = Exception("Network error")

            result = call_gemini_api(
                prompt="Test", output_file=self.test_output_file, verbose=False
            )

            self.assertFalse(result)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""

    def test_strip_code_fences(self):
        """Test code fence stripping."""
        test_cases = [
            ("```yaml\ncontent\n```", "content"),
            ("```markdown\ncontent\n```", "content"),
            ("```\ncontent\n```", "content"),
            ("content", "content"),
        ]

        for input_text, expected in test_cases:
            with self.subTest(input=input_text):
                result = strip_code_fences(input_text)
                self.assertEqual(result, expected)

    def test_parse_first_chunk_response(self):
        """Test parsing first chunk response."""
        # Valid response
        response = """
{
  "canonical_title": "परीक्षोपनिषत्",
  "grantha_id": "test-upanishad",
  "commentary_id": null,
  "commentator": null,
  "structure_type": "khanda"
}
---METADATA---
# Mantra 1.1
<!-- sanskrit:devanagari -->
Content
<!-- /sanskrit:devanagari -->
"""

        metadata, content = parse_first_chunk_response(response)

        self.assertIsNotNone(metadata)
        self.assertIsNotNone(content)
        self.assertEqual(metadata["grantha_id"], "test-upanishad")
        self.assertIn("Mantra 1.1", content)

    def test_parse_first_chunk_response_no_separator(self):
        """Test parsing response without metadata separator."""
        response = "No separator in this response"

        metadata, content = parse_first_chunk_response(response)

        self.assertIsNone(metadata)
        self.assertIsNone(content)

    def test_hide_editor_comments(self):
        """Test hiding editor comments in square brackets."""
        test_cases = [
            (
                "Text [editorial note] more text",
                "Text <!-- hide -->[editorial note]<!-- /hide --> more text",
            ),
            (
                "<!-- hide -->[already hidden]<!-- /hide -->",
                "<!-- hide -->[already hidden]<!-- /hide -->",
            ),
            ("[link](url)", "[link](url)"),  # Don't hide markdown links
        ]

        for input_text, expected in test_cases:
            with self.subTest(input=input_text):
                _, result = hide_editor_comments_in_content(input_text)
                self.assertEqual(result, expected)

    def test_validate_devanagari_unchanged(self):
        """Test Devanagari validation."""
        original = "Some text देवनागरी more text"
        unchanged = "Different text देवनागरी other text"
        changed = "Some text दवनागर more text"

        # Should pass when Devanagari is unchanged
        self.assertTrue(validate_devanagari_unchanged(original, unchanged))

        # Should fail when Devanagari is changed
        self.assertFalse(validate_devanagari_unchanged(original, changed))

    def test_extract_part_number_from_filename(self):
        """Test part number extraction from filenames."""
        test_cases = [
            ("03-01.md", 1),
            ("03-02.md", 2),
            ("part-3.md", 3),
            ("brihadaranyaka-05.md", 5),
            ("01.md", 1),
            ("random.md", 1),  # Default
        ]

        for filename, expected in test_cases:
            with self.subTest(filename=filename):
                result = extract_part_number_from_filename(filename)
                self.assertEqual(result, expected)


class TestErrorHandling(unittest.TestCase):
    """Test error handling with verbose mode."""

    @patch("convert_meghamala.genai.Client")
    @patch("convert_meghamala.traceback.print_exc")
    def test_verbose_mode_prints_stack_trace(self, mock_traceback, mock_client_class):
        """Test that verbose mode prints stack traces on errors."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.models.generate_content.side_effect = Exception("Test error")

            # Create a temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False
            ) as f:
                f.write("**परीक्षोपनिषत्**\n\nTest")
                temp_file = f.name

            try:
                # Call with verbose=True
                infer_metadata_with_gemini(temp_file, verbose=True)

                # Verify traceback was printed
                mock_traceback.assert_called()
            finally:
                os.unlink(temp_file)


if __name__ == "__main__":
    unittest.main()
