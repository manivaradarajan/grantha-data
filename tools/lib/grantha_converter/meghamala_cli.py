"""
CLI for converting meghamala markdown to Grantha structured markdown.

Usage:
    meghamala-md-to-structured-md -i input.md -o output.md \\
        --grantha-id kena-upanishad \\
        --canonical-title "केनोपनिषत्" \\
        --commentary-id kena-rangaramanuja \\
        --commentator "रङ्गरामानुजः"
"""

import argparse
import sys
from pathlib import Path

from grantha_converter.devanagari_validator import (
    get_devanagari_stats,
    validate_devanagari_preservation,
)
from grantha_converter.meghamala_converter import (
    MalformedMantraError,
    MeghamalaParser,
    convert_meghamala_to_grantha,
)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert meghamala markdown to Grantha structured markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic conversion with metadata
  meghamala-md-to-structured-md \\
      -i sources/upanishads/meghamala/kena/kenopaniSat.md \\
      -o kena-structured.md \\
      --grantha-id kena-upanishad \\
      --canonical-title "केनोपनिषत्"

  # With commentary metadata
  meghamala-md-to-structured-md \\
      -i input.md -o output.md \\
      --grantha-id kena-upanishad \\
      --canonical-title "केनोपनिषत्" \\
      --commentary-id kena-rangaramanuja \\
      --commentator "रङ्गरामानुजमुनिः"

  # Keep bold markup
  meghamala-md-to-structured-md \\
      -i input.md -o output.md \\
      --grantha-id isavasya-upanishad \\
      --canonical-title "ईशावास्योपनिषत्" \\
      --keep-bold

  # Multi-part text (part 3)
  meghamala-md-to-structured-md \\
      -i brihadaranyaka-3.md -o output.md \\
      --grantha-id brihadaranyaka-upanishad \\
      --canonical-title "बृहदारण्यकोपनिषत्" \\
      --part-num 3
        """
    )

    # Required arguments
    parser.add_argument('-i', '--input', required=True, help='Input meghamala markdown file')
    parser.add_argument('-o', '--output', required=True, help='Output structured markdown file')

    # Metadata arguments
    parser.add_argument('--grantha-id', required=True,
                        help='Grantha identifier (e.g., "kena-upanishad")')
    parser.add_argument('--canonical-title',
                        help='Canonical Devanagari title (e.g., "केनोपनिषत्"). '
                             'If not provided, will attempt to extract from file.')

    # Commentary metadata (optional)
    parser.add_argument('--commentary-id',
                        help='Commentary identifier (e.g., "kena-rangaramanuja")')
    parser.add_argument('--commentator',
                        help='Commentator name in Devanagari (e.g., "रङ्गरामानुजमुनिः"). '
                             'If not provided, will attempt to extract from file.')

    # Options
    parser.add_argument('--part-num', type=int, default=1,
                        help='Part number for multi-part texts (default: 1)')
    parser.add_argument('--keep-bold', action='store_true',
                        help='Keep bold (**) markup in output (default: remove)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output')
    parser.add_argument('--skip-validation', action='store_true',
                        help='Skip Devanagari validation (not recommended)')

    args = parser.parse_args()

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    # Read input file
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            meghamala_content = f.read()
    except Exception as e:
        print(f"❌ Error reading input file: {e}", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"📖 Reading: {args.input}")
        stats = get_devanagari_stats(meghamala_content)
        print(f"   Devanagari characters: {stats['total_chars']}")
        print(f"   Unique characters: {stats['unique_chars']}")

    # Extract metadata if not provided
    canonical_title = args.canonical_title
    commentator = args.commentator

    if not canonical_title or not commentator:
        if args.verbose:
            print("🔍 Extracting metadata from file...")

        parser_obj = MeghamalaParser(meghamala_content)
        parser_obj.parse()

        if not canonical_title and parser_obj.title:
            canonical_title = parser_obj.title
            if args.verbose:
                print(f"   Extracted title: {canonical_title}")

        if not commentator and parser_obj.commentator:
            commentator = parser_obj.commentator
            if args.verbose:
                print(f"   Extracted commentator: {commentator}")

    # Validate required metadata
    if not canonical_title:
        print("❌ Error: --canonical-title is required and could not be auto-extracted",
              file=sys.stderr)
        print("   Please provide it via command line argument", file=sys.stderr)
        return 1

    # Convert
    if args.verbose:
        print(f"⚙️  Converting to Grantha markdown...")
        print(f"   Grantha ID: {args.grantha_id}")
        print(f"   Canonical title: {canonical_title}")
        if args.commentary_id:
            print(f"   Commentary ID: {args.commentary_id}")
        if commentator:
            print(f"   Commentator: {commentator}")
        print(f"   Part number: {args.part_num}")
        print(f"   Remove bold: {not args.keep_bold}")

    try:
        grantha_content = convert_meghamala_to_grantha(
            meghamala_content=meghamala_content,
            grantha_id=args.grantha_id,
            canonical_title=canonical_title,
            commentary_id=args.commentary_id,
            commentator=commentator,
            part_num=args.part_num,
            remove_bold=not args.keep_bold
        )
    except MalformedMantraError as e:
        # Display the formatted error message
        print(str(e), file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Error during conversion: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    # Validate Devanagari preservation
    if not args.skip_validation:
        if args.verbose:
            print("✓ Validating Devanagari preservation...")

        # Skip frontmatter for validation (it contains metadata not in source)
        frontmatter_end = grantha_content.find("---\n\n", 4)
        if frontmatter_end > 0:
            grantha_body = grantha_content[frontmatter_end + 5:]  # Skip "---\n\n"
        else:
            grantha_body = grantha_content

        is_valid, error_msg = validate_devanagari_preservation(
            meghamala_content,
            grantha_body
        )

        if not is_valid:
            print(error_msg, file=sys.stderr)
            return 1

        if args.verbose:
            print("   ✓ All Devanagari text preserved")
            output_stats = get_devanagari_stats(grantha_body)
            print(f"   Output Devanagari characters: {output_stats['total_chars']}")

    # Write output file
    try:
        output_path = Path(args.output)
        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(grantha_content)
    except Exception as e:
        print(f"❌ Error writing output file: {e}", file=sys.stderr)
        return 1

    # Success
    if args.verbose:
        print(f"✅ Success! Output written to: {args.output}")
    else:
        print(f"✅ Converted {args.input} → {args.output}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
