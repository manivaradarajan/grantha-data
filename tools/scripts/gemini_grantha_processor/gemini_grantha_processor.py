#!/usr/bin/env python3
"""Gemini-based Grantha Markdown processor with Devanagari integrity verification.

This script processes Grantha Markdown files using Google's Gemini API while
ensuring that all Devanagari content is preserved exactly.
"""

import argparse
import os
import sys
import re
from pathlib import Path
from typing import Tuple

from google import genai

# Add tools/lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

from grantha_converter.hasher import normalize_text
from grantha_converter.grantha_markdown_validator import validate_markdown_file


# Default prompt for bolding key terms in commentary
DEFAULT_PROMPT = """You are an expert Sanskrit scholar and a meticulous data architect specializing in digital humanities. Your task is to analyze a provided text as described. You are strictly instructed to not modify a single character of devanagari. This is very important. No input character must be modified.

Bolding: Within commentary_text, find direct quotes or key terms from the text and make them bold using double asterisks (**word**).

IMPORTANT RULES:
1. ONLY modify text within commentary sections (between <!-- commentary: ... --> and the next heading)
2. DO NOT modify mantra/passage text
3. DO NOT modify YAML frontmatter
4. DO NOT modify HTML comments
5. Preserve ALL Devanagari characters exactly as they appear - DO NOT MODIFY A SINGLE DEVANAGARI CHARACTER
6. Only add bold formatting using **word** syntax
7. Output the COMPLETE file with all sections intact

Process this Grantha Markdown file:"""


def configure_gemini_api():
    """Configure Gemini API with key from environment."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY environment variable not set.", file=sys.stderr)
        print("Set it with: export GOOGLE_API_KEY='your-api-key'", file=sys.stderr)
        sys.exit(1)
    client = genai.Client(api_key=api_key)
    print("✓ Gemini API configured")
    return client


def read_file(filepath: str) -> str:
    """Read file content."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR reading file: {e}", file=sys.stderr)
        sys.exit(1)


def write_file(filepath: str, content: str):
    """Write content to file."""
    try:
        # Create parent directory if needed
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✓ Output saved to {filepath}")
    except Exception as e:
        print(f"ERROR writing file: {e}", file=sys.stderr)
        sys.exit(1)


def call_gemini(client, prompt: str, content: str, model_name: str = "gemini-2.5-pro") -> str:
    """Call Gemini API to process the content."""
    print(f"Calling Gemini API ({model_name})...")

    try:
        full_prompt = (
            f"{prompt}\n\n---START OF FILE---\n\n{content}\n\n---END OF FILE---"
        )

        response = client.models.generate_content(
            model=model_name,
            contents=full_prompt
        )

        if not response.text:
            print("WARNING: Empty or blocked response from API", file=sys.stderr)
            return ""

        result = response.text
        print(f"✓ Received response ({len(result)} chars)")
        return result

    except Exception as e:
        print(f"ERROR calling Gemini API: {e}", file=sys.stderr)
        sys.exit(1)


def extract_devanagari(text: str) -> str:
    """Extract all Devanagari characters from text."""
    devanagari_pattern = re.compile(r"[\u0900-\u097F]+")
    return "".join(devanagari_pattern.findall(text))


def verify_devanagari_integrity(original: str, processed: str) -> Tuple[bool, dict]:
    """Verify that Devanagari content was preserved.

    Returns:
        Tuple of (is_valid, stats_dict)
    """
    # Extract Devanagari characters
    original_devanagari = extract_devanagari(original)
    processed_devanagari = extract_devanagari(processed)

    # Normalize for comparison
    norm_original = normalize_text(original_devanagari)
    norm_processed = normalize_text(processed_devanagari)

    is_valid = norm_original == norm_processed

    stats = {
        "original_chars": len(original_devanagari),
        "processed_chars": len(processed_devanagari),
        "original_normalized": len(norm_original),
        "processed_normalized": len(norm_processed),
        "match": is_valid,
    }

    return is_valid, stats


def clean_gemini_output(text: str) -> str:
    """Clean Gemini output by removing markdown code fences if present."""
    # Remove markdown code fences that Gemini sometimes adds
    text = re.sub(r"^```(?:markdown)?\s*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n```\s*$", "", text, flags=re.MULTILINE)

    # Remove ---START OF FILE--- and ---END OF FILE--- if present
    text = re.sub(r"^---START OF FILE---\s*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n---END OF FILE---\s*$", "", text, flags=re.MULTILINE)

    return text.strip()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process Grantha Markdown files using Gemini API with Devanagari integrity verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process with default prompt (bold key terms in commentary)
  python %(prog)s -i input.md -o output.md

  # Use custom prompt from file
  python %(prog)s -i input.md -o output.md --prompt-file custom_prompt.txt

  # Use custom prompt text
  python %(prog)s -i input.md -o output.md --prompt "Your custom prompt here"

  # Skip validation
  python %(prog)s -i input.md -o output.md --no-validate

  # Use specific Gemini model
  python %(prog)s -i input.md -o output.md --model gemini-1.5-flash-latest
        """,
    )

    parser.add_argument(
        "-i", "--input", required=True, help="Path to input Grantha Markdown file"
    )
    parser.add_argument("-o", "--output", required=True, help="Path for output file")
    parser.add_argument(
        "--prompt", help="Custom prompt text (overrides --prompt-file and default)"
    )
    parser.add_argument(
        "--prompt-file",
        help="Path to file containing custom prompt (overrides default)",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-pro",
        help="Gemini model to use (default: gemini-2.5-pro)",
    )
    parser.add_argument(
        "--no-validate", action="store_true", help="Skip Grantha Markdown validation"
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip Devanagari integrity verification (not recommended)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Configure API
    client = configure_gemini_api()

    # Determine prompt to use
    if args.prompt:
        prompt = args.prompt
        if args.verbose:
            print(f"Using custom prompt from command line")
    elif args.prompt_file:
        prompt = read_file(args.prompt_file)
        if args.verbose:
            print(f"Using prompt from {args.prompt_file}")
    else:
        prompt = DEFAULT_PROMPT
        if args.verbose:
            print("Using default prompt (bold key terms in commentary)")

    # Read input file
    if args.verbose:
        print(f"Reading input file: {args.input}")
    original_content = read_file(args.input)

    # Call Gemini
    processed_content = call_gemini(client, prompt, original_content, args.model)

    if not processed_content:
        print("ERROR: No output received from Gemini", file=sys.stderr)
        sys.exit(1)

    # Clean output
    processed_content = clean_gemini_output(processed_content)

    # Verify Devanagari integrity
    if not args.no_verify:
        print("\nVerifying Devanagari integrity...")
        is_valid, stats = verify_devanagari_integrity(
            original_content, processed_content
        )

        if args.verbose:
            print(f"  Original Devanagari chars: {stats['original_chars']}")
            print(f"  Processed Devanagari chars: {stats['processed_chars']}")
            print(f"  Original normalized: {stats['original_normalized']}")
            print(f"  Processed normalized: {stats['processed_normalized']}")

        if is_valid:
            print("✓ Devanagari integrity verified - content preserved exactly")
        else:
            print("✗ DEVANAGARI MISMATCH DETECTED!", file=sys.stderr)
            print(
                f"  Expected {stats['original_normalized']} normalized chars",
                file=sys.stderr,
            )
            print(
                f"  Got {stats['processed_normalized']} normalized chars",
                file=sys.stderr,
            )
            print(
                f"  Difference: {abs(stats['original_normalized'] - stats['processed_normalized'])} chars",
                file=sys.stderr,
            )

            # Still save the file but warn the user
            print(
                "\nWARNING: Saving output despite mismatch. Review carefully!",
                file=sys.stderr,
            )

    # Write output
    write_file(args.output, processed_content)

    # Validate output
    if not args.no_validate:
        print("\nValidating output against Grantha Markdown spec...")
        errors = validate_markdown_file(args.output)

        if errors:
            print(f"✗ Validation failed with {len(errors)} error(s):", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            sys.exit(1)
        else:
            print("✓ Validation passed")

    print(f"\n✓ Processing complete: {args.output}")


if __name__ == "__main__":
    main()
