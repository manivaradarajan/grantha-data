"""Tests for cache_manager module."""

import json
import tempfile
import unittest
from pathlib import Path

from gemini_processor.cache_manager import AnalysisCache


class TestAnalysisCache(unittest.TestCase):
    """Test suite for AnalysisCache class."""

    def setUp(self):
        """Create temporary test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Create a test input file
        self.test_file = self.temp_path / "test_input.md"
        self.test_file.write_text("Test content for caching", encoding="utf-8")

        self.cache = AnalysisCache(str(self.test_file))

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_cache_path_generation(self):
        """Should generate correct cache path."""
        # Cache filename should follow pattern: .cache_analysis_{stem}-{hash}.json
        # where hash is first 8 chars of SHA256 of absolute path
        cache_name = self.cache.cache_path.name

        # Check filename pattern
        self.assertTrue(cache_name.startswith(".cache_analysis_test_input-"))
        self.assertTrue(cache_name.endswith(".json"))

        # Extract hash portion (between last '-' and '.json')
        hash_part = cache_name.split("-")[-1].replace(".json", "")
        self.assertEqual(len(hash_part), 8)  # Should be 8 hex chars
        self.assertTrue(all(c in "0123456789abcdef" for c in hash_part))

        # Check parent directory
        self.assertEqual(self.cache.cache_path.parent, self.temp_path)

    def test_load_missing_cache_returns_none(self):
        """Should return None when cache file doesn't exist."""
        result = self.cache.load(verbose=False)
        self.assertIsNone(result)

    def test_save_and_load_cache(self):
        """Should save and load cache successfully."""
        analysis = {"metadata": {"title": "Test"}, "structure": ["item1", "item2"]}

        # Save cache
        success = self.cache.save(analysis, verbose=False)
        self.assertTrue(success)
        self.assertTrue(self.cache.cache_path.exists())

        # Load cache
        loaded = self.cache.load(verbose=False)
        self.assertEqual(loaded, analysis)

    def test_cache_invalidation_on_file_change(self):
        """Should invalidate cache when file content changes."""
        analysis = {"data": "original"}

        # Save cache
        self.cache.save(analysis, verbose=False)

        # Modify the input file
        self.test_file.write_text("Modified content", encoding="utf-8")

        # Cache should be invalid
        loaded = self.cache.load(verbose=False)
        self.assertIsNone(loaded)

    def test_cache_with_unicode(self):
        """Should handle Unicode content correctly."""
        self.test_file.write_text("Sanskrit: ॐ नमः शिवाय", encoding="utf-8")
        cache = AnalysisCache(str(self.test_file))

        analysis = {"sanskrit": "ॐ नमः शिवाय", "chinese": "你好"}
        cache.save(analysis, verbose=False)
        loaded = cache.load(verbose=False)

        self.assertEqual(loaded["sanskrit"], "ॐ नमः शिवाय")
        self.assertEqual(loaded["chinese"], "你好")

    def test_corrupted_cache_returns_none(self):
        """Should return None for corrupted cache file."""
        # Create corrupted cache file
        self.cache.cache_path.write_text("not valid json{{{", encoding="utf-8")

        loaded = self.cache.load(verbose=False)
        self.assertIsNone(loaded)

    def test_cache_missing_required_fields(self):
        """Should return None if cache missing required fields."""
        # Create cache with missing 'analysis' field
        corrupt_cache = {"file_hash": "abc123", "timestamp": "2024-01-01"}
        self.cache.cache_path.write_text(
            json.dumps(corrupt_cache), encoding="utf-8"
        )

        loaded = self.cache.load(verbose=False)
        self.assertIsNone(loaded)

    def test_cache_includes_metadata(self):
        """Cache should include timestamp and version."""
        analysis = {"test": "data"}
        self.cache.save(analysis, verbose=False)

        # Read cache file directly
        with open(self.cache.cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        self.assertIn("timestamp", cache_data)
        self.assertIn("version", cache_data)
        self.assertIn("file_hash", cache_data)
        self.assertEqual(cache_data["version"], "1.0")

    def test_clear_cache(self):
        """Should delete cache file."""
        analysis = {"test": "data"}
        self.cache.save(analysis, verbose=False)
        self.assertTrue(self.cache.cache_path.exists())

        success = self.cache.clear(verbose=False)
        self.assertTrue(success)
        self.assertFalse(self.cache.cache_path.exists())

    def test_clear_nonexistent_cache(self):
        """Should return True when clearing non-existent cache."""
        success = self.cache.clear(verbose=False)
        self.assertTrue(success)

    def test_file_hash_consistency(self):
        """Same file content should produce same hash."""
        hash1 = self.cache._get_file_hash()
        hash2 = self.cache._get_file_hash()
        self.assertEqual(hash1, hash2)

    def test_file_hash_changes_with_content(self):
        """Different file content should produce different hash."""
        hash1 = self.cache._get_file_hash()

        self.test_file.write_text("Different content", encoding="utf-8")
        hash2 = self.cache._get_file_hash()

        self.assertNotEqual(hash1, hash2)

    def test_large_analysis_data(self):
        """Should handle large analysis data."""
        # Create large analysis result
        analysis = {
            "data": ["item" * 1000 for _ in range(100)],
            "metadata": {"key": "value" * 1000},
        }

        success = self.cache.save(analysis, verbose=False)
        self.assertTrue(success)

        loaded = self.cache.load(verbose=False)
        self.assertEqual(len(loaded["data"]), 100)

    def test_empty_analysis(self):
        """Should handle empty analysis dict."""
        analysis = {}
        success = self.cache.save(analysis, verbose=False)
        self.assertTrue(success)

        loaded = self.cache.load(verbose=False)
        self.assertEqual(loaded, {})

    def test_nonexistent_input_file(self):
        """Should raise FileNotFoundError for non-existent input file."""
        nonexistent = self.temp_path / "does_not_exist.md"
        cache = AnalysisCache(str(nonexistent))

        with self.assertRaises(FileNotFoundError):
            cache._get_file_hash()


if __name__ == "__main__":
    unittest.main()
