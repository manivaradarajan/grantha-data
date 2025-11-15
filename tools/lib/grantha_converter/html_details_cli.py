"""Command-line interface for HTML details to Grantha Markdown converter."""

import argparse
import sys
from pathlib import Path

from .html_details_to_grantha_md import convert_file
from .grantha_markdown_validator import validate_markdown_file


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Convert Vishvas-style markup (HTML details) to structured Grantha Markdown format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic conversion
  vishvas-markup-to-structured-markdown \\
    -i sources/upanishads/isavasya/isa-vedantadesika/isavasya-vedantadesika.md \\
    -o output.md \\
    --grantha-id isavasya-upanishad \\
    --canonical-title "ईशावास्योपनिषत्" \\
    --commentary-id isavasya-vedantadesika \\
    --commentator "वेङ्कटनाथः"

  # With custom structure
  vishvas-markup-to-structured-markdown \\
    -i input.md \\
    -o output.md \\
    --grantha-id bhagavad-gita \\
    --canonical-title "भगवद्गीता" \\
    --commentary-id ramanuja \\
    --structure-key Shloka \\
    --structure-name "श्लोकः"

  # Skip validation
  vishvas-markup-to-structured-markdown -i input.md -o output.md ... --no-validate
        """
    )

    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Path to input HTML details-based Markdown file'
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Path for output Grantha Markdown file'
    )
    parser.add_argument(
        '--grantha-id',
        required=True,
        help='Grantha identifier (e.g., isavasya-upanishad)'
    )
    parser.add_argument(
        '--canonical-title',
        required=True,
        help='Canonical title in Devanagari (e.g., ईशावास्योपनिषत्)'
    )
    parser.add_argument(
        '--commentary-id',
        required=True,
        help='Commentary identifier (e.g., isavasya-vedantadesika)'
    )
    parser.add_argument(
        '--commentator',
        help='Commentator name in Devanagari (extracted from frontmatter if not provided)'
    )
    parser.add_argument(
        '--commentary-title',
        help='Commentary title (defaults to canonical-title if not provided)'
    )
    parser.add_argument(
        '--structure-key',
        default='Mantra',
        help='Structure level key (default: Mantra)'
    )
    parser.add_argument(
        '--structure-name',
        default='मन्त्रः',
        help='Structure level name in Devanagari (default: मन्त्रः)'
    )
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip validation after conversion'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Create output directory if needed
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if args.verbose:
            print(f"Converting {input_path} to Grantha Markdown format...")
            print(f"  Grantha ID: {args.grantha_id}")
            print(f"  Canonical title: {args.canonical_title}")
            print(f"  Commentary ID: {args.commentary_id}")
            print(f"  Structure: {args.structure_key} ({args.structure_name})")

        # Perform conversion
        convert_file(
            input_path=str(input_path),
            output_path=str(output_path),
            grantha_id=args.grantha_id,
            canonical_title=args.canonical_title,
            commentary_id=args.commentary_id,
            commentator=args.commentator,
            commentary_title=args.commentary_title,
            structure_key=args.structure_key,
            structure_name_devanagari=args.structure_name
        )

        print(f"✓ Successfully converted to {output_path}")

        # Validate if requested
        if not args.no_validate:
            if args.verbose:
                print("\nValidating output...")

            try:
                errors = validate_markdown_file(str(output_path))
                if errors:
                    print(f"✗ Validation failed with {len(errors)} error(s):", file=sys.stderr)
                    for error in errors:
                        print(f"  - {error}", file=sys.stderr)
                    sys.exit(1)
                else:
                    print("✓ Validation passed")
            except Exception as e:
                print(f"✗ Validation error: {e}", file=sys.stderr)
                sys.exit(1)

    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
