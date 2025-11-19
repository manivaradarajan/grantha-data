"""File upload and caching utilities for Gemini API.

Provides file upload functionality with intelligent caching to avoid
redundant uploads of the same files.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from google import genai


def get_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file.

    Args:
        file_path: Path to the file.

    Returns:
        SHA256 hex digest of the file contents.
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


class FileUploadCache:
    """Manages caching of uploaded files to Gemini API.

    Caches upload information to avoid redundant uploads of the same files.
    Uses file path and SHA256 hash as cache key.

    Attributes:
        cache_file: Path to the cache file.
    """

    def __init__(self, cache_file: Path):
        """Initialize FileUploadCache with a cache file path.

        Args:
            cache_file: Path to the JSON cache file.
        """
        self.cache_file = cache_file

    def _load_cache(self) -> dict:
        """Load the file upload cache from disk.

        Returns:
            Dict mapping cache_key -> upload info.
        """
        if not self.cache_file.exists():
            return {}

        try:
            with open(self.cache_file, "r") as f:
                return json.load(f)
        except Exception:
            # If cache is corrupted, start fresh
            return {}

    def _save_cache(self, cache: dict) -> None:
        """Save the file upload cache to disk.

        Args:
            cache: Dict mapping cache_key -> upload info.
        """
        try:
            # Ensure parent directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            print(f"⚠️  Warning: Could not save upload cache: {e}")

    def get_cached_upload(self, client: genai.Client, file_path: Path) -> Optional[Any]:
        """Check if we have a valid cached upload for this file.

        Args:
            client: Gemini client to verify file still exists.
            file_path: Path to the file.

        Returns:
            Gemini File object if valid cache found, None otherwise.
        """
        try:
            file_hash = get_file_hash(file_path)
        except FileNotFoundError:
            return None

        cache = self._load_cache()
        cache_key = f"{file_path}:{file_hash}"

        if cache_key not in cache:
            return None

        cached_info = cache[cache_key]
        file_name = cached_info.get("name")

        # Verify the file still exists in Gemini and is active
        try:
            file_info = client.files.get(name=file_name)
            if file_info.state == "ACTIVE":
                return file_info  # Return the actual File object
            else:
                # File exists but not active, will re-upload
                return None
        except Exception:
            # File no longer exists in Gemini, will re-upload
            return None

    def cache_upload(
        self, file_path: Path, uploaded_file: Any, verbose: bool = False
    ) -> None:
        """Cache information about an uploaded file.

        Args:
            file_path: Path to the file.
            uploaded_file: The uploaded file object from Gemini.
            verbose: Print detailed messages.
        """
        try:
            file_hash = get_file_hash(file_path)
        except FileNotFoundError:
            return

        cache = self._load_cache()
        cache_key = f"{file_path}:{file_hash}"

        cache[cache_key] = {
            "name": uploaded_file.name,
            "uri": uploaded_file.uri,
            "display_name": uploaded_file.display_name,
            "size_bytes": uploaded_file.size_bytes,
            "uploaded_at": datetime.now().isoformat(),
            "file_path": str(file_path),
            "file_hash": file_hash,
        }

        self._save_cache(cache)
        if verbose:
            print("  💾 Cached upload info")

    def clear(self) -> bool:
        """Delete the cache file.

        Returns:
            True if cache was deleted or didn't exist, False on error.
        """
        if not self.cache_file.exists():
            return True

        try:
            self.cache_file.unlink()
            return True
        except Exception:
            return False


# Module-level convenience functions


def upload_file_with_cache(
    client: genai.Client,
    file_path: Path,
    cache_manager: Optional[FileUploadCache] = None,
    mime_type: str = "text/markdown",
    verbose: bool = False,
) -> Optional[Any]:
    """Upload a file to Gemini API with caching support.

    Args:
        client: Gemini client instance.
        file_path: Path to the file to upload.
        cache_manager: Optional FileUploadCache instance for caching.
        mime_type: MIME type of the file.
        verbose: Print detailed messages.

    Returns:
        Uploaded file object from Gemini API, or None on failure.

    Raises:
        FileNotFoundError: If file_path doesn't exist.
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

    # Upload file
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
        if verbose:
            print(f"⚠️  File upload failed: {e}")
        return None


def get_cached_upload(
    client: genai.Client, file_path: Path, cache_file: Path
) -> Optional[Any]:
    """Convenience function to check for cached upload.

    Args:
        client: Gemini client instance.
        file_path: Path to the file.
        cache_file: Path to the cache file.

    Returns:
        Gemini File object if valid cache found, None otherwise.
    """
    cache_manager = FileUploadCache(Path(cache_file))
    return cache_manager.get_cached_upload(client, file_path)


def clear_upload_cache(cache_file: Path) -> bool:
    """Convenience function to clear upload cache.

    Args:
        cache_file: Path to the cache file.

    Returns:
        True if cache was cleared successfully.
    """
    cache_manager = FileUploadCache(cache_file)
    return cache_manager.clear()
