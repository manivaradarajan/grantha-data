"""Analysis result caching with file hash validation.

Provides caching for expensive analysis operations with automatic invalidation
when source files change.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class AnalysisCache:
    """Manages caching of analysis results with file hash validation.

    Caches analysis results to disk with SHA256 hash validation to ensure
    cache is invalidated when source files change.

    Attributes:
        input_file: Path to the file being analyzed.
        cache_path: Path to the cache file.
    """

    def __init__(self, input_file: str, cache_dir: Optional[Path] = None):
        """Initialize AnalysisCache for a given input file.

        Args:
            input_file: Path to the file being analyzed.
            cache_dir: Optional directory to store the cache file.
        """
        self.input_file = Path(input_file)
        self.cache_dir = cache_dir
        self.cache_path = self._get_cache_path()

    def _get_cache_path(self) -> Path:
        """Get the cache file path for the input file.

        Returns:
            Path to the cache file.
        """
        # Create a short, stable hash of the absolute file path to ensure uniqueness
        path_hash = hashlib.sha256(str(self.input_file.resolve()).encode()).hexdigest()[:8]
        cache_filename = f"{self.input_file.stem}-{path_hash}.json"
        
        if self.cache_dir:
            print(f"  - Using specified cache directory: {self.cache_dir}")
            return self.cache_dir / cache_filename
        
        print(f"  - Using default cache location (next to input file).")
        # Fallback to the input file's directory if no cache_dir is provided
        return self.input_file.parent / f".cache_analysis_{cache_filename}"

    def _get_file_hash(self) -> str:
        """Calculate SHA256 hash of the input file.

        Returns:
            SHA256 hex digest of the file contents.

        Raises:
            FileNotFoundError: If the input file doesn't exist.
        """
        sha256_hash = hashlib.sha256()
        with open(self.input_file, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def load(self, verbose: bool = False) -> Optional[Dict[str, Any]]:
        """Load cached analysis if available and valid.

        Args:
            verbose: Print detailed messages.

        Returns:
            Cached analysis dict if valid, None if cache miss or invalid.
        """
        if not self.cache_path.exists():
            if verbose:
                print("📦 Cache miss: No cache file found")
            return None

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)

            # Validate cache structure
            if "file_hash" not in cached_data or "analysis" not in cached_data:
                if verbose:
                    print("⚠️  Cache invalid: Missing required fields")
                return None

            # Validate file hasn't changed
            current_hash = self._get_file_hash()
            cached_hash = cached_data["file_hash"]

            if current_hash != cached_hash:
                if verbose:
                    print("⚠️  Cache invalid: File has been modified")
                    print(f"     Cached hash: {cached_hash[:16]}...")
                    print(f"     Current hash: {current_hash[:16]}...")
                return None

            # Cache is valid
            cached_timestamp = cached_data.get("timestamp", "unknown")
            if verbose:
                print(f"✓ Cache hit: Using cached analysis from {cached_timestamp}")

            return cached_data["analysis"]

        except json.JSONDecodeError as e:
            if verbose:
                print(f"⚠️  Cache invalid: Could not parse cache file: {e}")
            return None
        except Exception as e:
            if verbose:
                print(f"⚠️  Cache error: {e}")
            return None

    def save(self, analysis: Dict[str, Any], verbose: bool = False) -> bool:
        """Save analysis to cache file.

        Args:
            analysis: The analysis result to cache.
            verbose: Print detailed messages.

        Returns:
            True if cache saved successfully, False otherwise.
        """
        try:
            # Ensure the cache directory exists before writing
            if self.cache_dir:
                self.cache_dir.mkdir(parents=True, exist_ok=True)

            file_hash = self._get_file_hash()
            timestamp = datetime.now().isoformat()

            cache_data = {
                "file_hash": file_hash,
                "timestamp": timestamp,
                "analysis": analysis,
                "version": "1.0",  # For future compatibility
            }

            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            if verbose:
                print(f"💾 Analysis cached to: {self.cache_path.name}")
            return True

        except Exception as e:
            if verbose:
                print(f"⚠️  Failed to save cache: {e}")
            return False

    def clear(self, verbose: bool = False) -> bool:
        """Delete the cache file.

        Args:
            verbose: Print detailed messages.

        Returns:
            True if cache was deleted or didn't exist, False on error.
        """
        if not self.cache_path.exists():
            if verbose:
                print("📦 No cache to clear")
            return True

        try:
            self.cache_path.unlink()
            if verbose:
                print(f"🗑️  Cleared cache: {self.cache_path.name}")
            return True
        except Exception as e:
            if verbose:
                print(f"⚠️  Failed to clear cache: {e}")
            return False
