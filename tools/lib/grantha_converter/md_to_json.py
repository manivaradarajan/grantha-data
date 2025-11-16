"""Markdown to JSON converter for grantha data.

This module converts a structured Grantha Markdown file back into the canonical
JSON format. It parses the YAML frontmatter, reconstructs passages and commentaries
from the Markdown headings and content blocks, and verifies content integrity
using the `validation_hash` from the frontmatter.
"""
import re
from typing import Any, Dict, List, Tuple

import yaml

from .devanagari_extractor import HASH_VERSION

# Regex patterns from the specification
HEADING_MANTRA = re.compile(r'^#\s+(?:Mantra|Valli|Khanda|Anuvaka)\s+([\d\.]+)$')
HEADING_PREFATORY = re.compile(r'^#\s+Prefatory:\s+([\d\.]+)\s+\((\w+):\s*\"(.*?)\"\)$', re.IGNORECASE | re.MULTILINE)
HEADING_CONCLUDING = re.compile(r'^#\s+Concluding:\s+([\d\.]+)\s+\((\w+):\s*\"(.*?)\"\)$', re.IGNORECASE | re.MULTILINE)
HEADING_COMMENTARY = re.compile(r'^#\s+Commentary:\s+([\d\.]+)$', re.IGNORECASE | re.MULTILINE)
COMMENTARY_METADATA = re.compile(r'<!--\s*commentary:\s*({.*?})\s*-->')
HEADING_ANY = re.compile(r'^#\s+.*$', re.MULTILINE)

def parse_frontmatter(markdown: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown."""
    match = re.match(r'^---\n(.*?)\n---\n(.*)$', markdown, re.DOTALL)
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
    matches = list(re.finditer(r'<!--\s*(.+?)\s*-->', content))

    for i, match in enumerate(matches):
        label = match.group(1).strip()
        start_pos = match.end()
        end_pos = matches[i+1].start() if i + 1 < len(matches) else len(content)

        text = content[start_pos:end_pos].strip()

        if label == 'sanskrit:devanagari':
            sanskrit_data['devanagari'] = text
        elif label == 'sanskrit:roman':
            sanskrit_data['roman'] = text
        elif label == 'sanskrit:kannada':
            sanskrit_data['kannada'] = text
        elif label == 'english_translation':
            data['english_translation'] = text
        elif label == 'english':
            data['english'] = text

    if sanskrit_data:
        data['sanskrit'] = sanskrit_data

    return data

def get_lowest_level_key(structure_levels: List[Dict[str, Any]]) -> str:
    """Recursively get the lowest 'key' value from structure_levels."""
    if not structure_levels:
        return 'Mantra' # Default if none

    last_level = structure_levels[-1]
    if 'children' in last_level and last_level['children']:
        return get_lowest_level_key(last_level['children'])
    else:
        return last_level['key']

def get_all_structure_keys(structure_levels: List[Dict[str, Any]]) -> List[str]:
    """Recursively get all 'key' values from structure_levels."""
    keys = []
    for level in structure_levels:
        keys.append(level['key'])
        if 'children' in level and level['children']:
            keys.extend(get_all_structure_keys(level['children']))
    return keys

def convert_to_json(markdown: str) -> Dict[str, Any]:
    """Convert Markdown to grantha JSON format using a single-pass strategy."""
    frontmatter, content = parse_frontmatter(markdown)
    commentaries_metadata = frontmatter.get('commentaries_metadata', {})

    # Dynamically build the regex for main content headings
    structure_levels = frontmatter.get('structure_levels', [])
    structure_keys = get_all_structure_keys(structure_levels)
    lowest_level_key = get_lowest_level_key(structure_levels)

    heading_structure_pattern = r'^#\s+(' + '|'.join(re.escape(key) for key in structure_keys) + r')\s+([\d\.]+)$'
    HEADING_STRUCTURE = re.compile(heading_structure_pattern, re.MULTILINE | re.IGNORECASE)

    data = {
        'grantha_id': frontmatter.get('grantha_id'),
        'part_num': frontmatter.get('part_num'),
        'canonical_title': frontmatter.get('canonical_title'),
        'text_type': frontmatter.get('text_type'),
        'language': frontmatter.get('language'),
        'structure_levels': structure_levels,
        'passages': [],
        'prefatory_material': [],
        'concluding_material': [],
        'commentaries': {cid: {"commentary_id": cid, **meta, "passages": []} for cid, meta in commentaries_metadata.items()}
    }

    all_headings = sorted(
        list(HEADING_STRUCTURE.finditer(content)) +
        list(HEADING_PREFATORY.finditer(content)) +
        list(HEADING_CONCLUDING.finditer(content)) +
        list(HEADING_COMMENTARY.finditer(content)),
        key=lambda m: m.start()
    )

    pending_commentary_meta = None

    for i, match in enumerate(all_headings):
        start_pos = match.end()
        end_pos = all_headings[i+1].start() if i + 1 < len(all_headings) else len(content)

        heading_line = match.group(0).strip()
        raw_body_content = content[start_pos:end_pos].strip()

        # Re-match to identify heading type
        match_prefatory = HEADING_PREFATORY.match(heading_line)
        match_concluding = HEADING_CONCLUDING.match(heading_line)
        match_commentary = HEADING_COMMENTARY.match(heading_line)
        match_structure = HEADING_STRUCTURE.match(heading_line)

        if match_commentary:
            if pending_commentary_meta:
                ref = match_commentary.group(1)
                commentary_id = pending_commentary_meta.get('commentary_id')

                if commentary_id and commentary_id in data['commentaries']:
                    commentary_passage = {
                        'ref': ref,
                        'content': parse_sanskrit_content(raw_body_content)
                    }
                    data['commentaries'][commentary_id]['passages'].append(commentary_passage)

                pending_commentary_meta = None # Consume it
            continue

        # This is a content-bearing heading, not a commentary heading.
        body_content = raw_body_content

        # Reset any stale metadata from a previous loop
        pending_commentary_meta = None

        # Check for attached commentary metadata for the *next* heading
        meta_match = COMMENTARY_METADATA.search(body_content)
        if meta_match and body_content.endswith(meta_match.group(0)):
            try:
                import json
                pending_commentary_meta = json.loads(meta_match.group(1))
                # Clean the metadata from the current body
                body_content = body_content[:meta_match.start()].strip()
            except (json.JSONDecodeError, yaml.YAMLError):
                pending_commentary_meta = None

        # Now process the passage with the cleaned body content
        if match_prefatory:
            ref = match_prefatory.group(1)
            script = match_prefatory.group(2)
            label = match_prefatory.group(3)
            passage = {
                'ref': ref,
                'passage_type': 'prefatory',
                'label': {script: label},
                'content': parse_sanskrit_content(body_content)
            }
            if passage['content']:
                data['prefatory_material'].append(passage)

        elif match_concluding:
            ref = match_concluding.group(1)
            script = match_concluding.group(2)
            label = match_concluding.group(3)
            passage = {
                'ref': ref,
                'passage_type': 'concluding',
                'label': {script: label},
                'content': parse_sanskrit_content(body_content)
            }
            if passage['content']:
                data['concluding_material'].append(passage)

        elif match_structure:
            key = match_structure.group(1)
            ref = match_structure.group(2)
            if key.lower() == lowest_level_key.lower():
                passage = {
                    'ref': ref,
                    'passage_type': 'main',
                    'content': parse_sanskrit_content(body_content)
                }
                if passage['content']:
                    data['passages'].append(passage)

    data['commentaries'] = [c for c in data['commentaries'].values() if c['passages']]
    return data
import json

from .hasher import hash_grantha


def markdown_file_to_json_file(input_path: str, output_path: str) -> None:
    """Reads a Markdown file, converts it to JSON, and writes to a file.

    This function also performs a validation check. It recalculates the hash of
    the generated JSON based on the parameters in the original Markdown's
    frontmatter and compares it to the `validation_hash` stored there.

    Args:
        input_path: The path to the input Markdown file.
        output_path: The path to the output JSON file.

    Raises:
        ValueError: If the validation hash check fails.
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    frontmatter, _ = parse_frontmatter(markdown_content)
    json_data = convert_to_json(markdown_content)

    # Verify hash version
    file_version = frontmatter.get('hash_version', None)
    if file_version is None:
        raise ValueError(
            f"Hash version missing. File has no hash_version field.\n"
            f"This is a legacy/unversioned file. Current version: {HASH_VERSION}\n"
            f"Please run: grantha-converter update-hash -i \"{input_path}\""
        )

    if file_version != HASH_VERSION:
        raise ValueError(
            f"Hash version mismatch.\n"
            f"File version: {file_version}\n"
            f"Current version: {HASH_VERSION}\n"
            f"The hashing algorithm has changed since this file was generated.\n"
            f"Please run: grantha-converter update-hash -i \"{input_path}\""
        )

    # Verify integrity
    scripts = frontmatter.get('scripts', ['devanagari'])
    commentaries = frontmatter.get('commentaries')
    expected_hash = frontmatter.get('validation_hash', '').replace('sha256:', '')

    recalculated_hash = hash_grantha(json_data, scripts=scripts, commentaries=commentaries)

    if expected_hash and recalculated_hash != expected_hash:
        raise ValueError(
            f"Validation hash mismatch. Data may be corrupt.\n"
            f"Expected: {expected_hash}\n"
            f"Got:      {recalculated_hash}"
        )

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
