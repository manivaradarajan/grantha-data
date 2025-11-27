# Standard library imports
import re
from pathlib import Path
from fnmatch import fnmatch

def extract_part_number_from_filename(filename: str) -> int:
    """Extract part number from filename."""
    # Sanskrit number words to digits
    sanskrit_numbers = {
        "prathama": 1,
        "pratham": 1,
        "dvitiya": 2,
        "dvitiya": 2,
        "dviti": 2,
        "tritiya": 3,
        "trtiya": 3,
        "trtiya": 3,
        "caturtha": 4,
        "catur": 4,
        "pancama": 5,
        "panchama": 5,
        "pajcama": 5,
        "shashtha": 6,
        "sastho": 6,
        "sastha": 6,
        "saptama": 7,
        "astama": 8,
        "ashtama": 8,
        "astama": 8,
        "navama": 9,
        "dasama": 10,
    }

    # Remove .md extension
    name = filename.replace(".md", "").lower()

    # Pattern 1: XX-YY.md (e.g., 03-01.md) - use YY as part number
    match = re.search(r"(\d{2})-(\d{2})$", name)
    if match:
        return int(match.group(2))

    # Pattern 2: part-N or partN
    match = re.search(r"part[-_]?(\d+)$", name, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Pattern 3: Sanskrit number words
    sorted_sanskrit = sorted(sanskrit_numbers.items(), key=lambda x: -len(x[0]))
    for sanskrit, number in sorted_sanskrit:
        if sanskrit.lower() in name:
            return number

    # Pattern 4: name-NN (e.g., brihadaranyaka-03)
    match = re.search(r"-(\d{2})$", name)
    if match:
        return int(match.group(1))

    # Pattern 5: just digits (e.g., 01.md)
    match = re.search(r"^(\d{2})$", name)
    if match:
        return int(match.group(1))

    # Default to part 1
    return 1


def get_directory_parts(directory: "Path", exclude_pattern: str = None) -> list:
    """Get all markdown files in directory sorted by part number.

    Args:
        directory: Directory containing markdown files
        exclude_pattern: Optional glob pattern to exclude files (e.g., "*-index.md")
                        Pattern is matched against filename relative to directory

    Returns:
        List of (file_path, part_number) tuples sorted by part number
    """
    md_files = []
    for file in directory.glob("*.md"):
        if file.name.upper() == "PROVENANCE.yaml":
            continue

        # Check if file matches exclude pattern
        if exclude_pattern:
            relative_path = file.relative_to(directory)
            if fnmatch(str(relative_path), exclude_pattern):
                continue

        part_num = extract_part_number_from_filename(file.name)
        md_files.append((file, part_num))

    # Sort by part number
    md_files.sort(key=lambda x: x[1])
    return md_files
