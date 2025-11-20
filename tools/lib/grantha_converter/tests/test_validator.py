# Standard library imports
import unittest
from pathlib import Path
import tempfile
import shutil

# Local imports
from grantha_converter.validator import Validator


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_validate_chunk_pass(self):
        validator = Validator(file_log_dir=self.test_dir)
        chunk_text = "This is a test with some Devanagari: देवनागरी"
        converted_body = "This is a converted test with the same Devanagari: देवनागरी"
        chunk_metadata = {"chunk_index": 1, "description": "Test Chunk"}

        result = validator.validate_chunk(chunk_text, converted_body, chunk_metadata)

        self.assertEqual(result["status"], "PASSED")
        self.assertEqual(result["char_diff"], 0)
        self.assertEqual(result["input_chars"], 8)
        self.assertEqual(result["output_chars"], 8)

    def test_validate_chunk_fail(self):
        validator = Validator(file_log_dir=self.test_dir, no_diff=True)
        chunk_text = "Original Devanagari: देवनागरी"
        converted_body = "Mismatched Devanagari: देवनागर"
        chunk_metadata = {"chunk_index": 2, "description": "Mismatch Test"}

        result = validator.validate_chunk(chunk_text, converted_body, chunk_metadata)

        self.assertEqual(result["status"], "MISMATCH")
        self.assertEqual(result["char_diff"], 1)
        self.assertEqual(result["input_chars"], 8)
        self.assertEqual(result["output_chars"], 7)


if __name__ == "__main__":
    unittest.main()
