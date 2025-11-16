import os
import shutil
import sys
import unittest
from typing import List, Tuple
from unittest.mock import patch

from grantha_converter.hide_editor_comments import (
    find_converted_md_files,
    hide_editor_comments,
    validate_devanagari,
)
from grantha_converter.hide_editor_comments import main as hide_comments_main


class TestHideEditorComments(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory with sample files for testing."""
        self.test_dir = 'temp_test_granthas'
        os.makedirs(self.test_dir, exist_ok=True)

        self.sample_files = {
            "no_comments.converted.md": "This file has no comments.",
            "simple_comment.converted.md": "Here is a comment [अश्चानुबन्धिषु दृष्टिः] that needs hiding.",
            "mixed_comment.converted.md": "Another [comment with mixed chars and numbers 123] here.",
            "already_hidden.converted.md": "This one is <!-- hide -->[already hidden]<!-- /hide -->.",
            "markdown_link.converted.md": "This is a [markdown link](to/somewhere) that should be ignored.",
            "escaped_bracket.converted.md": "This is an escaped \\\[comment] that needs hiding.",
            "multiple_comments.converted.md": "File with [comment 1] and [comment 2]. And a [link](url).",
            "empty_file.converted.md": "",
            "no_match.txt": "This file should not be processed [comment].",
        }

        for filename, content in self.sample_files.items():
            with open(os.path.join(self.test_dir, filename), 'w', encoding='utf-8') as f:
                f.write(content)

    def tearDown(self):
        """Remove the temporary directory after tests."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_find_converted_md_files(self):
        """Test that the script correctly finds all *.converted.md files."""
        found_files = find_converted_md_files(self.test_dir)
        self.assertEqual(len(found_files), 8)
        self.assertTrue(any("simple_comment.converted.md" in f for f in found_files))
        self.assertFalse(any("no_match.txt" in f for f in found_files))

    def test_hide_simple_comment(self):
        """Test hiding a simple Devanagari comment."""
        file_path = os.path.join(self.test_dir, "simple_comment.converted.md")
        _, modified_content = hide_editor_comments(file_path)
        self.assertIn("<!-- hide -->[अश्चानुबन्धिषु दृष्टिः]<!-- /hide -->", modified_content)

    def test_idempotency(self):
        """Test that the script does not re-wrap already hidden comments."""
        file_path = os.path.join(self.test_dir, "already_hidden.converted.md")
        original_content, modified_content = hide_editor_comments(file_path)
        self.assertEqual(original_content, modified_content)

    def test_ignore_markdown_links(self):
        """Test that markdown links are not modified."""
        file_path = os.path.join(self.test_dir, "markdown_link.converted.md")
        original_content, modified_content = hide_editor_comments(file_path)
        self.assertEqual(original_content, modified_content)
        self.assertNotIn("<!-- hide -->", modified_content)

    def test_escaped_bracket(self):
        """Test that escaped brackets are handled correctly."""
        file_path = os.path.join(self.test_dir, "escaped_bracket.converted.md")
        _, modified_content = hide_editor_comments(file_path)
        self.assertIn("<!-- hide -->\\\\[comment]<!-- /hide -->", modified_content)

    def test_multiple_comments_and_links(self):
        """Test a file with a mix of comments and links."""
        file_path = os.path.join(self.test_dir, "multiple_comments.converted.md")
        _, modified_content = hide_editor_comments(file_path)
        self.assertIn("<!-- hide -->[comment 1]<!-- /hide -->", modified_content)
        self.assertIn("<!-- hide -->[comment 2]<!-- /hide -->", modified_content)
        self.assertIn("[link](url)", modified_content)
        self.assertNotIn("<!-- hide -->[link](url)<!-- /hide -->", modified_content)

    def test_devanagari_validation(self):
        """Test the Devanagari character validation logic."""
        original = "some text [अक्षर] some more"
        modified_correct = "some text <!-- hide -->[अक्षर]<!-- /hide --> some more"
        modified_incorrect = "some text <!-- hide -->[अक्शर]<!-- /hide --> some more"
        self.assertTrue(validate_devanagari(original, modified_correct))
        self.assertFalse(validate_devanagari(original, modified_incorrect))

    def test_main_script_execution(self):
        """Test the main script execution path."""
        dummy_filepath = os.path.join(self.test_dir, "dummy_file.md")
        with open(dummy_filepath, "w", encoding="utf-8") as f:
            f.write("This is a test file with a [comment to hide].")

        with patch.object(sys, 'argv', ['hide_editor_comments.py', dummy_filepath]):
            hide_comments_main()

        with open(dummy_filepath, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("<!-- hide -->[comment to hide]<!-- /hide -->", content)


if __name__ == "__main__":
    unittest.main()
