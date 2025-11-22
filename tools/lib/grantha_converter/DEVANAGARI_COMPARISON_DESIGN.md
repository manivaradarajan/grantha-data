# Devanagari Comparison and Hashing Design

## Overview

This document explains the architecture for Devanagari text extraction, comparison, and hashing across the grantha-data toolchain. The design ensures consistency between diff, repair, and validation operations while preserving all Devanagari characters from source texts.

## Core Principle

**All Devanagari characters must be preserved during archival preservation.**

The text cleaning and extraction pipeline never removes or alters Devanagari characters. It only removes markup elements (YAML frontmatter, HTML comments, markdown bold markers) that are NOT part of the Devanagari text content.

## Architecture Components

### 1. Devanagari Extractor (`devanagari_extractor.py`)

Contains three key functions:

#### `extract_devanagari(text: str) -> str`
- **Purpose**: Extracts ONLY Devanagari characters (U+0900-U+097F) from any text
- **Input**: Raw text that may contain multiple scripts, markdown, etc.
- **Output**: Devanagari-only text with word boundaries preserved (single spaces between words)
- **Used by**: All tools (hasher, diff, repair, validator)

#### `clean_text_for_devanagari_comparison(text: str) -> str`
- **Purpose**: Removes markup while preserving ALL Devanagari characters
- **Removes**:
  - YAML frontmatter (`---...---`)
  - HTML comments (`<!-- ... -->`) → replaced with space to avoid word merging
  - Markdown bold markers (`**`)
  - Normalizes whitespace to single spaces
- **Preserves**: ALL Devanagari characters unchanged
- **Used by**: Tools working with Markdown files (diff, repair)

#### `extract_devanagari_words_with_positions(text: str) -> List[Tuple[str, int, int]]`
- **Purpose**: Extracts Devanagari words with their positions for repair operations
- **Used by**: Repair tool for surgical text replacements

### 2. Text Hashing (`hasher.py`)

```python
def hash_text(text: str) -> str:
    """Hashes ONLY Devanagari characters from text."""
    devanagari_only = extract_devanagari(text)
    return hashlib.sha256(devanagari_only.encode('utf-8')).hexdigest()
```

**Critical Design Decision**: The hasher operates on **JSON data**, not Markdown.

- **Input**: Clean text from JSON `content['sanskrit']['devanagari']` fields
- **Why no cleaning needed**: JSON data is already structured and clean (no YAML, HTML comments, or markdown)
- **Process**: `extract_devanagari()` directly (no pre-cleaning)
- **Output**: SHA256 hash of Devanagari characters
- **Storage**: Hash stored in Markdown frontmatter as `grantha_hash: <hex>`

### 3. Devanagari Diff (`devanagari_diff.py`)

Compares Devanagari text between two Markdown files.

**Pipeline**:
1. Read two MD files
2. `clean_text_for_devanagari_comparison()` on both
3. `extract_devanagari()` from cleaned text
4. Character-level diff visualization

**Key**: Cleaning happens BEFORE extraction to ensure consistent comparison.

### 4. Devanagari Repair (`devanagari_repair.py`)

Repairs Devanagari mismatches between source and target Markdown files.

**Pipeline**:
1. Read source and target MD files
2. `clean_text_for_devanagari_comparison()` on both
3. `extract_devanagari_words_with_positions()` from cleaned text
4. Align word sequences and apply surgical repairs
5. Preserve original frontmatter

**Consistency**: Uses identical cleaning logic as diff tool.

### 5. Hash Validation (`validator.py`)

Validates MD↔JSON round-trip integrity.

**Process**:
1. Parse Markdown → JSON structure
2. Extract text from reconstructed JSON `content['sanskrit']['devanagari']`
3. Hash using `hash_grantha()` → calls `hash_text()` → calls `extract_devanagari()`
4. Compare with stored hash in frontmatter

**Key**: Operates on JSON data, not raw Markdown, so no cleaning needed.

## Data Flow Diagrams

### JSON → Markdown (with hashing)

```
JSON data (clean)
    ↓
extract text from content['sanskrit']['devanagari']
    ↓
extract_devanagari()  [no cleaning needed - already clean]
    ↓
hash_text() → SHA256
    ↓
Store hash in MD frontmatter
    ↓
Write Markdown file
```

### Markdown → JSON (with validation)

```
Markdown file
    ↓
Parse to JSON structure
    ↓
Extract text from parsed content['sanskrit']['devanagari']
    ↓
extract_devanagari()  [no cleaning - operating on parsed JSON]
    ↓
hash_text() → SHA256
    ↓
Compare with stored hash from frontmatter
```

### Markdown Diff/Repair

```
Two Markdown files
    ↓
clean_text_for_devanagari_comparison()  [remove YAML, HTML, bold]
    ↓
extract_devanagari()
    ↓
Compare Devanagari sequences
    ↓
Show diff / Apply repairs
```

## Why Different Approaches for JSON vs Markdown?

### JSON Processing (hasher, validator)
- **Input**: Structured data with clean text in fields
- **No markup**: JSON doesn't contain YAML, HTML comments, or markdown
- **Direct extraction**: `extract_devanagari()` sufficient
- **Use case**: Computing validation hashes, checking round-trip integrity

### Markdown Processing (diff, repair)
- **Input**: Text files with markup (YAML, HTML comments, bold markers)
- **Has markup**: MD files contain structural elements around Devanagari text
- **Two-step process**: Clean first, then extract
- **Use case**: Comparing files, repairing mismatches

## Important Properties

### 1. Character Preservation
✓ `clean_text_for_devanagari_comparison()` **never removes Devanagari characters**
✓ Only removes non-Devanagari markup
✓ HTML comments replaced with spaces (acts as word separator, not character loss)

### 2. Consistency Guarantees
✓ Diff and repair use **identical** cleaning and extraction logic
✓ Both agree on what constitutes "matching Devanagari"
✓ Tested via `test_devanagari_consistency.py`

### 3. Hash Stability
✓ Hashing is deterministic and repeatable
✓ Same Devanagari text → same hash (regardless of source: JSON or parsed MD)
✓ Hash validates content integrity across JSON↔MD conversions

## Testing Strategy

See `test_devanagari_consistency.py` for comprehensive tests:

1. **Character preservation**: Cleaning never loses Devanagari
2. **Diff/repair consistency**: Both tools agree on matches/differences
3. **Hash stability**: Deterministic, repeatable hashes
4. **Whitespace normalization**: Consistent handling across tools
5. **Real-world files**: Tested on actual repository files

## Common Pitfalls

### ❌ Don't put HTML comments inside Devanagari words
```markdown
<!-- WRONG -->
अग्नि<!-- note -->मीळे
<!-- This becomes "अग्नि मीळे" (with space) after cleaning -->
```

### ✓ Put HTML comments between words
```markdown
<!-- CORRECT -->
अग्निमीळे <!-- note --> पुरोहितं
<!-- Cleaning preserves "अग्निमीळे पुरोहितं" -->
```

### Why?
HTML comments are replaced with spaces to avoid accidentally merging words. This is intentional and correct behavior for text preservation.

## Summary

| Tool | Input Type | Cleaning? | Extraction | Purpose |
|------|-----------|-----------|-----------|---------|
| **hasher.py** | JSON data | No | `extract_devanagari()` | Hash computation |
| **validator.py** | Parsed JSON | No | `extract_devanagari()` | Hash validation |
| **diff** | Markdown files | Yes | `clean_text_for_devanagari_comparison()` → `extract_devanagari()` | Compare files |
| **repair** | Markdown files | Yes | `clean_text_for_devanagari_comparison()` → `extract_devanagari()` | Fix mismatches |

The design is **correct and consistent** because:
1. JSON tools work with clean data (no markup to remove)
2. MD tools clean markup first (preserving all Devanagari)
3. All tools use the same `extract_devanagari()` core function
4. Comprehensive tests ensure mutual consistency
