# Meghamala to Grantha Markdown Converter (Gemini API)

This tool uses Google's Gemini API to intelligently convert meghamala-format markdown files to structured Grantha Markdown format.

## Why Gemini API?

The meghamala format has many variations and edge cases (multi-line mantras, complex commentary structures, different organizational patterns across Upanishads). Using Gemini API provides:

- **Intelligent parsing**: Handles multi-line mantras, complex structures
- **Context understanding**: Properly separates mantras from commentary
- **Format flexibility**: Adapts to variations across different Upanishads
- **High accuracy**: Better than rule-based parsers for complex cases

## Prerequisites

1. **Install dependencies:**
```bash
pip install google-generativeai
```

2. **Set up Gemini API key:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

Get your API key from: https://aistudio.google.com/app/apikey

## Usage

### Single File Conversion

```bash
# Basic conversion (part number auto-detected from filename)
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -i sources/upanishads/meghamala/kena/kenopaniSat.md \
    -o kena-structured.md \
    --grantha-id kena-upanishad \
    --canonical-title "केनोपनिषत्"
```

### With Commentary

```bash
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -i sources/upanishads/meghamala/kena/kenopaniSat.md \
    -o kena-structured.md \
    --grantha-id kena-upanishad \
    --canonical-title "केनोपनिषत्" \
    --commentary-id kena-rangaramanuja \
    --commentator "रङ्गरामानुजमुनिः"
```

### Directory Mode - Convert All Parts

**NEW!** Convert entire multi-part granthas automatically:

```bash
# Convert all parts in directory (part numbers auto-detected)
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -d sources/upanishads/meghamala/brihadaranyaka/ \
    -o output/brihadaranyaka/ \
    --grantha-id brihadaranyaka-upanishad \
    --canonical-title "बृहदारण्यकोपनिषत्" \
    --commentary-id brihadaranyaka-rangaramanuja \
    --commentator "रङ्गरामानुजमुनिः"
```

This will:
- Find all `.md` files in the directory
- Auto-detect part numbers from filenames
- Convert each part with correct `part_num` in frontmatter
- Output files as `brihadaranyaka-upanishad-part-01.md`, `part-02.md`, etc.
- All parts share the same `grantha_id`

### Override Part Number

```bash
# Manually specify part number (ignores filename pattern)
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -i some-file.md \
    -o output.md \
    --grantha-id test-upanishad \
    --canonical-title "Test" \
    --part-num 5
```

## Command-line Options

| Option | Required | Description |
|--------|----------|-------------|
| `-i, --input` | Either -i or -d | Input meghamala markdown file |
| `-d, --directory` | Either -i or -d | Input directory with multiple parts |
| `-o, --output` | Yes | Output file or directory |
| `--grantha-id` | Yes | Grantha identifier (shared by all parts) |
| `--canonical-title` | Yes | Canonical Devanagari title |
| `--commentary-id` | No | Commentary identifier (used in ALL `<!-- commentary: ... -->` blocks) |
| `--commentator` | No | Commentator name in Devanagari |
| `--part-num` | No | Part number (auto-detected if not specified) |
| `--skip-validation` | No | Skip Devanagari validation |

## Commentary ID Consistency

When you provide `--commentary-id`, the script ensures that **every commentary block** in the output uses this exact ID consistently in the HTML comment metadata:

```markdown
<!-- commentary: {"commentary_id": "your-provided-id"} -->

### Commentary: 1.1

<!-- sanskrit:devanagari -->
commentary text
<!-- /sanskrit:devanagari -->
```

**Why this matters:**
- All commentary sections for a given text should use the same `commentary_id`
- This ID links the commentary to its metadata in the frontmatter
- The Gemini API is explicitly instructed to use your provided ID in every commentary block
- No other commentary IDs will be used or generated

**Example:**
```bash
--commentary-id brihadaranyaka-rangaramanuja
```
Results in ALL commentary blocks having:
```markdown
<!-- commentary: {"commentary_id": "brihadaranyaka-rangaramanuja"} -->
```

## Part Number Detection

The script automatically detects part numbers from filenames. Supported patterns:

| Filename Pattern | Detected Part | Example |
|------------------|---------------|---------|
| `XX-YY.md` | YY | `03-01.md` → part 1 |
| `name-XX.md` | XX | `brihadaranyaka-03.md` → part 3 |
| `XX.md` | XX | `05.md` → part 5 |
| `part-X.md` | X | `part-2.md` → part 2 |
| Other | 1 | `kenopanishad.md` → part 1 (default) |

**Important for Multi-part Granthas:**
- All parts of a grantha share the same `grantha_id`
- Each part has a unique `part_num` (1, 2, 3, ...)
- In directory mode, parts are automatically sorted by part number
- Output filenames: `{grantha-id}-part-{NN}.md`

## What It Does

1. **Reads input file**: Loads the meghamala markdown
2. **Creates conversion prompt**: Generates a detailed prompt for Gemini
3. **Calls Gemini API**: Sends prompt and gets structured markdown
4. **Calculates hash**: Computes SHA256 validation hash for content
5. **Validates**: Ensures no Devanagari text was lost in conversion

## Output Format

The tool generates Grantha Markdown with:

- ✅ Complete YAML frontmatter with all metadata
- ✅ Hierarchical structure (Khanda/Valli → Mantras)
- ✅ Multi-line mantras properly combined
- ✅ Commentary properly separated and attributed
- ✅ All Sanskrit wrapped in `<!-- sanskrit:devanagari -->` blocks
- ✅ Bold markup removed from content
- ✅ Sequential reference numbering
- ✅ SHA256 validation hash

## Validation

The tool automatically validates that:
- All Devanagari characters from input are preserved in output
- Normalization accounts for punctuation and formatting changes
- Any text loss is reported with detailed error messages

If validation fails, **review the output manually** before using it.

## Batch Conversion

### Directory Mode (Recommended)

Convert all parts of a multi-part grantha in one command:

```bash
# Brihadaranyaka (6 parts)
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -d sources/upanishads/meghamala/brihadaranyaka/ \
    -o output/brihadaranyaka/ \
    --grantha-id brihadaranyaka-upanishad \
    --canonical-title "बृहदारण्यकोपनिषत्" \
    --commentary-id brihadaranyaka-rangaramanuja \
    --commentator "रङ्गरामानुजमुनिः"
```

Output:
```
📚 Found 6 part(s) to convert:
   Part 1: 03-01.md
   Part 2: 03-02.md
   Part 3: 03-03.md
   Part 4: 03-04.md
   Part 5: 04-01.md
   Part 6: 05-01.md

🔄 Converting part 1/6...
📖 Reading input: sources/upanishads/meghamala/brihadaranyaka/03-01.md
📝 Creating conversion prompt...
🤖 Calling Gemini API...
✓ Gemini response written to output/brihadaranyaka/brihadaranyaka-upanishad-part-01.md
🔢 Calculating validation hash...
✓ Validation hash calculated: a1b2c3d4...
✓ Validating Devanagari preservation...
✓ Devanagari validation passed - no text loss
✅ Conversion complete: output/brihadaranyaka/brihadaranyaka-upanishad-part-01.md

[... repeats for parts 2-6 ...]

============================================================
✅ All 6 parts converted successfully!
Output directory: output/brihadaranyaka/
```

### Convert Multiple Granthas

Use a shell script to convert multiple granthas:

```bash
#!/bin/bash

declare -A granthas=(
    ["brihadaranyaka"]="बृहदारण्यकोपनिषत्"
    ["chandogya"]="छान्दोग्योपनिषत्"
    ["taittiriya"]="तैत्तिरीयोपनिषत्"
)

for grantha in "${!granthas[@]}"; do
    echo "Converting ${grantha}..."
    python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
        -d "sources/upanishads/meghamala/${grantha}/" \
        -o "output/${grantha}/" \
        --grantha-id "${grantha}-upanishad" \
        --canonical-title "${granthas[$grantha]}" \
        --commentary-id "${grantha}-rangaramanuja" \
        --commentator "रङ्गरामानुजमुनिः"
done
```

## Cost Considerations

Gemini API pricing (as of 2025):
- **gemini-2.0-flash-exp**: Free tier available, very affordable
- Typical Upanishad file: ~5,000-15,000 input tokens
- Cost per conversion: < $0.01 USD (free in most cases)

The free tier is sufficient for converting the entire meghamala collection.

## Troubleshooting

### API Key Issues
```bash
# Check if API key is set
echo $GEMINI_API_KEY

# Set it in current session
export GEMINI_API_KEY="your-key"

# Or add to ~/.bashrc or ~/.zshrc for permanence
echo 'export GEMINI_API_KEY="your-key"' >> ~/.bashrc
```

### Validation Failures

If Devanagari validation fails:
1. Check the error message for details
2. Manually compare input and output
3. If it's a false positive (e.g., intentional normalization), use `--skip-validation`
4. If real text is missing, file an issue with the input file for prompt improvement

### Import Errors

```bash
# Ensure grantha_converter is installed
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/grantha-data/tools/lib"
```

## Quality Review Checklist

After conversion, manually verify:
- [ ] All mantras present and correctly numbered
- [ ] Multi-line mantras properly combined
- [ ] Commentary correctly separated from mantras
- [ ] Structure levels match document organization
- [ ] Prefatory/concluding passages identified
- [ ] No bold `**` markup in content
- [ ] All Sanskrit in comment blocks
- [ ] YAML frontmatter valid

## Examples

### Example 1: Single-part Upanishad (Kena)

```bash
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -i sources/upanishads/meghamala/kena/kenopaniSat.md \
    -o kena-structured.md \
    --grantha-id kena-upanishad \
    --canonical-title "केनोपनिषत्" \
    --commentary-id kena-rangaramanuja \
    --commentator "रङ्गरामानुजमुनिः"
```

Output:
```
📍 Auto-detected part number: 1
📖 Reading input: sources/upanishads/meghamala/kena/kenopaniSat.md
📝 Creating conversion prompt...
🤖 Calling Gemini API...
✓ Gemini response written to kena-structured.md
🔢 Calculating validation hash...
✓ Validation hash calculated: a1b2c3d4e5f6...
✓ Validating Devanagari preservation...
✓ Devanagari validation passed - no text loss

✅ Conversion complete: kena-structured.md
```

### Example 2: Multi-part Directory Conversion (Chandogya - 8 parts)

```bash
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -d sources/upanishads/meghamala/chandogya/ \
    -o output/chandogya/ \
    --grantha-id chandogya-upanishad \
    --canonical-title "छान्दोग्योपनिषत्" \
    --commentary-id chandogya-rangaramanuja \
    --commentator "रङ्गरामानुजमुनिः"
```

Output:
```
📚 Found 8 part(s) to convert:
   Part 1: 01.md
   Part 2: 02.md
   Part 3: 03.md
   Part 4: 04.md
   Part 5: 05.md
   Part 6: 06.md
   Part 7: 07.md
   Part 8: 08.md

🔄 Converting part 1/8...
[conversion details...]
✅ Conversion complete: output/chandogya/chandogya-upanishad-part-01.md

🔄 Converting part 2/8...
[conversion details...]
✅ Conversion complete: output/chandogya/chandogya-upanishad-part-02.md

[... parts 3-8 ...]

============================================================
✅ All 8 parts converted successfully!
Output directory: output/chandogya/
```

### Example 3: No Commentary

```bash
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -i sources/upanishads/meghamala/mandukya/mANDUkyopaniSat.md \
    -o mandukya-structured.md \
    --grantha-id mandukya-upanishad \
    --canonical-title "माण्डूक्योपनिषत्"
```

## Advanced: Custom Prompt

The conversion prompt is defined in `MEGHAMALA_CONVERSION_PROMPT.md`. You can customize it for specific needs:

1. Copy the prompt file
2. Modify the instructions
3. Use directly with Gemini API or modify `convert_meghamala.py` to use your custom prompt

## Comparison with Rule-Based Parser

| Feature | Gemini API | Rule-Based Parser |
|---------|------------|-------------------|
| Multi-line mantras | ✅ Handles intelligently | ❌ Requires special code |
| Format variations | ✅ Adapts automatically | ❌ Needs explicit rules |
| Commentary detection | ✅ Context-aware | ⚠️ Pattern matching |
| Edge cases | ✅ Better generalization | ❌ Must anticipate all cases |
| Speed | ⚠️ ~2-5 seconds/file | ✅ Instant |
| Cost | ⚠️ API calls (minimal) | ✅ Free |
| Offline | ❌ Requires internet | ✅ Works offline |
| Reliability | ✅ Very high | ⚠️ Depends on coverage |

**Recommendation**: Use Gemini API for best results, especially for complex files.

## License

Part of the grantha-data project.
