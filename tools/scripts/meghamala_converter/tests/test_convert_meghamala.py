import unittest
import json
import sys
import tempfile
import os
import contextlib
from pathlib import Path
from unittest.mock import patch, MagicMock

# Adjust the path to import from the parent directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tools.scripts.meghamala_converter.convert_meghamala import run_main as convert_meghamala_main
from tools.lib.gemini_processor.cache_manager import AnalysisCache

# Mock data for analysis responses
FAKE_ANALYSIS_JSON = {
    "metadata": {
        "canonical_title": "Test Upanishad",
        "grantha_id": "test-upanishad",
        "structure_type": "prose",
    },
    "structural_analysis": {
        "suggested_filename": "test-upanishad-rangaramanuja-01-01",
        "sections": [
            {"type": "paragraph", "start_line": 1, "end_line": 5},
            {"type": "verse", "start_line": 6, "end_line": 10},
        ],
    },
    "chunking_strategy": {
        "execution_plan": [
            {"type": "section", "start_line": 1, "end_line": 5, "description": "Introduction"},
            {"type": "section", "start_line": 6, "end_line": 10, "description": "Main Content"},
        ]
    },
    "parsing_instructions": {
        "recommended_unit": "paragraph",
        "parsing_rules": ["rule1", "rule2"],
    },
}


class TestMeghamalaConverter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.input_dir = self.temp_dir / "input"
        self.output_dir = self.temp_dir / "output"
        self.input_dir.mkdir()
        self.output_dir.mkdir()

        self.base_args = [
            "--output-dir",
            str(self.output_dir),
            "--grantha-id",
            "test-grantha",
            "--canonical-title",
            "Test Grantha Title",
            "--analysis-cache-dir",
            str(self.temp_dir / ".analysis_cache"),
            "--prompts-dir",
            "tools/scripts/meghamala_converter/prompts",
        ]

        # Mock get_run_log_dir to prevent FileNotFoundError
        self.run_log_dir_patcher = patch('tools.scripts.meghamala_converter.convert_meghamala.get_run_log_dir')
        self.mock_get_run_log_dir = self.run_log_dir_patcher.start()
        self.mock_get_run_log_dir.return_value = self.temp_dir / "logs"
        (self.temp_dir / "logs").mkdir()

    def tearDown(self):
        self.run_log_dir_patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir)

    def _create_file(self, filename, content):
        file_path = self.input_dir / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path

    @contextlib.contextmanager
    def temp_dir_as_cwd(self):
        """Temporarily changes the current working directory."""
        old_cwd = Path.cwd()
        os.chdir(self.temp_dir)
        try:
            yield
        finally:
            os.chdir(old_cwd)

    @patch('sys.argv')
    @patch('tools.scripts.meghamala_converter.convert_meghamala.GeminiClient')
    def test_single_file_conversion_success(self, mock_gemini_client_class, mock_argv):
        mock_client = mock_gemini_client_class.return_value
        input_file = self._create_file("test.md", "# Title\nContent here.")

        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps(FAKE_ANALYSIS_JSON)),
            MagicMock(text="Converted chunk 1"),
            MagicMock(text="Converted chunk 2"),
        ]
        mock_client.upload_file.return_value = None

        with self.temp_dir_as_cwd():
            mock_argv.return_value = ['convert_meghamala.py'] + self.base_args + ["-i", str(input_file)]
            result = convert_meghamala_main()

        self.assertEqual(result, 0)
        self.assertTrue(output_file.exists())
        self.assertIn("Converted chunk 1", output_file.read_text())
        self.assertIn("Converted chunk 2", output_file.read_text())
        mock_client.generate_content.assert_called()

    @patch('tools.scripts.meghamala_converter.convert_meghamala.GeminiClient')
    def test_directory_conversion_success(self, mock_gemini_client_class):
        mock_client = mock_gemini_client_class.return_value
        file1 = self._create_file("part1.md", "Content for part 1")
        file2 = self._create_file("part2.md", "Content for part 2")

        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps(FAKE_ANALYSIS_JSON)),  # For part1 analysis
            MagicMock(text="Converted part1 chunk1"),
            MagicMock(text="Converted part1 chunk2"),
            MagicMock(text=json.dumps(FAKE_ANALYSIS_JSON)),  # For part2 analysis
            MagicMock(text="Converted part2 chunk1"),
            MagicMock(text="Converted part2 chunk2"),
        ]
        mock_client.upload_file.return_value = None

        result = convert_meghamala_main(self.base_args + ["-d", str(self.input_dir)])

        self.assertEqual(result, 0)
        self.assertTrue((self.output_dir / "test-upanishad-rangaramanuja-01-01.md").exists())
        self.assertTrue((self.output_dir / "test-upanishad-rangaramanuja-01-01.md").exists()) # This will be the same filename due to mock
        mock_client.generate_content.assert_called()

    @patch('tools.scripts.meghamala_converter.convert_meghamala.GeminiClient')
    def test_analysis_failure(self, mock_gemini_client_class):
        mock_client = mock_gemini_client_class.return_value
        input_file = self._create_file("test.md", "Invalid content")

        mock_client.generate_content.return_value = MagicMock(text="Invalid JSON response")
        mock_client.upload_file.return_value = None

        result = convert_meghamala_main(self.base_args + ["-i", str(input_file)])

        self.assertEqual(result, 1)
        self.assertFalse((self.output_dir / "test_converted.md").exists())

    @patch('tools.scripts.meghamala_converter.convert_meghamala.GeminiClient')
    def test_caching_behavior(self, mock_gemini_client_class):
        mock_client = mock_gemini_client_class.return_value
        input_file = self._create_file("cached_file.md", "Content for caching")

        analysis_response = FAKE_ANALYSIS_JSON.copy()
        analysis_response["structural_analysis"]["suggested_filename"] = "cached-output"

        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps(analysis_response)),
            MagicMock(text="Converted chunk 1"),
            MagicMock(text="Converted chunk 2"),
        ]
        mock_client.upload_file.return_value = None

        # First run: should call API and cache
        convert_meghamala_main(self.base_args + ["-i", str(input_file)])

        self.assertEqual(mock_client.generate_content.call_count, 3)
        mock_client.generate_content.reset_mock()

        # Second run: should use cache, no API call for analysis
        convert_meghamala_main(self.base_args + ["-i", str(input_file)])

        # Only chunk conversions should be called, not analysis
        self.assertEqual(mock_client.generate_content.call_count, 2)

        # Verify analysis cache file exists and is valid
        cache_dir = self.temp_dir / ".analysis_cache"
        self.assertTrue(cache_dir.exists())
        cache_files = list(cache_dir.glob(f"{input_file.stem}-*.json"))
        self.assertEqual(len(cache_files), 1)
        cached_content = json.loads(cache_files[0].read_text())
        self.assertEqual(cached_content["metadata"]["grantha_id"], "test-upanishad")

    @patch('tools.scripts.meghamala_converter.convert_meghamala.GeminiClient')
    def test_caching_with_duplicate_filenames(self, mock_gemini_client_class):
        mock_client = mock_gemini_client_class.return_value

        # Create two files with the same name in different directories
        sub_dir1 = self.input_dir / "subdir1"
        sub_dir1.mkdir()
        file1 = sub_dir1 / "duplicate.md"
        file1.write_text("Content for duplicate 1")

        sub_dir2 = self.input_dir / "subdir2"
        sub_dir2.mkdir()
        file2 = sub_dir2 / "duplicate.md"
        file2.write_text("Content for duplicate 2")

        analysis_response1 = FAKE_ANALYSIS_JSON.copy()
        analysis_response1["metadata"]["grantha_id"] = "duplicate-1"
        analysis_response1["structural_analysis"]["suggested_filename"] = "duplicate-output-1"

        analysis_response2 = FAKE_ANALYSIS_JSON.copy()
        analysis_response2["metadata"]["grantha_id"] = "duplicate-2"
        analysis_response2["structural_analysis"]["suggested_filename"] = "duplicate-output-2"

        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps(analysis_response1)), # Analysis for file1
            MagicMock(text="Converted chunk 1.1"),
            MagicMock(text="Converted chunk 1.2"),
            MagicMock(text=json.dumps(analysis_response2)), # Analysis for file2
            MagicMock(text="Converted chunk 2.1"),
            MagicMock(text="Converted chunk 2.2"),
        ]
        mock_client.upload_file.return_value = None

        # Convert file1
        convert_meghamala_main(self.base_args + ["-i", str(file1)])
        # Convert file2
        convert_meghamala_main(self.base_args + ["-i", str(file2)])

        cache_dir = self.temp_dir / ".analysis_cache"
        self.assertTrue(cache_dir.exists())

        # Verify two unique cache files were created
        cache_files = list(cache_dir.glob("duplicate-*.json"))
        self.assertEqual(len(cache_files), 2)

        # Verify content of cached files
        cache_content1 = json.loads(AnalysisCache(file1).load(verbose=False))
        self.assertEqual(cache_content1["metadata"]["grantha_id"], "duplicate-1")

        cache_content2 = json.loads(AnalysisCache(file2).load(verbose=False))
        self.assertEqual(cache_content2["metadata"]["grantha_id"], "duplicate-2")

    @patch('tools.scripts.meghamala_converter.convert_meghamala.GeminiClient')
    def test_default_analysis_cache_directory_creation(self, mock_gemini_client_class):
        mock_client = mock_gemini_client_class.return_value
        input_file = self._create_file("default_cache.md", "Content for default cache")

        analysis_response = FAKE_ANALYSIS_JSON.copy()
        analysis_response["structural_analysis"]["suggested_filename"] = "default-cache-output"

        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps(analysis_response)),
            MagicMock(text="Converted chunk 1"),
            MagicMock(text="Converted chunk 2"),
        ]
        mock_client.upload_file.return_value = None

        # Run without specifying --analysis-cache-dir
        args_without_cache_dir = [
            "-i", str(input_file),
            "--output-dir", str(self.output_dir),
            "--grantha-id", "default-grantha",
            "--canonical-title", "Default Grantha Title",
        ]

        convert_meghamala_main(args_without_cache_dir)

        default_cache_dir = self.temp_dir / ".analysis_cache"
        self.assertTrue(default_cache_dir.exists())
        cache_files = list(default_cache_dir.glob(f"{input_file.stem}-*.json"))
        self.assertEqual(len(cache_files), 1)

    @patch('tools.scripts.meghamala_converter.convert_meghamala.GeminiClient')
    def test_validation_summary_with_none_description(self, mock_gemini_client_class):
        mock_client = mock_gemini_client_class.return_value
        input_file = self._create_file("none_desc.md", "Content with no description")

        analysis_response = FAKE_ANALYSIS_JSON.copy()
        analysis_response["structural_analysis"]["suggested_filename"] = "none-desc-output"
        # Modify analysis to have a chunk with no description
        analysis_response["chunking_strategy"]["execution_plan"][0]["description"] = None

        mock_client.generate_content.side_effect = [
            MagicMock(text=json.dumps(analysis_response)),
            MagicMock(text="Converted chunk 1"),
            MagicMock(text="Converted chunk 2"),
        ]
        mock_client.upload_file.return_value = None

        result = convert_meghamala_main(self.base_args + ["-i", str(input_file)])

        self.assertEqual(result, 0)
        output_file = self.output_dir / "none-desc-output.md"
        self.assertTrue(output_file.exists())
        self.assertIn("Converted chunk 1", output_file.read_text())

    @patch('tools.scripts.meghamala_converter.convert_meghamala.get_file_log_dir')
    @patch('tools.scripts.meghamala_converter.convert_meghamala.get_run_log_dir')
    @patch('tools.scripts.meghamala_converter.convert_meghamala.ReplayGeminiClient')
    @patch('tools.scripts.meghamala_converter.convert_meghamala.GeminiClient')
    def test_replay_from_log_directory(self, mock_gemini_client_class, mock_replay_client_class, mock_get_run_log_dir, mock_get_file_log_dir):
        mock_gemini_client = mock_gemini_client_class.return_value
        mock_replay_client = mock_replay_client_class.return_value

        input_file_name = "test_replay.md"
        input_file_content = "Content for replay"
        input_file = self._create_file(input_file_name, input_file_content)
        
        analysis_response = FAKE_ANALYSIS_JSON.copy()
        analysis_response["structural_analysis"]["suggested_filename"] = "replay-output"
        
        # First run: Generate logs
        mock_gemini_client.generate_content.side_effect = [
            MagicMock(text=json.dumps(analysis_response)),
            MagicMock(text="Converted content for replay")
        ]
        mock_gemini_client.upload_file.return_value = None # Mock upload to avoid actual upload

        first_run_log_dir = self.temp_dir / "run_first"
        first_run_log_dir.mkdir()
        mock_get_run_log_dir.return_value = first_run_log_dir
        file_log_dir = first_run_log_dir / input_file.stem
        file_log_dir.mkdir()
        (file_log_dir / "analysis").mkdir()
        (file_log_dir / "chunks").mkdir()
        mock_get_file_log_dir.return_value = file_log_dir

        convert_meghamala_main(self.base_args + ["-i", str(input_file)])
            
        self.assertTrue(first_run_log_dir.exists())
        self.assertTrue((first_run_log_dir / input_file.stem / "analysis" / "02_analysis_response_raw.txt").exists())
        self.assertTrue((first_run_log_dir / input_file.stem / "chunks" / "000_response.txt").exists())

        # Second run: Replay from logs
        mock_gemini_client.generate_content.reset_mock()
        mock_gemini_client.upload_file.reset_mock()

        replay_run_log_dir = self.temp_dir / "run_replay"
        mock_get_run_log_dir.return_value = replay_run_log_dir

        replay_args = self.base_args + [
            "-i", str(input_file),
            "--replay-from", str(first_run_log_dir)
        ]
        convert_meghamala_main(replay_args)

        # Verify ReplayGeminiClient was instantiated with the correct log directory and input_file_stem
        mock_replay_client_class.assert_called_once_with(first_run_log_dir, input_file_stem=input_file.stem)
        
        # Verify ReplayGeminiClient's generate_content was called
        self.assertTrue(mock_replay_client.generate_content.called)

        # Verify no GeminiClient API calls were made during replay
        mock_gemini_client.generate_content.assert_not_called()
        mock_gemini_client.upload_file.assert_not_called()

        # Verify output is identical
        output_file = self.output_dir / "replay-output.md"
        self.assertTrue(output_file.exists())
        self.assertEqual(output_file.read_text(), "Converted content for replay")


if __name__ == '__main__':
    unittest.main()
