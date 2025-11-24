"""Hides editor comments in Markdown files.

This script provides functionality to find Markdown files and wrap square-bracketed
comments (that are not Markdown links) within `<!-- hide -->...<!-- /hide -->` tags.
It is designed to be idempotent, meaning it will not re-wrap already hidden comments.
"""

import argparse
import os
import re
import sys
from typing import List, Tuple


def find_converted_md_files(directory: str) -> List[str]:
    """Finds all files ending with 'converted.md' in a directory.

    Args:
        directory: The path to the directory to search.

    Returns:
        A list of absolute paths to the found files.
    """
    matches = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith('converted.md'):
                matches.append(os.path.join(root, filename))
    return matches


def extract_devanagari(text: str) -> str:
    """Extracts all Devanagari characters from a string.

    Args:
        text: The input string.

    Returns:
        A string containing only the Devanagari characters from the input.
    """
    return "".join(re.findall(r'[\u0900-\u097F]', text))

def hide_editor_comments(file_path: str) -> Tuple[str, str]:
    """Hides editor comments in square brackets with HTML comment tags.

    This function reads a file and wraps any text enclosed in square brackets
    (e.g., `[some comment]`) with `<!-- hide -->` and `<!-- /hide -->`. It is
    idempotent and will not modify comments that are already hidden. It also
    ignores standard Markdown links like `[text](url)`.

    Args:
        file_path: The path to the file to process.

    Returns:
        A tuple containing the original and modified content of the.
        If no changes are made, both strings will be identical.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        original_content = f.read()

    modified_content = original_content

    # Regex to find a square bracket block (potentially escaped) that is NOT a markdown link.
    bracket_pattern = r'(\\*\[[^\]]+?\])(?!\()'

    hidden_block_pattern = r'<!-- hide -->.*?<!-- /hide -->'
    hidden_spans = [m.span() for m in re.finditer(hidden_block_pattern, modified_content, re.DOTALL)]

    matches = list(re.finditer(bracket_pattern, modified_content))

    for match in reversed(matches):
        is_already_hidden = False
        for start, end in hidden_spans:
            if start <= match.start() and end >= match.end():
                is_already_hidden = True
                break

        if not is_already_hidden:
            start, end = match.span()
            replacement = f'<!-- hide -->{match.group(0)}<!-- /hide -->'
            modified_content = modified_content[:start] + replacement + modified_content[end:]

    return original_content, modified_content


def validate_devanagari(original_content: str, modified_content: str) -> bool:
    """Validates that no Devanagari characters were altered during processing.

    Args:
        original_content: The original file content.
        modified_content: The content after hiding comments.

    Returns:
        True if the Devanagari text is identical, False otherwise.
    """
    original_devanagari = extract_devanagari(original_content)
    modified_devanagari = extract_devanagari(modified_content)
    return original_devanagari == modified_devanagari


def main():
    """Main function to process files and validate changes from the command line."""
    parser = argparse.ArgumentParser(description="Hide editor comments in specified Markdown files.")
    parser.add_argument("files", nargs='+', help="One or more files or directories to process.")
    args = parser.parse_args()

    files_to_process = []
    for path in args.files:
        if os.path.isdir(path):
            files_to_process.extend(find_converted_md_files(path))
        elif os.path.isfile(path):
            files_to_process.append(path)

    if not files_to_process:
        print("No files found to process.")
        return

    print(f"Processing {len(files_to_process)} file(s).")

    for file_path in files_to_process:
        if not os.path.exists(file_path):
            print(f"  Skipping '{file_path}' (not found).")
            continue

        print(f"Processing '{file_path}'...")
        try:
            original_content, modified_content = hide_editor_comments(file_path)

            if original_content == modified_content:
                print("  No changes made.")
                continue

            if not validate_devanagari(original_content, modified_content):
                print(f"  Validation failed for '{file_path}'. Aborting.", file=sys.stderr)
                return

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            print("  Changes written successfully.")

        except Exception as e:
            print(f"  An error occurred: {e}", file=sys.stderr)

    print("\nProcessing complete.")


if __name__ == '__main__':
    main()
