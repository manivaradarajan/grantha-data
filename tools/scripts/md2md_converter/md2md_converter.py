"""A command-line tool for processing and comparing Markdown files.

This script provides two main functionalities:
1.  **Convert**: Processes Markdown files using the Gemini API, applying a given prompt.
2.  **Diff**: Performs a Devanagari-only comparison between two Markdown files or all
    original/converted pairs within a directory, generating a detailed report.

It leverages the `grantha_converter.hasher` module for text normalization and integrity
verification.
"""

import os
import sys
import re
import difflib
import argparse
from typing import Tuple
from google import genai
from google.genai import types
from grantha_converter.hasher import normalize_text

# --- Configuration ---
MODEL_NAME = "gemini-1.5-pro-latest"

# --- Optional Dependency: Colorama for colored diff output ---
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    print("Colorama not found. Diff will not be colored. For a better experience, run: pip install colorama")
    class DummyColor:
        def __getattr__(self, name): return ""
    Fore = Style = DummyColor()


def configure_api():
    """Configures the Gemini API with the key from environment variables."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    client = genai.Client(api_key=api_key)
    print("Gemini API configured successfully.")
    return client


def read_file_content(filepath: str) -> str:
    """Reads the entire content of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found at '{filepath}'", file=sys.stderr)
        sys.exit(1)


def call_gemini_api(client, prompt: str, input_text: str) -> str:
    """Sends the combined prompt and input text to the Gemini API."""
    print(f"Initializing Gemini model: {MODEL_NAME}...")
    full_prompt = f"{prompt}\n\n--- START OF INPUT FILE ---\n\n{input_text}"
    print("Sending request to Gemini API. This may take a moment...")
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=full_prompt
        )
        print("Received response from API.")
        if not response.text:
             print("Warning: Received an empty or blocked response from the API.")
             return ""
        return response.text
    except Exception as e:
        print(f"An error occurred while calling the Gemini API: {e}", file=sys.stderr)
        return ""


def write_output_file(filepath: str, content: str):
    """Writes the given content to a file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Output successfully saved to '{filepath}'")


class IndexMapper:
    """Creates a mapping from normalized string indices to original string indices."""
    def __init__(self, original_text: str):
        self.map = []
        devanagari_pattern = re.compile(r'[\u0900-\u097F]')
        for i, char in enumerate(original_text):
            if devanagari_pattern.match(char):
                self.map.append(i)

    def get_original_index(self, normalized_index: int) -> int:
        """Gets the index in the original text corresponding to an index in the normalized text."""
        if 0 <= normalized_index < len(self.map):
            return self.map[normalized_index]
        return -1


def colorize_diff_chunks(original_chunk: str, generated_chunk: str) -> Tuple[str, str]:
    """Performs a character-by-character diff and adds ANSI color codes."""
    matcher = difflib.SequenceMatcher(None, original_chunk, generated_chunk)
    highlighted_original, highlighted_generated = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            highlighted_original.append(original_chunk[i1:i2])
            highlighted_generated.append(generated_chunk[j1:j2])
        elif tag in ['replace', 'delete']:
            highlighted_original.append(f"{Fore.RED}{Style.BRIGHT}{original_chunk[i1:i2]}{Style.RESET_ALL}")
        if tag in ['replace', 'insert']:
            highlighted_generated.append(f"{Fore.GREEN}{Style.BRIGHT}{generated_chunk[j1:j2]}{Style.RESET_ALL}")
    return "".join(highlighted_original), "".join(highlighted_generated)


def generate_diff_report(norm_original: str, norm_generated: str, original_text: str, generated_text: str) -> str:
    """Creates a human-readable, contextual diff report."""
    report_lines = [f"\n{Style.BRIGHT}--- Detailed Devanagari Diff Report ---{Style.NORMAL}"]
    added_chars, deleted_chars, has_changes = 0, 0, False
    original_mapper = IndexMapper(original_text)
    matcher = difflib.SequenceMatcher(None, norm_original, norm_generated, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        has_changes = True
        original_chunk, generated_chunk = norm_original[i1:i2], norm_generated[j1:j2]
        
        # Context Highlighting
        original_start_index = original_mapper.get_original_index(i1)
        if original_start_index != -1:
            line_start = original_text.rfind('\n', 0, original_start_index) + 1
            line_end = original_text.find('\n', original_start_index)
            line_end = line_end if line_end != -1 else len(original_text)
            line_number = original_text.count('\n', 0, line_start) + 1
            report_lines.append(f"\n{Style.DIM}Original context (line ~{line_number}):{Style.NORMAL}")
            report_lines.append(f"  {original_text[line_start:line_end].strip()}")

        # Diff Chunk Reporting
        h_orig, h_gen = colorize_diff_chunks(original_chunk, generated_chunk)
        if tag == 'replace':
            deleted_chars += len(original_chunk)
            added_chars += len(generated_chunk)
            report_lines.extend([f"- Original : {h_orig}", f"+ Generated: {h_gen}"])
        elif tag == 'delete':
            deleted_chars += len(original_chunk)
            report_lines.append(f"- Deleted  : {h_orig}")
        elif tag == 'insert':
            added_chars += len(generated_chunk)
            report_lines.append(f"+ Inserted : {h_gen}")

    if has_changes:
        summary = f"\n{Style.BRIGHT}--- Summary ---{Style.NORMAL}\n" \
                  f"{Fore.GREEN}Total characters added: {added_chars}{Style.RESET_ALL}\n" \
                  f"{Fore.RED}Total characters deleted: {deleted_chars}{Style.RESET_ALL}"
        report_lines.append(summary)
    return "\n".join(report_lines)


def verify_devanagari_integrity(original_file: str, generated_file: str, log_filepath: str) -> bool:
    """Verifies that the Devanagari content has not been altered and writes a log."""
    print("--- Starting Verification ---")
    log_lines = [f"Verification log for {original_file}"]
    original_text, generated_text = read_file_content(original_file), read_file_content(generated_file)
    norm_original = normalize_text("".join(re.findall(r'[\u0900-\u097F]+', original_text)))
    norm_generated = normalize_text("".join(re.findall(r'[\u0900-\u097F]+', generated_text)))

    if norm_original == norm_generated:
        status_message = "✅ SUCCESS: Devanagari content integrity verified."
        result = True
    else:
        status_message = f"{Fore.RED}{Style.BRIGHT}❌ FAILURE: Devanagari content was altered."
        result = False
        diff_report = generate_diff_report(norm_original, norm_generated, original_text, generated_text)
        log_lines.append(diff_report)
        print(diff_report)

    print(status_message)
    log_lines.append(status_message)
    with open(log_filepath, 'w', encoding='utf-8') as f:
        f.write("\n".join(log_lines))
    print(f"Verification log saved to '{log_filepath}'")
    return result

def extract_devanagari_from_file(filepath: str, ignore_header: bool) -> Tuple[str, str]:
    """Reads a file and extracts its normalized Devanagari content."""
    full_content = read_file_content(filepath)
    content_to_process = full_content
    if ignore_header:
        header_pattern = r'^(?:---|"++)\\s*\\n.*\\n(?:---|"++)\\s*\\n'
        content_to_process = re.sub(header_pattern, '', full_content, flags=re.DOTALL)
    devanagari_text = "".join(re.findall(r'[\u0900-\u097F]+', content_to_process))
    return normalize_text(devanagari_text), content_to_process


def perform_diff(file1: str, file2: str, ignore_header: bool):
    """Performs a Devanagari-only diff between two files and prints a report."""
    print(f"\n{Style.BRIGHT}--- Comparing Devanagari content ---{Style.NORMAL}")
    print(f"  File 1: {file1}\n  File 2: {file2}")
    if ignore_header:
        print(f"  {Style.DIM}(Ignoring YAML frontmatter){Style.NORMAL}")

    norm1, original_content1 = extract_devanagari_from_file(file1, ignore_header)
    norm2, original_content2 = extract_devanagari_from_file(file2, ignore_header)

    if norm1 == norm2:
        print(f"{Fore.GREEN}✅ No differences in normalized Devanagari content found.{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}⚠️ Differences found in normalized Devanagari content:{Style.RESET_ALL}")
        diff_report = generate_diff_report(norm1, norm2, original_content1, original_content2)
        print(diff_report)


def main():
    """Main function to run the conversion and verification process from the command line."""
    parser = argparse.ArgumentParser(
        description="A tool to process and compare Markdown files with a focus on Devanagari script integrity.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Examples:
  # Convert a file using the Gemini API
  python %(prog)s convert -p my_prompt.txt input.md

  # Convert multiple files
  python %(prog)s convert input1.md input2.md

  # Compare the Devanagari content of two specific files
  python %(prog)s diff file1.md file2.md

  # Scan a directory and compare all original/converted pairs (e.g., a.md vs a.converted.md)
  python %(prog)s diff ./my_directory/
"""
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Convert Command ---
    parser_convert = subparsers.add_parser("convert", help="Process Markdown files using the Gemini API.", description="Takes one or more Markdown files, applies a prompt, and saves the output from the Gemini API to a new '.converted.md' file. It then verifies the integrity of the Devanagari script.")
    parser_convert.add_argument("-p", "--prompt", default="prompt.txt", help="Path to the prompt file. Defaults to 'prompt.txt' in the same directory.")
    parser_convert.add_argument("input_files", metavar="FILE", nargs='+', help="One or more Markdown files to process.")

    # --- Diff Command ---
    parser_diff = subparsers.add_parser("diff", help="Perform a Devanagari-only diff on file pairs.", description="Compares the normalized Devanagari content between files. It can operate in two modes: comparing two specified files, or scanning a directory for pairs of original and converted files (e.g., 'file.md' and 'file.converted.md').")
    parser_diff.add_argument("paths", metavar="PATH", nargs='+', help="Either a single directory to scan for pairs, or two individual files to compare.")
    parser_diff.add_argument("--no-header", action="store_true", help="Ignore the YAML frontmatter (between '---' or '+++') in the diff.")

    args = parser.parse_args()

    if args.command == "convert":
        client = configure_api()
        prompt_content = read_file_content(args.prompt)
        for input_file in args.input_files:
            print(f"\n--- Processing file: {input_file} ---")
            base, _ = os.path.splitext(input_file)
            output_file = f"{base}.converted.md"
            input_content = read_file_content(input_file)
            api_response = call_gemini_api(client, prompt_content, input_content)
            if not api_response:
                print(f"Process for {input_file} halted due to empty API response.")
                continue
            write_output_file(output_file, api_response)
            log_file = f"{base}.conversion.log"
            verify_devanagari_integrity(input_file, output_file, log_file)

    elif args.command == "diff":
        if len(args.paths) == 1 and os.path.isdir(args.paths[0]):
            directory = args.paths[0]
            print(f"Scanning directory '{directory}' for file pairs...")
            for filename in sorted(os.listdir(directory)):
                if filename.endswith(".md") and not filename.endswith(".converted.md"):
                    original_path = os.path.join(directory, filename)
                    base, _ = os.path.splitext(original_path)
                    converted_path = f"{base}.converted.md"
                    if os.path.exists(converted_path):
                        perform_diff(original_path, converted_path, args.no_header)
        elif len(args.paths) == 2 and all(os.path.isfile(p) for p in args.paths):
            perform_diff(args.paths[0], args.paths[1], args.no_header)
        else:
            print("ERROR for 'diff' command: Please provide either a single directory or exactly two files.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
