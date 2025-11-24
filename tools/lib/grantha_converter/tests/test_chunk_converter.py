# Standard library imports
import unittest
from unittest.mock import MagicMock
from pathlib import Path
import tempfile
import shutil

# Local imports
from grantha_converter.chunk_converter import ChunkConverter


class TestChunkConverter(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.mock_client = MagicMock()
        self.mock_prompt_manager = MagicMock()
        self.file_log_dir = self.test_dir / "logs"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

        self.mock_client.upload_file.return_value = MagicMock(
            name="uploaded_file",
            display_name="chunk_1.md",
            size_bytes=100,
            state="ACTIVE",
            uri="file://dummy/chunk_1.md",
        )
        self.mock_prompt_manager.load_template.return_value = (
            "Prompt template with {commentary_id} and {analysis_json}"
        )
        self.mock_client.generate_content.return_value = "Converted chunk body"

        converter = ChunkConverter(
            client=self.mock_client,
            prompt_manager=self.mock_prompt_manager,
            file_log_dir=self.file_log_dir,
        )

        chunk_text = "This is a test chunk."
        chunk_metadata = {"chunk_index": 1}
        analysis_result = {
            "metadata": {
                "grantha_id": "test-id",
                "canonical_title": "Test Title",
                "structure_type": "verse",
            }
        }

        # Act
        result = converter.convert(
            chunk_text, chunk_metadata, analysis_result, "gemini-model"
        )

        # Assert
        self.assertIn("grantha_id: test-id", result)
        self.assertIn("Converted chunk body", result)
        self.mock_client.generate_content.assert_called_once()
        mock_upload.assert_called_once()


if __name__ == "__main__":
    unittest.main()
