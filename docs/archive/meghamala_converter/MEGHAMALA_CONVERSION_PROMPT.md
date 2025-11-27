# Meghamala to Grantha Markdown Conversion Prompt

Use this prompt with the Gemini API to convert meghamala-format markdown files to structured Grantha Markdown format.

## System Prompt

```
You are an expert in Sanskrit text processing and markdown conversion. Your task is to convert meghamala-format markdown files to structured Grantha Markdown format with perfect preservation of all Devanagari text.

CRITICAL REQUIREMENTS:
1. Preserve EVERY Devanagari character from the input - zero loss is mandatory
2. Follow the Grantha Markdown specification exactly
3. Generate proper YAML frontmatter with all required fields
4. Handle multi-line mantras by combining them into single mantra blocks
5. Properly separate mantras from commentary
6. Remove all bold (**) markup unless specified otherwise
```

## Conversion Prompt Template

```
Convert the following meghamala-format Upanishad markdown to structured Grantha Markdown format.

## Input Metadata
- Grantha ID: {grantha_id}
- Canonical Title: {canonical_title}
- Commentary ID: {commentary_id} (if applicable)
- Commentator: {commentator} (if applicable)
- Part Number: {part_num} (default: 1)

## Input Format (Meghamala)

The input uses this format:
- Bold text with `**`: Used for titles, mantras, section headers, commentary names
- `**[Label]**`: Special sections like शान्तिपाठः
- `**खण्डः**` or `**वल्ली**`: Major structural divisions
- Verse numbers: `।१।।`, `॥२॥`, etc. at end of mantras
- Bold lines with verse numbers are mantras
- Non-bold Devanagari text is commentary
- `**प्रकाशिका**`, `**टीका**`, etc.: Commentary section markers

## Output Format (Grantha Markdown)

Generate structured markdown with:

### 1. YAML Frontmatter
```yaml
---
grantha_id: {grantha_id}
part_num: {part_num}
canonical_title: "{canonical_title}"
text_type: upanishad
language: sanskrit
structure_levels:
  {level_1}:  # e.g., khanda, valli, adhyaya
    label_devanagari: "{label}"
    label_roman: "{romanized}"
  mantra:
    label_devanagari: "मन्त्रः"
    label_roman: "mantra"
validation_hash: {will_be_calculated}
commentaries_metadata:  # Only if commentary exists
- commentary_id: "{commentary_id}"
  commentator: "{commentator}"
  language: sanskrit
---
```

### 2. Structure Headers
- Use `#` for top-level (Khanda/Valli): `# खण्डः 1`
- Use `##` for mantras: `## Mantra 1.1`
- Use `###` for commentary: `### Commentary: 1.1`

### 3. Passage Types
**Main mantras:**
```markdown
## Mantra {reference}

<!-- sanskrit:devanagari -->

{mantra_text}

<!-- /sanskrit:devanagari -->
```

**Prefatory passages (शान्तिपाठः, etc.):**
```markdown
# Prefatory: {reference} (devanagari: "{label}")

<!-- sanskrit:devanagari -->

{text}

<!-- /sanskrit:devanagari -->
```

**Concluding passages:**
```markdown
# Concluding: {reference} (devanagari: "{label}")

<!-- sanskrit:devanagari -->

{text}

<!-- /sanskrit:devanagari -->
```

### 4. Commentary Format
```markdown
<!-- commentary: {"commentary_id": "{commentary_id}"} -->

### Commentary: {mantra_reference}

<!-- sanskrit:devanagari -->

{commentary_text}

<!-- /sanskrit:devanagari -->
```

## Conversion Rules

### Multi-line Mantras
When consecutive bold lines form a single mantra (only last line has verse number):
```
**केनेषितं पतति प्रेषितं मनः केन प्राणः प्रथमः प्रैति युक्तः ।**
**केनेषितां वाचमिमां वदन्ति चक्षुःश्रोत्रं क उ देवो युनक्ति ।१।।**
```
Combine into single mantra:
```markdown
## Mantra 1.1

<!-- sanskrit:devanagari -->

केनेषितं पतति प्रेषितं मनः केन प्राणः प्रथमः प्रैति युक्तः ।

केनेषितां वाचमिमां वदन्ति चक्षुःश्रोत्रं क उ देवो युनक्ति

<!-- /sanskrit:devanagari -->
```

### Reference Numbering
- Generate sequential references based on structure
- Format: `{khanda}.{mantra}` e.g., `1.1`, `1.2`, `2.1`
- For flat structure (no khandas): `1.1`, `1.2`, `1.3`...

### Bold Markup Removal
- Remove ALL `**` from output content (not from frontmatter)
- Text should be clean Devanagari without markdown formatting

### Special Sections
- `**श्रीः**`: Skip or include as prefatory
- `**[सामवेदशान्तिपाठः]**`: Convert to prefatory passage
- `**उत्तरशान्तिपाठः**`: Convert to concluding passage
- `**हरिः ओम्**`: Include in first mantra or as prefatory
- Colophons (`**इति केनोपनिषत्**`): Include as concluding passage

### Commentary Detection
Identify commentary by:
- Bold markers: `**प्रकाशिका**`, `**भाष्यम्**`, `**टीका**`
- Commentator names: `**{name}विरचिता**`, `**{name}कृत**`
- Non-bold Devanagari text following mantras

Group commentary by the mantra it explains.

## Validation Hash
Leave as placeholder in output:
```yaml
validation_hash: TO_BE_CALCULATED
```
(This will be calculated separately using the hasher module)

## Example Input

```markdown
**श्रीः ।।**

**केनोपनिषत्**

**[सामवेदशान्तिपाठः]**

**ओम् आप्यायन्तु ममाङ्गानि वाक्प्राणश्चक्षुः ।**

**ओं शान्तिः शान्तिः शान्तिः ।**

**प्रथमखण्डः**

**हरिः ओम् ।**

**केनेषितं पतति प्रेषितं मनः केन प्राणः प्रथमः प्रैति युक्तः ।**

**केनेषितां वाचमिमां वदन्ति चक्षुःश्रोत्रं क उ देवो युनक्ति ।१।।**

**श्रीरङ्गरामानुजमुनिविरचिता**

**प्रकाशिका**

परमात्मस्वरूपं प्रश्नप्रतिवचनरूपप्रकारेण प्रकाशयितुं प्रस्तौति- 'केनेषितं पतति'।
```

## Example Output

```markdown
---
grantha_id: kena-upanishad
part_num: 1
canonical_title: "केनोपनिषत्"
text_type: upanishad
language: sanskrit
structure_levels:
  khanda:
    label_devanagari: "खण्डः"
    label_roman: "khaṇḍa"
  mantra:
    label_devanagari: "मन्त्रः"
    label_roman: "mantra"
validation_hash: TO_BE_CALCULATED
commentaries_metadata:
- commentary_id: kena-rangaramanuja
  commentator: "रङ्गरामानुजमुनिः"
  language: sanskrit
---

# Prefatory: 0.1 (devanagari: "सामवेदशान्तिपाठः")

<!-- sanskrit:devanagari -->

ओम् आप्यायन्तु ममाङ्गानि वाक्प्राणश्चक्षुः ।

ओं शान्तिः शान्तिः शान्तिः ।

<!-- /sanskrit:devanagari -->

# खण्डः 1

## Mantra 1.1

<!-- sanskrit:devanagari -->

हरिः ओम् ।

केनेषितं पतति प्रेषितं मनः केन प्राणः प्रथमः प्रैति युक्तः ।

केनेषितां वाचमिमां वदन्ति चक्षुःश्रोत्रं क उ देवो युनक्ति

<!-- /sanskrit:devanagari -->

<!-- commentary: {"commentary_id": "kena-rangaramanuja"} -->

### Commentary: 1.1

<!-- sanskrit:devanagari -->

श्रीरङ्गरामानुजमुनिविरचिता

प्रकाशिका

परमात्मस्वरूपं प्रश्नप्रतिवचनरूपप्रकारेण प्रकाशयितुं प्रस्तौति- 'केनेषितं पतति'।

<!-- /sanskrit:devanagari -->
```

## Now convert this input:

{input_text}
```

## Usage with Gemini API Script

```bash
# Create a file with the conversion prompt
cat > conversion_prompt.txt << 'EOF'
[Paste the full conversion prompt from above with metadata filled in]
EOF

# Add the input file content
echo "" >> conversion_prompt.txt
echo "## Now convert this input:" >> conversion_prompt.txt
echo "" >> conversion_prompt.txt
cat sources/upanishads/meghamala/kena/kenopaniSat.md >> conversion_prompt.txt

# Run through Gemini API
python tools/scripts/gemini_grantha_processor/process_with_gemini.py \
    --prompt conversion_prompt.txt \
    --output kena-structured.md
```

## Post-Processing

After Gemini conversion:

1. **Calculate validation hash:**
```python
from grantha_converter.hasher import hash_text

with open('output.md', 'r') as f:
    content = f.read()

# Extract body (skip frontmatter)
frontmatter_end = content.find('---\n\n', 4)
body = content[frontmatter_end + 5:]

# Calculate hash
validation_hash = hash_text(body)

# Replace placeholder in frontmatter
content = content.replace('validation_hash: TO_BE_CALCULATED',
                         f'validation_hash: {validation_hash}')

with open('output.md', 'w') as f:
    f.write(content)
```

2. **Validate Devanagari preservation:**
```bash
python -c "
from grantha_converter.devanagari_validator import validate_file_conversion
validate_file_conversion('input.md', 'output.md')
print('✓ Validation passed')
"
```

## Quality Checklist

After conversion, verify:
- [ ] All Devanagari text preserved (no characters lost)
- [ ] All mantras have proper `## Mantra X.Y` headers
- [ ] All Sanskrit wrapped in `<!-- sanskrit:devanagari -->` blocks
- [ ] Commentary properly attributed with metadata comments
- [ ] No bold `**` markup in content (removed)
- [ ] YAML frontmatter complete and valid
- [ ] Structure levels match document hierarchy
- [ ] References numbered sequentially
- [ ] Prefatory/concluding passages identified correctly
