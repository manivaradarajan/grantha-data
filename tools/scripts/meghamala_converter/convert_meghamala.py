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
from colorama import Back, Fore, Style
from colorama import init as colorama_init

# Local imports
from gemini_processor.cache_manager import AnalysisCache
from gemini_processor.file_manager import get_file_hash
from gemini_processor.prompt_manager import PromptManager
from gemini_processor.sampler import create_smart_sample
from google import genai
from google.genai import types
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


def _create_log_directory(file_subdir: str = None) -> Path:
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


def _save_to_log(filename: str, content: str, subdir: str = None):
    """Save content to a log file in the current run's log directory.

    Args:
        filename: Name of the file to save
        content: Content to write
        subdir: Optional subdirectory within the log directory
    """
    log_dir = _create_log_directory()
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


def _load_upload_cache() -> dict:
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


def _save_upload_cache(cache: dict):
    """Save the file upload cache to disk.

    Args:
        cache: Dict mapping file_hash -> upload info
    """
    try:
        with open(UPLOAD_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"⚠️  Warning: Could not save upload cache: {e}", file=sys.stderr)


def _get_cached_upload(client: genai.Client, file_path: str, file_hash: str):
    """Check if we have a valid cached upload for this file.

    Args:
        client: Gemini client to verify file still exists
        file_path: Path to the file
        file_hash: SHA256 hash of the file

    Returns:
        Gemini File object if valid, None otherwise
    """
    cache = _load_upload_cache()
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


def _cache_upload(file_path: str, file_hash: str, uploaded_file) -> None:
    """Cache information about an uploaded file.

    Args:
        file_path: Path to the file
        file_hash: SHA256 hash of the file
        uploaded_file: The uploaded file object from Gemini
    """
    cache = _load_upload_cache()
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

    _save_upload_cache(cache)
    print(f"  💾 Cached upload info")


def _repair_json_escapes(text: str) -> str:
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


def _handle_analysis_cache(input_file, force_reanalysis, use_cache, verbose=False):
    """Handles loading and clearing of the analysis cache."""
    cache = AnalysisCache(input_file)
    if force_reanalysis:
        cache.clear(verbose=verbose)
        print("📡 Forcing re-analysis - will call Gemini API and update cache")
        return None, cache

    if use_cache:
        cached_analysis = cache.load(verbose=verbose)
        if cached_analysis is not None:
            print("🚀 Skipping Gemini API call (using cached analysis)")
            return cached_analysis, cache
        else:
            print("📡 Cache miss - will call Gemini API")
    elif not use_cache:
        print("📡 Cache disabled - calling Gemini API (will not save)")

    return None, cache

def _upload_file_for_analysis(client, input_file, use_upload_cache):
    """Uploads a file to the Gemini API for analysis, using a cache."""
    file_hash = get_file_hash(input_file)
    uploaded_file = None
    was_cached = False

    if use_upload_cache:
        print("📤 Checking for cached file upload...")
        uploaded_file = _get_cached_upload(client, input_file, file_hash)
        was_cached = uploaded_file is not None
    else:
        print("📤 Upload caching disabled")

    if not uploaded_file:
        print("📤 Uploading file to Gemini File API...")
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
            if use_upload_cache:
                _cache_upload(input_file, file_hash, uploaded_file)
        except Exception as e:
            print(f"⚠️  File upload failed: {e}", file=sys.stderr)
            print("   Falling back to text embedding...", file=sys.stderr)
            traceback.print_exc()
            uploaded_file = None # Ensure it's None on failure

    if uploaded_file:
        _save_to_log(
            "00_uploaded_file_info.txt",
            f"File name: {uploaded_file.name}\n"
            f"Display name: {uploaded_file.display_name}\n"
            f"Size: {uploaded_file.size_bytes} bytes\n"
            f"State: {uploaded_file.state}\n"
            f"URI: {uploaded_file.uri}\n"
            f"Cached: {'Yes' if was_cached else 'No'}\n",
            subdir="analysis",
        )
    return uploaded_file

def _prepare_analysis_prompt(template_name, full_text, uploaded_file):
    """Prepares the analysis prompt, using file API or text embedding."""
    template = prompt_manager.load_template(template_name)
    print(f"  📄 Using prompt: {template_name}")

    if uploaded_file:
        analysis_prompt = template.replace(
            "\n--- INPUT TEXT ---\n{input_text}\n--- END INPUT TEXT ---",
            "\n\n[File content provided via Gemini File API - see uploaded file]",
        )
        print("📄 Using File API for analysis (efficient mode)")
    else:
        analysis_text, was_sampled = create_smart_sample(full_text, max_size=500000)
        if was_sampled:
            sample_size = len(analysis_text)
            print(f"✂️ File too large - using smart sampling")
            print(f"  📊 Sample size: {sample_size:,} bytes")
        else:
            print("📄 Using text embedding for analysis")
        analysis_prompt = template.format(input_text=analysis_text)

    _save_to_log("01_analysis_prompt.txt", analysis_prompt, subdir="analysis")
    return analysis_prompt

def _call_gemini_for_analysis(client, model, prompt, uploaded_file):
    """Calls the Gemini API with the analysis prompt."""
    print("🤖 Calling Gemini API for structural analysis...")
    config = types.GenerateContentConfig(
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )
    contents = [prompt]
    if uploaded_file:
        contents.append(uploaded_file)

    response = client.models.generate_content(model=model, contents=contents, config=config)

    if not response.text:
        raise ValueError("Empty response from Gemini API during file analysis")

    _save_to_log("02_analysis_response_raw.txt", response.text, subdir="analysis")
    return response.text

def _parse_analysis_response(response_text):
    """Parses and validates the JSON response from the analysis API call."""
    print(f"📝 Gemini response received ({len(response_text)} chars)")
    try:
        cleaned_text = response_text
        if response_text.startswith("```"):
            print("🧹 Removing markdown code fences...")
            lines = response_text.split("\n")
            json_lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned_text = "\n".join(json_lines)

        print("🔍 Parsing JSON response...")
        try:
            analysis_result = json.loads(cleaned_text)
        except json.JSONDecodeError:
            print("⚠️  Initial JSON parse failed, attempting to repair...")
            repaired_text = _repair_json_escapes(cleaned_text)
            analysis_result = json.loads(repaired_text)
            print("✓ JSON parsed successfully after repair!")

        print("✓ JSON parsed successfully")
        return analysis_result

    except json.JSONDecodeError as e:
        print(f"\n❌ Error: Could not parse JSON from Gemini response: {e}", file=sys.stderr)
        # ... (error printing logic)
        raise ValueError(f"Invalid JSON response from Gemini: {e}")

def _validate_analysis_result(analysis_result):
    """Validates the structure and content of the parsed analysis result."""
    if "metadata" not in analysis_result:
        raise ValueError("Missing 'metadata' section in analysis response")
    if "chunking_strategy" not in analysis_result or "parsing_instructions" not in analysis_result:
        raise ValueError("Missing 'chunking_strategy' or 'parsing_instructions' in analysis response")

    metadata = analysis_result.get("metadata", {})
    chunking_strategy = analysis_result.get("chunking_strategy", {})
    parsing_instructions = analysis_result.get("parsing_instructions", {})

    required_metadata = ["canonical_title", "grantha_id", "structure_type"]
    for field in required_metadata:
        if field not in metadata:
            print(f"Warning: Missing required metadata field: {field}", file=sys.stderr)

    if "execution_plan" not in chunking_strategy:
        print(f"Warning: Missing execution_plan in chunking_strategy", file=sys.stderr)
    if "recommended_unit" not in parsing_instructions:
        print(f"Warning: Missing recommended_unit in parsing_instructions", file=sys.stderr)

    print("✓ Analysis complete")
    execution_plan = chunking_strategy.get("execution_plan", [])
    print(f"  • Chunking: {len(execution_plan)} chunks planned")
    print(
        f"  • Parsing unit: {parsing_instructions.get('recommended_unit', 'unknown')}"
    )

def analyze_file_structure(
    input_file: str,
    verbose: bool = False,
    use_cache: bool = True,
    use_upload_cache: bool = True,
    force_reanalysis: bool = False,
    model: str = DEFAULT_GEMINI_MODEL,
) -> dict:
    """
    Analyzes file structure by orchestrating caching, uploading, and API calls.
    """
    print("🔍 Analyzing file structure...")

    cached_result, cache = _handle_analysis_cache(input_file, force_reanalysis, use_cache, verbose)
    if cached_result:
        return cached_result

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Error: GEMINI_API_KEY environment variable not set.")

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            full_text = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: Input file not found: {input_file}")

    client = genai.Client(api_key=api_key)

    uploaded_file = _upload_file_for_analysis(client, input_file, use_upload_cache)

    analysis_prompt = _prepare_analysis_prompt("full_file_analysis_prompt.txt", full_text, uploaded_file)

    response_text = _call_gemini_for_analysis(client, model, analysis_prompt, uploaded_file)

    analysis_result = _parse_analysis_response(response_text)

    _validate_analysis_result(analysis_result)

    if use_cache:
        cache.save(analysis_result, verbose=verbose)

    return analysis_result




def _hide_editor_comments_in_content(content: str) -> tuple[str, str]:
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


def _validate_devanagari_unchanged(original_content: str, modified_content: str) -> bool:
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


def _extract_part_number_from_filename(filename: str) -> int:
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


def _get_directory_parts(directory: Path) -> list:
    """
    Get all markdown files in directory sorted by part number.

    Returns:
        List of tuples: (file_path, part_number)
    """
    md_files = []
    for file in directory.glob("*.md"):
        if file.name.upper() == "PROVENANCE.yaml":
            continue
        part_num = _extract_part_number_from_filename(file.name)
        md_files.append((file, part_num))

    # Sort by part number
    md_files.sort(key=lambda x: x[1])
    return md_files


def _strip_code_fences(text: str) -> str:
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
        continuation_template = prompt_manager.load_template(
            "chunk_continuation_prompt.txt"
        )
        print(f"  📄 Using prompt: chunk_continuation_prompt.txt")

        # Format with the chunk text
        return continuation_template.format(chunk_text=chunk_text)
    except Exception as e:
        print(f"Error loading chunk continuation prompt template: {e}", file=sys.stderr)
        raise


def __normalize_marker(text: str) -> str:
    """Normalize text by removing markdown formatting for marker matching.

    Removes bold (**), italic (*), and extra whitespace to allow flexible matching.
    """
    # Remove bold markers
    text = text.replace("**", "")
    # Remove italic markers (single asterisk, but not double)
    # Normalize multiple spaces to single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _find_chunk_start(i, chunk_spec, lines, previous_chunks, verbose, text):
    """Determines the starting byte position and line number for a chunk."""
    if i == 0:
        if verbose and chunk_spec.get("start_marker"):
            print("  ℹ️  First chunk: ignoring start_marker, including content from beginning")
        return 0, 1

    start_marker = chunk_spec.get("start_marker", "")
    if start_marker:
        normalized_start_marker = __normalize_marker(start_marker)
        for line_idx, line in enumerate(lines):
            if normalized_start_marker in __normalize_marker(line):
                chunk_start = sum(len(l) + 1 for l in lines[:line_idx])
                return chunk_start, line_idx + 1

        print(f"  ⚠️  Warning: Could not find start_marker '{start_marker[:50]}...' for chunk {chunk_spec.get('chunk_id')}", file=sys.stderr)
        return None, None

    if previous_chunks:
        chunk_start = previous_chunks[-1][1]["end_pos"]
        start_line = text[:chunk_start].count("\n") + 1
        return chunk_start, start_line

    return 0, 1

def _find_chunk_end(i, chunk_spec, lines, execution_plan, start_line):
    """Determines the ending byte position for a chunk."""
    end_marker = chunk_spec.get("end_marker", "")
    if i == len(execution_plan) - 1 and not end_marker:
        return len("\n".join(lines))

    if end_marker:
        normalized_end_marker = __normalize_marker(end_marker)
        for line_idx in range(start_line - 1, len(lines)):
            if normalized_end_marker in __normalize_marker(lines[line_idx]):
                return sum(len(l) + 1 for l in lines[: line_idx + 1])

        print(f"  ⚠️  Warning: Could not find end_marker '{end_marker[:50]}...' for chunk {chunk_spec.get('chunk_id')}, using EOF", file=sys.stderr)
        return len("\n".join(lines))

    if i < len(execution_plan) - 1:
        next_start_marker = execution_plan[i + 1].get("start_marker", "")
        if next_start_marker:
            normalized_next_marker = __normalize_marker(next_start_marker)
            for line_idx in range(start_line - 1, len(lines)):
                if normalized_next_marker in __normalize_marker(lines[line_idx]):
                    return sum(len(l) + 1 for l in lines[:line_idx])

    return len("\n".join(lines))

def _split_by_execution_plan(
    text: str, execution_plan: list[dict], verbose: bool = False
) -> list[tuple[str, dict]]:
    """Split text using execution plan from structural analysis."""
    print(f"✂️ Splitting file using execution plan ({len(execution_plan)} chunks specified)")
    chunks = []
    lines = text.split("\n")

    for i, chunk_spec in enumerate(execution_plan):
        chunk_start, start_line = _find_chunk_start(i, chunk_spec, lines, chunks, verbose, text)
        if chunk_start is None:
            continue

        chunk_end = _find_chunk_end(i, chunk_spec, lines, execution_plan, start_line)

        chunk_text = text[chunk_start:chunk_end]
        chunk_id = chunk_spec.get("chunk_id", i + 1)
        description = chunk_spec.get("description", f"Chunk {chunk_id}")

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
            print(f"  • Chunk {chunk_id}: {description[:50]} (lines {start_line}-{end_line}, {chunk_size:,} bytes)")
        elif i == 3:
            print("  • ...")

    print(f"✓ Split into {len(chunks)} chunks")
    return chunks


def _build_and_write_final_output(output_file, input_text, analysis_result, converted_bodies, skip_validation, verbose):
    """Builds the final output file from converted chunks and performs post-processing."""
    print(f"\n{'='*60}")
    print("📋 PHASE 4: MERGING AND WRITING OUTPUT")
    print(f"{'='*60}\n")

    merged_body = "\n\n".join(body.strip() for body in converted_bodies if body.strip())
    print(f"🔗 Merging {len(converted_bodies)} converted chunks")
    print(f"  • Total merged size: {len(merged_body):,} bytes")

    metadata = analysis_result.get("metadata", {})
    grantha_id = metadata.get("grantha_id", "unknown")
    canonical_title = metadata.get("canonical_title", "Unknown")
    commentary_id = metadata.get("commentary_id")
    commentator = metadata.get("commentator")

    validation_hash = hash_text(merged_body)

    frontmatter = {
        "grantha_id": grantha_id,
        "part_num": metadata.get("part_num", 1),
        "canonical_title": canonical_title,
        "text_type": "upanishad",
        "language": "sanskrit",
        "scripts": ["devanagari"],
        "structure_levels": analysis_result.get("structural_analysis", {}).get("structure_levels", {}),
        "validation_hash": validation_hash,
    }
    if commentary_id:
        frontmatter["commentaries_metadata"] = [{"commentary_id": commentary_id, "commentator": commentator or "Unknown", "language": "sanskrit"}]

    frontmatter_yaml = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    final_content = f"---\n{frontmatter_yaml}---\n\n{merged_body}"

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_content)
    print(f"✓ Output written: {output_file}\n")

    # Post-processing
    print("🔒 Hiding editor comments...")
    original_content, modified_content = _hide_editor_comments_in_content(final_content)
    if original_content != modified_content:
        if not _validate_devanagari_unchanged(original_content, modified_content):
            print("❌ Devanagari altered during comment hiding", file=sys.stderr)
            return False
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(modified_content)
        print("✓ Editor comments hidden\n")
    else:
        print("✓ No editor comments found\n")

    if not skip_validation:
        print("✅ Validating Devanagari preservation...")
        input_devanagari = extract_devanagari(input_text)
        output_devanagari = extract_devanagari(modified_content)

        if input_devanagari == output_devanagari:
            print(f"✓ Validation passed: {len(input_devanagari)} Devanagari characters preserved\n")
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
                    min_similarity=0.85,
                    conservative=True,
                    create_backup=True,
                )
                if repair_successful:
                    print(f"✓ {repair_message}\n")
                    with open(output_file, "r", encoding="utf-8") as f:
                        repaired_content = f.read()
                    repaired_body = repaired_content.split("---\n\n", 2)[-1]
                    new_hash = hash_text(repaired_body)
                    repaired_content = repaired_content.replace(f"validation_hash: {validation_hash}", f"validation_hash: {new_hash}", 1)
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(repaired_content)
                    print("✓ Validation hash recalculated\n")
                else:
                    print(f"❌ {repair_message}", file=sys.stderr)
                    return False
            else:
                print(f"❌ Difference too large ({diff} chars) - cannot auto-repair", file=sys.stderr)
                return False

    print(f"✅ CONVERSION COMPLETE: {output_file}")
    return True

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

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        if verbose:
            traceback.print_exc()
        return False

    chunks = _split_and_validate_chunks(input_text, chunking_strategy, verbose)
    if chunks is None:
        return False

    total_chunks = len(chunks)

    converted_bodies, chunk_validations = _convert_all_chunks(chunks, input_file, model, no_diff, show_transliteration, verbose)
    if converted_bodies is None:
        return False

    # Print per-chunk validation summary
    print(f"\n📊 Per-Chunk Devanagari Validation Summary:")
    passed_count = sum(1 for v in chunk_validations if v["status"] == "PASSED")
    failed_count = len(chunk_validations) - passed_count
    print(f"  ✅ Passed: {passed_count}/{len(chunk_validations)}")
    if failed_count > 0:
        print(f"  ⚠️  Mismatches: {failed_count}/{len(chunk_validations)}", file=sys.stderr)
        for v in chunk_validations:
            if v["status"] == "MISMATCH":
                print(f"    • Chunk {v['chunk']} ({v['unit_name']}): {v['input_chars']:,} → {v['output_chars']:,} (diff: {v['diff']:,})", file=sys.stderr)

    return _build_and_write_final_output(output_file, input_text, analysis_result, converted_bodies, skip_validation, verbose)






def _process_file(input_path, output_path, args, models):
    """Processes a single file, from analysis to conversion."""
    _create_log_directory(file_subdir=input_path.stem)

    print(f"\n{'='*60}")
    print(f"🔄 Converting: {input_path.name} -> {output_path.name}")
    print(f"{'='*60}")

    try:
        analysis = analyze_file_structure(
            str(input_path),
            verbose=False,
            use_cache=True,
            use_upload_cache=not args.no_upload_cache,
            force_reanalysis=args.force_analysis,
            model=models['analysis'],
        )
    except Exception as e:
        print(f"❌ File analysis failed for {input_path.name}: {e}", file=sys.stderr)
        return False

    # For directory mode, override metadata with command-line args
    if args.directory:
        analysis_metadata = analysis.get("metadata", {})
        if args.grantha_id:
            analysis_metadata["grantha_id"] = args.grantha_id
        if args.canonical_title:
            analysis_metadata["canonical_title"] = args.canonical_title
        if args.commentary_id:
            analysis_metadata["commentary_id"] = args.commentary_id
        if args.commentator:
            analysis_metadata["commentator"] = args.commentator
        analysis_metadata["part_num"] = _extract_part_number_from_filename(input_path.name)
        analysis["metadata"] = analysis_metadata

    # Display analysis results
    metadata = analysis.get("metadata", {})
    print(f"\n✓ Analysis complete for {input_path.name}:")
    print(f"  📖 Text: {metadata.get('canonical_title', 'Unknown')}")
    print(f"  🆔 ID: {metadata.get('grantha_id', 'unknown')}")
    if metadata.get("commentary_id"):
        print(f"  📝 Commentary: {metadata.get('commentary_id')}")
    print(f"  🏗️ Structure: {metadata.get('structure_type', 'unknown')}")

    try:
        success = convert_with_regex_chunking(
            input_file=str(input_path),
            output_file=str(output_path),
            analysis_result=analysis,
            skip_validation=args.skip_validation,
            no_diff=args.no_diff,
            show_transliteration=args.show_transliteration,
            verbose=False,
            model=models['conversion'],
        )
    except Exception as e:
        print(f"❌ Conversion failed for {input_path.name}: {e}", file=sys.stderr)
        traceback.print_exc()
        return False

    return success

def main():
    colorama_init(autoreset=True)

    parser = argparse.ArgumentParser(
        description="Convert meghamala markdown to Grantha structured markdown using Gemini API",
        epilog="""
Examples:
  # Single file with auto-detected part number
  %(prog)s -i input.md -o output.md

  # Directory mode - converts all files, requires ID and title
  %(prog)s -d sources/upanishads/meghamala/brihadaranyaka/ -o output/ --grantha-id brihadaranyaka-upanishad --canonical-title "बृहदारण्यकोपनिषत्"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-i", "--input", help="Input meghamala markdown file")
    input_group.add_argument("-d", "--directory", help="Input directory containing multiple parts")

    parser.add_argument("-o", "--output", required=True, help="Output file or directory")
    parser.add_argument("--grantha-id", help="Grantha identifier (required for directory mode)")
    parser.add_argument("--canonical-title", help="Canonical Devanagari title (required for directory mode)")
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
        help="Show Harvard-Kyoto transliteration diff in addition to Devanagari diff",
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

    models = {
        'analysis': args.analysis_model or args.model,
        'conversion': args.conversion_model or args.model,
    }

    if args.input:
        input_path = Path(args.input)
        output_path = Path(args.output)
        if output_path.is_dir() or str(output_path).endswith("/"):
            output_path.mkdir(parents=True, exist_ok=True)
            output_path = output_path / (input_path.stem + "_converted.md")
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        success = _process_file(input_path, output_path, args, models)
        return 0 if success else 1

    else: # Directory mode
        if not args.grantha_id or not args.canonical_title:
            parser.error("--grantha-id and --canonical-title are required for directory mode.")

        input_dir = Path(args.directory)
        output_dir = Path(args.output)
        if not input_dir.is_dir():
            print(f"Error: {input_dir} is not a directory", file=sys.stderr)
            return 1
        output_dir.mkdir(parents=True, exist_ok=True)

        parts = _get_directory_parts(input_dir)
        if not parts:
            print(f"Error: No markdown files found in {input_dir}", file=sys.stderr)
            return 1

        print(f"📚 Found {len(parts)} part(s) to convert in {input_dir.name}:")
        for file_path, part_num in parts:
            print(f"   - Part {part_num}: {file_path.name}")
        print()

        failed_parts = []
        for file_path, part_num in parts:
            output_file = output_dir / file_path.name
            if not _process_file(file_path, output_file, args, models):
                failed_parts.append(file_path.name)

        if failed_parts:
            print(f"\n{'='*60}")
            print(f"⚠️  Finished with {len(failed_parts)} failure(s):")
            for filename in failed_parts:
                print(f"  - {filename}")
            return 1
        else:
            print(f"\n{'='*60}")
            print(f"✅ All {len(parts)} parts converted successfully!")
            print(f"Output directory: {output_dir}")
            return 0


if __name__ == "__main__":
    sys.exit(main())
