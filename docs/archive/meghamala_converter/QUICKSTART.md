# Meghamala Converter - Quick Start

## 1. Install & Setup (30 seconds)

```bash
# Install SDK
pip install google-generativeai

# Get API key from: https://aistudio.google.com/app/apikey
# Then set it:
export GEMINI_API_KEY="your-api-key-here"
```

## 2. Convert Single File

```bash
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -i sources/upanishads/meghamala/kena/kenopaniSat.md \
    -o kena-structured.md \
    --grantha-id kena-upanishad \
    --canonical-title "केनोपनिषत्"
```

## 3. Convert Multi-part Grantha (Directory Mode)

```bash
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -d sources/upanishads/meghamala/brihadaranyaka/ \
    -o output/brihadaranyaka/ \
    --grantha-id brihadaranyaka-upanishad \
    --canonical-title "बृहदारण्यकोपनिषत्"
```

Output:
- Auto-detects all `.md` files
- Extracts part numbers from filenames (including Sanskrit: tRtIya, pancama, etc.)
- Converts each part with correct `part_num` in frontmatter
- All parts share same `grantha_id`
- Files named: `{grantha-id}-part-01.md`, `part-02.md`, etc.

## 4. With Commentary (Ensures Consistent Commentary ID)

```bash
python tools/scripts/gemini_grantha_processor/convert_meghamala.py \
    -d sources/upanishads/meghamala/chandogya/ \
    -o output/chandogya/ \
    --grantha-id chandogya-upanishad \
    --canonical-title "छान्दोग्योपनिषत्" \
    --commentary-id chandogya-rangaramanuja \
    --commentator "रङ्गरामानुजमुनिः"
```

**Note:** The `--commentary-id` ensures that EVERY commentary block uses this exact ID in the `<!-- commentary: ... -->` metadata comment throughout the entire document.

## What It Does

✅ Combines multi-line mantras intelligently
✅ Separates commentary from mantras
✅ Generates proper YAML frontmatter
✅ Auto-detects part numbers (digits or Sanskrit words)
✅ Numbers references sequentially
✅ Removes bold `**` markup
✅ Validates zero Devanagari text loss
✅ Calculates SHA256 validation hash

## Part Number Detection

Works with:
- `03-01.md` → part 1
- `05.md` → part 5
- `part-3.md` → part 3
- `name-tRtIya.md` → part 3 (Sanskrit)
- `name-pancama.md` → part 5 (Sanskrit)
- `name-aSTama.md` → part 8 (Sanskrit)

## Output Format

```yaml
---
grantha_id: chandogya-upanishad
part_num: 3
canonical_title: "छान्दोग्योपनिषत्"
text_type: upanishad
language: sanskrit
structure_levels:
  khanda:
    label_devanagari: "खण्डः"
    label_roman: "khaṇḍa"
  mantra:
    label_devanagari: "मन्त्रः"
    label_roman: "mantra"
validation_hash: abc123...
commentaries_metadata:
- commentary_id: chandogya-rangaramanuja
  commentator: "रङ्गरामानुजमुनिः"
  language: sanskrit
---

# खण्डः 1

## Mantra 1.1

<!-- sanskrit:devanagari -->

mantra text here

<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "chandogya-rangaramanuja"} -->

### Commentary: 1.1

<!-- sanskrit:devanagari -->

commentary text here

<!-- /sanskrit:devanagari -->
```

## Cost

Free tier sufficient for entire collection (~70 Upanishad files)

## Full Documentation

- `README_MEGHAMALA.md` - Complete usage guide
- `MEGHAMALA_CONVERSION_PROMPT.md` - Gemini prompt details
- `/MEGHAMALA_CONVERSION_SUMMARY.md` - Implementation summary
