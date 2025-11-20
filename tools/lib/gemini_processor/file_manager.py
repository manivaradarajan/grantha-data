"""File upload and caching utilities for Gemini API.

Provides file upload functionality with intelligent time-aware caching to avoid
redundant uploads of the same files. Respects Gemini's 48-hour file expiration
policy while minimizing unnecessary API validation calls.

Typical usage example:

    cache = FileUploadCache(Path(".upload_cache.json"))
    uploaded_file = upload_file_with_cache(
        client=genai_client,
        file_path=Path("document.pdf"),
        cache_manager=cache,
        verbose=True
    )
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from google import genai

# Configure module logger
logger = logging.getLogger(__name__)

# Gemini API file time-to-live (files expire after 48 hours)
_GEMINI_FILE_TTL_HOURS: int = 48

# Cache validation thresholds:
# - Fresh threshold: Skip API validation if upload is younger than this
# - Expiration threshold: Skip API call if upload is older than this
_CACHE_FRESH_THRESHOLD_HOURS: int = 46
_CACHE_EXPIRATION_HOURS: int = 48


def get_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file.

    Reads the file in 4KB chunks to handle large files efficiently without
    loading the entire file into memory.

    Args:
        file_path: Path to the file to hash.

    Returns:
        SHA256 hex digest (64 character lowercase hex string) of file contents.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        IOError: If the file cannot be read.

    Example:
        >>> hash_val = get_file_hash(Path("document.pdf"))
        >>> len(hash_val)
        64
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in 4KB chunks to handle large files efficiently
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _parse_upload_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse an ISO format timestamp string into a datetime object.

    Args:
        timestamp_str: ISO format timestamp string (e.g., "2025-11-20T08:30:00").

    Returns:
        Timezone-aware datetime object in UTC, or None if parsing fails.

    Example:
        >>> dt = _parse_upload_timestamp("2025-11-20T08:30:00")
        >>> dt.tzinfo is not None
        True
    """
    try:
        # Parse ISO format timestamp and ensure it's timezone-aware (UTC)
        dt = datetime.fromisoformat(timestamp_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def _get_file_age_hours(uploaded_at: str) -> Optional[float]:
    """Calculate how many hours ago a file was uploaded.

    Args:
        uploaded_at: ISO format timestamp string of when file was uploaded.

    Returns:
        Number of hours since upload as a float, or None if timestamp is invalid.

    Example:
        >>> age = _get_file_age_hours("2025-11-20T06:30:00")
        >>> age is not None and age >= 0
        True
    """
    upload_time = _parse_upload_timestamp(uploaded_at)
    if not upload_time:
        return None

    now = datetime.now(timezone.utc)
    age_delta = now - upload_time
    return age_delta.total_seconds() / 3600.0


def _is_file_fresh(uploaded_at: str) -> bool:
    """Check if an uploaded file is fresh enough to skip API validation.

    Fresh files are younger than 46 hours and can be trusted to still exist
    in Gemini without making an API call to verify.

    Args:
        uploaded_at: ISO format timestamp string of when file was uploaded.

    Returns:
        True if file is fresh (< 46 hours old), False otherwise.

    Example:
        >>> _is_file_fresh("2025-11-20T10:00:00")  # Recent upload
        True
        >>> _is_file_fresh("2025-11-18T10:00:00")  # Old upload
        False
    """
    age_hours = _get_file_age_hours(uploaded_at)
    if age_hours is None:
        return False
    return age_hours < _CACHE_FRESH_THRESHOLD_HOURS


def _is_file_expired(uploaded_at: str) -> bool:
    """Check if an uploaded file has expired in Gemini.

    Files older than 48 hours are expired and no longer accessible in Gemini.
    We can skip the API validation call and return None immediately.

    Args:
        uploaded_at: ISO format timestamp string of when file was uploaded.

    Returns:
        True if file is expired (>= 48 hours old), False otherwise.

    Example:
        >>> _is_file_expired("2025-11-18T10:00:00")  # Old upload
        True
        >>> _is_file_expired("2025-11-20T10:00:00")  # Recent upload
        False
    """
    age_hours = _get_file_age_hours(uploaded_at)
    if age_hours is None:
        return True  # Treat invalid timestamps as expired
    return age_hours >= _CACHE_EXPIRATION_HOURS


def _needs_validation(uploaded_at: str) -> bool:
    """Check if an uploaded file needs API validation.

    Files between 46-48 hours old are in the "validation window" where we
    should verify with the Gemini API that they're still active.

    Args:
        uploaded_at: ISO format timestamp string of when file was uploaded.

    Returns:
        True if file needs validation (46-48 hours old), False otherwise.

    Example:
        >>> _needs_validation("2025-11-18T11:00:00")  # 47 hours ago
        True
        >>> _needs_validation("2025-11-20T10:00:00")  # 1 hour ago
        False
    """
    age_hours = _get_file_age_hours(uploaded_at)
    if age_hours is None:
        return False  # Can't validate if timestamp is invalid
    return _CACHE_FRESH_THRESHOLD_HOURS <= age_hours < _CACHE_EXPIRATION_HOURS


class FileUploadCache:
    """Manages caching of uploaded files to Gemini API with time-aware validation.

    Implements intelligent caching that:
    - Uses SHA256 content hash as cache key (deduplicates identical files)
    - Skips API validation for fresh uploads (< 46 hours old)
    - Validates near-expiration uploads (46-48 hours old) with Gemini API
    - Auto-invalidates expired uploads (>= 48 hours old)

    Attributes:
        cache_file: Path to the JSON cache file where upload metadata is stored.

    Example:
        cache = FileUploadCache(Path(".upload_cache.json"))

        # Check for cached upload (may skip API call if file is fresh)
        cached_file = cache.get_cached_upload(client, Path("document.pdf"))

        # Clean up expired entries
        removed_count = cache.cleanup_expired()
    """

    def __init__(self, cache_file: Path) -> None:
        """Initialize FileUploadCache with a cache file path.

        Args:
            cache_file: Path to the JSON cache file. Parent directories will
                be created automatically when cache is saved.

        Example:
            >>> cache = FileUploadCache(Path(".cache/uploads.json"))
            >>> cache.cache_file.name
            'uploads.json'
        """
        self.cache_file: Path = cache_file

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        """Load the file upload cache from disk.

        Handles missing or corrupted cache files gracefully by returning
        an empty dict. Logs warning if cache is corrupted.

        Returns:
            Dict mapping SHA256 hash -> upload metadata. Empty dict if cache
            doesn't exist or is corrupted.

        Example cache structure:
            {
                "abc123...": {
                    "name": "files/xyz789",
                    "uri": "https://...",
                    "display_name": "document.pdf",
                    "size_bytes": 1024,
                    "uploaded_at": "2025-11-20T08:30:00",
                    "file_path": "/path/to/document.pdf"
                }
            }
        """
        if not self.cache_file.exists():
            return {}

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                # Validate it's a dict
                if not isinstance(cache_data, dict):
                    logger.warning(
                        f"Cache file {self.cache_file} has invalid format, "
                        "starting fresh"
                    )
                    return {}
                return cache_data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(
                f"Could not load cache from {self.cache_file}: {e}. "
                "Starting with empty cache."
            )
            return {}

    def _save_cache(self, cache: dict[str, dict[str, Any]]) -> None:
        """Save the file upload cache to disk.

        Creates parent directories if they don't exist. Logs warning but
        doesn't raise exception if save fails.

        Args:
            cache: Dict mapping SHA256 hash -> upload metadata.

        Side effects:
            - Creates parent directories if needed
            - Writes JSON file with 2-space indentation
            - Logs warning on failure
        """
        try:
            # Ensure parent directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            logger.warning(f"Could not save upload cache to {self.cache_file}: {e}")

    def get_cached_upload(
        self, client: genai.Client, file_path: Path
    ) -> Optional[Any]:
        """Check if we have a valid cached upload for this file.

        Implements time-aware caching to minimize API calls:
        - Fresh files (< 46 hours): Return immediately without API validation
        - Near-expiration (46-48 hours): Validate with Gemini API
        - Expired files (>= 48 hours): Return None without API call

        Args:
            client: Gemini client instance for API validation (only used for
                files approaching expiration).
            file_path: Path to the local file to check for cached upload.

        Returns:
            Gemini File object if valid cache entry found, None if:
            - File not found locally
            - No cache entry exists for this file
            - Cached upload has expired
            - API validation fails (for near-expiration files)

        Example:
            >>> cache = FileUploadCache(Path(".cache.json"))
            >>> file = cache.get_cached_upload(client, Path("doc.pdf"))
            >>> if file:
            ...     print(f"Using cached upload: {file.name}")
            ... else:
            ...     print("Need to upload file")
        """
        # Calculate file hash to use as cache key
        try:
            file_hash = get_file_hash(file_path)
        except (FileNotFoundError, IOError):
            return None

        cache = self._load_cache()

        # Check if we have a cache entry for this file
        if file_hash not in cache:
            return None

        cached_info = cache[file_hash]
        uploaded_at = cached_info.get("uploaded_at", "")
        file_name = cached_info.get("name")

        if not file_name or not uploaded_at:
            # Invalid cache entry - missing required fields
            logger.warning(
                f"Cache entry for {file_path.name} missing required fields, "
                "will re-upload"
            )
            return None

        # Time-aware cache validation logic
        if _is_file_expired(uploaded_at):
            # File is definitely expired (>= 48 hours), skip API call
            logger.debug(
                f"Cached upload for {file_path.name} has expired "
                f"(uploaded at {uploaded_at})"
            )
            return None

        if _is_file_fresh(uploaded_at):
            # File is fresh (< 46 hours), skip API validation
            logger.debug(
                f"Using fresh cached upload for {file_path.name} "
                f"without validation (uploaded at {uploaded_at})"
            )
            # Return a minimal file object with cached metadata
            # Note: We don't have the full File object, so we call API
            # but we know it should succeed
            try:
                file_info = client.files.get(name=file_name)
                if file_info.state == "ACTIVE":
                    return file_info
            except Exception as e:
                logger.warning(
                    f"Fresh cache hit but file retrieval failed for "
                    f"{file_path.name}: {e}"
                )
                return None

        # File is in validation window (46-48 hours), check with API
        if _needs_validation(uploaded_at):
            logger.debug(
                f"Validating near-expiration cached upload for {file_path.name} "
                f"(uploaded at {uploaded_at})"
            )
            try:
                file_info = client.files.get(name=file_name)
                if file_info.state == "ACTIVE":
                    return file_info
                else:
                    logger.debug(
                        f"Cached file {file_name} is not ACTIVE, will re-upload"
                    )
                    return None
            except Exception as e:
                logger.debug(
                    f"Cached file {file_name} no longer exists in Gemini: {e}"
                )
                return None

        # Shouldn't reach here, but be safe
        return None

    def cache_upload(
        self, file_path: Path, uploaded_file: Any, verbose: bool = False
    ) -> None:
        """Cache information about an uploaded file.

        Stores upload metadata including Gemini file ID, URI, and upload
        timestamp. Uses SHA256 hash of file content as cache key.

        Args:
            file_path: Path to the local file that was uploaded.
            uploaded_file: The File object returned from Gemini API after upload.
            verbose: If True, print confirmation message to stdout.

        Side effects:
            - Writes cache file to disk
            - Prints message if verbose=True

        Example:
            >>> cache.cache_upload(
            ...     Path("document.pdf"),
            ...     uploaded_file_object,
            ...     verbose=True
            ... )
              💾 Cached upload info
        """
        try:
            file_hash = get_file_hash(file_path)
        except (FileNotFoundError, IOError):
            logger.warning(f"Could not cache upload for {file_path}: file not found")
            return

        cache = self._load_cache()

        # Store upload metadata (using UTC timestamp)
        cache[file_hash] = {
            "name": uploaded_file.name,
            "uri": uploaded_file.uri,
            "display_name": uploaded_file.display_name,
            "size_bytes": uploaded_file.size_bytes,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "file_path": str(file_path),
        }

        self._save_cache(cache)
        if verbose:
            print("  💾 Cached upload info")

    def cleanup_expired(self) -> int:
        """Remove expired cache entries (>= 48 hours old).

        Removes cache entries for files that have expired in Gemini API,
        freeing up space and keeping the cache file clean.

        Returns:
            Number of cache entries removed.

        Example:
            >>> cache = FileUploadCache(Path(".cache.json"))
            >>> removed = cache.cleanup_expired()
            >>> print(f"Removed {removed} expired entries")
            Removed 3 expired entries
        """
        cache = self._load_cache()
        original_size = len(cache)

        # Filter out expired entries
        fresh_cache = {
            hash_key: metadata
            for hash_key, metadata in cache.items()
            if not _is_file_expired(metadata.get("uploaded_at", ""))
        }

        removed_count = original_size - len(fresh_cache)

        if removed_count > 0:
            self._save_cache(fresh_cache)
            logger.info(f"Cleaned up {removed_count} expired cache entries")

        return removed_count

    def clear(self) -> bool:
        """Delete the entire cache file.

        Removes all cache entries by deleting the cache file from disk.

        Returns:
            True if cache was successfully deleted or didn't exist,
            False if deletion failed.

        Example:
            >>> cache = FileUploadCache(Path(".cache.json"))
            >>> success = cache.clear()
            >>> if success:
            ...     print("Cache cleared")
        """
        if not self.cache_file.exists():
            return True

        try:
            self.cache_file.unlink()
            logger.info(f"Cleared cache file: {self.cache_file}")
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to clear cache file {self.cache_file}: {e}")
            return False


# Module-level convenience functions


def upload_file_with_cache(
    client: genai.Client,
    file_path: Path,
    cache_manager: Optional[FileUploadCache] = None,
    mime_type: str = "text/markdown",
    verbose: bool = False,
) -> Optional[Any]:
    """Upload a file to Gemini API with intelligent caching support.

    Checks cache first to avoid redundant uploads. If file is fresh in cache
    (< 46 hours), returns cached upload without API validation. Only uploads
    if cache miss or file has expired.

    Args:
        client: Gemini client instance for uploading and cache validation.
        file_path: Path to the local file to upload.
        cache_manager: Optional FileUploadCache for caching. If None, uploads
            without caching.
        mime_type: MIME type of the file (e.g., "application/pdf",
            "text/markdown"). Defaults to "text/markdown".
        verbose: If True, print progress messages to stdout.

    Returns:
        Gemini File object on success, None on failure. The File object
        includes attributes: name, uri, display_name, size_bytes, state.

    Raises:
        FileNotFoundError: If file_path doesn't exist.

    Example:
        >>> cache = FileUploadCache(Path(".cache.json"))
        >>> uploaded = upload_file_with_cache(
        ...     client=genai_client,
        ...     file_path=Path("document.pdf"),
        ...     cache_manager=cache,
        ...     mime_type="application/pdf",
        ...     verbose=True
        ... )
        ✓ Using cached upload: files/abc123
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check cache if available
    if cache_manager:
        cached_file = cache_manager.get_cached_upload(client, file_path)
        if cached_file:
            if verbose:
                print(f"✓ Using cached upload: {cached_file.name}")
            return cached_file

    # Cache miss - upload file
    try:
        if verbose:
            print(f"📤 Uploading file to Gemini API...")

        with open(file_path, "rb") as f:
            uploaded_file = client.files.upload(
                file=f,
                config={
                    "display_name": file_path.name,
                    "mime_type": mime_type,
                },
            )

        if verbose:
            print(f"✓ File uploaded: {uploaded_file.name}")
            print(f"  URI: {uploaded_file.uri}")

        # Cache the upload if cache manager provided
        if cache_manager:
            cache_manager.cache_upload(file_path, uploaded_file, verbose=verbose)

        return uploaded_file

    except Exception as e:
        logger.error(f"File upload failed for {file_path}: {e}")
        if verbose:
            print(f"⚠️  File upload failed: {e}")
        return None


def get_cached_upload(
    client: genai.Client, file_path: Path, cache_file: Path
) -> Optional[Any]:
    """Convenience function to check for cached upload.

    Creates a FileUploadCache instance and checks for a cached upload.
    Useful for one-off cache lookups without managing a cache instance.

    Args:
        client: Gemini client instance for API validation if needed.
        file_path: Path to the local file to check for cached upload.
        cache_file: Path to the JSON cache file.

    Returns:
        Gemini File object if valid cache found, None otherwise.

    Example:
        >>> file = get_cached_upload(
        ...     client=genai_client,
        ...     file_path=Path("document.pdf"),
        ...     cache_file=Path(".cache.json")
        ... )
    """
    cache_manager = FileUploadCache(Path(cache_file))
    return cache_manager.get_cached_upload(client, file_path)


def clear_upload_cache(cache_file: Path) -> bool:
    """Convenience function to clear entire upload cache.

    Deletes the cache file from disk, removing all cached upload metadata.
    Useful for one-off cache clearing without managing a cache instance.

    Args:
        cache_file: Path to the JSON cache file to delete.

    Returns:
        True if cache was cleared successfully or didn't exist,
        False if deletion failed.

    Example:
        >>> success = clear_upload_cache(Path(".cache.json"))
        >>> if success:
        ...     print("Cache cleared successfully")
    """
    cache_manager = FileUploadCache(cache_file)
    return cache_manager.clear()
