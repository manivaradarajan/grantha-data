# Meghamala Markdown to Structured Grantha Markdown Converter

## Overview

The `meghamala-md-to-structured-md` tool converts meghamala-format markdown files to structured Grantha Markdown format with proper YAML frontmatter, hierarchical structure, and commentary metadata.

## Installation

```bash
pip install -e .
```

This registers the `meghamala-md-to-structured-md` CLI command.

## Usage

### Basic Command

```bash
meghamala-md-to-structured-md \
    -i input.md \
    -o output.md \
    --grantha-id upanishad-id \
    --canonical-title "Devanagari Title"
```

### With Commentary

```bash
meghamala-md-to-structured-md \
    -i input.md \
    -o output.md \
    --grantha-id kena-upanishad \
    --canonical-title "केनोपनिषत्" \
    --commentary-id kena-rangaramanuja \
    --commentator "रङ्गरामानुजमुनिः"
```

### Options

- `-i/--input`: Input meghamala markdown file (required)
- `-o/--output`: Output structured markdown file (required)
- `--grantha-id`: Grantha identifier (required)
- `--canonical-title`: Canonical Devanagari title (auto-extracted if not provided)
- `--commentary-id`: Commentary identifier (optional)
- `--commentator`: Commentator name in Devanagari (auto-extracted if not provided)
- `--part-num`: Part number for multi-part texts (default: 1)
- `--keep-bold`: Keep bold `**` markup in output (default: remove)
- `-v/--verbose`: Verbose output
- `--skip-validation`: Skip Devanagari validation (not recommended)

## Features

### ✅ Implemented

1. **Structure Detection**
   - Automatically identifies khanda/valli structure
   - Handles flat mantra-only structure
   - Generates hierarchical headers

2. **Metadata Extraction**
   - Auto-extracts Upanishad title
   - Auto-extracts commentator information
   - Hybrid approach: auto-extract + CLI overrides

3. **Content Conversion**
   - Converts mantras with verse numbers
   - Wraps content in `<!-- sanskrit:devanagari -->` blocks
   - Generates sequential references
   - Removes bold markup by default (configurable)

4. **Commentary Handling**
   - Detects commentary sections
   - Adds proper commentary metadata
   - Structures commentary with headers

5. **Validation**
   - Validates Devanagari text preservation
   - Normalizes for comparison (ignores punctuation, digits, whitespace)
   - Reports detailed errors on validation failure

6. **YAML Frontmatter**
   - Generates complete metadata
   - Includes structure_levels
   - Includes commentaries_metadata
   - Calculates SHA256 validation_hash

### ⚠️ Known Limitations

1. **Multi-line Mantras**
   - Currently only recognizes mantras by verse numbers (।१।, ॥२॥, etc.)
   - Multi-line mantras where only the last line has a verse number are not fully supported
   - First lines without verse numbers may be treated as commentary

2. **Metadata Elements**
   - Initial invocations like `**श्रीः**` may not be preserved
   - Alternate titles in parentheses may be skipped
   - These are minor metadata elements, not core content

3. **Format Variations**
   - The meghamala collection has variations across different files
   - Some Upanishads may have unique formatting patterns
   - Manual review of output is recommended

## Testing

Run the test suite:

```bash
# All tests
pytest tools/lib/grantha_converter/test_meghamala_converter.py -v

# Specific test classes
pytest tools/lib/grantha_converter/test_meghamala_converter.py::TestMeghamalaParser -v
pytest tools/lib/grantha_converter/test_meghamala_converter.py::TestIntegration -v
```

**Test Results**: 22 passing, 1 skipped

## Architecture

### Core Modules

1. **`meghamala_converter.py`**
   - `MeghamalaParser`: Parses meghamala markdown format
   - `GranthaMarkdownGenerator`: Generates structured Grantha markdown
   - `convert_meghamala_to_grantha()`: Main conversion function

2. **`devanagari_validator.py`**
   - `extract_devanagari()`: Extracts Devanagari Unicode characters
   - `normalize_devanagari()`: Normalizes for comparison
   - `validate_devanagari_preservation()`: Validates no text loss

3. **`meghamala_cli.py`**
   - CLI argument parsing
   - Metadata extraction and validation
   - File I/O and error handling

### Data Structures

- `MantraPassage`: Represents a verse/mantra with reference
- `CommentarySection`: Represents commentary with associated mantra reference
- `StructureNode`: Hierarchical structure with passages and commentaries

## Examples

### Example 1: Simple Conversion

```bash
meghamala-md-to-structured-md \
    -i sources/upanishads/meghamala/isa/IsAvAsyopaniSat.md \
    -o isa-structured.md \
    --grantha-id isavasya-upanishad \
    --canonical-title "ईशावास्योपनिषत्"
```

### Example 2: With Verbose Output

```bash
meghamala-md-to-structured-md \
    -i sources/upanishads/meghamala/kena/kenopaniSat.md \
    -o kena-structured.md \
    --grantha-id kena-upanishad \
    --canonical-title "केनोपनिषत्" \
    --commentary-id kena-rangaramanuja \
    --commentator "रङ्गरामानुजमुनिः" \
    -v
```

### Example 3: Keep Bold Markup

```bash
meghamala-md-to-structured-md \
    -i input.md \
    -o output.md \
    --grantha-id test-upanishad \
    --canonical-title "Test" \
    --keep-bold
```

## Future Improvements

1. **Multi-line Mantra Support**
   - Implement lookahead parsing to group consecutive bold lines
   - Accumulate lines until verse number is found
   - Treat grouped lines as single mantra

2. **Enhanced Metadata Extraction**
   - Capture initial invocations as prefatory passages
   - Preserve alternate titles in metadata
   - Extract more detailed commentary information

3. **Format-Specific Handlers**
   - Create specialized parsers for different Upanishad formats
   - Add configuration files for format variations
   - Support more complex commentary structures

4. **Quality Assurance**
   - Add manual review mode with diff display
   - Generate conversion reports with statistics
   - Add interactive correction mode

## Contributing

When making changes:

1. Run the test suite to ensure no regressions
2. Add tests for new functionality
3. Update this documentation
4. Run `pip install -e .` to update the CLI command

## License

Part of the grantha-data project.
