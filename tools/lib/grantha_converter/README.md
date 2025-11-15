# Grantha JSON ↔ Markdown Converter

Bidirectional, lossless converter for grantha JSON data to Markdown format, enabling easy proofreading and editing of Sanskrit texts.

## Features

✓ **Lossless bidirectional conversion** - JSON → Markdown → JSON with hash validation
✓ **Arbitrary hierarchy depth** - Handles 1-4+ level hierarchies (Mundaka → Khanda → Mantra, etc.)
✓ **Selective commentary inclusion** - Choose which commentaries to include by ID
✓ **Configurable script output** - Include devanagari, roman, and/or kannada scripts
✓ **Content hash validation** - Detects data loss or corruption during round-trip
✓ **Preserves all metadata** - Complete JSON reconstruction from markdown
✓ **Multi-line text support** - Handles Sanskrit verses spanning multiple lines
✓ **Comprehensive test coverage** - 84 tests including real library data integration tests

## Installation

To use the `grantha-converter` command-line tool, you need to install the package in editable mode from the project root directory. This will make the `grantha-converter` executable available in your shell's PATH.

```bash
# From the project root directory (/Users/maniv/github/grantha-data)
pip install -e .
```

This command will install the `grantha_converter` package and its dependencies, and create the `grantha-converter` and `vishvas-markup-to-structured-markdown` executable scripts.

## Usage

### Vishvas Markup to Structured Markdown Converter

The `vishvas-markup-to-structured-markdown` tool converts Vishvas-style markup files (HTML `<details>`-based Markdown) to the standardized Grantha Markdown format.

#### Features

- Converts HTML `<details>` tags to Grantha Markdown format
- Automatically detects prefatory material
- Handles मूलम् (main text) and टीका (commentary) blocks
- Extracts mantra numbers from Sanskrit text (॥ १ ॥, ॥१॥, etc.)
- Validates output against Grantha Markdown specification
- Preserves Devanagari content integrity

#### Basic Usage

```bash
vishvas-markup-to-structured-markdown \
  -i sources/upanishads/isavasya/isa-vedantadesika/isavasya-vedantadesika.md \
  -o isavasya-converted.md \
  --grantha-id isavasya-upanishad \
  --canonical-title "ईशावास्योपनिषत्" \
  --commentary-id isavasya-vedantadesika \
  --commentator "वेङ्कटनाथः"
```

#### Advanced Options

```bash
# Custom structure (e.g., for Bhagavad Gita shlokas)
vishvas-markup-to-structured-markdown \
  -i input.md \
  -o output.md \
  --grantha-id bhagavad-gita \
  --canonical-title "भगवद्गीता" \
  --commentary-id ramanuja \
  --structure-key Shloka \
  --structure-name "श्लोकः"

# Skip validation (not recommended)
vishvas-markup-to-structured-markdown ... --no-validate

# Verbose output
vishvas-markup-to-structured-markdown ... -v
```

#### Source File Format

The converter expects HTML `<details>`-based Markdown with the following structure:

```markdown
+++
title = "Commentator Name"
+++

<details><summary>टीका</summary>
Prefatory commentary/invocations
</details>

<details open><summary>मूलम्</summary>
Sanskrit mantra text ॥ १ ॥
</details>

<details><summary>टीका</summary>
Commentary on mantra 1
</details>
```

#### Python API

```python
from grantha_converter.html_details_to_grantha_md import convert_file

convert_file(
    input_path='source.md',
    output_path='output.md',
    grantha_id='isavasya-upanishad',
    canonical_title='ईशावास्योपनिषत्',
    commentary_id='isavasya-vedantadesika',
    commentator='वेङ्कटनाथः'
)
```

### Command-Line Interface (JSON ↔ Markdown)

#### Convert JSON to Markdown

```bash
# Basic conversion (core text only, Devanagari script)
python -m tools.grantha_converter.cli json2md \
  -i public/data/library/isavasya-upanishad.json \
  -o isavasya.md

# Include multiple scripts
python -m tools.grantha_converter.cli json2md \
  -i public/data/library/isavasya-upanishad.json \
  -o isavasya.md \
  --scripts devanagari,roman

# Include specific commentary
python -m tools.grantha_converter.cli json2md \
  -i public/data/library/isavasya-upanishad.json \
  -o isavasya-with-commentary.md \
  --commentaries vedanta_desika

# Include ALL commentaries (auto-detected from file)
python -m tools.grantha_converter.cli json2md \
  -i public/data/library/isavasya-upanishad.json \
  -o isavasya-all.md \
  --all-commentaries

# Include multiple specific commentaries
python -m tools.grantha_converter.cli json2md \
  -i public/data/library/katha-upanishad.json \
  -o katha.md \
  --commentaries vedanta-desika,shankara
```

#### Convert Markdown to JSON

```bash
# Convert back to JSON (with validation)
python -m tools.grantha_converter.cli md2json \
  -i isavasya-edited.md \
  -o isavasya-edited.json
```

The MD→JSON conversion automatically validates the content hash to ensure no data loss occurred during editing.

### Python API

```python
from tools.grantha_converter.json_to_md import json_file_to_markdown_file
from tools.grantha_converter.md_to_json import markdown_file_to_json_file

# Convert JSON to Markdown
json_file_to_markdown_file(
    'input.json',
    'output.md',
    scripts=['devanagari', 'roman'],
    commentaries=['vedanta-desika']
)

# Convert Markdown to JSON
markdown_file_to_json_file(
    'output.md',
    'reconstructed.json'
)
```

## Markdown Format

The generated Markdown includes:

1. **YAML Frontmatter** - Complete metadata including validation hash
2. **Nested Headers** - Hierarchical structure (# → ## → ### → ...)
3. **Prefatory Material** - Shanti patha and other introductory content
4. **Main Passages** - Organized by hierarchy with refs
5. **Concluding Material** - Closing sections
6. **Commentaries** (optional) - Commentary text organized by passage
7. **HTML Comments** - Preserve JSON metadata for lossless reconstruction

### Example Markdown Structure

```markdown
---
grantha_id: isavasya-upanishad
canonical_title: ईशावास्योपनिषत्
text_type: upanishad
language: sanskrit
scripts:
- devanagari
structure_levels:
- key: Mantra
validation_hash: sha256:abc123...
---

# Prefatory Material

## शान्तिमन्त्रः

**Sanskrit (Devanagari):** ॐ पूर्णमदः पूर्णमिदं पूर्णात्पूर्णमुदच्यते ।
पूर्णस्य पूर्णमादाय पूर्णमेवावशिष्यते ॥

# Mantra 1

**Sanskrit (Devanagari):** ईशावास्यमिदँ सर्वं यत्किंच जगत्यां जगत् ।
तेन त्यक्तेन भुञ्जीथा मा गृधः कस्यस्विद्धनम् ॥ १
```

## Validation

The converter uses SHA256 content hashing to validate lossless conversion:

- **Whitespace** - Ignored (spaces, newlines, tabs)
- **Punctuation** - Ignored (dandas, commas, periods)
- **Zero-width marks** - Ignored (ZWNJ, ZWJ, etc.)
- **Significant characters** - All Sanskrit and English text content

This allows you to:
- Reformat the markdown (indentation, line breaks)
- Edit whitespace for readability
- **But detects any changes to actual text content**

## Workflow

### Proofreading Sanskrit Texts

1. **Export to Markdown**
   ```bash
   python -m tools.grantha_converter.cli json2md \
     -i public/data/library/katha-upanishad.json \
     -o katha-edit.md
   ```

2. **Edit in your favorite editor** (VSCode, Vim, etc.)
   - Fix typos in Sanskrit text
   - Update translations
   - Add missing content
   - Reformat for readability

3. **Convert back and validate**
   ```bash
   python -m tools.grantha_converter.cli md2json \
     -i katha-edit.md \
     -o public/data/library/katha-upanishad.json
   ```

   ✓ Validation hash verified - no data loss detected

4. **Commit changes**
   ```bash
   git add public/data/library/katha-upanishad.json
   git commit -m "Proofread Katha Upanishad Sanskrit text"
   ```

## Testing

```bash
# Run all tests (84 tests)
python -m pytest tests/grantha_converter_test/ -v

# Run specific test suites
python -m pytest tests/grantha_converter_test/test_hasher.py -v
python -m pytest tests/grantha_converter_test/test_json_to_md.py -v
python -m pytest tests/grantha_converter_test/test_md_to_json.py -v

# Run integration tests on real library files
python -m pytest tests/grantha_converter_test/test_integration.py -v
```

## Test Coverage

- **27 tests** - Content hashing and validation
- **24 tests** - JSON to Markdown conversion
- **18 tests** - Markdown to JSON conversion
- **15 tests** - Integration tests with 7 real library files

**Integration Test Results:** 14/15 library files pass (93%)
- ✓ isavasya-upanishad
- ✓ aitareya-upanishad
- ✓ katha-upanishad
- ✓ kena-upanishad
- ✓ mundaka-upanishad
- ⚠ taittiriya-upanishad (known issue - under investigation)
- ✓ mandukya-rangaramanuja-upanishad

## Architecture

### Core Modules

- **`hasher.py`** - Content hashing with normalization (excludes whitespace, punctuation, zero-width marks)
- **`json_to_md.py`** - JSON → Markdown converter with recursive hierarchy traversal
- **`md_to_json.py`** - Markdown → JSON converter with recursive header parsing
- **`cli.py`** - Command-line interface

### Key Algorithms

**Hierarchy Handling (JSON → MD):**
- Recursively traverse structure_levels tree
- Generate nested markdown headers dynamically (# → ## → ### → ...)
- Group passages by hierarchical path
- Handle arbitrary depth (not limited to 3-4 levels)

**Hierarchy Reconstruction (MD → JSON):**
- Parse headers counting `#` symbols for depth
- Build hierarchy tree from header nesting
- Reconstruct structure_levels from observed patterns
- Extract full refs from header text

**Multi-line Content Parsing:**
- Track current field across lines
- Accumulate continuation lines
- Join with newlines to preserve formatting

## Known Limitations

1. **Taittiriya Upanishad** - One library file has a validation issue under investigation
2. **Script coverage** - Roman and Kannada scripts not extensively tested (most data is Devanagari)
3. **Commentary parsing** - Complex nested commentary structures may need enhancement

## Future Enhancements

- [ ] Investigate taittiriya-upanishad validation issue
- [ ] Add support for parallel text display (side-by-side scripts)
- [ ] Implement diff tool for comparing versions
- [ ] Add batch conversion support for entire directories
- [ ] Create web-based editor with live preview

## License

Part of the Upanishad Explorer project.
