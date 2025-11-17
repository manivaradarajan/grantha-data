"""Tests for file_manager module."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from gemini_processor.file_manager import (
    FileUploadCache,
    clear_upload_cache,
    get_cached_upload,
    get_file_hash,
    upload_file_with_cache,
)


class TestFileUploadCache(unittest.TestCase):
    """Test suite for FileUploadCache class."""

    def setUp(self):
        """Create temporary cache file and test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.cache_file = self.temp_path / "upload_cache.json"
        self.test_file = self.temp_path / "test.md"
        self.test_file.write_text("Test content", encoding="utf-8")

        self.cache = FileUploadCache(str(self.cache_file))

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_init_creates_cache(self):
        """Should initialize with cache file path."""
        self.assertEqual(self.cache.cache_file, self.cache_file)

    def test_load_empty_cache(self):
        """Should return empty dict for non-existent cache."""
        cache_data = self.cache._load_cache()
        self.assertEqual(cache_data, {})

    def test_save_and_load_cache(self):
        """Should save and load cache successfully."""
        cache_data = {"key1": "value1", "key2": "value2"}
        self.cache._save_cache(cache_data)

        loaded = self.cache._load_cache()
        self.assertEqual(loaded, cache_data)

    def test_corrupted_cache_returns_empty(self):
        """Should return empty dict for corrupted cache."""
        self.cache_file.write_text("invalid json{{{", encoding="utf-8")
        cache_data = self.cache._load_cache()
        self.assertEqual(cache_data, {})

    def test_file_hash_calculation(self):
        """Should calculate consistent file hash."""
        hash1 = get_file_hash(str(self.test_file))
        hash2 = get_file_hash(str(self.test_file))
        self.assertEqual(hash1, hash2)

    def test_file_hash_changes_with_content(self):
        """Should produce different hash for different content."""
        hash1 = get_file_hash(str(self.test_file))

        self.test_file.write_text("Different content", encoding="utf-8")
        hash2 = get_file_hash(str(self.test_file))

        self.assertNotEqual(hash1, hash2)

    def test_get_cached_upload_miss(self):
        """Should return None when no cache entry exists."""
        mock_client = Mock()
        result = self.cache.get_cached_upload(mock_client, str(self.test_file))
        self.assertIsNone(result)

    def test_get_cached_upload_hit_active_file(self):
        """Should return file object for valid cached upload."""
        mock_client = Mock()
        mock_file = Mock()
        mock_file.state = "ACTIVE"
        mock_client.files.get.return_value = mock_file

        # Create cache entry
        file_hash = get_file_hash(str(self.test_file))
        cache_key = f"{self.test_file}:{file_hash}"
        cache_data = {cache_key: {"name": "files/test123"}}
        self.cache._save_cache(cache_data)

        result = self.cache.get_cached_upload(mock_client, str(self.test_file))
        self.assertEqual(result, mock_file)
        mock_client.files.get.assert_called_once_with(name="files/test123")

    def test_get_cached_upload_inactive_file(self):
        """Should return None if cached file is not active."""
        mock_client = Mock()
        mock_file = Mock()
        mock_file.state = "PROCESSING"
        mock_client.files.get.return_value = mock_file

        # Create cache entry
        file_hash = get_file_hash(str(self.test_file))
        cache_key = f"{self.test_file}:{file_hash}"
        cache_data = {cache_key: {"name": "files/test123"}}
        self.cache._save_cache(cache_data)

        result = self.cache.get_cached_upload(mock_client, str(self.test_file))
        self.assertIsNone(result)

    def test_get_cached_upload_file_not_found_in_gemini(self):
        """Should return None if file no longer exists in Gemini."""
        mock_client = Mock()
        mock_client.files.get.side_effect = Exception("File not found")

        # Create cache entry
        file_hash = get_file_hash(str(self.test_file))
        cache_key = f"{self.test_file}:{file_hash}"
        cache_data = {cache_key: {"name": "files/test123"}}
        self.cache._save_cache(cache_data)

        result = self.cache.get_cached_upload(mock_client, str(self.test_file))
        self.assertIsNone(result)

    def test_cache_upload(self):
        """Should cache upload information."""
        mock_file = Mock()
        mock_file.name = "files/test123"
        mock_file.uri = "https://example.com/file"
        mock_file.display_name = "test.md"
        mock_file.size_bytes = 1024

        self.cache.cache_upload(str(self.test_file), mock_file, verbose=False)

        # Verify cache was created
        cache_data = self.cache._load_cache()
        self.assertEqual(len(cache_data), 1)

        # Verify cache contains correct data
        cache_entry = list(cache_data.values())[0]
        self.assertEqual(cache_entry["name"], "files/test123")
        self.assertEqual(cache_entry["uri"], "https://example.com/file")
        self.assertEqual(cache_entry["display_name"], "test.md")
        self.assertEqual(cache_entry["size_bytes"], 1024)

    def test_clear_cache(self):
        """Should delete cache file."""
        # Create cache
        self.cache._save_cache({"key": "value"})
        self.assertTrue(self.cache_file.exists())

        # Clear cache
        success = self.cache.clear()
        self.assertTrue(success)
        self.assertFalse(self.cache_file.exists())

    def test_clear_nonexistent_cache(self):
        """Should return True for non-existent cache."""
        success = self.cache.clear()
        self.assertTrue(success)


class TestUploadFileWithCache(unittest.TestCase):
    """Test suite for upload_file_with_cache function."""

    def setUp(self):
        """Create temporary files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.test_file = self.temp_path / "test.md"
        self.test_file.write_text("Test content", encoding="utf-8")

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_upload_without_cache_manager(self):
        """Should upload file without caching when no cache manager."""
        mock_client = Mock()
        mock_file = Mock()
        mock_file.name = "files/test123"
        mock_file.uri = "https://example.com/file"
        mock_client.files.upload.return_value = mock_file

        result = upload_file_with_cache(
            mock_client, str(self.test_file), cache_manager=None, verbose=False
        )

        self.assertEqual(result, mock_file)
        mock_client.files.upload.assert_called_once()

    def test_upload_with_cache_hit(self):
        """Should use cached upload when available."""
        mock_client = Mock()
        mock_cached_file = Mock()

        mock_cache_manager = Mock()
        mock_cache_manager.get_cached_upload.return_value = mock_cached_file

        result = upload_file_with_cache(
            mock_client,
            str(self.test_file),
            cache_manager=mock_cache_manager,
            verbose=False,
        )

        self.assertEqual(result, mock_cached_file)
        # Should not upload
        mock_client.files.upload.assert_not_called()

    def test_upload_with_cache_miss(self):
        """Should upload and cache when cache miss."""
        mock_client = Mock()
        mock_file = Mock()
        mock_file.name = "files/test123"
        mock_file.uri = "https://example.com/file"
        mock_client.files.upload.return_value = mock_file

        mock_cache_manager = Mock()
        mock_cache_manager.get_cached_upload.return_value = None

        result = upload_file_with_cache(
            mock_client,
            str(self.test_file),
            cache_manager=mock_cache_manager,
            verbose=False,
        )

        self.assertEqual(result, mock_file)
        mock_client.files.upload.assert_called_once()
        mock_cache_manager.cache_upload.assert_called_once_with(
            str(self.test_file), mock_file, verbose=False
        )

    def test_upload_nonexistent_file_raises_error(self):
        """Should raise FileNotFoundError for non-existent file."""
        mock_client = Mock()
        nonexistent = self.temp_path / "does_not_exist.md"

        with self.assertRaises(FileNotFoundError):
            upload_file_with_cache(mock_client, str(nonexistent), verbose=False)

    def test_upload_failure_returns_none(self):
        """Should return None on upload failure."""
        mock_client = Mock()
        mock_client.files.upload.side_effect = Exception("Upload failed")

        result = upload_file_with_cache(mock_client, str(self.test_file), verbose=False)

        self.assertIsNone(result)

    def test_upload_with_custom_mime_type(self):
        """Should use custom MIME type when specified."""
        mock_client = Mock()
        mock_file = Mock()
        mock_client.files.upload.return_value = mock_file

        upload_file_with_cache(
            mock_client, str(self.test_file), mime_type="text/plain", verbose=False
        )

        # Check that upload was called with correct mime_type
        call_args = mock_client.files.upload.call_args
        self.assertEqual(call_args[1]["config"]["mime_type"], "text/plain")


class TestConvenienceFunctions(unittest.TestCase):
    """Test suite for module-level convenience functions."""

    def setUp(self):
        """Create temporary files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.test_file = self.temp_path / "test.md"
        self.test_file.write_text("Test content", encoding="utf-8")
        self.cache_file = self.temp_path / "cache.json"

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_get_cached_upload_convenience(self):
        """Should use FileUploadCache internally."""
        mock_client = Mock()
        mock_client.files.get.side_effect = Exception("Not found")

        result = get_cached_upload(
            mock_client, str(self.test_file), str(self.cache_file)
        )
        self.assertIsNone(result)

    def test_clear_upload_cache_convenience(self):
        """Should clear cache using FileUploadCache."""
        # Create cache file
        self.cache_file.write_text('{"key": "value"}', encoding="utf-8")

        success = clear_upload_cache(str(self.cache_file))
        self.assertTrue(success)
        self.assertFalse(self.cache_file.exists())


if __name__ == "__main__":
    unittest.main()
