"""
Markdown to JSON converter for grantha data.

This module converts a structured Grantha Markdown file back into the canonical
JSON format. It parses the YAML frontmatter, reconstructs passages and commentaries
from the Markdown headings and content blocks, and verifies content integrity
using the `validation_hash` from the frontmatter.
"""

import re
from typing import Any, Dict, List, Tuple

import yaml

from .devanagari_extractor import HASH_VERSION, extract_devanagari
from .hasher import hash_text


def _validate_markdown_file(markdown_text: str):
    """
    Validates the markdown file's frontmatter and content hash.

    This function performs two critical validations:
    1.  Frontmatter Validation: Checks for required fields, correct formats,
        and consistency in the YAML frontmatter.
    2.  Hash Verification: Verifies the integrity of the Devanagari content
        by comparing the computed hash against the `validation_hash` in the
        frontmatter.

    Raises:
        ValueError: If any validation check fails.
    """
    frontmatter, body = parse_frontmatter(markdown_text)
    errors = []

    # 1. Frontmatter Validation (adapted from cli.py's cmd_validate_header)
    required_fields = [
        "grantha_id",
        "canonical_title",
        "text_type",
        "language",
        "structure_levels",
    ]
    for field in required_fields:
        if field not in frontmatter:
            errors.append(f"Missing required field in frontmatter: {field}")

    if "grantha_id" in frontmatter and not re.match(
        r"^[a-z0-9-]+$", frontmatter["grantha_id"]
    ):
        errors.append(
            f"Invalid grantha_id format: '{frontmatter['grantha_id']}' (must be lowercase alphanumeric with hyphens)"
        )

    if "text_type" in frontmatter and frontmatter["text_type"] not in [
        "upanishad",
        "commentary",
    ]:
        errors.append(
            f"Invalid text_type: '{frontmatter['text_type']}' (must be 'upanishad' or 'commentary')"
        )

    if "language" in frontmatter and frontmatter["language"] not in [
        "sanskrit",
        "english",
    ]:
        errors.append(
            f"Invalid language: '{frontmatter['language']}' (must be 'sanskrit' or 'english')"
        )

    if "structure_levels" in frontmatter and not isinstance(
        frontmatter["structure_levels"], list
    ):
        errors.append("structure_levels must be an array/list")

    if errors:
        raise ValueError(
            "Frontmatter validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    print("✓ Frontmatter validation passed.")

    # 2. Hash Verification
    file_version = frontmatter.get("hash_version")
    if file_version is None:
        raise ValueError(
            "Hash version MISSING. File is unversioned. "
            "Please run `grantha-converter update-hash`."
        )
    if file_version != HASH_VERSION:
        raise ValueError(
            f"Hash version MISMATCH. File version: {file_version}, "
            f"Current version: {HASH_VERSION}. "
            "Please run `grantha-converter update-hash`."
        )

    expected_hash = frontmatter.get("validation_hash")
    if not expected_hash:
        raise ValueError("validation_hash field is missing from the frontmatter.")

    devanagari_text = extract_devanagari(body)
    actual_hash = hash_text(devanagari_text)

    if actual_hash != expected_hash:
        raise ValueError(
            "Validation hash mismatch. Content may have been altered.\n"
            f"  Expected: {expected_hash}\n"
            f"  Actual:   {actual_hash}"
        )

    print("✓ Markdown hash verification passed.")


# Regex patterns from the specification
HEADING_MANTRA = re.compile(r"^#\s+(?:Mantra|Valli|Khanda|Anuvaka)\s+([\d\.]+)$")
HEADING_PREFATORY = re.compile(
    r'^#\s+Prefatory:\s+([\d\.]+)\s+\((\w+):\s*"(.*?)"\)$', re.IGNORECASE | re.MULTILINE
)
HEADING_CONCLUDING = re.compile(
    r'^#\s+Concluding:\s+([\d\.]+)\s+\((\w+):\s*"(.*?)"\)$',
    re.IGNORECASE | re.MULTILINE,
)
HEADING_COMMENTARY = re.compile(
    r"^#+\s+Commentary:\s+([\d\.]+)$", re.IGNORECASE | re.MULTILINE
)
COMMENTARY_METADATA = re.compile(r"<!--\s*commentary:\s*({.*?})\s*-->")
HEADING_ANY = re.compile(r"^#\s+.*$", re.MULTILINE)


def parse_frontmatter(markdown: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", markdown, re.DOTALL)
    if not match:
        raise ValueError("No YAML frontmatter found in markdown")
    frontmatter = yaml.safe_load(match.group(1))
    content = match.group(2).strip()
    return frontmatter, content


def parse_sanskrit_content(content: str) -> Dict[str, Any]:
    """Parse a content block into a dictionary."""
    data = {}
    sanskrit_data = {}

    # Find all metadata comments and their positions
    matches = list(re.finditer(r"<!--\s*(.+?)\s*-->", content))

    # Process content within sanskrit: tags
    for i, match in enumerate(matches):
        label = match.group(1).strip()
        if label.startswith("sanskrit:"):
            script = label.split(":")[1]
            # Find the corresponding closing tag
            closing_tag = f"<!-- /{label} -->"
            for j in range(i + 1, len(matches)):
                if matches[j].group(0).strip() == closing_tag:
                    start_pos = match.end()
                    end_pos = matches[j].start()
                    text = content[start_pos:end_pos].strip()
                    if text:
                        sanskrit_data[script] = text
                    break

    # If no sanskrit data was found, and there are no explicit tags,
    # assume the entire block is Devanagari (after cleaning other comments)
    if not sanskrit_data:
        cleaned_content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()
        if cleaned_content:
            sanskrit_data["devanagari"] = cleaned_content

    if sanskrit_data:
        data["sanskrit"] = sanskrit_data

    return data


def get_lowest_level_key(structure_levels: List[Dict[str, Any]]) -> str:
    """Recursively get the lowest 'key' value from structure_levels.

    Handles both list and dict formats:
    - List: [{key: "Adhyaya", children: [{key: "Mantra"}]}]
    - Dict: {key: "Adhyaya", children: {key: "Mantra"}}
    """
    if not structure_levels:
        return "Mantra"  # Default if none

    # Handle dict format - convert to list
    if isinstance(structure_levels, dict):
        structure_levels = [structure_levels]

    last_level = structure_levels[-1]
    if "children" in last_level and last_level["children"]:
        children = last_level["children"]
        # Handle dict format for children
        if isinstance(children, dict):
            children = [children]
        return get_lowest_level_key(children)
    else:
        return last_level["key"]


def get_all_structure_keys(structure_levels: List[Dict[str, Any]]) -> List[str]:
    """Recursively get all 'key' values from structure_levels.

    Handles both list and dict formats:
    - List: [{key: "Adhyaya", children: [{key: "Mantra"}]}]
    - Dict: {key: "Adhyaya", children: {key: "Mantra"}}
    """
    keys = []

    # Handle dict format - convert to list
    if isinstance(structure_levels, dict):
        structure_levels = [structure_levels]

    for level in structure_levels:
        keys.append(level["key"])
        if "children" in level and level["children"]:
            children = level["children"]
            # Handle dict format for children
            if isinstance(children, dict):
                children = [children]
            keys.extend(get_all_structure_keys(children))
    return keys


def convert_to_json(markdown: str, schema_version: str = None) -> Dict[str, Any]:
    """Convert Markdown to grantha JSON format using a single-pass strategy.

    Args:
        markdown: The markdown text to convert
        schema_version: The schema version to inject into JSON (optional)
    """
    frontmatter, content = parse_frontmatter(markdown)
    commentaries_metadata = frontmatter.get("commentaries_metadata", {})

    # Dynamically build the regex for main content headings
    structure_levels = frontmatter.get("structure_levels", [])
    structure_keys = get_all_structure_keys(structure_levels)
    lowest_level_key = get_lowest_level_key(structure_levels)

    heading_structure_pattern = (
        r"^#+\s+("
        + "|".join(re.escape(key) for key in structure_keys)
        + r")\s+([\d\.]+)$"
    )
    HEADING_STRUCTURE = re.compile(
        heading_structure_pattern, re.MULTILINE | re.IGNORECASE
    )

    # Handle both dict and list formats for commentaries_metadata
    commentaries_dict = {}
    if isinstance(commentaries_metadata, dict):
        commentaries_dict = {
            cid: {"commentary_id": cid, **meta, "passages": []}
            for cid, meta in commentaries_metadata.items()
        }
    elif isinstance(commentaries_metadata, list):
        for item in commentaries_metadata:
            if isinstance(item, dict) and "commentary_id" in item:
                cid = item["commentary_id"]
                meta = {k: v for k, v in item.items() if k != "commentary_id"}
                commentaries_dict[cid] = {"commentary_id": cid, **meta, "passages": []}

    data = {
        "grantha_id": frontmatter.get("grantha_id"),
        "part_num": frontmatter.get("part_num"),
        "canonical_title": frontmatter.get("canonical_title"),
        "text_type": frontmatter.get("text_type"),
        "language": frontmatter.get("language"),
        "structure_levels": structure_levels,
        "passages": [],
        "prefatory_material": [],
        "concluding_material": [],
        "commentaries": commentaries_dict,
    }

    # Inject schema_version if provided
    if schema_version:
        data["schema_version"] = schema_version

    # Only include metadata if present in frontmatter
    if "metadata" in frontmatter:
        data["metadata"] = frontmatter["metadata"]

    data["commentaries"] = commentaries_dict

    # Collect all headings and commentary metadata tags with their start and end positions
    all_matches = []
    for pattern in [
        HEADING_STRUCTURE,
        HEADING_PREFATORY,
        HEADING_CONCLUDING,
        HEADING_COMMENTARY,
        COMMENTARY_METADATA,
    ]:
        for match in pattern.finditer(content):
            all_matches.append(match)

    # Sort matches by their start position
    all_matches.sort(key=lambda m: m.start())

    pending_commentary_meta = None

    for i, match in enumerate(all_matches):
        match_text = match.group(0).strip()

        # Determine the end of the current content block
        content_start = match.end()
        content_end = (
            all_matches[i + 1].start() if i + 1 < len(all_matches) else len(content)
        )
        body_content = content[content_start:content_end].strip()

        # Check if it's a commentary metadata tag
        meta_match = COMMENTARY_METADATA.search(match_text)
        if meta_match:
            try:
                import json

                pending_commentary_meta = json.loads(meta_match.group(1))
            except (json.JSONDecodeError, yaml.YAMLError):
                pending_commentary_meta = None
            continue  # This tag itself doesn't have content to process as a passage

        # Re-match to identify heading type
        match_prefatory = HEADING_PREFATORY.match(match_text)
        match_concluding = HEADING_CONCLUDING.match(match_text)
        match_commentary = HEADING_COMMENTARY.match(match_text)
        match_structure = HEADING_STRUCTURE.match(match_text)

        if match_commentary:
            if pending_commentary_meta:
                ref = match_commentary.group(1)
                commentary_id = pending_commentary_meta.get("commentary_id")

                if commentary_id and commentary_id in data["commentaries"]:
                    commentary_passage = {
                        "ref": ref,
                        "content": parse_sanskrit_content(body_content),
                    }
                    data["commentaries"][commentary_id]["passages"].append(
                        commentary_passage
                    )

                # Consume it only after processing the commentary
                pending_commentary_meta = None
            continue

        # Now process the passage with the cleaned body content
        if match_prefatory:
            ref = match_prefatory.group(1)
            script = match_prefatory.group(2)
            label = match_prefatory.group(3)
            passage = {
                "ref": ref,
                "passage_type": "prefatory",
                "label": {script: label},
                "content": parse_sanskrit_content(body_content),
            }
            if passage["content"]:
                data["prefatory_material"].append(passage)

        elif match_concluding:
            ref = match_concluding.group(1)
            script = match_concluding.group(2)
            label = match_concluding.group(3)
            passage = {
                "ref": ref,
                "passage_type": "concluding",
                "label": {script: label},
                "content": parse_sanskrit_content(body_content),
            }
            if passage["content"]:
                data["concluding_material"].append(passage)

        elif match_structure:
            key = match_structure.group(1)
            ref = match_structure.group(2)
            if key.lower() == lowest_level_key.lower():
                passage = {
                    "ref": ref,
                    "passage_type": "main",
                    "content": parse_sanskrit_content(body_content),
                }
                if passage["content"]:
                    data["passages"].append(passage)

    # Filter out commentaries that have no passages
    commentaries_with_passages = {}
    for cid, comm_data in data["commentaries"].items():
        if comm_data["passages"]:
            commentaries_with_passages[cid] = comm_data
    data["commentaries"] = commentaries_with_passages
    return data


def markdown_file_to_json_file(
    markdown_file: str,
    json_file: str,
    format: str = "single",
    validate_schema: bool = True,
    schema_version: str = None,
) -> None:
    """Convert a Grantha Markdown file to JSON format.

    Args:
        markdown_file: Path to the input Markdown file
        json_file: Path to the output JSON file
        format: Output format - 'single' for complete grantha, 'multipart' for grantha parts
        validate_schema: Whether to validate against JSON schema (default: True)
        schema_version: Schema version to inject (default: read from VERSION file)

    Raises:
        ValueError: If validation fails or file operations fail
        FileNotFoundError: If input file doesn't exist
    """
    import json
    from pathlib import Path

    # Read the markdown file
    markdown_path = Path(markdown_file)
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_file}")

    markdown_text = markdown_path.read_text(encoding="utf-8")

    # Validate the file before processing
    _validate_markdown_file(markdown_text)

    # Read schema version from VERSION file if not provided
    if schema_version is None:
        # Try to find VERSION file in repository root
        version_file = Path(__file__).parent.parent.parent.parent / "VERSION"
        if version_file.exists():
            schema_version = version_file.read_text(encoding="utf-8").strip()
        else:
            # Fallback to default version if VERSION file not found
            schema_version = "0.1.0"

    # Convert to JSON
    json_data = convert_to_json(markdown_text, schema_version=schema_version)

    # Validate schema if requested
    if validate_schema:
        from .schema_validator import validate_grantha_part, validate_grantha_single

        if format == "multipart":
            is_valid, errors = validate_grantha_part(json_data)
        else:
            is_valid, errors = validate_grantha_single(json_data)

        if not is_valid:
            error_msg = "\n".join(errors)
            raise ValueError(f"Schema validation failed:\n{error_msg}")

    # Write the JSON file
    json_path = Path(json_file)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
        f.write("\n")  # Add trailing newline
