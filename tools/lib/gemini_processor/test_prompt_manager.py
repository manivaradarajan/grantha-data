"""Tests for prompt_manager module."""

import tempfile
import unittest
from pathlib import Path

from gemini_processor.prompt_manager import PromptManager


class TestPromptManager(unittest.TestCase):
    """Test suite for PromptManager class."""

    def setUp(self):
        """Create temporary prompts directory for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.prompts_dir = Path(self.temp_dir.name)

        # Create test prompt files
        self.test_prompt = "This is a test prompt with {variable1} and {variable2}."
        (self.prompts_dir / "test_prompt.txt").write_text(
            self.test_prompt, encoding="utf-8"
        )

        self.simple_prompt = "Simple prompt without variables."
        (self.prompts_dir / "simple.txt").write_text(
            self.simple_prompt, encoding="utf-8"
        )

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_init_with_valid_directory(self):
        """Should initialize successfully with valid directory."""
        manager = PromptManager(self.prompts_dir)
        self.assertEqual(manager.prompts_dir, self.prompts_dir)

    def test_init_with_invalid_directory(self):
        """Should raise ValueError with invalid directory."""
        invalid_path = self.prompts_dir / "nonexistent"
        with self.assertRaises(ValueError) as context:
            PromptManager(invalid_path)
        self.assertIn("does not exist", str(context.exception))

    def test_load_template_success(self):
        """Should load template file successfully."""
        manager = PromptManager(self.prompts_dir)
        template = manager.load_template("test_prompt.txt")
        self.assertEqual(template, self.test_prompt)

    def test_load_template_file_not_found(self):
        """Should raise FileNotFoundError for missing file."""
        manager = PromptManager(self.prompts_dir)
        with self.assertRaises(FileNotFoundError) as context:
            manager.load_template("nonexistent.txt")
        self.assertIn("not found", str(context.exception))

    def test_format_template_with_variables(self):
        """Should format template with provided variables."""
        manager = PromptManager(self.prompts_dir)
        variables = {"variable1": "value1", "variable2": "value2"}
        result = manager.format_template(self.test_prompt, variables)
        self.assertEqual(
            result, "This is a test prompt with value1 and value2."
        )

    def test_format_template_without_variables(self):
        """Should return template unchanged if no variables."""
        manager = PromptManager(self.prompts_dir)
        result = manager.format_template(self.simple_prompt)
        self.assertEqual(result, self.simple_prompt)

    def test_format_template_missing_variable(self):
        """Should raise KeyError if required variable is missing."""
        manager = PromptManager(self.prompts_dir)
        variables = {"variable1": "value1"}  # Missing variable2
        with self.assertRaises(KeyError) as context:
            manager.format_template(self.test_prompt, variables)
        self.assertIn("Missing required variable", str(context.exception))

    def test_load_and_format_success(self):
        """Should load and format template in one step."""
        manager = PromptManager(self.prompts_dir)
        variables = {"variable1": "hello", "variable2": "world"}
        result = manager.load_and_format("test_prompt.txt", variables)
        self.assertEqual(result, "This is a test prompt with hello and world.")

    def test_load_and_format_without_variables(self):
        """Should load and return simple template."""
        manager = PromptManager(self.prompts_dir)
        result = manager.load_and_format("simple.txt")
        self.assertEqual(result, self.simple_prompt)

    def test_load_and_format_file_not_found(self):
        """Should raise FileNotFoundError for missing file."""
        manager = PromptManager(self.prompts_dir)
        with self.assertRaises(FileNotFoundError):
            manager.load_and_format("missing.txt", {})

    def test_load_and_format_missing_variable(self):
        """Should raise KeyError for missing variable."""
        manager = PromptManager(self.prompts_dir)
        with self.assertRaises(KeyError):
            manager.load_and_format("test_prompt.txt", {"variable1": "only_one"})

    def test_utf8_encoding(self):
        """Should handle UTF-8 encoded files correctly."""
        # Create a prompt with Unicode characters
        unicode_prompt = "Sanskrit: {sanskrit_text}"
        (self.prompts_dir / "unicode.txt").write_text(
            unicode_prompt, encoding="utf-8"
        )

        manager = PromptManager(self.prompts_dir)
        result = manager.load_and_format(
            "unicode.txt", {"sanskrit_text": "ॐ नमः शिवाय"}
        )
        self.assertEqual(result, "Sanskrit: ॐ नमः शिवाय")

    def test_multiline_template(self):
        """Should handle multiline templates."""
        multiline = "Line 1: {var1}\nLine 2: {var2}\nLine 3: Done"
        (self.prompts_dir / "multiline.txt").write_text(
            multiline, encoding="utf-8"
        )

        manager = PromptManager(self.prompts_dir)
        result = manager.load_and_format(
            "multiline.txt", {"var1": "first", "var2": "second"}
        )
        expected = "Line 1: first\nLine 2: second\nLine 3: Done"
        self.assertEqual(result, expected)

    def test_empty_template(self):
        """Should handle empty template files."""
        (self.prompts_dir / "empty.txt").write_text("", encoding="utf-8")

        manager = PromptManager(self.prompts_dir)
        result = manager.load_template("empty.txt")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
