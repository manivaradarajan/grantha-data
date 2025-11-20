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
import os
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

# Global log directory for current run
_run_log_dir: Path | None = None


class Tee:
    """A file-like object that tees output to a file and another stream."""

    def __init__(self, stream, log_path: Path):
        self.stream = stream
        self.log_file = open(log_path, "w", encoding="utf-8")

    def write(self, data):
        self.stream.write(data)
        self.log_file.write(data)
        self.flush()

    def flush(self):
        self.stream.flush()
        self.log_file.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def get_run_log_dir() -> Path:
    """Gets or creates the main log directory for the current run."""
    global _run_log_dir
    if _run_log_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _run_log_dir = LOGS_DIR / f"run_{timestamp}"
        _run_log_dir.mkdir(parents=True, exist_ok=True)
    return _run_log_dir


def get_file_log_dir(input_file_stem: str) -> Path:
    """Gets or creates the log directory for a specific file within the current run."""
    run_log_dir = get_run_log_dir()
    file_log_dir = run_log_dir / input_file_stem
    file_log_dir.mkdir(parents=True, exist_ok=True)
    return file_log_dir


def _parse_args(argv: Optional[List[str]] = None):
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert meghamala markdown to Grantha structured markdown using Gemini API.",
        epilog="""
Examples:
  # Single file, auto-named output
  %(prog)s -i input.md --output-dir ./out

  # Single file, explicit output name
  %(prog)s -i input.md -o my_custom_name.md

  # Directory mode - converts all files, requires ID and title
  %(prog)s -d sources/upanishads/ -o output/ --grantha-id brihadaranyaka-upanishad --canonical-title "बृहदारण्यकोपनिषत्"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-i", "--input", help="Input meghamala markdown file")
    input_group.add_argument(
        "-d", "--directory", help="Input directory containing multiple parts"
    )

    parser.add_argument(
        "-o", "--output", help="Explicit output filename (overrides auto-naming)"
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to save output files (default: current dir)",
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

def _handle_directory_mode(args, client, prompt_manager: PromptManager, output_dir: Path, models: dict):
    """Handles the logic for converting all files in a directory."""
    input_dir = Path(args.directory)
    parts = get_directory_parts(input_dir)
    if not parts:
        print(f"Error: No markdown files found in {input_dir}", file=sys.stderr)
        return 1

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

    failed_parts = []
    for file_path, _ in parts:
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
    print(f"✅ All {len(parts)} parts converted successfully!")
    print(f"Output directory: {output_dir}")
    return 0

def run_main(argv: Optional[List[str]] = None):
    """Main execution logic, designed to be callable for tests."""
    colorama_init(autoreset=True)
    run_log_dir = get_run_log_dir()
    sys.stdout = Tee(sys.stdout, run_log_dir / "stdout.log")
    sys.stderr = Tee(sys.stderr, run_log_dir / "stderr.log")
    print(f"📁 Logging to: {run_log_dir}")

    args = _parse_args(argv)

    models = {
        "analysis": args.analysis_model or args.model,
        "conversion": args.conversion_model or args.model,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Instantiate the appropriate client based on replay_from argument
        if args.replay_from:
            input_file_stem = Path(args.input).stem if args.input else None
            if not input_file_stem:
                print("❌ Error: --replay-from requires a single input file (-i)", file=sys.stderr)
                return 1
            print(f"🔁 Replay mode: using logs from {args.replay_from}")
            client = ReplayGeminiClient(args.replay_from, input_file_stem)
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

        if args.input:
            input_path = Path(args.input)
            file_log_dir = get_file_log_dir(input_path.stem)
            success = converter.convert_file(
                input_path, output_dir, file_log_dir, filename_override=args.output
            )
            return 0 if success else 1
        else:
            return _handle_directory_mode(args, client, prompt_manager, output_dir, models)

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run_main())
