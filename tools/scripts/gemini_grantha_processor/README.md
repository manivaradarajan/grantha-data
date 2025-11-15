# Gemini Grantha Markdown Processor

A Python script that processes Grantha Markdown files using Google's Gemini API while ensuring Devanagari content integrity.

## Features

- **AI-powered processing**: Uses Gemini API to enhance commentary with bold formatting
- **Devanagari integrity verification**: Automatically verifies that all Devanagari characters are preserved exactly
- **Grantha Markdown validation**: Validates output against the Grantha Markdown specification
- **Flexible prompts**: Use default prompt or provide custom prompts
- **Multiple model support**: Works with any Gemini model (Pro, Flash, etc.)

## Prerequisites

1. **Google API Key**: You need a Gemini API key from Google AI Studio
   - Get one at: https://makersuite.google.com/app/apikey
   - Set it as an environment variable:
     ```bash
     export GOOGLE_API_KEY='your-api-key-here'
     ```

2. **Python packages**: Install required dependencies
   ```bash
   pip install -e .  # From project root
   ```

## Usage

### Basic Usage

Process a file with the default prompt (bold key terms in commentary):

```bash
python tools/scripts/gemini_grantha_processor/gemini_grantha_processor.py \
  -i sources/upanishads/isavasya/isa-vedantadesika/isavasya-vedantadesika.converted.md \
  -o sources/upanishads/isavasya/isa-vedantadesika/isavasya-vedantadesika.bolded.md
```

### Advanced Options

#### Custom Prompt from Command Line

```bash
python tools/scripts/gemini_grantha_processor/gemini_grantha_processor.py \
  -i input.md \
  -o output.md \
  --prompt "Your custom processing instructions here"
```

#### Custom Prompt from File

```bash
python tools/scripts/gemini_grantha_processor/gemini_grantha_processor.py \
  -i input.md \
  -o output.md \
  --prompt-file my_custom_prompt.txt
```

#### Use Gemini Flash (faster, cheaper)

```bash
python tools/scripts/gemini_grantha_processor/gemini_grantha_processor.py \
  -i input.md \
  -o output.md \
  --model gemini-1.5-flash-latest
```

#### Verbose Output

```bash
python tools/scripts/gemini_grantha_processor/gemini_grantha_processor.py \
  -i input.md \
  -o output.md \
  -v
```

## Default Prompt

The default prompt instructs Gemini to:

> You are an expert Sanskrit scholar and a meticulous data architect specializing in digital humanities. Your task is to analyze a provided text as described. You are strictly instructed to not modify a single character of devanagari. This is very important. No input character must be modified.
>
> Bolding: Within commentary_text, find direct quotes or key terms from the text and make them bold using double asterisks (**word**).

With strict rules to:
- Only modify commentary sections
- Not modify mantras, frontmatter, or HTML comments
- Preserve ALL Devanagari characters exactly
- Only add bold formatting using `**word**` syntax

## Verification Process

The script performs two levels of verification:

### 1. Devanagari Integrity Check

- Extracts all Devanagari characters (Unicode range U+0900–U+097F)
- Normalizes both original and processed text
- Compares normalized versions
- Reports any mismatches with character counts

Example output:
```
✓ Devanagari integrity verified - content preserved exactly
  Original Devanagari chars: 24776
  Processed Devanagari chars: 24776
  Original normalized: 23145
  Processed normalized: 23145
```

### 2. Grantha Markdown Validation

- Validates YAML frontmatter structure
- Checks passage and commentary format
- Verifies all required fields
- Ensures commentary-passage linkage

Example output:
```
✓ Validation passed
```

## Error Handling

### API Key Not Set

```
ERROR: GOOGLE_API_KEY environment variable not set.
Set it with: export GOOGLE_API_KEY='your-api-key'
```

### Devanagari Mismatch

If Devanagari content differs:
```
✗ DEVANAGARI MISMATCH DETECTED!
  Expected 23145 normalized chars
  Got 23100 normalized chars
  Difference: 45 chars

WARNING: Saving output despite mismatch. Review carefully!
```

The file is still saved, but you should manually review it.

### Validation Errors

If the output doesn't conform to Grantha Markdown spec:
```
✗ Validation failed with 2 error(s):
  - Line 42: Missing required field in frontmatter: grantha_id
  - Line 156: Commentary for ref '5' has no corresponding passage.
```

## Options Reference

| Option | Description |
|--------|-------------|
| `-i, --input` | Input Grantha Markdown file (required) |
| `-o, --output` | Output file path (required) |
| `--prompt` | Custom prompt text (overrides default) |
| `--prompt-file` | Path to file with custom prompt |
| `--model` | Gemini model name (default: gemini-1.5-pro-latest) |
| `--no-validate` | Skip Grantha Markdown validation |
| `--no-verify` | Skip Devanagari integrity check (not recommended) |
| `-v, --verbose` | Enable verbose output |

## Available Gemini Models

- `gemini-1.5-pro-latest` - Most capable (default)
- `gemini-1.5-flash-latest` - Faster and cheaper
- `gemini-1.0-pro` - Previous generation

See [Google AI documentation](https://ai.google.dev/models) for latest models.

## Workflow Example

Complete workflow for processing a file:

```bash
# 1. Set API key (one time)
export GOOGLE_API_KEY='your-key-here'

# 2. Process the file
python tools/scripts/gemini_grantha_processor/gemini_grantha_processor.py \
  -i sources/upanishads/isavasya/isa-vedantadesika/isavasya-vedantadesika.converted.md \
  -o sources/upanishads/isavasya/isa-vedantadesika/isavasya-vedantadesika.bolded.md \
  -v

# 3. Review the output
# Check that formatting looks correct and Devanagari is preserved

# 4. Test round-trip conversion
grantha-converter md2json \
  -i sources/upanishads/isavasya/isa-vedantadesika/isavasya-vedantadesika.bolded.md \
  -o test-output.json

# If validation passes, the file is ready to use!
```

## Troubleshooting

### "Empty or blocked response from API"

The API may have blocked the request due to safety filters. Try:
1. Using a different model (`--model gemini-1.5-flash-latest`)
2. Modifying your prompt to be more specific
3. Processing smaller sections of the file

### High API Costs

For large files or many requests:
1. Use Gemini Flash instead of Pro (`--model gemini-1.5-flash-latest`)
2. Process files in batches
3. Monitor usage at https://makersuite.google.com/

### Slow Processing

- Large files can take 30-60 seconds
- Use `--model gemini-1.5-flash-latest` for faster processing
- Enable verbose mode (`-v`) to see progress

## License

Part of the Grantha Data project.
