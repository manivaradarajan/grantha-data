#!/usr/bin/env python3
"""Validates Grantha Markdown files against the formal specification.

This script checks for structural integrity, correct frontmatter, valid heading
formats, and proper commentary linking. It can be run as a standalone tool
from the command line.
"""
import argparse
import re
import sys
from typing import Dict, List

import yaml

# Regex patterns for different heading types
HEADING_MANTRA = re.compile(r'^#\s+Mantra\s+([\d\.-]+)$')
HEADING_PREFATORY = re.compile(r'^#\s+Prefatory:\s+([\d\.]+)\s+\((\w+):\s*"(.*?)"\)$')
HEADING_CONCLUDING = re.compile(r'^#\s+Concluding:\s+([\d\.]+)\s+\((\w+):\s*"(.*?)"\)$')
HEADING_COMMENTARY = re.compile(r'^#\s+Commentary:\s+([\d\.-]+)$')

# Regex for content blocks
CONTENT_BLOCK_START = re.compile(r'^<!--\s*sanskrit:(\w+)\s*-->$')
CONTENT_BLOCK_END = re.compile(r'^<!--\s*/sanskrit:(\w+)\s*-->$')
COMMENTARY_METADATA = re.compile(r'^<!--\s*commentary:\s*(.*?)\s*-->$')


class ValidationError(Exception):
    """Custom exception for validation errors.

    Attributes:
        message: The error message.
        line_num: The line number where the error occurred, if applicable.
    """
    def __init__(self, message, line_num=None):
        self.line_num = line_num
        if line_num:
            super().__init__(f"Line {line_num}: {message}")
        else:
            super().__init__(message)


def validate_frontmatter(frontmatter: Dict) -> List[str]:
    """Validates the structure and types of the YAML frontmatter.

    Args:
        frontmatter: The parsed YAML frontmatter as a dictionary.

    Returns:
        A list of string error messages, or an empty list if validation passes.
    """
    errors = []
    required_fields = [
        "grantha_id", "part_num", "canonical_title", "text_type",
        "language", "structure_levels", "commentaries_metadata"
    ]
    for field in required_fields:
        if field not in frontmatter:
            errors.append(f"Missing required frontmatter field: '{field}'")

    if "part_num" in frontmatter and not isinstance(frontmatter["part_num"], int):
        errors.append("'part_num' must be an integer.")

    return errors


def validate_markdown_file(filepath: str) -> List[str]:
    """Validates a single Grantha Markdown file against the specification.

    This function performs a multi-pass check:
    1.  Parses and validates the YAML frontmatter.
    2.  Collects all main passage references to check for duplicates.
    3.  Performs a line-by-line check for valid headings, commentary linking,
        and block structure.

    Args:
        filepath: The absolute path to the Grantha Markdown file.

    Returns:
        A list of string error messages. An empty list indicates successful
        validation.
    """
    errors = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.startswith('---'):
            raise ValidationError("File must start with YAML frontmatter.", line_num=1)

        parts = content.split('---', 2)
        if len(parts) < 3:
            raise ValidationError("YAML frontmatter is not properly closed with '---'.")

        frontmatter_str, body = parts[1], parts[2]
        try:
            frontmatter = yaml.safe_load(frontmatter_str)
            fm_errors = validate_frontmatter(frontmatter)
            if fm_errors:
                errors.extend(fm_errors)
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML in frontmatter: {e}")

        lines = body.split('\n')

        # First pass: Collect all passage_refs
        passage_refs = set()
        for i, line in enumerate(lines):
            line = line.strip()
            for pattern, name in [
                (HEADING_MANTRA, "Mantra"),
                (HEADING_PREFATORY, "Prefatory"),
                (HEADING_CONCLUDING, "Concluding")
            ]:
                match = pattern.match(line)
                if match:
                    ref = match.group(1)
                    if ref in passage_refs:
                        line_num = i + frontmatter_str.count('\n') + 3
                        errors.append(f"Line {line_num}: Duplicate passage ref '{ref}' found.")
                    passage_refs.add(ref)

        # Second pass: Full validation
        in_content_block = False
        expected_closing_script = None
        last_line_was_commentary_meta = False

        for i, line in enumerate(lines):
            line_num = i + frontmatter_str.count('\n') + 3
            line = line.strip()

            if in_content_block:
                match = CONTENT_BLOCK_END.match(line)
                if match:
                    if match.group(1) != expected_closing_script:
                        errors.append(f"Line {line_num}: Mismatched content block end tag. Expected '{expected_closing_script}', got '{match.group(1)}'.")
                    in_content_block = False
                    expected_closing_script = None
                continue

            if not line:
                continue

            is_valid_line = False

            # Check for headings
            heading_match = None
            for pattern, name in [
                (HEADING_MANTRA, "Mantra"),
                (HEADING_PREFATORY, "Prefatory"),
                (HEADING_CONCLUDING, "Concluding"),
                (HEADING_COMMENTARY, "Commentary")
            ]:
                match = pattern.match(line)
                if match:
                    heading_match = (match, name)
                    break

            if heading_match:
                is_valid_line = True
                match, name = heading_match
                ref = match.group(1)

                if name == "Commentary":
                    if not last_line_was_commentary_meta:
                        errors.append(f"Line {line_num}: Commentary heading is missing a preceding metadata comment.")

                    if ref in passage_refs:
                        pass
                    elif '-' in ref:
                        try:
                            base, range_part = ref.rsplit('.', 1)
                            start_str, end_str = range_part.split('-')
                            start, end = int(start_str), int(end_str)

                            for j in range(start, end + 1):
                                individual_ref = f"{base}.{j}"
                                if individual_ref not in passage_refs:
                                    errors.append(f"Line {line_num}: Commentary for ranged ref '{ref}' is missing a corresponding passage for '{individual_ref}'.")
                        except ValueError:
                            errors.append(f"Line {line_num}: Invalid range format in commentary ref '{ref}'.")
                    else:
                        errors.append(f"Line {line_num}: Commentary for ref '{ref}' has no corresponding passage.")

                last_line_was_commentary_meta = False

            if last_line_was_commentary_meta and not HEADING_COMMENTARY.match(line):
                errors.append(f"Line {line_num-1}: Commentary metadata comment must be immediately followed by a Commentary heading.")
                last_line_was_commentary_meta = False

            if is_valid_line:
                continue

            meta_match = COMMENTARY_METADATA.match(line)
            if meta_match:
                is_valid_line = True
                last_line_was_commentary_meta = True
                try:
                    import json
                    meta_json = json.loads(meta_match.group(1))
                    if 'commentary_id' not in meta_json:
                        errors.append(f"Line {line_num}: Commentary metadata is missing 'commentary_id'.")
                except (json.JSONDecodeError, yaml.YAMLError):
                    errors.append(f"Line {line_num}: Invalid JSON in commentary metadata.")
                continue

            content_match = CONTENT_BLOCK_START.match(line)
            if content_match:
                is_valid_line = True
                in_content_block = True
                expected_closing_script = content_match.group(1)
                continue

            if not is_valid_line:
                errors.append(f"Line {line_num}: Unrecognized line or invalid heading format: '{line}'")

        if in_content_block:
            errors.append(f"File Error: Reached end of file while inside an unclosed content block for script '{expected_closing_script}'.")
    except FileNotFoundError:
        errors.append(f"File not found at path: {filepath}")
    except ValidationError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"An unexpected error occurred: {e}")

    return errors


def main():
    """Command-line interface for the validator script."""
    parser = argparse.ArgumentParser(
        description="Validate a Grantha Markdown file against the specification."
    )
    parser.add_argument(
        "filepath",
        help="Path to the markdown file to validate."
    )
    args = parser.parse_args()

    print(f"Validating {args.filepath}...")
    errors = validate_markdown_file(args.filepath)
    if errors:
        print("Validation failed with the following errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Validation successful!")


if __name__ == "__main__":
    main()
