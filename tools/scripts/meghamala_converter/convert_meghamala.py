#!/usr/bin/env python3
"""
Convert meghamala markdown to Grantha structured markdown using Gemini API.

Usage:
    python convert_meghamala.py \
        -i input.md \
        -o output.md \
        --grantha-id kena-upanishad \
        --canonical-title "केनोपनिषत्" \
        --commentary-id kena-rangaramanuja \
        --commentator "रङ्गरामानुजमुनिः"
"""

# Standard library imports
import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Third-party imports
import yaml
from google import genai
from google.genai import types

try:
    from colorama import Back, Fore, Style
    from colorama import init as colorama_init

    colorama_init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    # Fallback if colorama not installed
    COLORAMA_AVAILABLE = False

    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ""

    class Back:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ""

    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""

# Local imports
from gemini_processor.cache_manager import AnalysisCache
from gemini_processor.prompt_manager import PromptManager
from gemini_processor.sampler import create_smart_sample
from grantha_converter.devanagari_repair import extract_devanagari, repair_file
from grantha_converter.devanagari_validator import validate_devanagari_preservation
from grantha_converter.diff_utils import show_devanagari_diff, show_transliteration_diff
from grantha_converter.hasher import hash_text
from grantha_converter.meghamala_chunker import (
    estimate_chunk_count,
    should_chunk,
    split_at_boundaries,
)
from grantha_converter.meghamala_stitcher import (
    cleanup_temp_chunks,
    merge_chunks,
    validate_merged_output,
)

# Constants
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash-exp"

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
PROMPTS_DIR = SCRIPT_DIR / "prompts"
LOGS_DIR = Path("logs")  # Save logs in current working directory
UPLOAD_CACHE_FILE = SCRIPT_DIR / ".file_upload_cache.json"

# Initialize prompt manager
prompt_manager = PromptManager(PROMPTS_DIR)

# Global log directory for current run
_current_log_dir = None
_current_file_subdir = None


def create_log_directory(file_subdir: str = None) -> Path:
    """Create a timestamped log directory for this run.

    Args:
        file_subdir: Optional subdirectory for multi-file runs (e.g., "part-01")

    Returns:
        Path to the created log directory
    """
    global _current_log_dir, _current_file_subdir

    # Update file subdirectory if provided
    if file_subdir is not None:
        _current_file_subdir = file_subdir

    # Create base run directory if it doesn't exist
    if _current_log_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _current_log_dir = LOGS_DIR / f"run_{timestamp}"
        _current_log_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Logging to: {_current_log_dir}")

    # Return file-specific subdirectory if set, otherwise base directory
    if _current_file_subdir:
        file_log_dir = _current_log_dir / _current_file_subdir
        file_log_dir.mkdir(parents=True, exist_ok=True)
        return file_log_dir
    else:
        return _current_log_dir


def save_to_log(filename: str, content: str, subdir: str = None):
    """Save content to a log file in the current run's log directory.

    Args:
        filename: Name of the file to save
        content: Content to write
        subdir: Optional subdirectory within the log directory
    """
    log_dir = create_log_directory()

    if subdir:
        save_dir = log_dir / subdir
        save_dir.mkdir(parents=True, exist_ok=True)
    else:
        save_dir = log_dir

    file_path = save_dir / filename

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  💾 Saved: {file_path.relative_to(LOGS_DIR)}")
    except Exception as e:
        print(f"  ⚠️  Warning: Could not save log file {filename}: {e}", file=sys.stderr)


def load_upload_cache() -> dict:
    """Load the file upload cache from disk.

    Returns:
        Dict mapping file_hash -> upload info
    """
    if not UPLOAD_CACHE_FILE.exists():
        return {}

    try:
        with open(UPLOAD_CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Warning: Could not load upload cache: {e}", file=sys.stderr)
        return {}


def save_upload_cache(cache: dict):
    """Save the file upload cache to disk.

    Args:
        cache: Dict mapping file_hash -> upload info
    """
    try:
        with open(UPLOAD_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"⚠️  Warning: Could not save upload cache: {e}", file=sys.stderr)


def get_cached_upload(client: genai.Client, file_path: str, file_hash: str):
    """Check if we have a valid cached upload for this file.

    Args:
        client: Gemini client to verify file still exists
        file_path: Path to the file
        file_hash: SHA256 hash of the file

    Returns:
        Gemini File object if valid, None otherwise
    """
    cache = load_upload_cache()
    cache_key = f"{file_path}:{file_hash}"

    if cache_key not in cache:
        return None

    cached_info = cache[cache_key]
    file_name = cached_info.get("name")

    # Verify the file still exists in Gemini and return the File object
    try:
        file_info = client.files.get(name=file_name)
        if file_info.state == "ACTIVE":
            print(f"✓ Using cached upload: {file_name}")
            print(f"  Uploaded: {cached_info.get('uploaded_at')}")
            return file_info  # Return the actual File object
        else:
            print(
                f"⚠️  Cached file not active (state: {file_info.state}), will re-upload"
            )
            return None
    except Exception as e:
        print(f"⚠️  Cached file not found in Gemini, will re-upload")
        return None


def cache_upload(file_path: str, file_hash: str, uploaded_file) -> None:
    """Cache information about an uploaded file.

    Args:
        file_path: Path to the file
        file_hash: SHA256 hash of the file
        uploaded_file: The uploaded file object from Gemini
    """
    cache = load_upload_cache()
    cache_key = f"{file_path}:{file_hash}"

    cache[cache_key] = {
        "name": uploaded_file.name,
        "uri": uploaded_file.uri,
        "display_name": uploaded_file.display_name,
        "size_bytes": uploaded_file.size_bytes,
        "uploaded_at": datetime.now().isoformat(),
        "file_path": str(file_path),
        "file_hash": file_hash,
    }

    save_upload_cache(cache)
    print(f"  💾 Cached upload info")




def repair_json_escapes(text: str) -> str:
    """Attempt to repair common JSON escape sequence issues.

    Gemini sometimes returns regex patterns with single backslashes which are
    invalid in JSON. This function attempts to fix those issues.

    Args:
        text: The JSON text that may have escape issues

    Returns:
        Repaired JSON text
    """
    # Find all strings that look like regex patterns in the JSON
    # Pattern: "regex": "..." where ... contains backslashes
    regex_pattern = r'"regex":\s*"([^"]*)"'

    def fix_regex(match):
        regex_value = match.group(1)
        # Double all single backslashes that aren't already doubled
        # This is tricky because we need to handle:
        # \* -> \\*
        # \\ -> \\ (already correct)
        # \S -> \\S
        fixed = regex_value.replace("\\", "\\\\")
        # But if they were already doubled, we just quadrupled them, so fix that
        fixed = fixed.replace("\\\\\\\\", "\\\\")
        return f'"regex": "{fixed}"'

    repaired = re.sub(regex_pattern, fix_regex, text)
    return repaired




def analyze_file_structure(
    input_file: str,
    verbose: bool = False,
    use_cache: bool = True,
    use_upload_cache: bool = True,
    force_reanalysis: bool = False,
    model: str = DEFAULT_GEMINI_MODEL,
) -> dict:
    """Analyze file structure to extract metadata and splitting instructions.

    Sends full file (or smart sample for >500KB files) to Gemini for comprehensive
    analysis. Returns metadata (grantha_id, canonical_title, etc.) and detailed
    splitting instructions (regex patterns, handling rules).

    Uses caching to avoid redundant API calls when analyzing the same file multiple times.

    Args:
        input_file: Path to input meghamala markdown file
        verbose: Print detailed progress and error messages
        use_cache: If True, try to load from cache and save new analysis to cache
        use_upload_cache: If True, cache file uploads to Gemini to save bandwidth
        force_reanalysis: If True, clear existing cache and force new analysis (still saves to cache)

    Returns:
        Dict with structure:
        {
            "metadata": {
                "canonical_title": "...",
                "grantha_id": "...",
                "commentary_id": "...",
                "commentator": "...",
                "structure_type": "..."
            },
            "splitting_instructions": {
                "recommended_unit": "...",
                "justification": "...",
                "start_pattern": {...},
                "end_pattern": {...},
                "pre_content_handling": "...",
                "final_unit_handling": "..."
            }
        }

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If GEMINI_API_KEY not set or response is invalid
    """
    print("🔍 Analyzing file structure...")

    # Clear cache if force_reanalysis is requested
    cache = AnalysisCache(input_file)
    if force_reanalysis:
        cache.clear(verbose=verbose)
        print("📡 Forcing re-analysis - will call Gemini API and update cache")

    # Try to load from cache first (unless force_reanalysis)
    if use_cache and not force_reanalysis:
        cached_analysis = cache.load(verbose=verbose)
        if cached_analysis is not None:
            # Cache hit - return cached result
            print("🚀 Skipping Gemini API call (using cached analysis)")
            return cached_analysis
        else:
            print("📡 Cache miss - will call Gemini API")
    elif not use_cache:
        print("📡 Cache disabled - calling Gemini API (will not save)")

    # Configure API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "Error: GEMINI_API_KEY environment variable not set\n"
            "  Please set the GEMINI_API_KEY environment variable to your API key."
        )

    # Read file and check size
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            full_text = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: Input file not found: {input_file}")
    except Exception as e:
        print(f"Error reading input file {input_file}:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        raise

    file_size = len(full_text)
    print(f"📊 File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")

    # Create Gemini client early for file upload
    client = genai.Client(api_key=api_key)

    # Get file hash for caching
    file_hash = get_file_hash(input_file)

    # Check if we have a cached upload (if caching is enabled)
    uploaded_file = None
    was_cached = False

    if use_upload_cache:
        print(f"📤 Checking for cached file upload...")
        uploaded_file = get_cached_upload(client, input_file, file_hash)
        was_cached = uploaded_file is not None
    else:
        print(f"📤 Upload caching disabled")

    if not uploaded_file:
        # Upload file to Gemini File API
        print(f"📤 Uploading file to Gemini File API...")
        try:
            with open(input_file, "rb") as f:
                uploaded_file = client.files.upload(
                    file=f,
                    config={
                        "display_name": Path(input_file).name,
                        "mime_type": "text/markdown",
                    },
                )
            print(f"✓ File uploaded: {uploaded_file.name}")
            print(f"  URI: {uploaded_file.uri}")

            # Cache the upload (if caching is enabled)
            if use_upload_cache:
                cache_upload(input_file, file_hash, uploaded_file)

        except Exception as e:
            print(f"⚠️  File upload failed: {e}", file=sys.stderr)
            print(f"   Falling back to text embedding...", file=sys.stderr)
            traceback.print_exc()

    # Save upload info to log
    if uploaded_file:
        save_to_log(
            "00_uploaded_file_info.txt",
            f"File name: {uploaded_file.name}\n"
            f"Display name: {uploaded_file.display_name}\n"
            f"Size: {uploaded_file.size_bytes} bytes\n"
            f"State: {uploaded_file.state}\n"
            f"URI: {uploaded_file.uri}\n"
            f"Cached: {'Yes' if was_cached else 'No'}\n",
            subdir="analysis",
        )

    # Load prompt template
    template = prompt_manager.load_template("full_file_analysis_prompt.txt")
    print(f"  📄 Using prompt: full_file_analysis_prompt.txt")

    if uploaded_file:
        # Use File API - prompt doesn't need the actual content embedded
        analysis_prompt = template.replace(
            "\n--- INPUT TEXT ---\n{input_text}\n--- END INPUT TEXT ---",
            "\n\n[File content provided via Gemini File API - see uploaded file]",
        )
        print(f"📄 Using File API for analysis (efficient mode)")
    else:
        # Fallback: Apply smart sampling and embed in text
        analysis_text, was_sampled = create_smart_sample(full_text, max_size=500000)

        if was_sampled:
            sample_size = len(analysis_text)
            print(
                f"✂️ File too large ({file_size / 1024:.1f} KB) - using smart sampling"
            )
            print(f"  📖 Sample: first 100KB + middle 50KB + last 50KB")
            print(
                f"  📊 Sample size: {sample_size:,} bytes ({sample_size / 1024:.1f} KB)"
            )
        else:
            print(f"📄 Using text embedding for analysis")

        analysis_prompt = template.format(input_text=analysis_text)

    # Save prompt to log
    save_to_log("01_analysis_prompt.txt", analysis_prompt, subdir="analysis")

    if verbose:
        print(f"📝 Prompt size: {len(analysis_prompt):,} characters")

    print("🤖 Calling Gemini API for structural analysis...")

    # Configure API call
    config = types.GenerateContentConfig(
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )

    # Call Gemini API with file reference or text
    if uploaded_file:
        # Use File API - provide both prompt and file
        response = client.models.generate_content(
            model=model,
            contents=[analysis_prompt, uploaded_file],
            config=config,
        )
    else:
        # Fallback to text embedding
        response = client.models.generate_content(
            model=model, contents=analysis_prompt, config=config
        )

    # Note: We don't delete cached files - Gemini automatically cleans up files after 48 hours
    # Our cache verification will detect expired files and re-upload as needed

    if not response.text:
        raise ValueError("Empty response from Gemini API during file analysis")

    response_text = response.text.strip()
    print(f"📝 Gemini response received ({len(response_text)} chars)")

    # Save raw response to log
    save_to_log("02_analysis_response_raw.txt", response_text, subdir="analysis")

    # Parse JSON response
    try:
        # Remove markdown code fences if present
        cleaned_text = response_text
        if response_text.startswith("```"):
            print("🧹 Removing markdown code fences...")
            lines = response_text.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            cleaned_text = "\n".join(json_lines)
            print(f"✓ Cleaned text: {len(cleaned_text)} chars")

        print("🔍 Parsing JSON response...")
        try:
            analysis_result = json.loads(cleaned_text)
            print("✓ JSON parsed successfully")
        except json.JSONDecodeError as first_error:
            # First parse failed - try repairing escape sequences
            print(f"⚠️  Initial JSON parse failed: {first_error}")
            print(f"🔧 Attempting to repair JSON escape sequences...")

            repaired_text = repair_json_escapes(cleaned_text)

            # Try parsing the repaired version
            try:
                analysis_result = json.loads(repaired_text)
                print("✓ JSON parsed successfully after repair!")
            except json.JSONDecodeError as e:
                # Even repair didn't work - raise detailed error
                print(
                    f"\n❌ Error: Could not parse JSON even after repair:",
                    file=sys.stderr,
                )
                print(f"  {type(e).__name__}: {e}", file=sys.stderr)
                print(f"  Error at line {e.lineno}, column {e.colno}", file=sys.stderr)
                raise  # Re-raise to trigger the outer exception handler

    except json.JSONDecodeError as e:
        print(
            f"\n❌ Error: Could not parse JSON from Gemini response:", file=sys.stderr
        )
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        print(f"  Error at line {e.lineno}, column {e.colno}", file=sys.stderr)

        # Show context around the error
        lines = cleaned_text.split("\n")
        if e.lineno and 1 <= e.lineno <= len(lines):
            print(f"\n  Context around error (line {e.lineno}):", file=sys.stderr)
            start = max(0, e.lineno - 3)
            end = min(len(lines), e.lineno + 2)
            for i in range(start, end):
                marker = ">>>" if i == e.lineno - 1 else "   "
                print(f"  {marker} {i+1:3d}: {lines[i]}", file=sys.stderr)
                if i == e.lineno - 1 and e.colno:
                    print(
                        f"       {' ' * (e.colno + 3)}^-- Error here", file=sys.stderr
                    )

        print(f"\n  First 500 chars of cleaned text:", file=sys.stderr)
        print(f"  {cleaned_text[:500]}", file=sys.stderr)

        if verbose:
            traceback.print_exc()

        raise ValueError(f"Invalid JSON response from Gemini: {e}")

    # Validate structure (support both old and new formats)
    if "metadata" not in analysis_result:
        raise ValueError("Missing 'metadata' section in analysis response")

    # Must have either new format (chunking_strategy) or old format (splitting_instructions)
    has_new_format = (
        "chunking_strategy" in analysis_result
        and "parsing_instructions" in analysis_result
    )
    has_old_format = "splitting_instructions" in analysis_result

    if not has_new_format and not has_old_format:
        raise ValueError(
            "Missing chunking information: need either 'chunking_strategy' (new) or 'splitting_instructions' (old)"
        )

    metadata = analysis_result.get("metadata", {})

    # Validate required metadata fields
    required_metadata = ["canonical_title", "grantha_id", "structure_type"]
    for field in required_metadata:
        if field not in metadata:
            print(f"Warning: Missing required metadata field: {field}", file=sys.stderr)

    # Support both old and new format
    chunking_strategy = analysis_result.get("chunking_strategy", {})
    parsing_instructions = analysis_result.get("parsing_instructions", {})
    splitting_instructions = analysis_result.get("splitting_instructions", {})

    # Validate required fields based on format
    if chunking_strategy:
        # New format validation
        if "execution_plan" not in chunking_strategy:
            print(
                f"Warning: Missing execution_plan in chunking_strategy", file=sys.stderr
            )
        if parsing_instructions and "recommended_unit" not in parsing_instructions:
            print(
                f"Warning: Missing recommended_unit in parsing_instructions",
                file=sys.stderr,
            )
    elif splitting_instructions:
        # Old format validation
        required_splitting = ["recommended_unit", "start_pattern", "end_pattern"]
        for field in required_splitting:
            if field not in splitting_instructions:
                print(
                    f"Warning: Missing required splitting instruction field: {field}",
                    file=sys.stderr,
                )

    print(f"✓ Analysis complete")
    print(f"  • Structure type: {metadata.get('structure_type', 'unknown')}")

    # Display chunking info based on format
    if chunking_strategy:
        execution_plan = chunking_strategy.get("execution_plan", [])
        print(f"  • Chunking: {len(execution_plan)} chunks planned")
        if parsing_instructions:
            print(
                f"  • Parsing unit: {parsing_instructions.get('recommended_unit', 'unknown')}"
            )
    elif splitting_instructions:
        print(
            f"  • Recommended unit: {splitting_instructions.get('recommended_unit', 'unknown')}"
        )
        if (
            "start_pattern" in splitting_instructions
            and "regex" in splitting_instructions["start_pattern"]
        ):
            print(
                f"  • Split pattern: {splitting_instructions['start_pattern']['regex']}"
            )

    # Save to cache for future runs
    if use_cache:
        cache.save(analysis_result, verbose=verbose)

    return analysis_result


def split_by_regex_pattern(
    text: str, splitting_instructions: dict, verbose: bool = False
) -> list[tuple[str, dict]]:
    """Split text using regex patterns from structural analysis.

    Uses the start_pattern.regex from splitting_instructions to identify
    unit boundaries and split the text accordingly. Handles pre-content
    and final unit as specified in the instructions.

    Args:
        text: The full text content to split
        splitting_instructions: Dict containing recommended_unit, start_pattern,
                               end_pattern, pre_content_handling, final_unit_handling
        verbose: Print detailed progress messages

    Returns:
        List of (chunk_text, metadata) tuples where metadata contains:
        - chunk_index: 0-based index
        - total_chunks: Total number of chunks
        - unit_name: Extracted unit name (e.g., "प्रथमः खण्डः")
        - boundary_type: Type of boundary (e.g., "khanda")
        - start_line: Approximate starting line number
    """
    start_pattern = splitting_instructions.get("start_pattern", {})
    regex_pattern = start_pattern.get("regex")

    if not regex_pattern:
        raise ValueError("Missing start_pattern.regex in splitting_instructions")

    recommended_unit = splitting_instructions.get("recommended_unit", "unit")

    print(f"✂️ Splitting file using pattern: {regex_pattern}")

    # Find all matches
    try:
        matches = list(re.finditer(regex_pattern, text, re.MULTILINE))
    except re.error as e:
        raise ValueError(f"Invalid regex pattern '{regex_pattern}': {e}")

    num_matches = len(matches)
    print(f"📍 Found {num_matches} split points")

    # Debug: if no matches found, try to help diagnose the issue
    if num_matches == 0:
        structure_type = splitting_instructions.get("recommended_unit", "").lower()

        # Try to find lines containing key structural markers
        if "khanda" in structure_type or "खण्ड" in regex_pattern:
            sample_lines = []
            for i, line in enumerate(text.split("\n"), 1):
                if "खण्डः" in line:
                    sample_lines.append(f"    Line {i}: {line[:100]}")
                    if len(sample_lines) >= 3:
                        break

            if sample_lines:
                print(
                    f"⚠️ No matches found for pattern, but found these lines with 'खण्डः':"
                )
                for sample in sample_lines:
                    print(sample)
                print(f"\n💡 Trying flexible fallback pattern...")

                # Try a more flexible pattern that matches the actual format:
                # **प्रथमः** **खण्डः** (two separate bold sections)
                fallback_pattern = r"^\*\*\S+\*\*\s+\*\*खण्डः\*\*$"
                try:
                    matches = list(re.finditer(fallback_pattern, text, re.MULTILINE))
                    num_matches = len(matches)
                    if num_matches > 0:
                        print(f"✓ Fallback pattern matched {num_matches} split points!")
                        regex_pattern = (
                            fallback_pattern  # Use fallback for rest of processing
                        )
                except re.error:
                    pass

        if num_matches == 0:
            print(f"⚠️ No split points found - treating entire file as single unit")
            return [
                (
                    text,
                    {
                        "chunk_index": 0,
                        "total_chunks": 1,
                        "unit_name": "Complete File",
                        "boundary_type": recommended_unit.lower(),
                        "start_line": 1,
                    },
                )
            ]

    # Build chunks
    chunks = []

    for i, match in enumerate(matches):
        # Determine chunk boundaries
        if i == 0:
            # First chunk: include pre-content (everything from start)
            chunk_start = 0
            start_line = 1
        else:
            # Subsequent chunks: start at previous match end
            chunk_start = matches[i - 1].start()
            start_line = text[:chunk_start].count("\n") + 1

        if i < num_matches - 1:
            # Not the last chunk: end at next match start
            chunk_end = matches[i + 1].start()
        else:
            # Last chunk: extend to EOF
            chunk_end = len(text)

        chunk_text = text[chunk_start:chunk_end]

        # Extract unit name from match
        unit_name = match.group(0).strip()
        # Remove bold markers if present
        unit_name = re.sub(r"\*\*", "", unit_name)

        chunk_metadata = {
            "chunk_index": i,
            "total_chunks": num_matches,
            "unit_name": unit_name,
            "boundary_type": recommended_unit.lower(),
            "start_line": start_line,
        }

        chunks.append((chunk_text, chunk_metadata))

        if verbose or i < 3 or i >= num_matches - 1:
            end_line = start_line + chunk_text.count("\n")
            chunk_size = len(chunk_text)
            print(
                f"  • Unit {i+1}: {unit_name} (lines {start_line}-{end_line}, {chunk_size:,} bytes)"
            )
        elif i == 3:
            print(f"  • ...")

    print(f"✓ Split into {len(chunks)} chunks")

    return chunks


def hide_editor_comments_in_content(content: str) -> tuple[str, str]:
    """Hides editor comments in square brackets with HTML comment tags.

    This function wraps any text enclosed in square brackets (e.g., `[some comment]`)
    with `<!-- hide -->` and `<!-- /hide -->`. It is idempotent and will not modify
    comments that are already hidden. It also ignores standard Markdown links like
    `[text](url)`.

    Args:
        content: The content to process.

    Returns:
        A tuple containing the original and modified content.
        If no changes are made, both strings will be identical.
    """
    original_content = content
    modified_content = content

    # Regex to find a square bracket block (potentially escaped) that is NOT a markdown link.
    bracket_pattern = r"(\\*\[[^\]]+?\])(?!\()"

    hidden_block_pattern = r"<!-- hide -->.*?<!-- /hide -->"
    hidden_spans = [
        m.span() for m in re.finditer(hidden_block_pattern, modified_content, re.DOTALL)
    ]

    matches = list(re.finditer(bracket_pattern, modified_content))

    for match in reversed(matches):
        is_already_hidden = False
        for start, end in hidden_spans:
            if start <= match.start() and end >= match.end():
                is_already_hidden = True
                break

        if not is_already_hidden:
            start, end = match.span()
            replacement = f"<!-- hide -->{match.group(0)}<!-- /hide -->"
            modified_content = (
                modified_content[:start] + replacement + modified_content[end:]
            )

    return original_content, modified_content


def validate_devanagari_unchanged(original_content: str, modified_content: str) -> bool:
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


def extract_part_number_from_filename(filename: str) -> int:
    """
    Extract part number from filename.

    Patterns supported:
    - 03-01.md → part 1 of section 3
    - part-3.md → part 3
    - brihadaranyaka-03.md → part 3
    - 01.md → part 1
    - name-tRtIya.md → part 3 (Sanskrit numbers)

    Args:
        filename: Name of the file (not full path)

    Returns:
        Part number, or 1 if not found
    """
    # Sanskrit number words to digits
    sanskrit_numbers = {
        "prathama": 1,
        "pratham": 1,
        "dvitiya": 2,
        "dvitiya": 2,
        "dviti": 2,
        "tritiya": 3,
        "trtiya": 3,
        "trtiya": 3,
        "caturtha": 4,
        "catur": 4,
        "pancama": 5,
        "panchama": 5,
        "pajcama": 5,
        "shashtha": 6,
        "sastho": 6,
        "sastha": 6,
        "saptama": 7,
        "astama": 8,
        "ashtama": 8,
        "astama": 8,
        "navama": 9,
        "dasama": 10,
    }

    # Remove .md extension
    name = filename.replace(".md", "").lower()

    # Pattern 1: XX-YY.md (e.g., 03-01.md) - use YY as part number
    match = re.search(r"(\d{2})-(\d{2})$", name)
    if match:
        return int(match.group(2))

    # Pattern 2: part-N or partN
    match = re.search(r"part[-_]?(\d+)$", name, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Pattern 3: Sanskrit number words (check longest matches first to avoid false positives)
    sorted_sanskrit = sorted(sanskrit_numbers.items(), key=lambda x: -len(x[0]))
    for sanskrit, number in sorted_sanskrit:
        if sanskrit.lower() in name:
            return number

    # Pattern 4: name-NN (e.g., brihadaranyaka-03)
    match = re.search(r"-(\d{2})$", name)
    if match:
        return int(match.group(1))

    # Pattern 5: just digits (e.g., 01.md)
    match = re.search(r"^(\d{2})$", name)
    if match:
        return int(match.group(1))

    # Default to part 1
    return 1


def get_directory_parts(directory: Path) -> list:
    """
    Get all markdown files in directory sorted by part number.

    Returns:
        List of tuples: (file_path, part_number)
    """
    md_files = []
    for file in directory.glob("*.md"):
        if file.name.upper() == "PROVENANCE.yaml":
            continue
        part_num = extract_part_number_from_filename(file.name)
        md_files.append((file, part_num))

    # Sort by part number
    md_files.sort(key=lambda x: x[1])
    return md_files


def create_conversion_prompt(
    input_text: str,
    grantha_id: str,
    canonical_title: str,
    commentary_id: str = None,
    commentator: str = None,
    part_num: int = 1,
) -> str:
    """Create the full conversion prompt for Gemini using external template.

    Args:
        input_text: The meghamala markdown text to convert
        grantha_id: Grantha identifier
        canonical_title: Canonical title in Devanagari
        commentary_id: Optional commentary identifier
        commentator: Optional commentator name
        part_num: Part number

    Returns:
        The formatted prompt ready to send to Gemini

    Raises:
        FileNotFoundError: If the prompt template file is missing
    """
    try:
        template = prompt_manager.load_template("conversion_prompt.txt")
        print(f"  📄 Using prompt: conversion_prompt.txt")
    except Exception as e:
        print(f"Error loading conversion prompt template: {e}", file=sys.stderr)
        raise

    # Build commentary metadata section
    commentary_metadata = ""
    if commentary_id:
        commentary_metadata += f"- Commentary ID: {commentary_id}\n"
    if commentator:
        commentary_metadata += f"- Commentator: {commentator}\n"

    # Build commentary frontmatter section
    commentaries_frontmatter = ""
    if commentary_id and commentator:
        commentaries_frontmatter = f"""commentaries_metadata:
- commentary_id: "{commentary_id}"
  commentator: "{commentator}"
  language: sanskrit
"""

    # Build commentary instructions section
    commentary_instructions = ""
    if commentary_id:
        commentary_instructions = f"""### CRITICAL: Commentary ID = "{commentary_id}"

ALL commentary blocks must use: <!-- commentary: {{"commentary_id": "{commentary_id}"}} -->

Format:
```markdown
<!-- commentary: {{"commentary_id": "{commentary_id}"}} -->
### Commentary: <ref>
<!-- sanskrit:devanagari -->
commentary text with **bold quotes**
<!-- /sanskrit:devanagari -->
```

"""

    # Build commentary example
    commentary_example = ""
    if commentary_id:
        commentary_example = f"""<!-- commentary: {{"commentary_id": "{commentary_id}"}} -->
### Commentary: 1.1
<!-- sanskrit:devanagari -->
commentary with **bold quotes** from mantra
<!-- /sanskrit:devanagari -->
"""

    # Format the template with all variables
    prompt = template.format(
        grantha_id=grantha_id,
        canonical_title=canonical_title,
        part_num=part_num,
        commentary_metadata=commentary_metadata,
        commentaries_frontmatter=commentaries_frontmatter,
        commentary_instructions=commentary_instructions,
        commentary_example=commentary_example,
        input_text=input_text,
    )

    return prompt


def infer_metadata_with_gemini(
    input_file: str, verbose: bool = False, model: str = DEFAULT_GEMINI_MODEL
) -> dict:
    """Infer metadata (grantha_id, canonical_title, etc.) using Gemini API.

    Sends the first portion of the file to Gemini to extract metadata.

    Args:
        input_file: Path to input meghamala markdown file
        verbose: Print inference details

    Returns:
        Dict with keys: grantha_id, canonical_title, commentary_id, commentator
        Returns empty dict on failure
    """

    # Configure API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        return {}

    # Read first portion of file (first 5000 chars should contain metadata)
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            excerpt = f.read(5000)
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Error reading input file {input_file}:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return {}

    if verbose:
        print(
            f"📖 Read {len(excerpt)} characters from input file for metadata inference"
        )

    # Load and create inference prompt using external template
    try:
        template = prompt_manager.load_template("metadata_inference_prompt.txt")
        print(f"  📄 Using prompt: metadata_inference_prompt.txt")
        inference_prompt = template.format(excerpt=excerpt)
    except Exception as e:
        print(f"Error loading metadata inference prompt template:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return {}

    if verbose:
        print("🤖 Calling Gemini API for metadata inference...")

    # Configure and call Gemini
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error creating Gemini client:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return {}

    # Disable safety filters - using dict format for compatibility
    config = types.GenerateContentConfig(
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )

    try:
        response = client.models.generate_content(
            model=model, contents=inference_prompt, config=config
        )

        # Check response
        if not response.text:
            print(
                "Error: Empty response from Gemini API during metadata inference",
                file=sys.stderr,
            )
            return {}

        # Get response text
        response_text = response.text.strip()

        if verbose:
            print(f"📝 Gemini response:\n{response_text}")

        # Parse JSON from response
        # Remove markdown code fences if present
        if response_text.startswith("```"):
            # Find the JSON content
            lines = response_text.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_json = not in_json
                    continue
                if in_json or (line.strip().startswith("{") or json_lines):
                    json_lines.append(line)
                    if line.strip().endswith("}"):
                        break
            response_text = "\n".join(json_lines)

        # Parse JSON
        metadata = json.loads(response_text)

        # Validate required fields
        required_fields = [
            "canonical_title",
            "grantha_id",
            "commentary_id",
            "commentator",
            "structure_type",
        ]
        for field in required_fields:
            if field not in metadata:
                print(
                    f"Warning: Missing field '{field}' in Gemini response",
                    file=sys.stderr,
                )
                metadata[field] = None

        # Convert "none" strings to None
        for key in metadata:
            if isinstance(metadata[key], str) and metadata[key].lower() == "none":
                metadata[key] = None

        if verbose:
            print(f"✓ Inferred metadata:")
            print(f"  canonical_title: {metadata.get('canonical_title')}")
            print(f"  grantha_id: {metadata.get('grantha_id')}")
            print(f"  commentary_id: {metadata.get('commentary_id')}")
            print(f"  commentator: {metadata.get('commentator')}")
            print(f"  structure_type: {metadata.get('structure_type')}")

        return metadata

    except json.JSONDecodeError as e:
        print(f"Error: Could not parse JSON from Gemini response:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            print(f"  Response was: {response_text[:500]}")
            traceback.print_exc()
        return {}
    except Exception as e:
        print(f"Error during Gemini API call for metadata inference:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return {}


def call_gemini_api(prompt: str, output_file: str, verbose: bool = False):
    """Call Gemini API with the conversion prompt.

    Args:
        prompt: The prompt to send to Gemini
        output_file: Where to write the response
        verbose: Print detailed error messages and stack traces

    Returns:
        True if successful, False otherwise
    """
    # Configure API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        print(
            "  Please set the GEMINI_API_KEY environment variable to your API key.",
            file=sys.stderr,
        )
        return False

    # Create Gemini client
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error: Failed to create Gemini client:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return False

    # Disable all safety filters for Sanskrit text processing - using dict format for compatibility
    config = types.GenerateContentConfig(
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )

    print("🤖 Calling Gemini API...")

    # Call the API
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest", contents=prompt, config=config
        )
    except Exception as e:
        print(f"Error: Gemini API call failed:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            print("  Stack trace:", file=sys.stderr)
            traceback.print_exc()
        return False

    # Try to get the text from response
    try:
        output = response.text
        if not output:
            print("Error: Empty response from Gemini API", file=sys.stderr)
            return False
    except AttributeError as e:
        print(f"Error: Response object has no 'text' attribute:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            print(f"  Response object: {response}", file=sys.stderr)
            traceback.print_exc()
        return False
    except Exception as e:
        print(f"Error: Could not extract text from Gemini response:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return False

    # Extract markdown from response (remove code fences if present)
    try:
        if output.startswith("```"):
            # Remove opening fence
            output = output[3:].strip()
            # Remove language identifier if present (e.g., "markdown", "yaml", "md")
            first_line_end = output.find("\n")
            if first_line_end > 0:
                first_line = output[:first_line_end].strip().lower()
                # Common language identifiers
                if first_line in ["markdown", "md", "yaml", "yml"]:
                    output = output[first_line_end + 1 :].strip()

        if output.endswith("```"):
            output = output[:-3].strip()
    except Exception as e:
        print(
            f"Warning: Error stripping code fences (continuing anyway):",
            file=sys.stderr,
        )
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()

    # Create parent directory if it doesn't exist
    try:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error: Could not create output directory:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return False

    # Write output
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)
    except Exception as e:
        print(f"Error: Could not write output file {output_file}:", file=sys.stderr)
        print(f"  {type(e).__name__}: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return False

    print(f"✓ Gemini response written to {output_file}")
    return True


def calculate_and_update_hash(output_file: str):
    """Calculate validation hash and update in frontmatter."""
    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract body (skip frontmatter)
    frontmatter_end = content.find("---\n\n", 4)
    if frontmatter_end == -1:
        print("Warning: Could not find end of frontmatter", file=sys.stderr)
        return False

    body = content[frontmatter_end + 5 :]

    # Calculate hash
    validation_hash = hash_text(body)

    # Replace placeholder
    content = content.replace(
        "validation_hash: TO_BE_CALCULATED", f"validation_hash: {validation_hash}"
    )

    # Write back
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✓ Validation hash calculated: {validation_hash[:16]}...")
    return True


def validate_output(input_file: str, output_file: str, show_diff: bool = True):
    """Validate Devanagari preservation.

    Args:
        input_file: Path to input file
        output_file: Path to output file
        show_diff: If True, show colored diff on validation failure
    """
    with open(input_file, "r", encoding="utf-8") as f:
        input_text = f.read()

    with open(output_file, "r", encoding="utf-8") as f:
        output_text = f.read()

    # Skip frontmatter in output
    frontmatter_end = output_text.find("---\n\n", 4)
    if frontmatter_end > 0:
        output_body = output_text[frontmatter_end + 5 :]
    else:
        output_body = output_text

    is_valid, error_msg = validate_devanagari_preservation(input_text, output_body)

    if is_valid:
        print("✓ Devanagari validation passed - no text loss")
        return True
    else:
        print("❌ Devanagari validation failed:", file=sys.stderr)
        print(error_msg, file=sys.stderr)

        # Show colored diff to help debug
        if show_diff:
            from grantha_converter.devanagari_repair import extract_devanagari

            input_dev = extract_devanagari(input_text)
            output_dev = extract_devanagari(output_body)
            show_devanagari_diff(input_dev, output_dev, max_diff_lines=30)

        return False


def convert_chunk(
    chunk_text: str,
    chunk_metadata: dict,
    output_file: str,
    grantha_id: str,
    canonical_title: str,
    commentary_id: str,
    commentator: str,
    part_num: int,
) -> bool:
    """Convert a single chunk using Gemini API.

    This is a simplified version of convert_single_file for chunk processing.
    No validation or repair - that happens after merging.

    Args:
        chunk_text: The chunk content to convert
        chunk_metadata: Metadata about the chunk (index, total, boundary_type, etc.)
        output_file: Where to write the converted chunk
        grantha_id: Grantha identifier
        canonical_title: Canonical title in Devanagari
        commentary_id: Commentary identifier (optional)
        commentator: Commentator name (optional)
        part_num: Part number

    Returns:
        True if successful, False otherwise
    """
    chunk_idx = chunk_metadata.get("chunk_index", 0)
    total_chunks = chunk_metadata.get("total_chunks", 1)
    boundary_type = chunk_metadata.get("boundary_type", "unknown")

    print(
        f"  📄 Processing chunk {chunk_idx + 1}/{total_chunks} ({boundary_type} boundary)"
    )

    # Create conversion prompt for this chunk
    # For chunks after the first, we add context about chunking
    if chunk_idx == 0:
        prompt = create_conversion_prompt(
            input_text=chunk_text,
            grantha_id=grantha_id,
            canonical_title=canonical_title,
            commentary_id=commentary_id,
            commentator=commentator,
            part_num=part_num,
        )
    else:
        # For subsequent chunks, add context
        prompt = create_conversion_prompt(
            input_text=chunk_text,
            grantha_id=grantha_id,
            canonical_title=canonical_title,
            commentary_id=commentary_id,
            commentator=commentator,
            part_num=part_num,
        )
        # Add a note about continuing from previous chunk
        continuation_note = f"""

NOTE: This is chunk {chunk_idx + 1} of {total_chunks}. This chunk continues from the previous chunk.
Maintain the same formatting and structure conventions as the previous chunk.
"""
        prompt += continuation_note

    # Call Gemini API
    if not call_gemini_api(prompt, output_file):
        return False

    print(f"  ✓ Chunk {chunk_idx + 1}/{total_chunks} converted")
    return True


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences from text."""
    # Remove ```yaml, ```markdown, ```md, ```yml, etc.
    text = re.sub(
        r"^```(?:yaml|markdown|md|yml|text)?\s*\n", "", text, flags=re.MULTILINE
    )
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def create_first_chunk_prompt(chunk_text: str, part_num: int) -> str:
    """Create prompt for first chunk that extracts metadata AND converts content.

    Args:
        chunk_text: The text of the first chunk
        part_num: Part number

    Returns:
        Formatted prompt that requests both metadata and converted markdown

    Raises:
        FileNotFoundError: If the prompt template file is missing
    """
    try:
        template = prompt_manager.load_template("first_chunk_prompt.txt")
        print(f"  📄 Using prompt: first_chunk_prompt.txt")
        return template.format(chunk_text=chunk_text)
    except Exception as e:
        print(f"Error loading first chunk prompt template: {e}", file=sys.stderr)
        raise


def parse_first_chunk_response(response_text: str) -> tuple[dict, str]:
    """Parse first chunk response into metadata dict and converted body.

    Returns:
        (metadata_dict, converted_body) or (None, None) if parsing fails
    """
    # Split by metadata separator
    if "---METADATA---" not in response_text:
        print(
            "Warning: No metadata separator found in first chunk response",
            file=sys.stderr,
        )
        return None, None

    parts = response_text.split("---METADATA---", 1)
    metadata_part = parts[0].strip()
    content_part = parts[1].strip() if len(parts) > 1 else ""

    # Strip code fences from content
    content_part = strip_code_fences(content_part)

    # Parse metadata JSON
    try:
        # Remove any markdown code fences around JSON
        metadata_part = re.sub(
            r"^```(?:json)?\s*\n", "", metadata_part, flags=re.MULTILINE
        )
        metadata_part = re.sub(r"\n```\s*$", "", metadata_part)
        metadata_part = metadata_part.strip()

        metadata = json.loads(metadata_part)
        return metadata, content_part
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse metadata JSON: {e}", file=sys.stderr)
        print(f"Metadata part: {metadata_part[:200]}...", file=sys.stderr)
        return None, None


def create_chunk_conversion_prompt(chunk_text: str) -> str:
    """Create simple conversion prompt for subsequent chunks (no metadata extraction).

    Args:
        chunk_text: The text of the chunk to convert

    Returns:
        Formatted prompt for chunk continuation

    Raises:
        FileNotFoundError: If the prompt template file is missing
    """
    try:
        # Load the chunk continuation template
        continuation_template = prompt_manager.load_template("chunk_continuation_prompt.txt")
        print(f"  📄 Using prompt: chunk_continuation_prompt.txt")

        # Format with the chunk text
        return continuation_template.format(chunk_text=chunk_text)
    except Exception as e:
        print(f"Error loading chunk continuation prompt template: {e}", file=sys.stderr)
        raise


def normalize_marker(text: str) -> str:
    """Normalize text by removing markdown formatting for marker matching.

    Removes bold (**), italic (*), and extra whitespace to allow flexible matching.
    """
    # Remove bold markers
    text = text.replace("**", "")
    # Remove italic markers (single asterisk, but not double)
    # Normalize multiple spaces to single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_by_execution_plan(
    text: str, execution_plan: list[dict], verbose: bool = False
) -> list[tuple[str, dict]]:
    """Split text using execution plan from structural analysis.

    Uses start_marker and end_marker from each chunk specification to
    identify chunk boundaries and split the text accordingly.

    Args:
        text: The full text content to split
        execution_plan: List of chunk specifications, each containing:
                       - chunk_id: Numeric identifier
                       - description: Human-readable description
                       - start_marker: Text pattern marking chunk start
                       - end_marker: Text pattern marking chunk end
        verbose: Print detailed progress messages

    Returns:
        List of (chunk_text, metadata) tuples where metadata contains:
        - chunk_index: 0-based index
        - chunk_id: ID from execution plan
        - total_chunks: Total number of chunks
        - description: Description from execution plan
        - start_line: Approximate starting line number
    """
    print(
        f"✂️ Splitting file using execution plan ({len(execution_plan)} chunks specified)"
    )

    chunks = []
    lines = text.split("\n")

    for i, chunk_spec in enumerate(execution_plan):
        chunk_id = chunk_spec.get("chunk_id", i + 1)
        description = chunk_spec.get("description", f"Chunk {chunk_id}")
        start_marker = chunk_spec.get("start_marker", "")
        end_marker = chunk_spec.get("end_marker", "")

        # Find start position
        if i == 0:
            # First chunk always starts from beginning (to include prefatory material)
            chunk_start = 0
            start_line = 1
            if verbose and start_marker:
                print(
                    f"  ℹ️  First chunk: ignoring start_marker, including content from beginning"
                )
        elif start_marker:
            # Find the line containing start_marker (normalize both for comparison)
            start_line_idx = None
            normalized_start_marker = normalize_marker(start_marker)
            for line_idx, line in enumerate(lines):
                if normalized_start_marker in normalize_marker(line):
                    start_line_idx = line_idx
                    break

            if start_line_idx is None:
                print(
                    f"  ⚠️  Warning: Could not find start_marker '{start_marker[:50]}...' for chunk {chunk_id}",
                    file=sys.stderr,
                )
                continue

            chunk_start = sum(
                len(l) + 1 for l in lines[:start_line_idx]
            )  # +1 for newline
            start_line = start_line_idx + 1
        else:
            # No start marker, start after previous chunk
            if chunks:
                # Start where the last chunk ended
                chunk_start = chunks[-1][1]["end_pos"]
                start_line = text[:chunk_start].count("\n") + 1
            else:
                chunk_start = 0
                start_line = 1

        # Find end position
        if i == len(execution_plan) - 1 and not end_marker:
            # Last chunk, no specific end marker - go to end of file
            chunk_end = len(text)
        elif end_marker:
            # Find the line containing end_marker (search AFTER start position, normalize for comparison)
            end_line_idx = None
            normalized_end_marker = normalize_marker(end_marker)
            for line_idx in range(start_line - 1, len(lines)):
                if normalized_end_marker in normalize_marker(lines[line_idx]):
                    end_line_idx = line_idx
                    break

            if end_line_idx is None:
                # If not found, go to end of file
                print(
                    f"  ⚠️  Warning: Could not find end_marker '{end_marker[:50]}...' for chunk {chunk_id}, using EOF",
                    file=sys.stderr,
                )
                chunk_end = len(text)
            else:
                # Include the line with the end marker
                chunk_end = sum(len(l) + 1 for l in lines[: end_line_idx + 1])
        else:
            # No end marker specified
            if i < len(execution_plan) - 1:
                # Not the last chunk - find start of next chunk
                next_start_marker = execution_plan[i + 1].get("start_marker", "")
                if next_start_marker:
                    # Find next chunk's start (normalize for comparison)
                    normalized_next_marker = normalize_marker(next_start_marker)
                    for line_idx in range(start_line - 1, len(lines)):
                        if normalized_next_marker in normalize_marker(lines[line_idx]):
                            # End just before the next chunk starts
                            chunk_end = sum(len(l) + 1 for l in lines[:line_idx])
                            break
                    else:
                        chunk_end = len(text)
                else:
                    chunk_end = len(text)
            else:
                chunk_end = len(text)

        chunk_text = text[chunk_start:chunk_end]

        chunk_metadata = {
            "chunk_index": i,
            "chunk_id": chunk_id,
            "total_chunks": len(execution_plan),
            "description": description,
            "start_line": start_line,
            "end_pos": chunk_end,
        }

        chunks.append((chunk_text, chunk_metadata))

        if verbose or i < 3 or i >= len(execution_plan) - 1:
            end_line = start_line + chunk_text.count("\n")
            chunk_size = len(chunk_text)
            print(
                f"  • Chunk {chunk_id}: {description[:50]} (lines {start_line}-{end_line}, {chunk_size:,} bytes)"
            )
        elif i == 3:
            print(f"  • ...")

    print(f"✓ Split into {len(chunks)} chunks")

    return chunks


def convert_with_regex_chunking(
    input_file: str,
    output_file: str,
    analysis_result: dict,
    skip_validation: bool = False,
    no_diff: bool = False,
    show_transliteration: bool = False,
    verbose: bool = False,
    model: str = DEFAULT_GEMINI_MODEL,
) -> bool:
    """Convert file using analysis-driven regex chunking.

    Uses metadata and splitting instructions from analyze_file_structure()
    to split and convert the file intelligently.

    Args:
        input_file: Path to input file
        output_file: Path to output file
        analysis_result: Dict from analyze_file_structure() containing
                        metadata and splitting_instructions
        skip_validation: Skip Devanagari validation
        no_diff: Suppress diff output when validation fails
        show_transliteration: Show Harvard-Kyoto transliteration diff
        verbose: Print detailed progress

    Returns:
        True if successful, False otherwise
    """
    metadata = analysis_result.get("metadata", {})

    # Support both old format (splitting_instructions) and new format (chunking_strategy + parsing_instructions)
    chunking_strategy = analysis_result.get("chunking_strategy", {})
    parsing_instructions = analysis_result.get("parsing_instructions", {})
    splitting_instructions = analysis_result.get(
        "splitting_instructions", {}
    )  # Backwards compatibility

    grantha_id = metadata.get("grantha_id", "unknown")
    canonical_title = metadata.get("canonical_title", "Unknown")
    commentary_id = metadata.get("commentary_id")
    commentator = metadata.get("commentator")
    structure_type = metadata.get("structure_type", "section")

    print(f"\n{'='*60}")
    print("📋 PHASE 2: SPLITTING FILE")
    print(f"{'='*60}\n")

    # Read input file
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return False

    # Split using execution plan (new format) or regex patterns (old format)
    try:
        execution_plan = chunking_strategy.get("execution_plan", [])
        if execution_plan:
            # New format: use execution plan
            print(f"Using execution plan from chunking_strategy")
            chunks = split_by_execution_plan(
                input_text, execution_plan, verbose=verbose
            )
        elif splitting_instructions:
            # Old format: use regex splitting
            print(f"Using regex patterns from splitting_instructions (legacy mode)")
            chunks = split_by_regex_pattern(
                input_text, splitting_instructions, verbose=verbose
            )
        else:
            raise ValueError("No chunking strategy found in analysis result")
    except Exception as e:
        print(f"Error splitting file: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return False

    total_chunks = len(chunks)

    # Validate chunk sizes against safety_character_limit
    proposed_strategy = chunking_strategy.get("proposed_strategy", {})
    safety_limit = proposed_strategy.get("safety_character_limit")

    if safety_limit:
        print(
            f"🔒 Validating chunk sizes against safety limit: {safety_limit:,} characters"
        )
        oversized_chunks = []
        for i, (chunk_text, chunk_metadata) in enumerate(chunks):
            chunk_size = len(chunk_text)
            if chunk_size > safety_limit:
                chunk_id = chunk_metadata.get("chunk_id", i + 1)
                description = chunk_metadata.get("description", f"Chunk {chunk_id}")
                oversized_chunks.append((chunk_id, description, chunk_size))

        if oversized_chunks:
            print(
                f"\n❌ ERROR: {len(oversized_chunks)} chunk(s) exceed safety limit:",
                file=sys.stderr,
            )
            for chunk_id, description, size in oversized_chunks:
                excess = size - safety_limit
                print(f"  • Chunk {chunk_id}: {description[:50]}", file=sys.stderr)
                print(
                    f"    Size: {size:,} characters (exceeds limit by {excess:,})",
                    file=sys.stderr,
                )
            print(
                f"\n💡 The analysis recommended a safety limit of {safety_limit:,} characters,",
                file=sys.stderr,
            )
            print(
                f"   but the execution plan created chunks larger than this.",
                file=sys.stderr,
            )
            print(
                f"   This may cause API errors or incomplete conversions.",
                file=sys.stderr,
            )
            return False

    print(f"\n{'='*60}")
    print(f"📋 PHASE 3: CONVERTING {total_chunks} CHUNKS")
    print(f"{'='*60}\n")

    # Initialize Gemini client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        return False

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"Error creating Gemini client: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return False

    config = types.GenerateContentConfig(
        temperature=0.1,
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    )

    # Convert each chunk sequentially with per-chunk validation
    converted_bodies = []
    start_time = time.time()
    cache_hits = 0

    # Track Devanagari counts for verification
    total_input_devanagari_chars = 0
    total_output_devanagari_chars = 0
    chunk_validations = []

    for chunk_text, chunk_metadata in chunks:
        chunk_num = chunk_metadata["chunk_index"] + 1
        # Support both old format (unit_name) and new format (description)
        unit_name = chunk_metadata.get("unit_name") or chunk_metadata.get(
            "description", f"Chunk {chunk_num}"
        )

        save_to_log(f"chunk_{chunk_num:03d}_input.md", chunk_text, subdir="chunks")

        print(f"🤖 Converting chunk {chunk_num}/{total_chunks}: {unit_name}")
        print(f"  📊 Chunk size: {len(chunk_text):,} bytes")

        # Extract Devanagari from input chunk for validation
        chunk_input_devanagari = extract_devanagari(chunk_text)
        chunk_input_count = len(chunk_input_devanagari)
        print(f"  📝 Input Devanagari: {chunk_input_count:,} characters")

        chunk_start = time.time()

        # --- Start of new File API and Caching Logic ---

        chunk_hash = hash_text(chunk_text)
        # Use a virtual path for the cache key to make it stable across runs
        virtual_path = f"chunk://{input_file}/{chunk_hash}"

        # Check for a cached file upload
        uploaded_file = get_cached_upload(client, virtual_path, chunk_hash)

        if uploaded_file:
            print(f"  📦 Using cached chunk upload from File API: {uploaded_file.name}")
            cache_hits += 1
        else:
            print(f"  📤 Uploading chunk {chunk_num} to Gemini File API...")
            uploaded_file = None
            temp_file_path = None
            try:
                # Write chunk to a temporary file to upload it
                with tempfile.NamedTemporaryFile(
                    mode="w", delete=False, suffix=".md", encoding="utf-8"
                ) as temp_f:
                    temp_f.write(chunk_text)
                    temp_file_path = temp_f.name

                # Upload the temporary file
                with open(temp_file_path, "rb") as f:
                    uploaded_file = client.files.upload(
                        file=f,
                        config={
                            "display_name": f"chunk_{chunk_num}_{Path(input_file).name}",
                            "mime_type": "text/markdown",
                        },
                    )

                print(f"  ✓ Chunk uploaded: {uploaded_file.name}")

                # Cache the successful upload using the virtual path
                cache_upload(virtual_path, chunk_hash, uploaded_file)

            except Exception as e:
                print(f"  ❌ Chunk upload failed: {e}", file=sys.stderr)
                traceback.print_exc()
                return False
            finally:
                # Clean up the temporary file
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

        if not uploaded_file:
            print(
                f"  ❌ Could not get an uploaded file to process for chunk {chunk_num}",
                file=sys.stderr,
            )
            return False

        # Create prompt that refers to the uploaded file
        try:
            template = prompt_manager.load_template("chunk_continuation_prompt.txt")
            print(f"  📄 Using prompt: chunk_continuation_prompt.txt")
            # Replace the placeholder with a note about the File API
            chunk_prompt = template.replace(
                "{chunk_text}", "[Content provided via Gemini File API]"
            )
        except Exception as e:
            print(f"  ❌ Error creating prompt: {e}", file=sys.stderr)
            if verbose:
                traceback.print_exc()
            return False

        # Save chunk prompt to log
        save_to_log(f"chunk_{chunk_num:03d}_prompt.txt", chunk_prompt, subdir="chunks")

        # Call Gemini API with the prompt and the file
        response = client.models.generate_content(
            model=model,
            contents=[chunk_prompt, uploaded_file],  # Pass both prompt and file
            config=config,
        )

        # --- End of new File API and Caching Logic ---

        if not response.text:
            print(f"  ❌ Empty response from Gemini", file=sys.stderr)
            return False

        chunk_converted = response.text.strip()

        # Save raw response to log
        save_to_log(
            f"chunk_{chunk_num:03d}_response_raw.txt", chunk_converted, subdir="chunks"
        )

        # Strip code fences if present
        chunk_converted = strip_code_fences(chunk_converted)

        # Save final converted chunk to log
        save_to_log(
            f"chunk_{chunk_num:03d}_result.md", chunk_converted, subdir="chunks"
        )

        # CRITICAL: Validate Devanagari preservation for this chunk
        chunk_output_devanagari = extract_devanagari(chunk_converted)
        chunk_output_count = len(chunk_output_devanagari)

        # Compare Devanagari content
        devanagari_match = chunk_input_devanagari == chunk_output_devanagari
        char_diff = abs(chunk_input_count - chunk_output_count)

        if devanagari_match:
            print(f"  ✅ Devanagari validation: PASSED ({chunk_output_count:,} chars)")
            chunk_validations.append(
                {
                    "chunk": chunk_num,
                    "unit_name": unit_name,
                    "status": "PASSED",
                    "input_chars": chunk_input_count,
                    "output_chars": chunk_output_count,
                    "diff": 0,
                }
            )
        else:
            print(
                f"  ⚠️  Devanagari validation: MISMATCH ({chunk_input_count:,} → {chunk_output_count:,}, diff: {char_diff:,})",
                file=sys.stderr,
            )
            chunk_validations.append(
                {
                    "chunk": chunk_num,
                    "unit_name": unit_name,
                    "status": "MISMATCH",
                    "input_chars": chunk_input_count,
                    "output_chars": chunk_output_count,
                    "diff": char_diff,
                }
            )

            # Show colored diff for this chunk
            if not no_diff or show_transliteration:
                print(
                    f"\n  {Fore.YELLOW}📊 Showing differences for chunk {chunk_num}:{Style.RESET_ALL}"
                )

            if not no_diff:
                show_devanagari_diff(
                    chunk_input_devanagari,
                    chunk_output_devanagari,
                    max_diff_lines=20,
                    chunk_num=chunk_num,
                    save_to_log_func=save_to_log,
                )

            if show_transliteration:
                show_transliteration_diff(
                    chunk_input_devanagari,
                    chunk_output_devanagari,
                    chunk_num,
                    save_to_log_func=save_to_log,
                )

            # Don't fail immediately - collect all issues
            # But warn the user
            if char_diff > 100:
                print(
                    f"  ⚠️  WARNING: Large difference detected in chunk {chunk_num}!",
                    file=sys.stderr,
                )

        # Track totals
        total_input_devanagari_chars += chunk_input_count
        total_output_devanagari_chars += chunk_output_count

        converted_bodies.append(chunk_converted)

        chunk_elapsed = time.time() - chunk_start
        print(f"  ✓ Converted ({len(chunk_converted):,} bytes)")
        print(f"  ⏱️  Elapsed: {chunk_elapsed:.1f}s\n")

    total_elapsed = time.time() - start_time

    # Print per-chunk validation summary
    cache_info = f"({cache_hits} from file cache)" if cache_hits > 0 else ""
    print(f"✓ All {total_chunks} chunks converted in {total_elapsed:.1f}s {cache_info}")
    print(f"\n📊 Per-Chunk Devanagari Validation Summary:")

    passed_count = sum(1 for v in chunk_validations if v["status"] == "PASSED")
    failed_count = sum(1 for v in chunk_validations if v["status"] == "MISMATCH")

    print(f"  ✅ Passed: {passed_count}/{total_chunks}")
    if failed_count > 0:
        print(f"  ⚠️  Mismatches: {failed_count}/{total_chunks}", file=sys.stderr)
        print(f"\n  Chunks with mismatches:", file=sys.stderr)
        for v in chunk_validations:
            if v["status"] == "MISMATCH":
                print(
                    f"    • Chunk {v['chunk']} ({v['unit_name']}): {v['input_chars']:,} → {v['output_chars']:,} (diff: {v['diff']:,})",
                    file=sys.stderr,
                )

    print(
        f"  📊 Total: {total_input_devanagari_chars:,} → {total_output_devanagari_chars:,} chars"
    )

    total_diff = abs(total_input_devanagari_chars - total_output_devanagari_chars)
    if total_diff > 0:
        print(f"  ⚠️  Cumulative difference: {total_diff:,} characters", file=sys.stderr)
    else:
        print(f"  ✓ Perfect match across all chunks!")

    print(f"\n{'='*60}")
    print("📋 PHASE 4: MERGING CHUNKS")
    print(f"{'='*60}\n")

    # Merge converted bodies
    print(f"🔗 Merging {len(converted_bodies)} converted chunks")
    merged_body = "\n\n".join(body.strip() for body in converted_bodies if body.strip())
    print(f"  • Total merged size: {len(merged_body):,} bytes")
    print(f"✓ Merged successfully\n")

    print(f"{'='*60}")
    print("📋 PHASE 5: BUILDING FRONTMATTER")
    print(f"{'='*60}\n")

    # Build frontmatter
    print(f"  • grantha_id: {grantha_id}")
    print(f"  • canonical_title: {canonical_title}")
    if commentary_id:
        print(f"  • commentary_id: {commentary_id}")
    print(f"  • structure_type: {structure_type}")

    # Extract structure_levels from analysis
    structural_analysis = analysis_result.get("structural_analysis", {})
    structure_levels = structural_analysis.get("structure_levels", {})
    if structure_levels:
        print(f"  • structure_levels extracted from analysis")

    # Calculate validation hash
    print(f"🔢 Calculating validation hash...")
    validation_hash = hash_text(merged_body)
    print(f"✓ Hash: {validation_hash[:16]}...\n")

    # Build frontmatter dict
    frontmatter = {
        "grantha_id": grantha_id,
        "part_num": metadata.get("part_num", 1),  # Use from metadata if available
        "canonical_title": canonical_title,
        "text_type": "upanishad",
        "language": "sanskrit",
        "scripts": ["devanagari"],
        "structure_levels": structure_levels,  # From analysis
        "validation_hash": validation_hash,
    }

    if commentary_id:
        frontmatter["commentaries_metadata"] = [
            {
                "commentary_id": commentary_id,
                "commentator": commentator or "Unknown",
                "language": "sanskrit",
            }
        ]

    # Convert to YAML
    frontmatter_yaml = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    final_content = f"---\n{frontmatter_yaml}---\n\n{merged_body}"

    # Write output
    print(f"{'='*60}")
    print("📋 PHASE 6: WRITING OUTPUT")
    print(f"{'='*60}\n")

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_content)
        print(f"✓ Output written: {output_file}\n")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return False

    # Hide editor comments
    print(f"{'='*60}")
    print("📋 PHASE 7: POST-PROCESSING")
    print(f"{'='*60}\n")

    print("🔒 Hiding editor comments...")
    original_content, modified_content = hide_editor_comments_in_content(final_content)

    if original_content != modified_content:
        if not validate_devanagari_unchanged(original_content, modified_content):
            print("❌ Devanagari altered during comment hiding", file=sys.stderr)
            return False

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(modified_content)
        print("✓ Editor comments hidden\n")
    else:
        print("✓ No editor comments found\n")

    # Validate Devanagari
    if not skip_validation:
        print("✅ Validating Devanagari preservation...")
        input_devanagari = extract_devanagari(input_text)
        output_devanagari = extract_devanagari(modified_content)

        if input_devanagari == output_devanagari:
            print(
                f"✓ Validation passed: {len(input_devanagari)} Devanagari characters preserved\n"
            )
        else:
            diff = abs(len(input_devanagari) - len(output_devanagari))
            print(f"⚠️  Validation failed: {diff} character difference")

            if diff < 1000:
                print(f"⚠️  Attempting repair...")
                repair_successful, repair_message = repair_file(
                    input_file=input_file,
                    output_file=output_file,
                    max_diff_size=1000,
                    skip_frontmatter=True,
                    verbose=verbose,
                    dry_run=False,
                    min_similarity=0.85,  # Require 85% similarity
                    conservative=True,  # Only do replacements, skip insert/delete
                    create_backup=True,  # Create backup before modifying
                )

                if repair_successful:
                    print(f"✓ {repair_message}\n")
                    # Recalculate hash
                    with open(output_file, "r", encoding="utf-8") as f:
                        repaired_content = f.read()
                    repaired_body = repaired_content.split("---\n\n", 2)[-1]
                    new_hash = hash_text(repaired_body)

                    repaired_content = repaired_content.replace(
                        f"validation_hash: {validation_hash}",
                        f"validation_hash: {new_hash}",
                        1,
                    )
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(repaired_content)
                    print("✓ Validation hash recalculated\n")
                else:
                    print(f"❌ {repair_message}", file=sys.stderr)
                    return False
            else:
                print(
                    f"❌ Difference too large ({diff} chars) - cannot auto-repair",
                    file=sys.stderr,
                )
                return False

    print(f"{'='*60}")
    print(f"✅ CONVERSION COMPLETE: {output_file}")
    print(f"{'='*60}\n")

    return True


def convert_with_chunking(
    input_file: str,
    output_file: str,
    grantha_id: str,
    canonical_title: str,
    commentary_id: str,
    commentator: str,
    part_num: int,
    skip_validation: bool,
    chunk_size: int = 50000,
    keep_temp_chunks: bool = False,
    model: str = DEFAULT_GEMINI_MODEL,
) -> bool:
    """Convert a file with automatic chunking (sequential processing).

    Strategy:
    1. First chunk (0-50KB): Extract metadata (structure_type) + convert content
    2. Remaining chunks: Split at structure boundaries, convert sequentially
    3. Merge all bodies (no frontmatter in chunks)
    4. Build frontmatter at end with validation hash

    Args:
        input_file: Path to input file
        output_file: Path to output file
        grantha_id: Grantha identifier (used only if first chunk doesn't infer)
        canonical_title: Canonical title (used only if first chunk doesn't infer)
        commentary_id: Commentary identifier (optional)
        commentator: Commentator name (optional)
        part_num: Part number
        skip_validation: Skip Devanagari validation
        chunk_size: Maximum chunk size in bytes (default: 50KB)
        keep_temp_chunks: Keep temporary chunk files for debugging (default: False)

    Returns:
        True if successful, False otherwise
    """
    # Initialize Gemini API
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set", file=sys.stderr)
        return False

    client = genai.Client(api_key=api_key)

    # Disable safety filters - using dict format for compatibility
    config = types.GenerateContentConfig(
        temperature=0.1,
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    )

    # Read input file
    print(f"📖 Reading input: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        input_text = f.read()

    file_size = len(input_text)
    print(f"📊 File size: {file_size:,} bytes")

    # Check if chunking is needed
    if file_size < chunk_size:
        print(
            f"ℹ️  File size below {chunk_size:,} byte threshold - processing as single file"
        )
        return convert_single_file(
            input_file=input_file,
            output_file=output_file,
            grantha_id=grantha_id,
            canonical_title=canonical_title,
            commentary_id=commentary_id,
            commentator=commentator,
            part_num=part_num,
            skip_validation=skip_validation,
        )

    # === STEP 1: Process first chunk and extract metadata ===
    print(
        f"\n📝 Step 1: Processing first chunk (0-{chunk_size:,} bytes) to extract metadata..."
    )

    first_chunk_text = input_text[:chunk_size]

    # Call Gemini with enhanced prompt that extracts both metadata and content
    first_chunk_prompt = create_first_chunk_prompt(first_chunk_text, part_num)

    try:
        response = client.models.generate_content(
            model=model, contents=first_chunk_prompt, config=config
        )

        if not response.text:
            print(f"Error: Gemini API failed on first chunk", file=sys.stderr)
            return False

        first_chunk_response = response.text.strip()

    except Exception as e:
        print(f"Error calling Gemini API for first chunk: {e}", file=sys.stderr)
        return False

    # Parse metadata and content from first chunk response
    metadata, first_converted_body = parse_first_chunk_response(first_chunk_response)

    if not metadata:
        print(f"Error: Failed to extract metadata from first chunk", file=sys.stderr)
        return False

    # Use inferred metadata (fallback to provided args if missing)
    inferred_grantha_id = metadata.get("grantha_id") or grantha_id
    inferred_canonical_title = metadata.get("canonical_title") or canonical_title
    inferred_commentary_id = metadata.get("commentary_id") or commentary_id
    inferred_commentator = metadata.get("commentator") or commentator
    structure_type = metadata.get("structure_type")

    print(f"✓ Metadata extracted:")
    print(f"  - grantha_id: {inferred_grantha_id}")
    print(f"  - canonical_title: {inferred_canonical_title}")
    print(f"  - commentary_id: {inferred_commentary_id or 'none'}")
    print(f"  - commentator: {inferred_commentator or 'none'}")
    print(f"  - structure_type: {structure_type or 'none'}")

    # === STEP 2: Split remaining text at boundaries ===
    remaining_text = input_text[chunk_size:]

    if not remaining_text.strip():
        print("✓ No remaining text - single chunk covers entire file")
        converted_bodies = [first_converted_body]
    else:
        print(
            f"\n📝 Step 2: Splitting remaining {len(remaining_text):,} bytes at structure boundaries..."
        )

        if structure_type:
            print(f"📍 Using structure type: {structure_type}")
            chunks = split_at_boundaries(
                remaining_text,
                max_size=chunk_size,
                preferred_boundary=structure_type,
                verbose=False,
            )
        else:
            # No structure type - split by size only
            print(f"📍 No structure type found - splitting by size")
            num_chunks = (len(remaining_text) + chunk_size - 1) // chunk_size
            chunks = []
            for i in range(num_chunks):
                start = i * chunk_size
                end = min((i + 1) * chunk_size, len(remaining_text))
                chunk_text = remaining_text[start:end]
                chunks.append(
                    (chunk_text, {"chunk_index": i, "total_chunks": num_chunks})
                )

        print(f"✓ Split into {len(chunks)} additional chunk(s)")

        # === STEP 3: Process remaining chunks sequentially ===
        print(f"\n📝 Step 3: Converting remaining chunks sequentially...")
        converted_bodies = [first_converted_body]

        for i, (chunk_text, chunk_metadata) in enumerate(chunks, start=1):
            chunk_num = i + 1  # +1 because first chunk is #1
            total_chunks = len(chunks) + 1

            print(f"  📄 Converting chunk {chunk_num}/{total_chunks}...")

            # Simple conversion prompt (no metadata, no frontmatter)
            chunk_prompt = create_chunk_conversion_prompt(chunk_text)

            try:
                response = client.models.generate_content(
                    model=model, contents=chunk_prompt, config=config
                )

                if not response.text:
                    print(
                        f"  ❌ Gemini API failed on chunk {chunk_num}", file=sys.stderr
                    )
                    return False

                chunk_converted = response.text.strip()

                # Strip code fences if present
                chunk_converted = strip_code_fences(chunk_converted)

                converted_bodies.append(chunk_converted)
                print(
                    f"  ✓ Chunk {chunk_num}/{total_chunks} converted ({len(chunk_converted)} bytes)"
                )

            except Exception as e:
                print(f"  ❌ Error converting chunk {chunk_num}: {e}", file=sys.stderr)
                return False

        print(f"✓ All {total_chunks} chunks converted successfully")

    # === STEP 4: Merge bodies and build frontmatter ===
    print(f"\n📝 Step 4: Merging chunks and building frontmatter...")

    # Merge all converted bodies
    merged_body = "\n\n".join(body.strip() for body in converted_bodies if body.strip())
    print(f"✓ Merged body: {len(merged_body):,} bytes")

    # Build frontmatter
    from grantha_converter.hasher import hash_text

    validation_hash = hash_text(merged_body)

    frontmatter = {
        "grantha_id": inferred_grantha_id,
        "part_num": part_num,
        "canonical_title": inferred_canonical_title,
        "text_type": "upanishad",
        "language": "sanskrit",
        "scripts": ["devanagari"],
        "structure_levels": [],  # TODO: Could be inferred
        "validation_hash": validation_hash,
    }

    if inferred_commentary_id:
        frontmatter["commentaries_metadata"] = [
            {
                "commentary_id": inferred_commentary_id,
                "commentator": inferred_commentator or "Unknown",
            }
        ]

    # Convert frontmatter to YAML
    frontmatter_yaml = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    final_content = f"---\n{frontmatter_yaml}---\n\n{merged_body}"

    # === STEP 5: Write output ===
    print(f"\n📝 Step 5: Writing output...")
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_content)

    print(f"✓ Output written: {output_file}")

    # === STEP 6: Hide editor comments ===
    print(f"\n📝 Step 6: Hiding editor comments...")
    original_content, modified_content = hide_editor_comments_in_content(final_content)

    if original_content != modified_content:
        if not validate_devanagari_unchanged(original_content, modified_content):
            print("Error: Devanagari altered during comment hiding", file=sys.stderr)
            return False

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(modified_content)
        print("✓ Editor comments hidden")
    else:
        print("✓ No editor comments found")

    # === STEP 7: Validate Devanagari ===
    if not skip_validation:
        print(f"\n📝 Step 7: Validating Devanagari preservation...")
        from grantha_converter.devanagari_repair import extract_devanagari

        input_devanagari = extract_devanagari(input_text)
        output_devanagari = extract_devanagari(modified_content)

        if input_devanagari == output_devanagari:
            print(
                f"✓ Validation passed: {len(input_devanagari)} Devanagari characters preserved"
            )
        else:
            diff = abs(len(input_devanagari) - len(output_devanagari))
            print(f"⚠️  Validation failed: {diff} character difference")

            if diff < 1000:
                print(f"⚠️  Attempting repair...")
                from grantha_converter.devanagari_repair import repair_file

                repair_successful, repair_message = repair_file(
                    input_file=input_file,
                    output_file=output_file,
                    max_diff_size=1000,
                    skip_frontmatter=True,
                    verbose=True,
                    dry_run=False,
                    min_similarity=0.85,  # Require 85% similarity
                    conservative=True,  # Only do replacements, skip insert/delete
                    create_backup=True,  # Create backup before modifying
                )

                if repair_successful:
                    print(f"✓ {repair_message}")
                    # Recalculate hash
                    with open(output_file, "r", encoding="utf-8") as f:
                        repaired_content = f.read()
                    repaired_body = repaired_content.split("---\n\n", 2)[-1]
                    new_hash = hash_text(repaired_body)

                    repaired_content = repaired_content.replace(
                        f"validation_hash: {validation_hash}",
                        f"validation_hash: {new_hash}",
                        1,
                    )
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(repaired_content)
                    print("✓ Validation hash recalculated")
                else:
                    print(f"❌ {repair_message}", file=sys.stderr)
                    return False
            else:
                print(
                    f"❌ Difference too large ({diff} chars) - cannot auto-repair",
                    file=sys.stderr,
                )
                return False

    print(f"\n✅ Chunked conversion complete: {output_file}\n")
    return True


def convert_single_file(
    input_file: str,
    output_file: str,
    grantha_id: str,
    canonical_title: str,
    commentary_id: str,
    commentator: str,
    part_num: int,
    skip_validation: bool,
    no_diff: bool = False,
    show_transliteration: bool = False,
) -> bool:
    """Convert a single file."""
    # Read input file
    print(f"📖 Reading input: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        input_text = f.read()

    # Create conversion prompt
    print("📝 Creating conversion prompt...")
    prompt = create_conversion_prompt(
        input_text=input_text,
        grantha_id=grantha_id,
        canonical_title=canonical_title,
        commentary_id=commentary_id,
        commentator=commentator,
        part_num=part_num,
    )

    # Call Gemini API
    if not call_gemini_api(prompt, output_file):
        return False

    # Calculate hash
    print("🔢 Calculating validation hash...")
    if not calculate_and_update_hash(output_file):
        print("Warning: Hash calculation failed, continuing...", file=sys.stderr)

    # Hide editor comments
    print("🔒 Hiding editor comments in square brackets...")
    with open(output_file, "r", encoding="utf-8") as f:
        file_content = f.read()

    original_content, modified_content = hide_editor_comments_in_content(file_content)

    if original_content != modified_content:
        # Validate that Devanagari wasn't changed
        if not validate_devanagari_unchanged(original_content, modified_content):
            print(
                "Error: Devanagari text was altered during comment hiding",
                file=sys.stderr,
            )
            return False

        # Write the modified content back
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(modified_content)
        print("✓ Editor comments hidden successfully")
    else:
        print("✓ No editor comments found to hide")

    # Validate
    if not skip_validation:
        print("✓ Validating Devanagari preservation...")
        validation_passed = validate_output(
            input_file, output_file, show_diff=not no_diff
        )

        if not validation_passed:
            print("\n⚠️  Initial validation failed - attempting repair...")

            # Attempt repair using the library function with safe defaults
            repair_successful, repair_message = repair_file(
                input_file=input_file,
                output_file=output_file,
                max_diff_size=1000,
                skip_frontmatter=True,
                verbose=True,
                dry_run=False,
                min_similarity=0.85,  # Require 85% similarity
                conservative=True,  # Only do replacements, skip insert/delete
                create_backup=True,  # Create backup before modifying
            )

            if repair_successful:
                print(repair_message)
                # Recalculate hash after repair
                print("🔢 Recalculating validation hash after repair...")
                if not calculate_and_update_hash(output_file):
                    print("Warning: Hash recalculation failed", file=sys.stderr)

                # Validate again
                print("✓ Re-validating after repair...")
                if not validate_output(input_file, output_file, show_diff=not no_diff):
                    print(
                        "\n⚠️  Validation still failed after repair - please review output manually",
                        file=sys.stderr,
                    )
                    return False

                print("✓ Validation passed after repair!")
            else:
                print(f"\n⚠️  {repair_message}", file=sys.stderr)
                print("Please review output manually", file=sys.stderr)
                return False

    print(f"✅ Conversion complete: {output_file}\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Convert meghamala markdown to Grantha structured markdown using Gemini API",
        epilog="""
Examples:
  # Single file with auto-detected part number
  %(prog)s -i input.md -o output.md --grantha-id kena-upanishad --canonical-title "केनोपनिषत्"

  # Directory mode - converts all files
  %(prog)s -d sources/upanishads/meghamala/brihadaranyaka/ -o output/ --grantha-id brihadaranyaka-upanishad --canonical-title "बृहदारण्यकोपनिषत्"

  # Override part number
  %(prog)s -i 03-01.md -o output.md --grantha-id test --canonical-title "Test" --part-num 5
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-i", "--input", help="Input meghamala markdown file")
    input_group.add_argument(
        "-d", "--directory", help="Input directory containing multiple parts"
    )

    parser.add_argument(
        "-o", "--output", required=True, help="Output file or directory"
    )
    parser.add_argument(
        "--grantha-id", help="Grantha identifier (auto-inferred if not provided)"
    )
    parser.add_argument(
        "--canonical-title",
        help="Canonical Devanagari title (auto-inferred if not provided)",
    )
    parser.add_argument(
        "--commentary-id", help="Commentary identifier (auto-inferred if present)"
    )
    parser.add_argument(
        "--commentator",
        help="Commentator name in Devanagari (auto-inferred if present)",
    )
    parser.add_argument(
        "--no-auto-infer",
        action="store_true",
        help="Disable automatic metadata inference with Gemini (requires manual metadata)",
    )
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
        help="Show Harvard-Kyoto transliteration diff in addition to Devanagari diff",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=200000,
        help="Maximum chunk size in bytes for large files (default: 200000)",
    )
    parser.add_argument(
        "--no-chunking",
        action="store_true",
        help="Disable automatic chunking even for large files",
    )
    parser.add_argument(
        "--keep-temp-chunks",
        action="store_true",
        help="Keep temporary chunk files for debugging",
    )
    parser.add_argument(
        "--force-analysis",
        action="store_true",
        help="Force re-analysis: clear cache, re-analyze file, and save new result to cache",
    )
    parser.add_argument(
        "--no-upload-cache",
        action="store_true",
        help="Disable file upload caching (always upload fresh)",
    )

    # Model selection
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
        "--metadata-model",
        help="Gemini model for metadata inference phase (overrides --model)",
    )

    args = parser.parse_args()

    # Resolve model selections (specific args override --model)
    analysis_model = args.analysis_model or args.model
    conversion_model = args.conversion_model or args.model
    metadata_model = args.metadata_model or args.model

    # Single file mode
    if args.input:
        input_path = Path(args.input)
        output_path = Path(args.output)

        # If output is a directory, generate filename from input
        if output_path.is_dir() or str(output_path).endswith("/"):
            output_path.mkdir(parents=True, exist_ok=True)
            output_filename = input_path.stem + "_converted.md"
            output_path = output_path / output_filename
            print(f"📁 Output is a directory, using filename: {output_filename}")
        else:
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print("📋 PHASE 1: ANALYZING FILE STRUCTURE")
        print(f"{'='*60}\n")

        # PHASE 1: Analyze file structure (always do this first)
        try:
            analysis = analyze_file_structure(
                str(input_path),
                verbose=False,
                use_cache=True,
                use_upload_cache=not args.no_upload_cache,
                force_reanalysis=args.force_analysis,
                model=analysis_model,
            )
        except Exception as e:
            print(f"❌ File analysis failed: {e}", file=sys.stderr)
            return 1

        metadata = analysis.get("metadata", {})
        chunking_strategy = analysis.get("chunking_strategy", {})
        parsing_instructions = analysis.get("parsing_instructions", {})
        splitting_instructions = analysis.get(
            "splitting_instructions", {}
        )  # Backwards compatibility

        # Display analysis results
        print(f"\n✓ Analysis complete:")
        print(f"  📖 Text: {metadata.get('canonical_title', 'Unknown')}")
        print(f"  🆔 ID: {metadata.get('grantha_id', 'unknown')}")
        if metadata.get("commentary_id"):
            print(f"  📝 Commentary: {metadata.get('commentary_id')}")
        print(f"  🏗️ Structure: {metadata.get('structure_type', 'unknown')}")

        # Show chunking strategy (new format) or splitting instructions (old format)
        if chunking_strategy:
            execution_plan = chunking_strategy.get("execution_plan", [])
            proposed_strategy = chunking_strategy.get("proposed_strategy", {})
            strategy_name = proposed_strategy.get("name", "Unknown")
            safety_limit = proposed_strategy.get("safety_character_limit")
            print(
                f"  ✂️  Chunking strategy: {strategy_name} ({len(execution_plan)} chunks)"
            )
            if safety_limit:
                print(f"  🔒 Safety limit: {safety_limit:,} characters per chunk")
            if parsing_instructions:
                print(
                    f"  📋 Parsing unit: {parsing_instructions.get('recommended_unit', 'unknown')}"
                )
        elif splitting_instructions:
            print(
                f"  ✂️  Recommended unit: {splitting_instructions.get('recommended_unit', 'unknown')} (legacy mode)"
            )

        # PHASE 2-7: Convert using regex chunking
        try:
            success = convert_with_regex_chunking(
                input_file=str(input_path),
                output_file=str(output_path),
                analysis_result=analysis,
                skip_validation=args.skip_validation,
                no_diff=args.no_diff,
                show_transliteration=args.show_transliteration,
                verbose=False,
                model=conversion_model,
            )
        except Exception as e:
            print(f"❌ Conversion failed: {e}", file=sys.stderr)
            return 1

        return 0 if success else 1

    # Directory mode
    else:
        input_dir = Path(args.directory)
        output_dir = Path(args.output)

        if not input_dir.is_dir():
            print(f"Error: {input_dir} is not a directory", file=sys.stderr)
            return 1

        # Create output directory if needed
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get all parts
        parts = get_directory_parts(input_dir)

        if not parts:
            print(f"Error: No markdown files found in {input_dir}", file=sys.stderr)
            return 1

        print(f"📚 Found {len(parts)} part(s) to convert:")
        for file_path, part_num in parts:
            print(f"   Part {part_num}: {file_path.name}")
        print()

        # Auto-infer metadata if not provided (using first file)
        grantha_id = args.grantha_id
        canonical_title = args.canonical_title
        commentary_id = args.commentary_id
        commentator = args.commentator

        if not grantha_id or not canonical_title:
            if args.no_auto_infer:
                print(
                    "Error: --grantha-id and --canonical-title are required when --no-auto-infer is set",
                    file=sys.stderr,
                )
                return 1

            first_file = str(parts[0][0])
            print(f"🔍 Auto-inferring metadata from first file: {parts[0][0].name}")
            inferred = infer_metadata_with_gemini(
                first_file, verbose=True, model=metadata_model
            )

            if not inferred:
                print(
                    "Error: Failed to infer metadata. Please provide --grantha-id and --canonical-title manually",
                    file=sys.stderr,
                )
                return 1

            # Use inferred values for missing fields
            if not grantha_id:
                grantha_id = inferred.get("grantha_id")
                print(f"✓ Inferred grantha-id: {grantha_id}")

            if not canonical_title:
                canonical_title = inferred.get("canonical_title")
                print(f"✓ Inferred canonical-title: {canonical_title}")

            if not commentary_id and inferred.get("commentary_id"):
                commentary_id = inferred.get("commentary_id")
                print(f"✓ Inferred commentary-id: {commentary_id}")

            if not commentator and inferred.get("commentator"):
                commentator = inferred.get("commentator")
                print(f"✓ Inferred commentator: {commentator}")
            print()

        # Validate required metadata
        if not grantha_id or not canonical_title:
            print(
                "Error: Could not determine grantha_id and canonical_title",
                file=sys.stderr,
            )
            return 1

        # Convert each part
        failed = []
        for file_path, part_num in parts:
            # Set file-specific log subdirectory for this part
            create_log_directory(file_subdir=f"part-{part_num:02d}")

            # Preserve original filename
            output_file = output_dir / file_path.name

            print(f"\n🔄 Converting part {part_num}/{len(parts)}: {file_path.name}")
            print(f"{'='*60}")
            print("📋 PHASE 1: ANALYZING FILE STRUCTURE")
            print(f"{'='*60}\n")

            # PHASE 1: Analyze file structure (same as single file mode)
            try:
                analysis = analyze_file_structure(
                    str(file_path),
                    verbose=False,
                    use_cache=True,
                    use_upload_cache=not args.no_upload_cache,
                    force_reanalysis=args.force_analysis,
                    model=analysis_model,
                )
            except Exception as e:
                print(f"❌ File analysis failed: {e}", file=sys.stderr)
                failed.append((part_num, file_path.name))
                continue

            # Override metadata from analysis with command-line args
            analysis_metadata = analysis.get("metadata", {})
            analysis_metadata["grantha_id"] = grantha_id
            analysis_metadata["canonical_title"] = canonical_title
            analysis_metadata["part_num"] = part_num
            if commentary_id:
                analysis_metadata["commentary_id"] = commentary_id
            if commentator:
                analysis_metadata["commentator"] = commentator
            analysis["metadata"] = analysis_metadata

            chunking_strategy = analysis.get("chunking_strategy", {})
            parsing_instructions = analysis.get("parsing_instructions", {})
            splitting_instructions = analysis.get(
                "splitting_instructions", {}
            )  # Backwards compatibility

            # Display analysis results
            print(f"\n✓ Analysis complete:")
            print(f"  📖 Text: {analysis_metadata.get('canonical_title', 'Unknown')}")
            print(f"  🆔 ID: {grantha_id}")
            print(f"  #️⃣ Part: {part_num}")
            if commentary_id:
                print(f"  📝 Commentary: {commentary_id}")
            print(
                f"  🏗️ Structure: {analysis_metadata.get('structure_type', 'unknown')}"
            )

            # Show chunking strategy (new format) or splitting instructions (old format)
            if chunking_strategy:
                execution_plan = chunking_strategy.get("execution_plan", [])
                proposed_strategy = chunking_strategy.get("proposed_strategy", {})
                strategy_name = proposed_strategy.get("name", "Unknown")
                safety_limit = proposed_strategy.get("safety_character_limit")
                print(
                    f"  ✂️  Chunking strategy: {strategy_name} ({len(execution_plan)} chunks)"
                )
                if safety_limit:
                    print(f"  🔒 Safety limit: {safety_limit:,} characters per chunk")
                if parsing_instructions:
                    print(
                        f"  📋 Parsing unit: {parsing_instructions.get('recommended_unit', 'unknown')}"
                    )
            elif splitting_instructions:
                print(
                    f"  ✂️  Recommended unit: {splitting_instructions.get('recommended_unit', 'unknown')} (legacy mode)"
                )

            # PHASE 2-7: Convert using regex chunking (same as single file mode)
            try:
                success = convert_with_regex_chunking(
                    input_file=str(file_path),
                    output_file=str(output_file),
                    analysis_result=analysis,
                    skip_validation=args.skip_validation,
                    no_diff=args.no_diff,
                    show_transliteration=args.show_transliteration,
                    verbose=False,
                    model=conversion_model,
                )
            except Exception as e:
                print(f"❌ Conversion failed: {e}", file=sys.stderr)
                success = False

            if not success:
                failed.append((part_num, file_path.name))

        # Summary
        print(f"\n{'='*60}")
        if failed:
            print(
                f"⚠️  Converted {len(parts) - len(failed)}/{len(parts)} parts successfully"
            )
            print(f"Failed parts:")
            for part_num, filename in failed:
                print(f"  - Part {part_num}: {filename}")
            return 1
        else:
            print(f"✅ All {len(parts)} parts converted successfully!")
            print(f"Output directory: {output_dir}")
            return 0


if __name__ == "__main__":
    sys.exit(main())
