# GEMINI.md

This file provides guidance to Gemini AI when working with code in this repository.

## Repository Overview

This is the **grantha-data** repository, a Sanskrit text processing and conversion system focused on Upanishads. The project provides bidirectional, lossless conversion between JSON and Markdown formats for Sanskrit texts, enabling easy proofreading and editing while maintaining data integrity through SHA256 content hashing.

## Python Coding Standards

### Style and Quality
- Follow Google Python style guide strictly
- Keep functions under ~50 lines
- Add comprehensive docstrings to all functions (Google style)
- Use strict type hints (PEP 484) for all function signatures
- Aim for beautiful, highly readable, and highly testable code
- Follow Python best practices (PEP 8, PEP 20 - Zen of Python)

### Example Function Format
```python
def convert_text(
    source: str,
    target_format: str,
    *,
    preserve_whitespace: bool = False
) -> str:
    """Converts text from one format to another.

    Args:
        source: The input text to convert.
        target_format: The desired output format (e.g., 'devanagari', 'roman').
        preserve_whitespace: Whether to preserve all whitespace in conversion.

    Returns:
        The converted text in the target format.

    Raises:
        ValueError: If target_format is not supported.
    """
    # Implementation here
```

## Gemini API Usage Requirements

### Model Selection
- **NEVER** use `gemini-1.5-*` model names (deprecated)
- **NEVER** use `google-generativeai` library (old SDK)
- **ALWAYS** use `google-genai` library (new SDK)
- Prefer `gemini-2.0-flash-exp` or `gemini-2.0-flash-thinking-exp` for most tasks
- Use appropriate model based on task complexity:
  - Analysis tasks: flash models with thinking mode
  - Conversion tasks: flash models
  - Complex reasoning: thinking-enabled models

### API Patterns
```python
from google import genai
from google.genai import types

# Initialize client
client = genai.Client(api_key=api_key)

# Use modern API patterns
response = client.models.generate_content(
    model='gemini-2.0-flash-exp',
    contents=contents,
    config=types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type='application/json'
    )
)
```

## Project Architecture

### Library Structure
- **`tools/lib/grantha_converter/`**: Core JSON↔Markdown conversion library
- **`tools/lib/gemini_processor/`**: Generic Gemini API interaction library
- **`tools/scripts/`**: Standalone utility scripts (meghamala_converter, devanagari_tools, etc.)

### Key Components
1. **Content Hashing** (`hasher.py`): SHA256-based validation with normalization
2. **JSON to Markdown** (`json_to_md.py`): Hierarchical structure traversal and markdown generation
3. **Markdown to JSON** (`md_to_json.py`): Header parsing and tree reconstruction
4. **Gemini Integration** (`gemini_processor`): File upload, caching, prompt management, response parsing

## Testing Requirements

### Test Coverage
- Write pytest tests for all new functionality
- Tests should live alongside code: `tools/lib/package_name/test_*.py`
- Current test counts:
  - grantha_converter: 84 tests
  - gemini_processor: 90 tests
  - meghamala_converter: 18 tests

### Running Tests
```bash
# Run all tests
pytest tools/lib/grantha_converter/
pytest tools/lib/gemini_processor/

# Run specific test file
pytest tools/lib/grantha_converter/test_hasher.py

# Run single test
pytest tools/lib/grantha_converter/test_hasher.py::test_normalize_text
```

## Development Workflow

### Adding New Features
1. Read relevant code first before making changes
2. Understand existing patterns and conventions
3. Write tests before implementation (TDD encouraged)
4. Use type hints and comprehensive docstrings
5. Run tests to verify: `pytest tools/lib/package_name/`
6. If adding CLI commands, update `pyproject.toml` and run `pip install -e .`

### Code Patterns to Follow
- Use `pathlib.Path` for file operations (not string paths)
- Use context managers (`with` statements) for file I/O
- Prefer explicit over implicit (Zen of Python)
- Use dataclasses or Pydantic models for structured data
- Handle errors explicitly; don't use bare `except:`
- Log important operations using Python's logging module

### Error Handling
```python
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def safe_read_file(path: Path) -> Optional[str]:
    """Safely reads a file with proper error handling.

    Args:
        path: Path to the file to read.

    Returns:
        File contents as string, or None if read failed.
    """
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        logger.error(f"File not found: {path}")
        return None
    except UnicodeDecodeError as e:
        logger.error(f"Unicode decode error in {path}: {e}")
        return None
```

## Data Integrity

### Validation Hash
- All Grantha Markdown files have SHA256 `validation_hash` in frontmatter
- Hash validates lossless round-trip conversion (JSON → MD → JSON)
- Normalization excludes whitespace, punctuation, zero-width marks
- Never modify text content without updating hash

### Sanskrit Text Handling
- All files are UTF-8 encoded
- Preserve Devanagari characters exactly (no normalization)
- Use `<!-- sanskrit:devanagari -->` blocks in markdown
- Validate Devanagari preservation in conversions

## Common Pitfalls to Avoid

1. **Don't guess file paths** - Always verify file existence before operations
2. **Don't use relative imports** - Use: `from grantha_converter import module`
3. **Don't modify hashes manually** - Let the hasher compute them
4. **Don't break hierarchies** - Respect structure_levels depth when parsing
5. **Don't use old Gemini SDK** - Only use `google-genai`, not `google-generativeai`
6. **Don't hardcode model names** - Make models configurable via arguments
7. **Don't skip error handling** - Sanskrit text processing can have encoding issues

## File Naming Conventions

- Test files: `test_*.py` or `*_test.py`
- CLI modules: `cli.py` with `main()` function
- Utility modules: Descriptive names like `hasher.py`, `diff_utils.py`
- Config files: `UPPERCASE.yaml` or `UPPERCASE.md`

## Documentation

- Docstrings: Google style for all public functions and classes
- Type hints: All function parameters and return values
- Comments: Explain "why", not "what" (code should be self-explanatory)
- README files: Only create when adding new major components
- Inline documentation: Use for complex algorithms or Sanskrit-specific logic

## Performance Considerations

- **Caching**: Use SHA256-based file upload cache to avoid redundant API calls
- **Sampling**: For large files, use smart sampling (first 100KB + middle 50KB + last 50KB)
- **Batching**: Process multiple files in batch operations when possible
- **Memory**: Be mindful of memory with large Sanskrit text files

## Integration with Claude Code

This repository also uses Claude Code (see `CLAUDE.md`). When working with both systems:
- Maintain consistency in code style and patterns
- Both systems should produce compatible outputs
- Testing should validate integration between Gemini-powered and manual conversions
- Documentation should be clear about which AI system handles what tasks
