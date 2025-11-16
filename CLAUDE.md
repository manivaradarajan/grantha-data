# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the **grantha-data** repository, a Sanskrit text processing and conversion system focused on Upanishads. The project provides bidirectional, lossless conversion between JSON and Markdown formats for Sanskrit texts, enabling easy proofreading and editing while maintaining data integrity through SHA256 content hashing.

## Project Structure

- **`sources/`**: Source Sanskrit texts (Upanishads) in Markdown format with YAML frontmatter. Each subdirectory represents a text (e.g., `upanishads/brihadaranyaka/`, `upanishads/isavasya/`). Each source includes a `PROVENANCE.yaml` file documenting its origin.
- **`formats/`**: Contains `GRANTHA_MARKDOWN.md`, the official specification for authoring grantha content in Markdown format.
- **`tools/lib/`**: Installable Python packages:
  - `grantha_converter`: Core library for JSON↔Markdown conversion
  - `gemini_processor`: Generic library for Gemini API interactions (file uploads, caching, prompt management, response parsing)
- **`tools/scripts/`**: Standalone utility scripts:
  - `meghamala_converter/`: Converts Meghamala-formatted texts to Grantha Markdown using Gemini API
  - `md2md_converter/`: Generic Markdown-to-Markdown converter using Gemini API
  - `devanagari_tools/`: Tools for Devanagari text comparison and diff visualization

## Installation and Setup

This project uses an editable install pattern. **After creating new libraries or adding command-line entry points, you MUST run:**

```bash
pip install -e .
```

This command must be executed from the project root directory. It updates the Python environment to recognize new files and CLI commands defined in `pyproject.toml`.

## Common Commands

### Running Tests

Tests live alongside the code they test within library packages:

```bash
# Run all grantha_converter tests (84 tests total)
pytest tools/lib/grantha_converter/

# Run all gemini_processor tests (90 tests total)
pytest tools/lib/gemini_processor/

# Run meghamala_converter tests (18 tests)
pytest tools/scripts/meghamala_converter/test_convert_meghamala.py

# Run specific test modules
pytest tools/lib/grantha_converter/test_hasher.py
pytest tools/lib/grantha_converter/test_json_to_md.py
pytest tools/lib/gemini_processor/test_cache_manager.py
pytest tools/lib/gemini_processor/test_prompt_manager.py

# Run a single test
pytest tools/lib/grantha_converter/test_hasher.py::test_normalize_text
```

### Using grantha-converter CLI

The main tool for working with Sanskrit texts:

```bash
# Convert JSON to Markdown (core text only, Devanagari)
grantha-converter json2md -i input.json -o output.md

# Include multiple scripts
grantha-converter json2md -i input.json -o output.md --scripts devanagari,roman

# Include specific commentaries
grantha-converter json2md -i input.json -o output.md --commentaries vedanta-desika

# Include ALL commentaries from source file
grantha-converter json2md -i input.json -o output.md --all-commentaries

# Convert Markdown back to JSON (with automatic hash validation)
grantha-converter md2json -i edited.md -o output.json

# Verify JSON and Markdown are in sync
grantha-converter verify -j input.json -m output.md
```

### Using vishvas-markup-to-structured-markdown

Convert Vishvas-style source files (HTML details-based Markdown) to structured Grantha Markdown:

```bash
# Basic conversion
vishvas-markup-to-structured-markdown \
  -i sources/upanishads/isavasya/isa-vedantadesika/isavasya.md \
  -o isavasya-converted.md \
  --grantha-id isavasya-upanishad \
  --canonical-title "ईशावास्योपनिषत्" \
  --commentary-id isavasya-vedantadesika \
  --commentator "वेङ्कटनाथः"

# With verbose output
vishvas-markup-to-structured-markdown ... -v
```

### Python API Usage

```python
from grantha_converter.json_to_md import json_file_to_markdown_file
from grantha_converter.md_to_json import markdown_file_to_json_file

# JSON → Markdown
json_file_to_markdown_file(
    'input.json',
    'output.md',
    scripts=['devanagari', 'roman'],
    commentaries=['vedanta-desika']
)

# Markdown → JSON
markdown_file_to_json_file('output.md', 'reconstructed.json')
```

## Architecture

### grantha_converter Library

The core conversion system consists of:

- **`hasher.py`**: Content hashing with normalization. Excludes whitespace, punctuation, and zero-width marks to allow formatting changes while detecting text modifications.
- **`json_to_md.py`**: JSON → Markdown converter. Recursively traverses hierarchical structure (Adhyaya → Brahmana → Mantra, etc.) and generates nested markdown headers dynamically. Handles arbitrary depth, not limited to 3-4 levels.
- **`md_to_json.py`**: Markdown → JSON converter. Parses headers by counting `#` symbols for depth, reconstructs hierarchy tree, and validates content hash to ensure lossless round-trip.
- **`cli.py`**: Command-line interface with three subcommands: `json2md`, `md2json`, and `verify`.
- **`grantha_markdown_validator.py`**: Validates Markdown files against the Grantha Markdown specification.
- **`hide_editor_comments.py`**: Utility to control visibility of editorial content using `<!-- hide -->` tags.
- **`diff_utils.py`**: Character-level diff utilities for Devanagari and transliteration comparison.
- **`devanagari_repair.py`**: Automatic repair of small Devanagari mismatches between files.

### gemini_processor Library

Generic library for Gemini API interactions, used by meghamala_converter and other scripts:

- **`file_manager.py`**: File upload with SHA256-based caching to avoid redundant uploads
- **`sampler.py`**: Smart text sampling for large files (first 100KB + middle 50KB + last 50KB)
- **`prompt_manager.py`**: Template system for loading and formatting prompt files
- **`response_parser.py`**: Robust JSON/markdown parsing with error recovery (code fence removal, escape sequence repair)
- **`cache_manager.py`**: Analysis result caching with file hash validation

### meghamala_converter Script

Located in `tools/scripts/meghamala_converter/`, this script converts Meghamala-formatted texts to Grantha Markdown using the Gemini API:

- **Model selection**: Use `--model`, `--analysis-model`, `--conversion-model`, `--metadata-model` to specify different Gemini models for each phase
- **Prompt templates**: All prompts stored in `prompts/` subdirectory
- **Chunking support**: Automatically handles large files by splitting into chunks
- **Devanagari validation**: Ensures Devanagari text is preserved correctly through conversion
- **Caching**: Uses both file upload cache and analysis cache to minimize API calls

### devanagari_diff Tool

Located in `tools/scripts/devanagari_tools/devanagari_diff.py`:

This tool extracts ONLY Devanagari characters from both files (ignoring markdown, YAML frontmatter, etc.) and shows a character-level diff with three colors:
- **RED background**: text deleted from file1
- **GREEN background**: text inserted in file2
- **YELLOW background**: text replaced/changed

Both Devanagari and Harvard-Kyoto transliteration are shown for each difference.

```bash
# Compare Devanagari text between two files
python tools/scripts/devanagari_tools/devanagari_diff.py file1.md file2.md

# Increase context and show more diffs
python tools/scripts/devanagari_tools/devanagari_diff.py file1.md file2.md -c 60 -m 20

# Example: Compare source and converted files
python tools/scripts/devanagari_tools/devanagari_diff.py \
  sources/upanishads/meghamala/kausitaki/kausitaki-1.md \
  structured_md/upanishads/kausitaki/kausitaki-1.md
```

### Grantha Markdown Format

The project uses a specific Markdown format documented in `formats/GRANTHA_MARKDOWN.md`. Key elements:

- **YAML frontmatter**: Contains metadata including `grantha_id`, `part_num`, `canonical_title`, `text_type`, `language`, `structure_levels`, `commentaries_metadata`, and `validation_hash` (SHA256).
- **Three passage types**:
  - Main passages: `# Mantra <ref>`
  - Prefatory material: `# Prefatory: <ref> (devanagari: "<label>")`
  - Concluding material: `# Concluding: <ref> (devanagari: "<label>")`
- **Sanskrit content blocks**: Enclosed in `<!-- sanskrit:devanagari -->` ... `<!-- /sanskrit:devanagari -->`
- **Commentary format**: Uses metadata comment `<!-- commentary: {"commentary_id": "id"} -->` followed by `# Commentary: <ref>`
- **Content hiding**: `<!-- hide -->` ... `<!-- /hide -->` for editorial notes

### Hierarchical Structure

The system handles arbitrary-depth hierarchies:
- Recursively traverse structure_levels tree
- Generate nested markdown headers dynamically (# → ## → ### → ...)
- Group passages by hierarchical path (e.g., Adhyaya 3 → Brahmana 1 → Mantra 1)
- Reconstruct structure_levels from observed header patterns during parsing

### Validation Strategy

- **SHA256 content hashing** validates lossless conversion
- **Normalization** ignores whitespace, punctuation, and zero-width marks
- **Significant characters** include all Sanskrit and English text content
- Allows reformatting (indentation, line breaks) but detects text changes
- **Integration tests** verify round-trip conversion on 7 real Upanishad files (14/15 tests pass; taittiriya-upanishad has a known issue under investigation)

## Development Workflow

### Adding a New Library

1. Create directory: `mkdir tools/lib/my_new_library`
2. Add init file: `touch tools/lib/my_new_library/__init__.py`
3. Add Python modules to the directory
4. Run from project root: `pip install -e .`

### Adding a CLI Command

1. Place code in `tools/lib/your_library/cli.py` with a `main()` function
2. Edit `pyproject.toml` and add to `[project.scripts]`:
   ```toml
   your-command = "your_library.cli:main"
   ```
3. Run from project root: `pip install -e .`

### Test Organization

- **Library tests**: Place in `tools/lib/library_name/test_*.py`
- **Run from project root**: `pytest tools/lib/library_name/`
- Test files should follow the pattern `test_*.py` or `*_test.py`

### Working with Source Files

Source files in `sources/upanishads/` follow the Grantha Markdown format. Each source directory contains:
- One or more `.md` files (for multi-part texts like Brihadaranyaka, use numbered files like `03-01.md`)
- A `PROVENANCE.yaml` file documenting source URL, retrieval date, and notes

## Known Issues

- **taittiriya-upanishad**: One integration test fails validation (under investigation)
- **Script coverage**: Roman and Kannada scripts not extensively tested (most data is Devanagari)
- **Complex commentary structures**: Nested commentaries may need enhancement

## Important Notes

- All files must be UTF-8 encoded
- The `validation_hash` in frontmatter is critical for round-trip verification
- Markdown files are processed in alphabetical order for multi-part texts
- The `part_num` field in frontmatter must be `1` for single-part granthas
- When importing libraries, use: `from grantha_converter import module_name` (not relative paths)
