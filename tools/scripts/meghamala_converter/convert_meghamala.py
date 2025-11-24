#!/usr/bin/env python3
"""
Convert meghamala markdown to Grantha structured markdown using Gemini API.

Usage:
    python convert_meghamala.py \
        -i input.md \
        --output-dir ./output
"""

# Standard library imports
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

# Third-party imports
from colorama import init as colorama_init

# Local imports
from gemini_processor.client import GeminiClient
from gemini_processor.replay_client import ReplayGeminiClient
from gemini_processor.prompt_manager import PromptManager
from grantha_converter.meghamala_converter import MeghamalaConverter
from grantha_converter.utils import get_directory_parts
from grantha_converter.analyzer import Analyzer


# Constants
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"
SCRIPT_DIR = Path(__file__).parent
PROMPTS_DIR = SCRIPT_DIR / "prompts"
LOGS_DIR = Path("logs")
UPLOAD_CACHE_FILE = Path.cwd() / ".file_upload_cache.json"

# Global log directory for current run - created once per invocation
_run_log_dir: Path | None = None


# class Tee:
#     """A file-like object that tees output to a file and another stream."""

#     def __init__(self, stream, log_path: Path):
#         self.stream = stream
#         self.log_file = open(log_path, "w", encoding="utf-8")

#     def write(self, data):
#         self.stream.write(data)
#         self.log_file.write(data)
#         self.flush()

#     def flush(self):
#         self.stream.flush()
#         self.log_file.flush()

#     def __getattr__(self, name):
#         return getattr(self.stream, name)


def get_run_timestamp_dir() -> Path:
    """Generates a timestamped directory path for the current run without creating it."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return LOGS_DIR / f"run_{timestamp}"


def get_or_create_run_log_dir() -> Path:
    """Gets or creates a single run log directory for the entire invocation.

    This ensures that when converting multiple files (directory mode),
    all files log to the same timestamped run directory.
    """
    global _run_log_dir
    if _run_log_dir is None:
        _run_log_dir = get_run_timestamp_dir()
        _run_log_dir.mkdir(parents=True, exist_ok=True)
    return _run_log_dir


def get_file_log_dir(input_file_stem: str) -> Path:
    """Gets or creates the log directory for a specific file within the current run."""
    run_log_dir = get_or_create_run_log_dir()
    file_log_dir = run_log_dir / input_file_stem
    file_log_dir.mkdir(parents=True, exist_ok=True)
    return file_log_dir


def _parse_args(argv: Optional[List[str]] = None):
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert meghamala markdown to Grantha structured markdown using Gemini API.",
        epilog="""
Examples:
  # Single file, auto-named output in current directory
  %(prog)s -i input.md

  # Single file, explicit output file
  %(prog)s -i input.md -o output.md

  # Single file, output to specific directory
  %(prog)s -i input.md -o ./output/

  # Directory mode - converts all files, requires ID and title
  %(prog)s -i sources/upanishads/ -o output/ --grantha-id brihadaranyaka-upanishad --canonical-title "बृहदारण्यकोपनिषत्"

  # Using custom prompts
  %(prog)s -i input.md -o output.md --analysis-prompt my_analysis.txt --conversion-prompt my_conversion.txt
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Input file or directory containing meghamala markdown files"
    )

    parser.add_argument(
        "-o", "--output",
        help="Output file or directory (required if input is directory, optional for single file)"
    )

    parser.add_argument(
        "--grantha-id", help="Grantha identifier (required for directory mode)"
    )
    parser.add_argument(
        "--canonical-title",
        help="Canonical Devanagari title (required for directory mode)",
    )
    parser.add_argument("--commentary-id", help="Commentary identifier")
    parser.add_argument("--commentator", help="Commentator name in Devanagari")
    parser.add_argument(
        "--part-num", type=int, help="Part number (auto-detected if not specified)"
    )
    parser.add_argument(
        "--skip-validation", action="store_true", help="Skip Devanagari validation"
    )
    parser.add_argument(
        "--no-diff",
        action="store_true",
        help="Suppress diff output when validation fails (validation still runs)",
    )
    parser.add_argument(
        "--show-transliteration",
        action="store_true",
        help="Show Harvard-Kyoto transliteration diff",
    )
    parser.add_argument(
        "--force-analysis",
        action="store_true",
        help="Force re-analysis: clear cache, re-analyze file, and save new result",
    )
    parser.add_argument(
        "--no-upload-cache",
        action="store_true",
        help="Disable file upload caching (always upload fresh)",
    )
    parser.add_argument(
        "--clear-upload-cache",
        action="store_true",
        help="Clear expired entries (>48h old) from upload cache before starting",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable analysis caching",
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_GEMINI_MODEL,
        help=f"Gemini model to use for all phases (default: {DEFAULT_GEMINI_MODEL})",
    )
    parser.add_argument(
        "--analysis-model",
        help="Gemini model for file analysis phase (overrides --model)",
    )
    parser.add_argument(
        "--conversion-model",
        help="Gemini model for conversion phase (overrides --model)",
    )
    parser.add_argument(
        "--prompts-dir",
        type=Path,
        default=PROMPTS_DIR,
        help=f"Directory containing prompt templates (default: {PROMPTS_DIR})",
    )
    parser.add_argument(
        "--analysis-prompt",
        type=Path,
        help="Custom analysis prompt file (overrides default template)",
    )
    parser.add_argument(
        "--conversion-prompt",
        type=Path,
        help="Custom conversion prompt file (overrides default template)",
    )
    parser.add_argument(
        "--analysis-cache-dir",
        type=Path,
        default=Path.cwd() / ".analysis_cache",
        help="Directory to store analysis cache files (default: ./.analysis_cache)",
    )
    parser.add_argument(
        "--replay-from",
        type=Path,
        help="Replay from a log directory instead of calling the Gemini API.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the script without making any changes.",
    )
    return parser.parse_args(argv)

def _check_already_converted(output_dir: Path, input_file_stem: str, grantha_id: str) -> tuple[bool, str]:
    """Check if a file has already been converted successfully.

    Returns:
        Tuple of (is_converted, output_path_or_message)
    """
    # Try to find the output file
    # Format: grantha_id-commentary-part_num.md or similar
    pattern = f"{grantha_id}*{input_file_stem}*.md"
    matches = list(output_dir.glob(pattern))

    if not matches:
        # Try simpler pattern
        pattern = f"*{input_file_stem}*.md"
        matches = list(output_dir.glob(pattern))

    if matches:
        output_file = matches[0]
        if output_file.exists() and output_file.stat().st_size > 0:
            from datetime import datetime
            mtime = output_file.stat().st_mtime
            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            return True, f"{output_file.name} (written {mtime_str})"

    return False, ""

def _handle_directory_mode(args, client, prompt_manager: PromptManager, output_dir: Path, models: dict):
    """Handles the logic for converting all files in a directory."""
    input_dir = Path(args.input)
    parts = get_directory_parts(input_dir)
    if not parts:
        print(f"Error: No markdown files found in {input_dir}", file=sys.stderr)
        return 1

    # Create run log directory once for the entire directory conversion
    run_log_dir = get_or_create_run_log_dir()
    print(f"\n📁 Logging for this run to: {run_log_dir}")

    # Infer metadata from the first file if not provided via command line.
    # This is useful for multi-part works where the core metadata is consistent.
    if not args.grantha_id or not args.canonical_title:
        print("\n🔍 Inferring metadata from the first file...")
        first_file_path, _ = parts[0]
        analyzer = Analyzer(
            client=client,
            prompt_manager=prompt_manager,
            file_log_dir=get_file_log_dir(first_file_path.stem),
            use_cache=not args.no_cache,
            use_upload_cache=not args.no_upload_cache,
            force_reanalysis=args.force_analysis,
            analysis_cache_dir=args.analysis_cache_dir,
            custom_analysis_prompt=args.analysis_prompt,
        )
        analysis = analyzer.analyze(first_file_path, models["analysis"])
        if not analysis:
            print(f"❌ Error: Could not analyze {first_file_path.name} to infer metadata.", file=sys.stderr)
            return 1

        inferred_metadata = analysis.get("metadata", {})
        args.grantha_id = args.grantha_id or inferred_metadata.get("grantha_id")
        args.canonical_title = args.canonical_title or inferred_metadata.get("canonical_title")

        if not args.grantha_id or not args.canonical_title:
            print(f"❌ Error: Could not infer required metadata from {first_file_path.name}.", file=sys.stderr)
            return 1
        print(f"  ✓ Inferred grantha_id: {args.grantha_id}")
        print(f"  ✓ Inferred canonical_title: {args.canonical_title}")

    # Check for already-converted files
    already_converted = []
    remaining_parts = []

    for file_path, _ in parts:
        is_converted, info = _check_already_converted(output_dir, file_path.stem, args.grantha_id)
        if is_converted:
            already_converted.append((file_path.name, info))
        else:
            remaining_parts.append((file_path, _))

    # Show resume prompt if some files are already converted
    if already_converted:
        print(f"\n{'='*60}")
        print(f"📋 FOUND {len(already_converted)} ALREADY-CONVERTED FILE(S)")
        print(f"{'='*60}\n")
        for source_name, output_info in already_converted:
            print(f"  ✓ {source_name} → {output_info}")

        if remaining_parts:
            print(f"\n{len(remaining_parts)} file(s) remaining to convert:")
            for file_path, _ in remaining_parts[:5]:
                print(f"  • {file_path.name}")
            if len(remaining_parts) > 5:
                print(f"  • ... and {len(remaining_parts) - 5} more")

            print(f"\n{'='*60}")
            response = input("Skip already-converted files and resume? [Y/n]: ").strip().lower()
            if response and response not in ('y', 'yes'):
                print("Converting all files (including already-converted ones)...")
                parts_to_process = parts
            else:
                print(f"Resuming: will convert {len(remaining_parts)} remaining file(s)...")
                parts_to_process = remaining_parts
        else:
            print("\n✅ All files already converted!")
            return 0
    else:
        parts_to_process = parts

    failed_parts = []
    for file_path, _ in parts_to_process:
        file_log_dir = get_file_log_dir(file_path.stem)
        # Create a new converter for each file
        file_converter = MeghamalaConverter(
            client=client,
            prompt_manager=prompt_manager,
            args=args,
            models=models,
        )
        if not file_converter.convert_file(file_path, output_dir, file_log_dir):
            failed_parts.append(file_path.name)

    if failed_parts:
        print(f"\n{'='*60}")
        print(f"⚠️  Finished with {len(failed_parts)} failure(s):")
        for filename in failed_parts:
            print(f"  - {filename}")
        return 1

    print(f"\n{'='*60}")
    print(f"✅ All {len(parts_to_process)} parts converted successfully!")
    if already_converted and parts_to_process != parts:
        print(f"   ({len(already_converted)} file(s) were skipped as already converted)")
    print(f"Output directory: {output_dir}")
    return 0

def main(argv: Optional[List[str]] = None):
    """Main execution logic, designed to be callable for tests."""
    colorama_init(autoreset=True)
    # run_log_dir = get_run_log_dir()
    # sys.stdout = Tee(sys.stdout, run_log_dir / "stdout.log")
    # sys.stderr = Tee(sys.stderr, run_log_dir / "stderr.log")
    # print(f"📁 Logging to: {run_log_dir}")

    args = _parse_args(argv)

    # Validate input exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Error: Input path does not exist: {input_path}", file=sys.stderr)
        return 1

    # Determine if we're in file or directory mode
    is_directory_mode = input_path.is_dir()

    # Validate output argument based on mode
    if is_directory_mode:
        if not args.output:
            print("❌ Error: --output is required when input is a directory", file=sys.stderr)
            return 1
        output_path = Path(args.output)
    else:
        # Single file mode
        if args.output:
            output_path = Path(args.output)
            # If output ends with /, treat it as a directory
            if str(args.output).endswith('/') or output_path.is_dir():
                output_dir = output_path
                filename_override = None
            else:
                output_dir = output_path.parent if output_path.parent != Path('.') else Path.cwd()
                filename_override = output_path.name
        else:
            output_dir = Path.cwd()
            filename_override = None

    models = {
        "analysis": args.analysis_model or args.model,
        "conversion": args.conversion_model or args.model,
    }

    try:
        # Instantiate the appropriate client based on replay_from argument
        if args.replay_from:
            if is_directory_mode:
                print("❌ Error: --replay-from is not supported in directory mode", file=sys.stderr)
                return 1
            print(f"🔁 Replay mode: using logs from {args.replay_from}")
            client = ReplayGeminiClient(args.replay_from, input_path.stem)
        else:
            client = GeminiClient(upload_cache_file=UPLOAD_CACHE_FILE)
            print(f"📁 Upload Cache File: {UPLOAD_CACHE_FILE}")

            # Clean up expired cache entries if requested
            if args.clear_upload_cache:
                from gemini_processor.file_manager import FileUploadCache

                cache = FileUploadCache(UPLOAD_CACHE_FILE)
                removed_count = cache.cleanup_expired()
                if removed_count > 0:
                    print(f"🧹 Cleaned up {removed_count} expired upload cache entries")
                else:
                    print("✓ Upload cache is clean (no expired entries)")

        prompt_manager = PromptManager(args.prompts_dir)
        converter = MeghamalaConverter(client, prompt_manager, args, models)

        if is_directory_mode:
            # Directory mode
            output_dir = output_path
            output_dir.mkdir(parents=True, exist_ok=True)
            return _handle_directory_mode(args, client, prompt_manager, output_dir, models)
        else:
            # Single file mode
            output_dir.mkdir(parents=True, exist_ok=True)
            file_log_dir = get_file_log_dir(input_path.stem)
            print(f"📁 Logging for this file to: {file_log_dir}")
            success = converter.convert_file(
                input_path, output_dir, file_log_dir, filename_override=filename_override
            )
            return 0 if success else 1

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
