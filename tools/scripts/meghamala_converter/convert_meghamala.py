#!/usr/bin/env python3
"""
Convert meghamala markdown to Grantha structured markdown using Gemini API.

Usage:
    python convert_meghamala.py \
        -i input.md \
        --output-dir ./output \
        --grantha-id kena-upanishad \
        --canonical-title "केनोपनिषत्"
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
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Final, Optional

# Third-party imports
import yaml
from colorama import Back, Fore, Style
from colorama import init as colorama_init

# Local imports
from gemini_processor.cache_manager import AnalysisCache
from gemini_processor.file_manager import (
    FileUploadCache,
    get_file_hash,
    upload_file_with_cache,
)
from gemini_processor.prompt_manager import PromptManager
from gemini_processor.sampler import create_smart_sample
from google import genai
from google.genai.types import (
    GenerateContentConfig,
    SafetySetting,
    HarmCategory,
    HarmBlockThreshold,
    ThinkingConfig,
)
from grantha_converter.devanagari_repair import extract_devanagari, repair_file
from grantha_converter.devanagari_validator import validate_devanagari_preservation
from grantha_converter.diff_utils import show_devanagari_diff, show_transliteration_diff
from grantha_converter.hasher import hash_text
from grantha_converter.meghamala_chunker import (
    split_by_execution_plan,
)
from grantha_converter.meghamala_stitcher import (
    cleanup_temp_chunks,
    merge_chunks,
    validate_merged_output,
)

# Constants
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent
PROMPTS_DIR = SCRIPT_DIR / "prompts"
LOGS_DIR = Path("logs")  # Save logs in current working directory
UPLOAD_CACHE_FILE = SCRIPT_DIR / ".file_upload_cache.json"

# Reusable config used for Gemini generate_content calls.
GEMINI_CONTENT_CONFIG: Final = GenerateContentConfig(
    safety_settings=[
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
    ],
)

# Initialize prompt manager
prompt_manager = PromptManager(PROMPTS_DIR)

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


def _save_log_file(log_path: Path, content: str):
    """Saves content to a specified path in the log directory."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(content, encoding="utf-8")
        try:
            relative_path = log_path.relative_to(Path.cwd())
        except ValueError:
            relative_path = log_path
        print(f"  💾 Saved: {relative_path}")
    except Exception as e:
        print(f"  ⚠️  Warning: Could not save log file {log_path}: {e}", file=sys.stderr)


def _repair_json_escapes(text: str) -> str:
    """Attempt to repair common JSON escape sequence issues."""
    regex_pattern = r'"regex":\s*"([^"]*)"'

    def fix_regex(match):
        regex_value = match.group(1)
        fixed = regex_value.replace("\\", "\\\\")
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


upload_cache_manager = FileUploadCache(UPLOAD_CACHE_FILE)


def _upload_file_for_analysis(
    client, input_file: Path, use_upload_cache, file_log_dir: Path
):
    """Uploads a file to the Gemini API for analysis, using a cache."""
    cache_manager = upload_cache_manager if use_upload_cache else None
    uploaded_file = upload_file_with_cache(
        client=client,
        file_path=input_file,
        cache_manager=cache_manager,
        verbose=True,
    )

    if uploaded_file:
        analysis_log_dir = file_log_dir / "analysis"
        _save_log_file(
            analysis_log_dir / "00_uploaded_file_info.txt",
            f"File name: {uploaded_file.name}\n"
            f"Display name: {uploaded_file.display_name}\n"
            f"Size: {uploaded_file.size_bytes} bytes\n"
            f"State: {uploaded_file.state}\n"
            f"URI: {uploaded_file.uri}\n",
        )
    else:
        print("   Falling back to text embedding...", file=sys.stderr)

    return uploaded_file


def _prepare_analysis_prompt(
    template_name, full_text, uploaded_file, file_log_dir: Path
):
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

    analysis_log_dir = file_log_dir / "analysis"
    _save_log_file(analysis_log_dir / "01_analysis_prompt.txt", analysis_prompt)
    return analysis_prompt


def _call_gemini_for_analysis(client, model, prompt, uploaded_file, file_log_dir: Path):
    """Calls the Gemini API with the analysis prompt."""
    print("🤖 Calling Gemini API for structural analysis...")
    config = GEMINI_CONTENT_CONFIG
    contents = [prompt]
    if uploaded_file:
        contents.append(uploaded_file)

    response = client.models.generate_content(
        model=model, contents=contents, config=config
    )

    if not response.text:
        raise ValueError("Empty response from Gemini API during file analysis")

    analysis_log_dir = file_log_dir / "analysis"
    _save_log_file(analysis_log_dir / "02_analysis_response_raw.txt", response.text)
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
        print(
            f"\n❌ Error: Could not parse JSON from Gemini response: {e}",
            file=sys.stderr,
        )
        raise ValueError(f"Invalid JSON response from Gemini: {e}")


def _validate_analysis_result(analysis_result):
    """Validates the structure and content of the parsed analysis result."""
    if "metadata" not in analysis_result:
        raise ValueError("Missing 'metadata' section in analysis response")
    if (
        "chunking_strategy" not in analysis_result
        or "parsing_instructions" not in analysis_result
    ):
        raise ValueError(
            "Missing 'chunking_strategy' or 'parsing_instructions' in analysis response"
        )

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
        print(
            f"Warning: Missing recommended_unit in parsing_instructions",
            file=sys.stderr,
        )

    print("✓ Analysis complete")
    execution_plan = chunking_strategy.get("execution_plan", [])
    print(f"  • Chunking: {len(execution_plan)} chunks planned")
    print(
        f"  • Parsing unit: {parsing_instructions.get('recommended_unit', 'unknown')}"
    )


def analyze_file_structure(
    input_file: Path,
    file_log_dir: Path,
    client: genai.Client | None = None,
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

    cached_result, cache = _handle_analysis_cache(
        input_file, force_reanalysis, use_cache, verbose
    )

    if client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Error: GEMINI_API_KEY environment variable not set.")
        client = genai.Client(api_key=api_key)

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            full_text = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Error: Input file not found: {input_file}")

    uploaded_file = _upload_file_for_analysis(
        client, input_file, use_upload_cache, file_log_dir
    )

    analysis_prompt = _prepare_analysis_prompt(
        "full_file_analysis_prompt.txt", full_text, uploaded_file, file_log_dir
    )

    if cached_result:
        print("🚀 Skipping Gemini API call (using cached analysis)")
        analysis_log_dir = file_log_dir / "analysis"
        _save_log_file(
            analysis_log_dir / "03_analysis_result_from_cache.json",
            json.dumps(cached_result, indent=2, ensure_ascii=False),
        )
        return cached_result

    response_text = _call_gemini_for_analysis(
        client, model, analysis_prompt, uploaded_file, file_log_dir
    )

    analysis_result = _parse_analysis_response(response_text)

    _validate_analysis_result(analysis_result)

    if use_cache:
        cache.save(analysis_result, verbose=verbose)

    return analysis_result


def _hide_editor_comments_in_content(content: str) -> tuple[str, str]:
    """Hides editor comments in square brackets with HTML comment tags."""
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


def _extract_part_number_from_filename(filename: str) -> int:
    """Extract part number from filename."""
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

    # Pattern 3: Sanskrit number words
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
    """Get all markdown files in directory sorted by part number."""
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
    text = re.sub(
        r"^```(?:yaml|markdown|md|yml|text)?\s*\n", "", text, flags=re.MULTILINE
    )
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def create_chunk_conversion_prompt(analysis_result: dict) -> str:
    """Creates the prompt for chunk conversion."""
    try:
        continuation_template = prompt_manager.load_template(
            "chunk_continuation_prompt.txt"
        )
        print(f"  📄 Using prompt: chunk_continuation_prompt.txt")

        metadata = analysis_result.get("metadata", {})
        commentary_id = metadata.get("commentary_id")
        if not commentary_id:
            commentary_id = "prakasika"

        # Convert the analysis result to a JSON string for injection into the prompt
        analysis_json = json.dumps(analysis_result, indent=2, ensure_ascii=False)

        return continuation_template.format(
            commentary_id=commentary_id, analysis_json=analysis_json
        )
    except Exception as e:
        print(f"Error creating chunk conversion prompt: {e}", file=sys.stderr)
        traceback.print_exc()
        raise


def _convert_single_chunk(
    client: genai.Client,
    chunk_text: str,
    chunk_metadata: dict,
    model: str,
    analysis_result: dict,
    file_log_dir: Path,
    use_upload_cache: bool,
) -> str:
    """Calls the Gemini API to convert a single chunk of text using the File API."""
    chunk_index = chunk_metadata.get("chunk_index")
    chunk_log_dir = file_log_dir / "chunks" / f"chunk_{chunk_index}"

    temp_chunk_dir = Path(tempfile.gettempdir()) / "grantha_temp_chunks"
    temp_chunk_dir.mkdir(exist_ok=True)
    temp_file_path = temp_chunk_dir / f"chunk_{chunk_index}.md"

    try:
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(chunk_text)

        cache_manager = upload_cache_manager if use_upload_cache else None
        uploaded_chunk_file = upload_file_with_cache(
            client=client,
            file_path=temp_file_path,
            cache_manager=cache_manager,
            verbose=True,
        )

        if not uploaded_chunk_file:
            raise ValueError(f"Failed to upload chunk {chunk_index} to File API.")

        _save_log_file(
            chunk_log_dir / "00_uploaded_chunk_info.txt",
            f"File name: {uploaded_chunk_file.name}\n"
            f"Display name: {uploaded_chunk_file.display_name}\n"
            f"Size: {uploaded_chunk_file.size_bytes} bytes\n"
            f"State: {uploaded_chunk_file.state}\n"
            f"URI: {uploaded_chunk_file.uri}\n",
        )

        prompt = create_chunk_conversion_prompt(analysis_result)
        _save_log_file(chunk_log_dir / "01_chunk_input.md", chunk_text)
        _save_log_file(chunk_log_dir / "02_conversion_prompt.txt", prompt)

        config = GEMINI_CONTENT_CONFIG
        contents = [prompt, uploaded_chunk_file]
        response = client.models.generate_content(
            model=model, contents=contents, config=config
        )

        if not response.text:
            raise ValueError("Empty response from Gemini API during chunk conversion")

        _save_log_file(chunk_log_dir / "03_conversion_response_raw.txt", response.text)
        converted_body = _strip_code_fences(response.text)
        _save_log_file(chunk_log_dir / "04_converted_body.md", converted_body)

        return converted_body
    finally:
        if temp_file_path.exists():
            temp_file_path.unlink()


def _validate_chunk_devanagari(
    chunk_text: str,
    converted_body: str,
    chunk_metadata: dict,
    file_log_dir: Path,
    no_diff: bool,
    show_transliteration: bool,
) -> dict:
    """Validates Devanagari preservation for a single chunk."""
    chunk_index = chunk_metadata.get("chunk_index")
    assert chunk_index
    chunk_log_dir = file_log_dir / "chunks" / f"chunk_{chunk_index}"

    def save_diff_log(filename: str, content: str, subdir: str | None = None):
        log_path = chunk_log_dir / filename
        _save_log_file(log_path, content)

    description = chunk_metadata.get("description")
    input_devanagari = extract_devanagari(chunk_text)
    output_devanagari = extract_devanagari(converted_body)

    validation_status = "PASSED"
    diff_chars = 0
    if input_devanagari != output_devanagari:
        validation_status = "MISMATCH"
        diff_chars = abs(len(input_devanagari) - len(output_devanagari))
        print(
            f"  ⚠️  Devanagari mismatch in chunk {chunk_index} ({len(input_devanagari)} -> {len(output_devanagari)} chars, diff: {diff_chars})",
            file=sys.stderr,
        )
        if not no_diff:
            show_devanagari_diff(input_devanagari, output_devanagari)
            if show_transliteration:
                show_transliteration_diff(
                    input_devanagari, output_devanagari, chunk_index, save_diff_log
                )
    else:
        print(f"  ✓ Devanagari preserved ({len(input_devanagari)} chars)")

    return {
        "chunk_index": chunk_index,
        "description": description,
        "status": validation_status,
        "input_chars": len(input_devanagari),
        "output_chars": len(output_devanagari),
        "char_diff": diff_chars,
    }


def _convert_all_chunks(
    client: genai.Client,
    chunks: list[tuple[str, dict]],
    analysis_result: dict,
    file_log_dir: Path,
    model: str,
    no_diff: bool,
    show_transliteration: bool,
    verbose: bool,
    use_upload_cache: bool,
) -> tuple[list[str] | None, list[dict] | None]:
    """Orchestrates the conversion of all chunks, saving each to a temp file."""
    print(f"\n{'='*60}")
    print(f"📋 PHASE 3: CONVERTING {len(chunks)} CHUNKS WITH GEMINI")
    print(f"{'='*60}\n")

    temp_dir = tempfile.mkdtemp(prefix="grantha_chunks_")
    print(f"  📦 Created temporary chunk directory: {temp_dir}")

    temp_file_paths = []
    chunk_validations = []
    main_metadata = analysis_result.get("metadata", {})

    for i, (chunk_text, chunk_metadata) in enumerate(chunks):
        display_chunk_index = i + 1
        chunk_metadata["chunk_index"] = display_chunk_index

        description = chunk_metadata.get("description", f"Chunk {display_chunk_index}")
        print(
            f"🔄 Converting chunk {display_chunk_index}/{len(chunks)}: {description[:70]}..."
        )

        try:
            converted_body = _convert_single_chunk(
                client=client,
                chunk_text=chunk_text,
                chunk_metadata=chunk_metadata,
                model=model,
                analysis_result=analysis_result,
                file_log_dir=file_log_dir,
                use_upload_cache=use_upload_cache,
            )

            # --- UPDATE: Add Commentator and Colophon to Frontmatter ---
            commentaries_metadata = []
            if main_metadata.get("commentary_id"):
                commentaries_metadata.append(
                    {
                        "commentary_id": main_metadata.get("commentary_id"),
                        "commentator": main_metadata.get("commentator"),
                        "authored_colophon": main_metadata.get("authored_colophon"),
                    }
                )

            chunk_frontmatter = {
                "grantha_id": main_metadata.get("grantha_id"),
                "part_num": main_metadata.get("part_num", 1),
                "canonical_title": main_metadata.get("canonical_title"),
                "structure_type": main_metadata.get("structure_type"),
                "commentaries_metadata": (
                    commentaries_metadata if commentaries_metadata else None
                ),
                "structure_levels": analysis_result.get("structural_analysis", {}).get(
                    "structure_levels", {}
                ),
            }
            chunk_frontmatter = {
                k: v for k, v in chunk_frontmatter.items() if v is not None
            }

            frontmatter_yaml = yaml.dump(
                chunk_frontmatter, allow_unicode=True, sort_keys=False
            )
            full_chunk_content = f"---\n{frontmatter_yaml}---\n\n{converted_body}"

            temp_file = Path(temp_dir) / f"chunk_{i:03d}.md"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(full_chunk_content)
            temp_file_paths.append(str(temp_file))

            validation_result = _validate_chunk_devanagari(
                chunk_text,
                converted_body,
                chunk_metadata,
                file_log_dir,
                no_diff,
                show_transliteration,
            )
            chunk_validations.append(validation_result)

        except Exception as e:
            print(
                f"❌ Error converting chunk {chunk_metadata.get('chunk_index')}: {e}",
                file=sys.stderr,
            )
            traceback.print_exc()
            cleanup_temp_chunks(temp_file_paths, verbose=True)
            return None, None

    return temp_file_paths, chunk_validations


def convert_with_regex_chunking(
    client: genai.Client,
    input_file: str,
    output_file: str,
    analysis_result: dict,
    file_log_dir: Path,
    skip_validation: bool = False,
    no_diff: bool = False,
    show_transliteration: bool = False,
    verbose: bool = False,
    model: str = DEFAULT_GEMINI_MODEL,
    use_upload_cache: bool = True,
) -> bool:
    """Convert file using analysis-driven execution plan chunking."""
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return False

    # --- PHASE 1: CHUNKING ---
    chunking_strategy = analysis_result.get("chunking_strategy", {})
    execution_plan = chunking_strategy.get("execution_plan", [])

    if not execution_plan:
        print("❌ No execution plan found in analysis result.", file=sys.stderr)
        return False

    print(f"✂️ Splitting file using execution plan ({len(execution_plan)} chunks)...")
    chunks = split_by_execution_plan(input_text, execution_plan, verbose=verbose)

    if not chunks:
        print("❌ Could not split file into chunks.", file=sys.stderr)
        return False

    if len(chunks) != len(execution_plan):
        print(
            f"⚠️ Warning: Expected {len(execution_plan)} chunks but got {len(chunks)}.",
            file=sys.stderr,
        )

    # --- PHASE 2: CONVERSION ---
    temp_file_paths, chunk_validations = _convert_all_chunks(
        client=client,
        chunks=chunks,
        analysis_result=analysis_result,
        file_log_dir=file_log_dir,
        model=model,
        no_diff=no_diff,
        show_transliteration=show_transliteration,
        verbose=verbose,
        use_upload_cache=use_upload_cache,
    )
    if not temp_file_paths:
        print("❌ Chunk conversion failed.", file=sys.stderr)
        return False

    if chunk_validations:
        print(f"\n{'='*60}")
        print("📋 CHUNK VALIDATION SUMMARY")
        print(f"{'='*60}")

        descriptions = [(v.get("description") or "") for v in chunk_validations]
        max_desc_len = max(len(d) for d in descriptions) if descriptions else 20
        max_desc_len = min(max(max_desc_len, 20), 50)

        header = f"| {'Chunk':<5} | {'Status':<8} | {'Input':>7} | {'Output':>7} | {'Diff':>5} | {'Description':<{max_desc_len}} |"
        print(header)
        print(f"|{'-'*7}|{'-'*10}|{'-'*9}|{'-'*9}|{'-'*7}|{'-'*(max_desc_len+2)}|")

        total_diff = 0
        for i, v in enumerate(chunk_validations):
            status = v.get("status", "N/A")
            status_color = (
                Fore.YELLOW
                if status == "MISMATCH"
                else Fore.GREEN if status == "PASSED" else ""
            )
            diff = v.get("char_diff", 0)
            total_diff += diff
            desc = descriptions[i] if i < len(descriptions) else ""
            if len(desc) > max_desc_len:
                desc = desc[: max_desc_len - 3] + "..."

            row = (
                f"| {v.get('chunk_index', ''):<5} "
                f"| {status_color}{status:<8}{Style.RESET_ALL} "
                f"| {v.get('input_chars', ''):>7} "
                f"| {v.get('output_chars', ''):>7} "
                f"| {diff:>5} "
                f"| {desc:<{max_desc_len}} |"
            )
            print(row)

        print(f"|{'-'*7}|{'-'*10}|{'-'*9}|{'-'*9}|{'-'*7}|{'-'*(max_desc_len+2)}|")
        print(f"Total Devanagari Character Difference: {total_diff}")

    # --- PHASE 3: STITCHING ---
    print(f"\n{'='*60}")
    print("📋 PHASE 4: MERGING AND WRITING OUTPUT")
    print(f"{'='*60}\n")
    success, merged_content, message = merge_chunks(temp_file_paths, verbose=verbose)
    if not success:
        print(f"❌ Merging failed: {message}", file=sys.stderr)
        cleanup_temp_chunks(temp_file_paths, verbose=True)
        return False
    print(f"✓ {message}")

    if merged_content is None:
        print("❌ Merging failed: No content returned", file=sys.stderr)
        cleanup_temp_chunks(temp_file_paths, verbose=True)
        return False
    print(f"✓ Merging complete: {len(merged_content)} characters")

    # --- PHASE 4: VALIDATION AND REPAIR ---
    if not skip_validation:
        is_valid, validation_message = validate_merged_output(
            input_text, merged_content
        )
        if is_valid:
            print(f"✓ {validation_message}\n")
        else:
            print(f"⚠️  {validation_message}", file=sys.stderr)
            pre_repair_diff_match = re.search(
                r"(\d+) character difference", validation_message
            )
            pre_repair_diff = (
                int(pre_repair_diff_match.group(1))
                if pre_repair_diff_match
                else float("inf")
            )

            repair_log_dir = file_log_dir / "repair"
            _save_log_file(repair_log_dir / "01_pre_repair_output.md", merged_content)

            print("   Attempting repair...")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(merged_content)

            repair_successful, repair_message = repair_file(
                input_file=input_file,
                output_file=output_file,
                max_diff_size=2000,
                skip_frontmatter=False,
                verbose=verbose,
                dry_run=False,
                min_similarity=0.80,
                conservative=True,
                create_backup=True,
            )

            if repair_successful:
                repaired_content = Path(output_file).read_text(encoding="utf-8")
                _save_log_file(
                    repair_log_dir / "02_post_repair_output.md", repaired_content
                )
                post_is_valid, post_validation_message = validate_merged_output(
                    input_text, repaired_content
                )
                post_repair_diff = 0
                if not post_is_valid:
                    post_repair_diff_match = re.search(
                        r"(\d+) character difference", post_validation_message
                    )
                    post_repair_diff = (
                        int(post_repair_diff_match.group(1))
                        if post_repair_diff_match
                        else float("inf")
                    )

                if post_repair_diff < pre_repair_diff:
                    print(
                        f"✓ Repair accepted: Diff improved {pre_repair_diff} -> {post_repair_diff}."
                    )
                    merged_content = repaired_content
                else:
                    print(f"⚠️  Repair rejected: Diff did not improve. Reverting.")
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(merged_content)
            else:
                print(f"❌ {repair_message}", file=sys.stderr)
                cleanup_temp_chunks(temp_file_paths, verbose=True)
                return False

    # Final write
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(merged_content)
    print(f"✓ Output written to {output_file}")
    cleanup_temp_chunks(temp_file_paths, verbose=verbose)
    print(f"\n✅ CONVERSION COMPLETE: {output_file}")
    return True


def _process_file(
    input_path: Path,
    output_dir: Path,
    args,
    models,
    filename_override: Optional[str] = None,
):
    """Processes a single file, from analysis to conversion."""
    file_log_dir = get_file_log_dir(input_path.stem)

    # Save the input file to the log directory.
    _save_log_file(
        file_log_dir / "input_file.md",
        input_path.read_text(encoding="utf-8"),
    )

    print(f"\n{'='*60}")
    print(f"🔄 Processing: {input_path.name}")
    print(f"{'='*60}")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        return False
    client = genai.Client(api_key=api_key)

    try:
        analysis = analyze_file_structure(
            client=client,
            input_file=input_path,
            file_log_dir=file_log_dir,
            verbose=False,
            use_cache=True,
            use_upload_cache=not args.no_upload_cache,
            force_reanalysis=args.force_analysis,
            model=models["analysis"],
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
        analysis_metadata["part_num"] = _extract_part_number_from_filename(
            input_path.name
        )
        analysis["metadata"] = analysis_metadata

    # --- DETERMINE OUTPUT PATH ---
    # If an override was provided (via -o in single mode), use it.
    # Otherwise, look for 'suggested_filename' in the analysis.
    # Fallback to input_stem_converted.md if neither exists.
    if filename_override:
        final_filename = filename_override
    else:
        suggestion = analysis.get("structural_analysis", {}).get("suggested_filename")
        if suggestion:
            final_filename = f"{suggestion}.md"
        else:
            final_filename = f"{input_path.stem}_converted.md"

    # Handle case where filename_override might be a full path (from -o)
    if filename_override and Path(filename_override).is_absolute():
        final_output_path = Path(filename_override)
    elif filename_override and os.sep in filename_override:
        final_output_path = Path(filename_override)
    else:
        final_output_path = output_dir / final_filename

    print(f"🎯 Target Output: {final_output_path}")

    # Display analysis results
    metadata = analysis.get("metadata", {})
    print(f"\n✓ Analysis complete for {input_path.name}:")
    print(f"  📖 Text: {metadata.get('canonical_title', 'Unknown')}")
    print(f"  🆔 ID: {metadata.get('grantha_id', 'unknown')}")
    if metadata.get("commentary_id"):
        print(f"  📝 Commentary: {metadata.get('commentary_id')}")

    chunking_strategy = analysis.get("chunking_strategy", {})
    execution_plan = chunking_strategy.get("execution_plan", [])
    num_chunks = len(execution_plan)

    if num_chunks > 0:
        chunk_lengths = [c.get("estimated_character_count", 0) for c in execution_plan]
        valid_lengths = [l for l in chunk_lengths if l > 0]
        if valid_lengths:
            avg_chunk_len = sum(valid_lengths) / len(valid_lengths)
            proposed_strategy = chunking_strategy.get("proposed_strategy", {})
            target_chars = proposed_strategy.get("safety_character_limit", "N/A")
            print(f"  📦 Strategy: {num_chunks} chunks (Target: {target_chars} chars)")
            print(
                f"    • Est. Lengths: Min={min(valid_lengths)}, Max={max(valid_lengths)}, Avg={avg_chunk_len:.0f}"
            )

    try:
        success = convert_with_regex_chunking(
            client=client,
            input_file=str(input_path),
            output_file=str(final_output_path),
            analysis_result=analysis,
            file_log_dir=file_log_dir,
            skip_validation=args.skip_validation,
            no_diff=args.no_diff,
            show_transliteration=args.show_transliteration,
            verbose=False,
            model=models["conversion"],
            use_upload_cache=not args.no_upload_cache,
        )
    except Exception as e:
        print(f"❌ Conversion failed for {input_path.name}: {e}", file=sys.stderr)
        traceback.print_exc()
        return False

    return success


def main():
    colorama_init(autoreset=True)
    run_log_dir = get_run_log_dir()
    sys.stdout = Tee(sys.stdout, run_log_dir / "stdout.log")
    sys.stderr = Tee(sys.stderr, run_log_dir / "stderr.log")
    print(f"📁 Logging to: {run_log_dir}")

    parser = argparse.ArgumentParser(
        description="Convert meghamala markdown to Grantha structured markdown using Gemini API",
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

    # Changed: -o is now optional and specific to filename override
    parser.add_argument(
        "-o", "--output", help="Explicit output filename (overrides auto-naming)"
    )
    # Added: --output-dir for target directory
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
        "analysis": args.analysis_model or args.model,
        "conversion": args.conversion_model or args.model,
    }

    # Prepare Output Directory
    output_dir = Path(args.output_dir)
    # If user passed -o directory/filename.md, we treat that as absolute/relative override.
    # If -o is just filename.md, we combine with output_dir.
    # In directory mode, -o is treated as the output directory if provided (for backward compatibility)
    # or better, mapped to --output-dir if provided?
    # Let's stick to the parser logic: args.output_dir is the folder.

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    if args.input:
        input_path = Path(args.input)
        filename_override = args.output  # Might be None

        # Case: user used -o for directory in previous version?
        # Current logic: -o is filename.
        # Check if -o looks like a directory (ends in slash or is existing dir)
        if args.output and (args.output.endswith(os.sep) or Path(args.output).is_dir()):
            print(
                f"⚠️  Warning: -o/--output '{args.output}' looks like a directory but is now treated as a filename override.",
                file=sys.stderr,
            )
            print(f"   Please use --output-dir for directories.", file=sys.stderr)

        success = _process_file(
            input_path, output_dir, args, models, filename_override=filename_override
        )
        return 0 if success else 1

    else:  # Directory mode
        input_dir = Path(args.directory)
        if not input_dir.is_dir():
            print(f"Error: {input_dir} is not a directory", file=sys.stderr)
            return 1

        # In Directory Mode, if -o is provided, we treat it as output_dir to maintain some backward compatibility
        # or strict override? Strict override implies one file, which doesn't work for directory input.
        # Let's map -o to output_dir if provided and output_dir is default.
        if args.output:
            if args.output_dir == ".":
                output_dir = Path(args.output)
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                print(
                    f"⚠️  Warning: Both -o and --output-dir provided in directory mode. Ignoring -o.",
                    file=sys.stderr,
                )

        parts = _get_directory_parts(input_dir)
        if not parts:
            print(f"Error: No markdown files found in {input_dir}", file=sys.stderr)
            return 1

        # Infer metadata logic (same as before)
        if not args.grantha_id or not args.canonical_title:
            print(
                "\n🔍 No --grantha-id or --canonical-title provided. Inferring from first file..."
            )
            first_file_path, _ = parts[0]
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                print(
                    "Error: GEMINI_API_KEY environment variable not set.",
                    file=sys.stderr,
                )
                return 1
            client = genai.Client(api_key=api_key)
            first_file_log_dir = get_file_log_dir(first_file_path.stem)

            try:
                analysis = analyze_file_structure(
                    client=client,
                    input_file=first_file_path,
                    file_log_dir=first_file_log_dir,
                    force_reanalysis=args.force_analysis,
                    model=models["analysis"],
                    use_cache=True,
                    use_upload_cache=not args.no_upload_cache,
                )
                inferred_metadata = analysis.get("metadata", {})
                if not args.grantha_id:
                    args.grantha_id = inferred_metadata.get("grantha_id")
                if not args.canonical_title:
                    args.canonical_title = inferred_metadata.get("canonical_title")

                if not args.grantha_id or not args.canonical_title:
                    print(
                        f"❌ Error: Could not infer metadata from {first_file_path.name}.",
                        file=sys.stderr,
                    )
                    return 1
                print(f"  ✓ Inferred grantha_id: {args.grantha_id}")
                print(f"  ✓ Inferred canonical_title: {args.canonical_title}")
            except Exception as e:
                print(f"❌ Analysis of first file failed: {e}", file=sys.stderr)
                return 1

        print(f"\n📚 Found {len(parts)} part(s) to convert in {input_dir.name}")
        failed_parts = []
        for file_path, part_num in parts:
            # We pass None for filename_override so each file gets auto-named based on analysis
            if not _process_file(
                file_path, output_dir, args, models, filename_override=None
            ):
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
