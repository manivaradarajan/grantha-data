"""Generate release manifest for grantha-data releases."""

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def calculate_directory_hash(directory: Path, pattern: str = "**/*.json") -> str:
    """Calculate combined SHA256 hash of all files in a directory matching pattern."""
    sha256_hash = hashlib.sha256()
    files = sorted(directory.glob(pattern))

    for file_path in files:
        if file_path.is_file():
            # Include filename in hash for ordering
            sha256_hash.update(str(file_path.relative_to(directory)).encode())
            # Include file content
            with open(file_path, "rb") as f:
                sha256_hash.update(f.read())

    return sha256_hash.hexdigest()


def extract_grantha_metadata(json_path: Path) -> dict[str, Any]:
    """Extract metadata from a grantha JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both envelope and regular files
    is_envelope = "parts" in data
    grantha_id = data.get("grantha_id", "unknown")
    canonical_title = data.get("canonical_title", "")

    # Extract commentaries
    commentaries = []
    if "commentaries" in data:
        if isinstance(data["commentaries"], dict):
            commentaries = list(data["commentaries"].keys())
        elif isinstance(data["commentaries"], list):
            commentaries = [c.get("commentary_id", "") for c in data["commentaries"]]

    metadata = {
        "grantha_id": grantha_id,
        "canonical_title": canonical_title,
        "multipart": is_envelope,
    }

    if is_envelope:
        metadata["parts"] = len(data.get("parts", []))

    if commentaries:
        metadata["commentaries"] = commentaries

    return metadata


def generate_manifest(
    data_dir: Path,
    schemas_dir: Path,
    version_file: Path,
    output_file: Path,
) -> None:
    """Generate release manifest.json.

    Args:
        data_dir: Directory containing JSON data files
        schemas_dir: Directory containing JSON schema files
        version_file: Path to VERSION file
        output_file: Path to write manifest.json
    """
    # Read version
    with open(version_file, "r") as f:
        version = f.read().strip()

    # Get current timestamp
    release_date = datetime.now(timezone.utc).isoformat()

    # Scan all JSON files in data directory
    json_files = sorted(data_dir.glob("**/*.json"))
    files_list = []
    upanishads_map = {}

    for json_file in json_files:
        if json_file.is_file():
            rel_path = json_file.relative_to(data_dir.parent)
            file_info = {
                "path": str(rel_path),
                "sha256": calculate_sha256(json_file),
                "size_bytes": json_file.stat().st_size,
            }
            files_list.append(file_info)

            # Extract upanishad metadata from envelope files
            if json_file.name == "envelope.json":
                metadata = extract_grantha_metadata(json_file)
                grantha_id = metadata["grantha_id"]
                if grantha_id not in upanishads_map:
                    upanishads_map[grantha_id] = metadata

    # Also check for single-file granthas
    for json_file in json_files:
        if json_file.name != "envelope.json" and not json_file.name.startswith("part"):
            try:
                metadata = extract_grantha_metadata(json_file)
                grantha_id = metadata["grantha_id"]
                if grantha_id not in upanishads_map:
                    upanishads_map[grantha_id] = metadata
            except (json.JSONDecodeError, KeyError):
                # Skip files that don't have expected structure
                pass

    # Calculate directory hashes
    data_sha256 = calculate_directory_hash(data_dir)
    schemas_sha256 = calculate_directory_hash(schemas_dir, "*.schema.json")

    # Count commentaries
    total_commentaries = sum(
        len(u.get("commentaries", []))
        for u in upanishads_map.values()
    )

    # Build manifest
    manifest = {
        "version": version,
        "schema_version": version,
        "release_date": release_date,
        "checksums": {
            "manifest_sha256": "",  # Will be calculated after removing this field
            "data_sha256": data_sha256,
            "schemas_sha256": schemas_sha256,
        },
        "files": files_list,
        "upanishads": list(upanishads_map.values()),
        "statistics": {
            "total_upanishads": len(upanishads_map),
            "total_commentaries": total_commentaries,
            "total_files": len(files_list),
        },
    }

    # Write manifest
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Add trailing newline

    # Calculate manifest checksum (excluding the manifest_sha256 field itself)
    manifest_copy = manifest.copy()
    manifest_copy["checksums"] = manifest_copy["checksums"].copy()
    manifest_copy["checksums"]["manifest_sha256"] = ""
    manifest_content = json.dumps(manifest_copy, indent=2, ensure_ascii=False)
    manifest_sha256 = hashlib.sha256(manifest_content.encode()).hexdigest()

    # Update manifest with its own checksum
    manifest["checksums"]["manifest_sha256"] = manifest_sha256

    # Write final manifest
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Generated manifest: {output_file}")
    print(f"Version: {version}")
    print(f"Total files: {len(files_list)}")
    print(f"Total upanishads: {len(upanishads_map)}")
    print(f"Total commentaries: {total_commentaries}")


def main():
    """CLI entry point for manifest generator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate release manifest for grantha-data"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Directory containing JSON data files",
    )
    parser.add_argument(
        "--schemas-dir",
        type=Path,
        required=True,
        help="Directory containing JSON schema files",
    )
    parser.add_argument(
        "--version-file",
        type=Path,
        required=True,
        help="Path to VERSION file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for manifest.json",
    )

    args = parser.parse_args()

    generate_manifest(
        data_dir=args.data_dir,
        schemas_dir=args.schemas_dir,
        version_file=args.version_file,
        output_file=args.output,
    )


if __name__ == "__main__":
    main()
