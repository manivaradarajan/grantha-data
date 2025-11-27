#!/usr/bin/env python3
"""Synchronize YAML frontmatter across multi-part grantha files.

This script interactively prompts for YAML frontmatter field values and
synchronizes them across all parts of a multi-part grantha. It:
- Shows the most common value as the default for each field
- Updates commentary references in the body when commentary_id changes
- Validates all changes before saving
- Requires confirmation before modifying files
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

# Import from grantha_converter
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'lib'))
from grantha_converter.md_to_json import parse_frontmatter


# Protected fields that should not be edited
PROTECTED_FIELDS = {'validation_hash', 'hash_version', 'part_num', 'part_title'}


def parse_file(filepath: Path) -> Dict[str, Any]:
    """Parse a markdown file and extract frontmatter and body.

    Args:
        filepath: Path to the markdown file

    Returns:
        Dictionary with keys: path, frontmatter, body, part_num, original_text
    """
    try:
        original_text = filepath.read_text(encoding='utf-8')
        frontmatter, body = parse_frontmatter(original_text)

        return {
            'path': filepath,
            'frontmatter': frontmatter,
            'body': body,
            'part_num': frontmatter.get('part_num', 1),
            'original_text': original_text
        }
    except Exception as e:
        print(f"  Warning: Failed to parse {filepath.name}: {e}")
        return None


def discover_files(directory: Path) -> Dict[str, Dict]:
    """Find all .md files in directory and parse them.

    Args:
        directory: Path to directory containing multi-part .md files

    Returns:
        Dictionary mapping filename to FileData
    """
    print(f"Discovering files in: {directory}")

    md_files = sorted(directory.glob('*.md'))

    if not md_files:
        print(f"Error: No .md files found in {directory}")
        sys.exit(1)

    files_data = {}
    part_nums = []

    for filepath in md_files:
        file_data = parse_file(filepath)
        if file_data:
            files_data[filepath.name] = file_data
            part_nums.append(file_data['part_num'])

    if not files_data:
        print("Error: No valid .md files could be parsed")
        sys.exit(1)

    # Validate consecutive part numbers
    part_nums.sort()
    expected = list(range(1, len(part_nums) + 1))
    if part_nums != expected:
        print(f"Warning: Part numbers are not consecutive: {part_nums}")
        print(f"Expected: {expected}")

    # Check for duplicates
    part_counter = Counter(part_nums)
    duplicates = [num for num, count in part_counter.items() if count > 1]
    if duplicates:
        print(f"Error: Duplicate part numbers found: {duplicates}")
        sys.exit(1)

    print(f"Found {len(files_data)} part(s)\n")
    return files_data


def extract_universal_fields(files_data: Dict) -> List[str]:
    """Extract fields that are present in ALL files.

    Args:
        files_data: Dictionary mapping filename to FileData

    Returns:
        List of field names present in all files
    """
    if not files_data:
        return []

    # Get field sets for each file
    field_sets = [set(data['frontmatter'].keys()) for data in files_data.values()]

    # Intersect all sets to find universal fields
    universal = field_sets[0]
    for field_set in field_sets[1:]:
        universal &= field_set

    return sorted(list(universal))


def serialize_field(value: Any) -> str:
    """Serialize a field value for display.

    Args:
        value: The field value

    Returns:
        String representation
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def deserialize_field(user_input: str, current_value: Any) -> Any:
    """Parse user input based on current value type.

    Args:
        user_input: The user's input string
        current_value: The current field value (for type inference)

    Returns:
        Parsed value matching the type of current_value

    Raises:
        ValueError: If parsing fails
    """
    if isinstance(current_value, (dict, list)):
        try:
            return json.loads(user_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    elif isinstance(current_value, int):
        return int(user_input)
    else:
        return user_input


def analyze_fields(files_data: Dict) -> Dict[str, Dict]:
    """Analyze field values across all parts.

    Args:
        files_data: Dictionary mapping filename to FileData

    Returns:
        Dictionary mapping field name to analysis data
    """
    print("Analyzing fields across all parts...")

    universal_fields = extract_universal_fields(files_data)
    editable_fields = [f for f in universal_fields if f not in PROTECTED_FIELDS]

    field_analysis = {}

    for field in editable_fields:
        # Collect values (using JSON serialization for complex types)
        values = []
        for file_data in files_data.values():
            value = file_data['frontmatter'].get(field)
            # Use JSON string as key for complex types to enable comparison
            if isinstance(value, (dict, list)):
                values.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
            else:
                values.append(value)

        value_counter = Counter(values)
        most_common_serialized = value_counter.most_common(1)[0][0]

        # Deserialize the most common value
        if isinstance(files_data[list(files_data.keys())[0]]['frontmatter'].get(field), (dict, list)):
            most_common = json.loads(most_common_serialized)
        else:
            most_common = most_common_serialized

        # Track which files have different values
        files_with_diff = []
        for filename, file_data in files_data.items():
            value = file_data['frontmatter'].get(field)
            serialized = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value
            if serialized != most_common_serialized:
                files_with_diff.append(filename)

        field_analysis[field] = {
            'values': value_counter,
            'most_common': most_common,
            'files_with_diff': files_with_diff
        }

    return field_analysis


def prompt_for_field_values(field_analysis: Dict) -> Dict[str, Any]:
    """Interactively prompt user for each field value.

    Args:
        field_analysis: Dictionary from analyze_fields()

    Returns:
        Dictionary mapping field name to new value
    """
    print("\n" + "="*60)
    print("INTERACTIVE FIELD PROMPTING")
    print("="*60)
    print("For each field, press Enter to keep the default (most common value),")
    print("or type a new value. For complex fields (dict/list), provide JSON.\n")

    new_values = {}

    for field_name, analysis in sorted(field_analysis.items()):
        print(f"\n{'='*60}")
        print(f"Field: {field_name}")

        # Show current state
        if len(analysis['values']) > 1:
            print("\nCurrent values differ across parts:")
            for value, count in analysis['values'].most_common():
                # Deserialize for display if it's a JSON string
                try:
                    display_value = json.loads(value) if value and value[0] in '[{' else value
                    display_str = json.dumps(display_value, ensure_ascii=False) if isinstance(display_value, (dict, list)) else str(value)
                except:
                    display_str = str(value)
                print(f"  [{count} file(s)]: {display_str}")

            if analysis['files_with_diff']:
                print(f"  Files with non-default values: {', '.join(analysis['files_with_diff'][:3])}")
                if len(analysis['files_with_diff']) > 3:
                    print(f"    ... and {len(analysis['files_with_diff']) - 3} more")

        # Show default
        default = analysis['most_common']
        default_str = serialize_field(default)
        print(f"\nDefault (most common): {default_str}")

        # For complex fields: offer to show full JSON
        if isinstance(default, (dict, list)):
            show = input("Show full formatted JSON? [y/N]: ").strip().lower()
            if show == 'y':
                print(json.dumps(default, indent=2, ensure_ascii=False))

        # Get user input
        user_input = input(f"\nNew value [Enter to keep default]: ").strip()

        if user_input:
            try:
                new_values[field_name] = deserialize_field(user_input, default)
            except ValueError as e:
                print(f"  Error: {e}")
                print(f"  Using default value instead.")
                new_values[field_name] = default
        else:
            new_values[field_name] = default

    return new_values


def extract_commentary_ids(commentaries_metadata: Any) -> List[str]:
    """Extract commentary IDs from commentaries_metadata field.

    Args:
        commentaries_metadata: Can be list of dicts or dict of dicts

    Returns:
        List of commentary IDs
    """
    if not commentaries_metadata:
        return []

    if isinstance(commentaries_metadata, list):
        return [c.get('commentary_id', '') for c in commentaries_metadata]
    elif isinstance(commentaries_metadata, dict):
        return list(commentaries_metadata.keys())

    return []


def build_commentary_id_mapping(old_metadata: Any, new_metadata: Any) -> Dict[str, str]:
    """Build mapping from old commentary IDs to new IDs by position.

    Args:
        old_metadata: Old commentaries_metadata value
        new_metadata: New commentaries_metadata value

    Returns:
        Dictionary mapping old_id -> new_id (only for changed IDs)
    """
    old_ids = extract_commentary_ids(old_metadata)
    new_ids = extract_commentary_ids(new_metadata)

    mapping = {}
    for i, (old_id, new_id) in enumerate(zip(old_ids, new_ids)):
        if old_id != new_id:
            mapping[old_id] = new_id

    return mapping


def update_commentary_references(body: str, id_mapping: Dict[str, str]) -> str:
    """Replace commentary IDs in body content.

    Args:
        body: The markdown body content
        id_mapping: Dictionary mapping old_id -> new_id

    Returns:
        Updated body with replaced commentary IDs
    """
    if not id_mapping:
        return body

    # Pattern: <!-- commentary: {"commentary_id": "SOME_ID"} -->
    pattern = r'<!--\s*commentary:\s*\{[^}]*"commentary_id":\s*"([^"]+)"[^}]*\}\s*-->'

    def replace_id(match):
        old_id = match.group(1)
        if old_id in id_mapping:
            return match.group(0).replace(f'"{old_id}"', f'"{id_mapping[old_id]}"')
        return match.group(0)

    return re.sub(pattern, replace_id, body)


def build_changes(files_data: Dict, new_values: Dict) -> Dict:
    """Build change set for all files.

    Args:
        files_data: Dictionary mapping filename to FileData
        new_values: Dictionary mapping field name to new value

    Returns:
        Dictionary mapping filename to changes
    """
    changes = {}

    for filename, file_data in files_data.items():
        file_changes = {
            'frontmatter_updates': {},
            'commentary_replacements': []
        }

        # 1. Frontmatter updates
        for field, new_value in new_values.items():
            old_value = file_data['frontmatter'].get(field)
            # Deep comparison for complex types
            if old_value != new_value:
                file_changes['frontmatter_updates'][field] = new_value

        # 2. Commentary ID mapping (if commentaries_metadata changed)
        if 'commentaries_metadata' in file_changes['frontmatter_updates']:
            old_meta = file_data['frontmatter'].get('commentaries_metadata')
            new_meta = new_values['commentaries_metadata']

            id_mapping = build_commentary_id_mapping(old_meta, new_meta)

            if id_mapping:
                file_changes['commentary_replacements'] = list(id_mapping.items())

        if file_changes['frontmatter_updates'] or file_changes['commentary_replacements']:
            changes[filename] = file_changes

    return changes


def preview_changes(changes: Dict, files_data: Dict):
    """Display all changes before applying.

    Args:
        changes: Dictionary from build_changes()
        files_data: Dictionary mapping filename to FileData
    """
    print("\n" + "="*60)
    print("PREVIEW OF CHANGES")
    print("="*60)

    if not changes:
        print("\nNo changes detected. All files already have the selected values.")
        return

    for filename in sorted(changes.keys()):
        print(f"\n{filename}:")

        change = changes[filename]

        # Show frontmatter changes
        if change['frontmatter_updates']:
            print("  Frontmatter updates:")
            for field, new_value in sorted(change['frontmatter_updates'].items()):
                old_value = files_data[filename]['frontmatter'].get(field)
                print(f"    {field}:")
                print(f"      OLD: {serialize_field(old_value)[:100]}")
                print(f"      NEW: {serialize_field(new_value)[:100]}")

        # Show body commentary replacements
        if change['commentary_replacements']:
            print("  Commentary reference updates in body:")
            for old_id, new_id in change['commentary_replacements']:
                print(f"    {old_id} -> {new_id}")


def write_frontmatter(frontmatter: Dict, body: str) -> str:
    """Write YAML frontmatter + body.

    Args:
        frontmatter: Dictionary of frontmatter fields
        body: Body content (preserved exactly)

    Returns:
        Complete markdown file content
    """
    yaml_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n{body}"


def validate_changes(files_data: Dict, changes: Dict) -> bool:
    """Validate all modified files (basic frontmatter validation).

    Args:
        files_data: Dictionary mapping filename to FileData
        changes: Dictionary from build_changes()

    Returns:
        True if all validations pass, False otherwise
    """
    print("\n" + "="*60)
    print("VALIDATING CHANGES")
    print("="*60)

    if not changes:
        print("\nNo changes to validate.")
        return True

    all_valid = True

    required_fields = ['grantha_id', 'canonical_title', 'text_type', 'language', 'structure_levels']

    for filename, change in changes.items():
        # Apply changes to in-memory copy
        frontmatter = files_data[filename]['frontmatter'].copy()
        frontmatter.update(change['frontmatter_updates'])

        body = files_data[filename]['body']
        for old_id, new_id in change['commentary_replacements']:
            body = update_commentary_references(body, {old_id: new_id})

        # Basic validation
        errors = []

        # Check required fields
        for field in required_fields:
            if field not in frontmatter:
                errors.append(f"Missing required field: {field}")

        # Check grantha_id format
        if 'grantha_id' in frontmatter and not re.match(r'^[a-z0-9-]+$', frontmatter['grantha_id']):
            errors.append(f"Invalid grantha_id format: '{frontmatter['grantha_id']}'")

        # Check text_type
        if 'text_type' in frontmatter and frontmatter['text_type'] not in ['upanishad', 'commentary']:
            errors.append(f"Invalid text_type: '{frontmatter['text_type']}'")

        # Check language
        if 'language' in frontmatter and frontmatter['language'] not in ['sanskrit', 'english']:
            errors.append(f"Invalid language: '{frontmatter['language']}'")

        if errors:
            print(f"  ✗ {filename}: VALIDATION FAILED")
            for error in errors:
                print(f"      - {error}")
            all_valid = False
        else:
            print(f"  ✓ {filename}: Valid")

    return all_valid


def apply_changes(files_data: Dict, changes: Dict):
    """Prompt for confirmation and save changes.

    Args:
        files_data: Dictionary mapping filename to FileData
        changes: Dictionary from build_changes()
    """
    if not changes:
        print("\nNo changes to apply. Exiting.")
        return

    print("\n" + "="*60)
    response = input("Apply changes? [yes/no]: ").strip().lower()

    if response != 'yes':
        print("\nChanges aborted. No files modified.")
        return

    print("\nSaving changes...")
    saved_count = 0
    failed = []

    for filename, change in changes.items():
        try:
            # Apply frontmatter updates
            frontmatter = files_data[filename]['frontmatter'].copy()
            frontmatter.update(change['frontmatter_updates'])

            # Apply body updates
            body = files_data[filename]['body']
            for old_id, new_id in change['commentary_replacements']:
                body = update_commentary_references(body, {old_id: new_id})

            # Write file
            markdown = write_frontmatter(frontmatter, body)
            files_data[filename]['path'].write_text(markdown, encoding='utf-8')
            print(f"  ✓ Saved: {filename}")
            saved_count += 1
        except Exception as e:
            print(f"  ✗ Failed to save {filename}: {e}")
            failed.append(filename)

    print(f"\nSuccessfully updated {saved_count} file(s).")
    if failed:
        print(f"Failed to update {len(failed)} file(s): {', '.join(failed)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Synchronize YAML frontmatter across multi-part grantha files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  grantha-sync-yaml structured_md/upanishads/brihadaranyaka/

This will:
1. Analyze all .md files in the directory
2. Prompt you for each frontmatter field (showing most common value as default)
3. Update commentary references if commentary_id changes
4. Validate all changes
5. Ask for confirmation before saving
        """
    )
    parser.add_argument(
        'directory',
        type=Path,
        help='Directory containing multi-part .md files'
    )

    args = parser.parse_args()

    if not args.directory.exists():
        print(f"Error: Directory does not exist: {args.directory}")
        sys.exit(1)

    if not args.directory.is_dir():
        print(f"Error: Not a directory: {args.directory}")
        sys.exit(1)

    # Phase 1: Discovery
    files_data = discover_files(args.directory)

    # Phase 2: Analysis
    field_analysis = analyze_fields(files_data)

    if not field_analysis:
        print("No editable fields found (all fields are protected or no universal fields).")
        sys.exit(0)

    # Phase 3: Interactive Prompting
    new_values = prompt_for_field_values(field_analysis)

    # Phase 4: Build Changes
    changes = build_changes(files_data, new_values)

    # Phase 5: Preview
    preview_changes(changes, files_data)

    # Phase 6: Validation
    is_valid = validate_changes(files_data, changes)

    if not is_valid:
        print("\n" + "="*60)
        response = input("Validation failed. Continue anyway? [yes/no]: ").strip().lower()
        if response != 'yes':
            print("Aborted due to validation errors.")
            sys.exit(1)

    # Phase 7: Confirmation & Save
    apply_changes(files_data, changes)


if __name__ == '__main__':
    main()
