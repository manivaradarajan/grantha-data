"""Command-line interface for the Grantha converter.

This module provides a CLI for converting between the Grantha JSON and Markdown
formats, as well as for verifying the integrity of the conversions.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .devanagari_extractor import HASH_VERSION, extract_devanagari
from .hasher import hash_grantha, hash_text
from .json_to_md import json_file_to_markdown_file
from .md_to_json import markdown_file_to_json_file


def parse_scripts(scripts_str: Optional[str]) -> List[str]:
    """Parses a comma-separated string of script names."""
    if not scripts_str:
        return ['devanagari']
    scripts = [s.strip() for s in scripts_str.split(',')]
    valid_scripts = {'devanagari', 'roman', 'kannada'}
    for script in scripts:
        if script not in valid_scripts:
            print(f"Warning: Unknown script '{script}'. Valid: {', '.join(valid_scripts)}")
    return scripts


def parse_commentaries(commentaries_str: Optional[str]) -> Optional[List[str]]:
    """Parses a comma-separated string of commentary IDs."""
    if not commentaries_str:
        return None
    return [c.strip() for c in commentaries_str.split(',')]


def verify_files(json_path: str, md_path: str) -> bool:
    """Verifies that a JSON file and a Markdown file have matching content."""
    import json
    import re

    import yaml

    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    match = re.match(r'^---\n(.*?)\n---\n', md_content, re.DOTALL)
    if not match:
        print("Error: No frontmatter found in markdown file")
        return False
    frontmatter = yaml.safe_load(match.group(1))

    scripts = frontmatter.get('scripts', ['devanagari'])
    commentaries = frontmatter.get('commentaries', None)
    json_hash = hash_grantha(json_data, scripts=scripts, commentaries=commentaries)
    expected_hash = frontmatter.get('validation_hash', '').replace('sha256:', '')
    return json_hash == expected_hash


def cmd_json2md(args: argparse.Namespace):
    """Handles the 'json2md' command."""
    import json
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    scripts = parse_scripts(args.scripts)
    commentaries = parse_commentaries(args.commentaries)

    if args.all_commentaries:
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'commentaries' in data and data['commentaries']:
                commentaries = [c['commentary_id'] for c in data['commentaries']]
                print(f"Found {len(commentaries)} commentaries in source file.")
            else:
                print("Warning: No commentaries found in source file.")
                commentaries = None
        except Exception as e:
            print(f"Error reading source for commentary detection: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        print(f"Converting {input_path} to {output_path}...")
        print(f"  Scripts: {', '.join(scripts)}")
        print(f"  Commentaries: {', '.join(commentaries) if commentaries else 'core text only'}")
        json_file_to_markdown_file(
            str(input_path), str(output_path), scripts=scripts, commentaries=commentaries
        )
        print(f"✓ Successfully converted to {output_path}")

        if args.verify:
            print("\nVerifying conversion...")
            if verify_files(str(input_path), str(output_path)):
                print("✓ Verification passed - content hashes match.")
            else:
                print("✗ Verification failed - content mismatch detected.", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_md2json(args: argparse.Namespace):
    """Handles the 'md2json' command."""
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Validate format argument
    format_type = args.format
    if format_type not in ['single', 'multipart']:
        print(f"Error: Invalid format '{format_type}'. Must be 'single' or 'multipart'.", file=sys.stderr)
        sys.exit(1)

    try:
        print(f"Converting {input_path} to {output_path}...")
        markdown_file_to_json_file(
            str(input_path),
            str(output_path),
            format=format_type,
            validate_schema=not args.no_schema_validation
        )
        print(f"✓ Successfully converted to {output_path}")
        print("✓ Validation hash verified - no data loss detected.")
        if not args.no_schema_validation:
            schema_name = 'grantha-part.schema.json' if format_type == 'multipart' else 'grantha.schema.json'
            print(f"✓ JSON schema validation passed ({schema_name})")
    except ValueError as e:
        if "Validation hash mismatch" in str(e):
            print(f"✗ Validation failed: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            raise
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_md2json_envelope(args: argparse.Namespace):
    """Handles the 'md2json-envelope' command."""
    from .envelope_generator import create_envelope_from_markdown_files, write_envelope
    from .schema_validator import validate_grantha_envelope

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    if not input_dir.is_dir():
        print(f"Error: Input path is not a directory: {input_dir}", file=sys.stderr)
        sys.exit(1)

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all .md files in the directory
    md_files = sorted(input_dir.glob('*.md'))
    if not md_files:
        print(f"Error: No .md files found in {input_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(md_files)} markdown file(s) in {input_dir}")

    # Determine grantha_id from first file
    from .md_to_json import parse_frontmatter
    with open(md_files[0], 'r', encoding='utf-8') as f:
        content = f.read()
    frontmatter, _ = parse_frontmatter(content)
    grantha_id = frontmatter.get('grantha_id')

    if not grantha_id:
        print(f"Error: No grantha_id found in {md_files[0]}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing grantha: {grantha_id}")

    try:
        # Convert each markdown file to a part JSON
        part_files = []
        for i, md_file in enumerate(md_files, start=1):
            part_num = i
            output_file = output_dir / f"part{part_num}.json"

            print(f"  Converting {md_file.name} → {output_file.name}...")
            markdown_file_to_json_file(
                str(md_file),
                str(output_file),
                format='multipart',
                validate_schema=not args.no_schema_validation
            )
            part_files.append(output_file)

        # Create envelope.json
        print(f"\nGenerating envelope.json...")
        envelope = create_envelope_from_markdown_files(
            grantha_id,
            md_files,
            output_dir
        )

        envelope_path = output_dir / 'envelope.json'
        write_envelope(envelope, envelope_path)
        print(f"✓ Created {envelope_path}")

        # Validate envelope against schema
        if not args.no_schema_validation:
            print(f"  Validating envelope against schema...")
            is_valid, errors = validate_grantha_envelope(envelope)
            if not is_valid:
                error_msg = "Envelope schema validation failed:\n"
                error_msg += "\n".join(f"  - {err}" for err in errors)
                raise ValueError(error_msg)
            print(f"  ✓ Envelope schema validation passed")

        print(f"\n✓ Successfully created multi-part grantha in {output_dir}")
        print(f"  - {len(part_files)} part file(s)")
        print(f"  - 1 envelope.json")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_verify(args: argparse.Namespace):
    """Handles the 'verify' command."""
    json_path = Path(args.json)
    md_path = Path(args.markdown)

    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}", file=sys.stderr)
        sys.exit(1)
    if not md_path.exists():
        print(f"Error: Markdown file not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    try:
        print(f"Verifying {json_path} ↔ {md_path}...")
        if verify_files(str(json_path), str(md_path)):
            print("✓ Files match - content hashes are identical.")
        else:
            print("✗ Files do NOT match - content differs.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error during verification: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_validate_header(args: argparse.Namespace):
    """Handles the 'validate-header' command."""
    import re
    import json as json_module

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    from .md_to_json import parse_frontmatter

    try:
        # Read the file
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse frontmatter
        frontmatter, body = parse_frontmatter(content)

        errors = []
        warnings = []

        # Check required top-level fields
        required_fields = ['grantha_id', 'canonical_title', 'text_type', 'language', 'structure_levels']
        for field in required_fields:
            if field not in frontmatter:
                errors.append(f"Missing required field: {field}")

        # Check grantha_id format
        if 'grantha_id' in frontmatter:
            grantha_id = frontmatter['grantha_id']
            if not re.match(r'^[a-z0-9-]+$', grantha_id):
                errors.append(f"Invalid grantha_id format: '{grantha_id}' (must be lowercase alphanumeric with hyphens)")

        # Check text_type
        if 'text_type' in frontmatter:
            if frontmatter['text_type'] not in ['upanishad', 'commentary']:
                errors.append(f"Invalid text_type: '{frontmatter['text_type']}' (must be 'upanishad' or 'commentary')")

        # Check language
        if 'language' in frontmatter:
            if frontmatter['language'] not in ['sanskrit', 'english']:
                errors.append(f"Invalid language: '{frontmatter['language']}' (must be 'sanskrit' or 'english')")

        # Check structure_levels format
        if 'structure_levels' in frontmatter:
            structure_levels = frontmatter['structure_levels']
            if not isinstance(structure_levels, list):
                errors.append("structure_levels must be an array/list")
            elif len(structure_levels) == 0:
                errors.append("structure_levels cannot be empty")
            else:
                # Validate structure_levels format
                for i, level in enumerate(structure_levels):
                    if not isinstance(level, dict):
                        errors.append(f"structure_levels[{i}] must be an object/dict")
                        continue
                    if 'key' not in level:
                        errors.append(f"structure_levels[{i}] missing required field: key")
                    if 'scriptNames' not in level:
                        errors.append(f"structure_levels[{i}] missing required field: scriptNames")
                    elif 'devanagari' not in level.get('scriptNames', {}):
                        errors.append(f"structure_levels[{i}].scriptNames missing required field: devanagari")

        # Check commentaries_metadata format
        if 'commentaries_metadata' in frontmatter:
            commentaries_metadata = frontmatter['commentaries_metadata']

            # Get all commentary IDs from metadata
            metadata_ids = set()

            if isinstance(commentaries_metadata, list):
                for i, item in enumerate(commentaries_metadata):
                    if not isinstance(item, dict):
                        errors.append(f"commentaries_metadata[{i}] must be an object/dict")
                        continue

                    if 'commentary_id' not in item:
                        errors.append(f"commentaries_metadata[{i}] missing required field: commentary_id")
                    else:
                        metadata_ids.add(item['commentary_id'])

                    if 'commentary_title' not in item:
                        errors.append(f"commentaries_metadata[{i}] missing required field: commentary_title")

                    if 'commentator' not in item:
                        errors.append(f"commentaries_metadata[{i}] missing required field: commentator")
                    elif isinstance(item['commentator'], str):
                        errors.append(f"commentaries_metadata[{i}].commentator must be an object with 'devanagari' field, not a string")
                    elif not isinstance(item['commentator'], dict):
                        errors.append(f"commentaries_metadata[{i}].commentator must be an object/dict")
                    elif 'devanagari' not in item['commentator']:
                        errors.append(f"commentaries_metadata[{i}].commentator missing required field: devanagari")

            elif isinstance(commentaries_metadata, dict):
                # Dict format (legacy)
                warnings.append("commentaries_metadata is in dict format; list format is preferred")
                metadata_ids = set(commentaries_metadata.keys())

            # Check commentary ID references in the body
            COMMENTARY_METADATA = re.compile(r'<!--\s*commentary:\s*({.*?})\s*-->')
            referenced_ids = set()

            for match in COMMENTARY_METADATA.finditer(body):
                try:
                    meta = json_module.loads(match.group(1))
                    if 'commentary_id' in meta:
                        referenced_ids.add(meta['commentary_id'])
                except json_module.JSONDecodeError:
                    warnings.append(f"Invalid JSON in commentary metadata comment: {match.group(1)[:50]}...")

            # Check for mismatches
            if metadata_ids and referenced_ids:
                # IDs in body but not in metadata
                missing_in_metadata = referenced_ids - metadata_ids
                if missing_in_metadata:
                    for cid in missing_in_metadata:
                        errors.append(f"Commentary ID '{cid}' referenced in body but not declared in commentaries_metadata")

                # IDs in metadata but not used in body
                unused_ids = metadata_ids - referenced_ids
                if unused_ids:
                    for cid in unused_ids:
                        warnings.append(f"Commentary ID '{cid}' declared in commentaries_metadata but not used in body")

        # Check hash_version
        if 'hash_version' not in frontmatter:
            warnings.append("Missing hash_version field")

        # Check validation_hash
        if 'validation_hash' not in frontmatter:
            warnings.append("Missing validation_hash field")

        # Print results
        print(f"Validating header of {input_path}...")
        print()

        if errors:
            print(f"✗ Found {len(errors)} error(s):")
            for error in errors:
                print(f"  - {error}")
            print()

        if warnings:
            print(f"⚠ Found {len(warnings)} warning(s):")
            for warning in warnings:
                print(f"  - {warning}")
            print()

        if not errors and not warnings:
            print("✓ Header validation passed - no issues found")
            sys.exit(0)
        elif not errors:
            print("✓ Header validation passed with warnings")
            sys.exit(0)
        else:
            print(f"✗ Header validation failed with {len(errors)} error(s)")
            sys.exit(1)

    except Exception as e:
        print(f"Error during validation: {e}", file=sys.stderr)
        import traceback
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


def cmd_update_hash(args: argparse.Namespace):
    """Handles the 'update-hash' command."""
    import re

    import yaml

    input_path = Path(args.input)

    # Validate that file is in structured_md/ directory
    if 'structured_md' not in input_path.parts:
        print(f"Error: File must be in structured_md/ directory: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        # Read the file
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract YAML frontmatter
        match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        if not match:
            print(f"Error: No YAML frontmatter found in {input_path}", file=sys.stderr)
            sys.exit(1)

        frontmatter_str = match.group(1)
        body = match.group(2)
        frontmatter = yaml.safe_load(frontmatter_str)

        # Extract Devanagari from body only (not from YAML header)
        devanagari_text = extract_devanagari(body)

        # Compute hash
        new_hash = hash_text(devanagari_text)

        # Update frontmatter
        old_hash = frontmatter.get('validation_hash', '')
        old_version = frontmatter.get('hash_version', None)
        frontmatter['hash_version'] = HASH_VERSION
        frontmatter['validation_hash'] = new_hash

        # Write back to file
        new_frontmatter_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
        new_content = f"---\n{new_frontmatter_str}---\n{body}"

        with open(input_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✓ Updated validation_hash in {input_path}")
        if old_version is not None and old_version != HASH_VERSION:
            print(f"  Version updated: {old_version} → {HASH_VERSION}")
        elif old_version is None:
            print(f"  Version set: {HASH_VERSION} (was unversioned)")
        if old_hash and old_hash != new_hash:
            print(f"  Old hash: {old_hash}")
            print(f"  New hash: {new_hash}")
        else:
            print(f"  Hash: {new_hash}")

    except Exception as e:
        print(f"Error updating hash: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_verify_hash(args: argparse.Namespace):
    """Handles the 'verify-hash' command."""
    import re

    import yaml

    input_path = Path(args.input)

    # Validate that file is in structured_md/ directory
    if 'structured_md' not in input_path.parts:
        print(f"Error: File must be in structured_md/ directory: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        # Read the file
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract YAML frontmatter
        match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
        if not match:
            print(f"Error: No YAML frontmatter found in {input_path}", file=sys.stderr)
            sys.exit(1)

        frontmatter_str = match.group(1)
        body = match.group(2)
        frontmatter = yaml.safe_load(frontmatter_str)

        # Check hash version
        file_version = frontmatter.get('hash_version', None)
        if file_version is None:
            print(f"✗ Hash version MISSING in {input_path}", file=sys.stderr)
            print(f"  File has no hash_version field (legacy/unversioned file)", file=sys.stderr)
            print(f"  Current version: {HASH_VERSION}", file=sys.stderr)
            print(f"  Please run: grantha-converter update-hash -i \"{input_path}\"", file=sys.stderr)
            sys.exit(1)

        if file_version != HASH_VERSION:
            print(f"✗ Hash version MISMATCH in {input_path}", file=sys.stderr)
            print(f"  File version: {file_version}", file=sys.stderr)
            print(f"  Current version: {HASH_VERSION}", file=sys.stderr)
            print(f"  The hashing algorithm has changed since this hash was generated.", file=sys.stderr)
            print(f"  Please run: grantha-converter update-hash -i \"{input_path}\"", file=sys.stderr)
            sys.exit(1)

        # Get expected hash from frontmatter
        expected_hash = frontmatter.get('validation_hash', '')
        if not expected_hash:
            print(f"Error: No validation_hash field in {input_path}", file=sys.stderr)
            sys.exit(1)

        # Extract Devanagari from body only (not from YAML header)
        devanagari_text = extract_devanagari(body)

        # Compute actual hash
        actual_hash = hash_text(devanagari_text)

        # Compare
        if actual_hash == expected_hash:
            print(f"✓ Hash valid for {input_path}")
            print(f"  Version: {HASH_VERSION}")
            print(f"  Hash: {actual_hash}")
            sys.exit(0)
        else:
            print(f"✗ Hash INVALID for {input_path}", file=sys.stderr)
            print(f"  Expected: {expected_hash}", file=sys.stderr)
            print(f"  Actual:   {actual_hash}", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error verifying hash: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """The main command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description='A tool to convert between Grantha Project JSON and structured Markdown formats.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert JSON to Markdown (core text, Devanagari script)
  grantha-converter json2md -i data.json -o data.md

  # Convert JSON to Markdown, including multiple scripts
  grantha-converter json2md -i data.json -o data.md --scripts devanagari,roman

  # Convert JSON to Markdown, including a specific commentary
  grantha-converter json2md -i data.json -o data.md --commentaries vedanta-desika

  # Convert JSON to Markdown and include ALL commentaries found in the source
  grantha-converter json2md -i data.json -o data.md --all-commentaries

  # Convert Markdown back to JSON (hash integrity is checked automatically)
  grantha-converter md2json -i data.md -o data.json

  # Verify that a JSON file and a Markdown file are in sync
  grantha-converter verify -j data.json -m data.md

  # Update validation_hash in a structured Markdown file
  grantha-converter update-hash -i structured_md/upanishads/isavasya/isavasya-1.md

  # Verify validation_hash in a structured Markdown file
  grantha-converter verify-hash -i structured_md/upanishads/isavasya/isavasya-1.md
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    subparsers.required = True

    # json2md command
    json2md_parser = subparsers.add_parser(
        'json2md',
        help='Convert a canonical JSON file to structured Markdown.',
        description='Converts a Grantha JSON file into a human-readable, structured Markdown file. The output includes a YAML frontmatter block with metadata for lossless round-trip conversion.'
    )
    json2md_parser.add_argument('-i', '--input', required=True, help='Path to the input JSON file.')
    json2md_parser.add_argument('-o', '--output', required=True, help='Path for the output Markdown file.')
    json2md_parser.add_argument('--scripts', default='devanagari', help='Comma-separated list of scripts to include (e.g., "devanagari,roman"). Default: devanagari.')
    json2md_parser.add_argument('--commentaries', help='Comma-separated list of commentary IDs to include in the output.')
    json2md_parser.add_argument('--all-commentaries', action='store_true', help='A convenience flag to include all commentaries found in the source JSON file.')
    json2md_parser.add_argument('--verify', action='store_true', help='After conversion, verify that the output Markdown correctly represents the source JSON by checking the content hash.')
    json2md_parser.set_defaults(func=cmd_json2md)

    # md2json command
    md2json_parser = subparsers.add_parser(
        'md2json',
        help='Convert a structured Markdown file back to canonical JSON.',
        description='Converts a structured Markdown file back into the Grantha JSON format. This command automatically verifies the `validation_hash` in the frontmatter to ensure no data was lost or corrupted.'
    )
    md2json_parser.add_argument('-i', '--input', required=True, help='Path to the input Markdown file.')
    md2json_parser.add_argument('-o', '--output', required=True, help='Path for the output JSON file.')
    md2json_parser.add_argument('--format', default='single', choices=['single', 'multipart'], help='Output format: "single" for complete grantha (default), "multipart" for grantha parts.')
    md2json_parser.add_argument('--no-schema-validation', action='store_true', help='Skip JSON schema validation.')
    md2json_parser.set_defaults(func=cmd_md2json)

    # md2json-envelope command
    envelope_parser = subparsers.add_parser(
        'md2json-envelope',
        help='Convert a directory of Markdown files to multi-part JSON with envelope.',
        description='Scans a directory for .md files, converts each to a part JSON file (part1.json, part2.json, etc.), and generates an envelope.json file with metadata. All files are validated against their respective schemas.'
    )
    envelope_parser.add_argument('-i', '--input', required=True, help='Path to the input directory containing .md files.')
    envelope_parser.add_argument('-o', '--output', required=True, help='Path to the output directory for JSON files.')
    envelope_parser.add_argument('--no-schema-validation', action='store_true', help='Skip JSON schema validation.')
    envelope_parser.set_defaults(func=cmd_md2json_envelope)

    # verify command
    verify_parser = subparsers.add_parser(
        'verify',
        help='Verify that a JSON file and a Markdown file are in sync.',
        description="Checks if a Markdown file is a faithful representation of a JSON file by recalculating the JSON hash based on the Markdown's frontmatter and comparing it to the stored validation hash."
    )
    verify_parser.add_argument('-j', '--json', required=True, help='Path to the JSON file.')
    verify_parser.add_argument('-m', '--markdown', required=True, help='Path to the Markdown file.')
    verify_parser.set_defaults(func=cmd_verify)

    # update-hash command
    update_hash_parser = subparsers.add_parser(
        'update-hash',
        help='Update the validation_hash in a structured Markdown file.',
        description='Extracts Devanagari text from a structured Markdown file, computes the validation hash, and updates the YAML frontmatter. Only works on files in structured_md/ directory.'
    )
    update_hash_parser.add_argument('-i', '--input', required=True, help='Path to the structured Markdown file to update.')
    update_hash_parser.set_defaults(func=cmd_update_hash)

    # verify-hash command
    verify_hash_parser = subparsers.add_parser(
        'verify-hash',
        help='Verify the validation_hash in a structured Markdown file.',
        description='Extracts Devanagari text from a structured Markdown file, computes the hash, and compares it to the validation_hash in the YAML frontmatter. Only works on files in structured_md/ directory. Exits with code 0 if valid, 1 if invalid.'
    )
    verify_hash_parser.add_argument('-i', '--input', required=True, help='Path to the structured Markdown file to verify.')
    verify_hash_parser.set_defaults(func=cmd_verify_hash)

    # validate-header command
    validate_header_parser = subparsers.add_parser(
        'validate-header',
        help='Validate the frontmatter structure of a markdown file.',
        description='Validates the YAML frontmatter structure and checks that commentary IDs in metadata match those referenced in the body. Exits with code 0 if valid, 1 if errors found.'
    )
    validate_header_parser.add_argument('-i', '--input', required=True, help='Path to the markdown file to validate.')
    validate_header_parser.add_argument('--verbose', action='store_true', help='Show detailed error traces.')
    validate_header_parser.set_defaults(func=cmd_validate_header)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
