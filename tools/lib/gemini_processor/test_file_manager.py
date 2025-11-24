"""Tests for file_manager module."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from gemini_processor.file_manager import (
    FileUploadCache,
    clear_upload_cache,
    get_cached_upload,
    get_file_hash,
    upload_file_with_cache,
)


def _make_timestamp(hours_ago: float) -> str:
    """Helper to create ISO timestamp for testing.

    Args:
        hours_ago: How many hours in the past to create timestamp for.

    Returns:
        ISO format timestamp string.
    """
    timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return timestamp.isoformat()


class TestFileUploadCache(unittest.TestCase):
    """Test suite for FileUploadCache class."""

    def setUp(self):
        """Create temporary cache file and test files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.cache_file = self.temp_path / "upload_cache.json"
        self.test_file = self.temp_path / "test.md"
        self.test_file.write_text("Test content", encoding="utf-8")

        self.cache = FileUploadCache(self.cache_file)

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
        hash1 = get_file_hash(self.test_file)
        hash2 = get_file_hash(self.test_file)
        self.assertEqual(hash1, hash2)

    def test_file_hash_changes_with_content(self):
        """Should produce different hash for different content."""
        hash1 = get_file_hash(self.test_file)

        self.test_file.write_text("Different content", encoding="utf-8")
        hash2 = get_file_hash(self.test_file)

        self.assertNotEqual(hash1, hash2)

    def test_get_cached_upload_miss(self):
        """Should return None when no cache entry exists."""
        mock_client = Mock()
        result = self.cache.get_cached_upload(mock_client, self.test_file)
        self.assertIsNone(result)

    def test_get_cached_upload_hit_active_file(self):
        """Should return file object for valid fresh cached upload."""
        mock_client = Mock()
        mock_file = Mock()
        mock_file.state = "ACTIVE"
        mock_client.files.get.return_value = mock_file

        # Create cache entry with fresh timestamp (uploaded 1 hour ago)
        file_hash = get_file_hash(self.test_file)
        cache_key = file_hash
        cache_data = {
            cache_key: {
                "name": "files/test123",
                "uploaded_at": _make_timestamp(hours_ago=1),
            }
        }
        self.cache._save_cache(cache_data)

        result = self.cache.get_cached_upload(mock_client, self.test_file)
        self.assertEqual(result, mock_file)
        # Should still call API to get file object (fresh files skip validation
        # but still need to fetch the file object)
        mock_client.files.get.assert_called_once_with(name="files/test123")

    def test_get_cached_upload_inactive_file(self):
        """Should return None if cached file is not active (validation window)."""
        mock_client = Mock()
        mock_file = Mock()
        mock_file.state = "PROCESSING"
        mock_client.files.get.return_value = mock_file

        # Create cache entry in validation window (47 hours old)
        file_hash = get_file_hash(self.test_file)
        cache_key = file_hash
        cache_data = {
            cache_key: {
                "name": "files/test123",
                "uploaded_at": _make_timestamp(hours_ago=47),
            }
        }
        self.cache._save_cache(cache_data)

        result = self.cache.get_cached_upload(mock_client, self.test_file)
        self.assertIsNone(result)

    def test_get_cached_upload_file_not_found_in_gemini(self):
        """Should return None if file no longer exists in Gemini."""
        mock_client = Mock()
        mock_client.files.get.side_effect = Exception("File not found")

        # Create cache entry with fresh timestamp
        file_hash = get_file_hash(self.test_file)
        cache_key = file_hash
        cache_data = {
            cache_key: {
                "name": "files/test123",
                "uploaded_at": _make_timestamp(hours_ago=1),
            }
        }
        self.cache._save_cache(cache_data)

        result = self.cache.get_cached_upload(mock_client, self.test_file)
        self.assertIsNone(result)

    def test_cache_upload(self):
        """Should cache upload information."""
        mock_file = Mock()
        mock_file.name = "files/test123"
        mock_file.uri = "https://example.com/file"
        mock_file.display_name = "test.md"
        mock_file.size_bytes = 1024

        self.cache.cache_upload(self.test_file, mock_file, verbose=False)

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

    def test_get_cached_upload_expired_file(self):
        """Should return None for expired cached upload without API call."""
        mock_client = Mock()

        # Create cache entry that's expired (50 hours old)
        file_hash = get_file_hash(self.test_file)
        cache_data = {
            file_hash: {
                "name": "files/test123",
                "uploaded_at": _make_timestamp(hours_ago=50),
            }
        }
        self.cache._save_cache(cache_data)

        result = self.cache.get_cached_upload(mock_client, self.test_file)
        self.assertIsNone(result)
        # Should NOT call API for expired files
        mock_client.files.get.assert_not_called()

    def test_get_cached_upload_near_expiration_validates(self):
        """Should validate with API for files near expiration (46-48h old)."""
        mock_client = Mock()
        mock_file = Mock()
        mock_file.state = "ACTIVE"
        mock_client.files.get.return_value = mock_file

        # Create cache entry in validation window (47 hours old)
        file_hash = get_file_hash(self.test_file)
        cache_data = {
            file_hash: {
                "name": "files/test123",
                "uploaded_at": _make_timestamp(hours_ago=47),
            }
        }
        self.cache._save_cache(cache_data)

        result = self.cache.get_cached_upload(mock_client, self.test_file)
        self.assertEqual(result, mock_file)
        # SHOULD call API to validate near-expiration files
        mock_client.files.get.assert_called_once_with(name="files/test123")

    def test_cleanup_expired_removes_old_entries(self):
        """Should remove expired cache entries."""
        # Create cache with both fresh and expired entries
        fresh_hash = "fresh_hash_123"
        expired_hash = "expired_hash_456"

        cache_data = {
            fresh_hash: {
                "name": "files/fresh",
                "uploaded_at": _make_timestamp(hours_ago=1),  # Fresh
            },
            expired_hash: {
                "name": "files/expired",
                "uploaded_at": _make_timestamp(hours_ago=50),  # Expired
            },
        }
        self.cache._save_cache(cache_data)

        # Run cleanup
        removed_count = self.cache.cleanup_expired()

        # Should have removed 1 entry
        self.assertEqual(removed_count, 1)

        # Verify only fresh entry remains
        loaded_cache = self.cache._load_cache()
        self.assertEqual(len(loaded_cache), 1)
        self.assertIn(fresh_hash, loaded_cache)
        self.assertNotIn(expired_hash, loaded_cache)

    def test_cleanup_expired_preserves_fresh_entries(self):
        """Should preserve all fresh cache entries."""
        # Create cache with only fresh entries
        cache_data = {
            "hash1": {
                "name": "files/test1",
                "uploaded_at": _make_timestamp(hours_ago=1),
            },
            "hash2": {
                "name": "files/test2",
                "uploaded_at": _make_timestamp(hours_ago=5),
            },
        }
        self.cache._save_cache(cache_data)

        # Run cleanup
        removed_count = self.cache.cleanup_expired()

        # Should have removed 0 entries
        self.assertEqual(removed_count, 0)

        # Verify all entries remain
        loaded_cache = self.cache._load_cache()
        self.assertEqual(len(loaded_cache), 2)

    def test_cleanup_expired_no_entries(self):
        """Should handle cleanup with empty cache."""
        removed_count = self.cache.cleanup_expired()
        self.assertEqual(removed_count, 0)


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
            mock_client, self.test_file, cache_manager=None, verbose=False
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
            self.test_file,
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
            self.test_file,
            cache_manager=mock_cache_manager,
            verbose=False,
        )

        self.assertEqual(result, mock_file)
        mock_client.files.upload.assert_called_once()
        mock_cache_manager.cache_upload.assert_called_once_with(
            self.test_file, mock_file, verbose=False
        )

    def test_upload_nonexistent_file_raises_error(self):
        """Should raise FileNotFoundError for non-existent file."""
        mock_client = Mock()
        nonexistent = self.temp_path / "does_not_exist.md"

        with self.assertRaises(FileNotFoundError):
            upload_file_with_cache(mock_client, nonexistent, verbose=False)

    def test_upload_failure_returns_none(self):
        """Should return None on upload failure."""
        mock_client = Mock()
        mock_client.files.upload.side_effect = Exception("Upload failed")

        result = upload_file_with_cache(mock_client, self.test_file, verbose=False)

        self.assertIsNone(result)

    def test_upload_with_custom_mime_type(self):
        """Should use custom MIME type when specified."""
        mock_client = Mock()
        mock_file = Mock()
        mock_client.files.upload.return_value = mock_file

        upload_file_with_cache(
            mock_client, self.test_file, mime_type="text/plain", verbose=False
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

        result = get_cached_upload(mock_client, self.test_file, self.cache_file)
        self.assertIsNone(result)

    def test_clear_upload_cache_convenience(self):
        """Should clear cache using FileUploadCache."""
        # Create cache file
        self.cache_file.write_text('{"key": "value"}', encoding="utf-8")

        success = clear_upload_cache(self.cache_file)
        self.assertTrue(success)
        self.assertFalse(self.cache_file.exists())


if __name__ == "__main__":
    unittest.main()
