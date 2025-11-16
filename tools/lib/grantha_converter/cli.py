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

    try:
        print(f"Converting {input_path} to {output_path}...")
        markdown_file_to_json_file(str(input_path), str(output_path))
        print(f"✓ Successfully converted to {output_path}")
        print("✓ Validation hash verified - no data loss detected.")
    except ValueError as e:
        if "Validation hash mismatch" in str(e):
            print(f"✗ Validation failed: {e}", file=sys.stderr)
            sys.exit(1)
        else:
            raise
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
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
    md2json_parser.set_defaults(func=cmd_md2json)

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

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
