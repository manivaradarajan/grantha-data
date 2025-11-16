# Structured Markdown Files

This directory contains Grantha Sanskrit texts in structured Markdown format with YAML frontmatter. These files are designed for easy proofreading and editing while maintaining data integrity through cryptographic validation.

## Content Validation System

Every file includes a **validation hash** that ensures the Devanagari content hasn't been corrupted or accidentally modified. The hash is computed from:

- **Only Devanagari text** (Unicode U+0900-U+097F)
- **Word boundaries preserved** (spaces between Devanagari words)
- **All other content ignored** (markdown formatting, YAML, English translations, Roman transliteration)

This means you can freely edit:
- Markdown formatting (headers, lists, bold, italic)
- English translations
- Roman transliteration
- YAML frontmatter (except `validation_hash` and `hash_version`)

The hash will **only change** if you modify Devanagari text.

## Hash Versioning

The `hash_version` field tracks the algorithm used to generate the validation hash:

```yaml
hash_version: 1
validation_hash: sha256:abc123def456...
```

**Current Version: 1** (word-boundary-preserving extraction)

When the hashing algorithm changes, the version is incremented. Files with old versions must be updated before committing.

## Verifying File Integrity

To check if a file's hash is valid:

```bash
grantha-converter verify-hash -i structured_md/upanishads/isavasya/isavasya-1.md
```

**Success output:**
```
✓ Hash valid for structured_md/upanishads/isavasya/isavasya-1.md
  Version: 1
  Hash: abc123def456...
```

**Failure output (version mismatch):**
```
✗ Hash version MISMATCH in structured_md/upanishads/isavasya/isavasya-1.md
  File version: 0
  Current version: 1
  The hashing algorithm has changed since this hash was generated.
  Please run: grantha-converter update-hash -i "structured_md/upanishads/isavasya/isavasya-1.md"
```

**Failure output (content changed):**
```
✗ Hash INVALID for structured_md/upanishads/isavasya/isavasya-1.md
  Expected: abc123...
  Actual:   def456...
```

## Updating Hashes

### After Editing Devanagari Text

When you intentionally modify Devanagari content, update the hash:

```bash
grantha-converter update-hash -i structured_md/upanishads/isavasya/isavasya-1.md
```

This will:
1. Extract the Devanagari text from the file
2. Compute a new validation hash
3. Update both `hash_version` and `validation_hash` in the YAML frontmatter

### After Algorithm Updates

When the hash algorithm is updated (version incremented), regenerate all hashes:

```bash
# Update all structured_md files
find structured_md -name "*.md" -type f -exec grantha-converter update-hash -i {} \;
```

## Git Pre-Commit Hook

A **pre-commit hook** automatically validates all modified files before allowing commits.

### What the Hook Does

1. Finds all modified `.md` files in `structured_md/`
2. Runs `verify-hash` on each file
3. **Blocks the commit** if any file has:
   - Invalid hash (content doesn't match)
   - Wrong version (outdated algorithm)
   - Missing version field

### Hook Location

`.git/hooks/pre-commit` (automatically created by the grantha-converter setup)

### If a Commit is Blocked

The hook will show which files failed:

```
✗ Commit blocked: 2 file(s) have invalid validation_hash

The following files have mismatched validation_hash:
  - structured_md/upanishads/isavasya/isavasya-1.md
  - structured_md/upanishads/kena/kena-1.md

To fix this, run:
  grantha-converter update-hash -i <file>

Or update all failed files:
  grantha-converter update-hash -i "structured_md/upanishads/isavasya/isavasya-1.md"
  grantha-converter update-hash -i "structured_md/upanishads/kena/kena-1.md"
```

### Bypassing the Hook (Not Recommended)

If you absolutely need to commit without validation (not recommended):

```bash
git commit --no-verify -m "Your message"
```

⚠️ **Warning:** This skips validation and may allow corrupted files into the repository.

## Common Workflows

### Editing Devanagari Text

1. Edit the file (modify Devanagari content)
2. Update the hash:
   ```bash
   grantha-converter update-hash -i path/to/file.md
   ```
3. Verify it worked:
   ```bash
   grantha-converter verify-hash -i path/to/file.md
   ```
4. Commit:
   ```bash
   git add path/to/file.md
   git commit -m "Fix typo in mantra 3.1.5"
   ```

### Editing Translations or Formatting

1. Edit the file (modify English, markdown, or formatting)
2. Verify hash is still valid:
   ```bash
   grantha-converter verify-hash -i path/to/file.md
   ```
3. Commit (hash doesn't need updating):
   ```bash
   git add path/to/file.md
   git commit -m "Improve translation clarity"
   ```

### Bulk Hash Update (After Algorithm Change)

```bash
# Update all files to current hash version
find structured_md -name "*.md" -type f -exec grantha-converter update-hash -i {} \;

# Verify all files
find structured_md -name "*.md" -type f -exec grantha-converter verify-hash -i {} \;

# Commit the updates
git add structured_md/
git commit -m "Update all hashes to version 1 (word-boundary-preserving)"
```

## Troubleshooting

### "Hash version MISSING"

Your file doesn't have a `hash_version` field (legacy file).

**Fix:**
```bash
grantha-converter update-hash -i path/to/file.md
```

### "Hash version MISMATCH"

The file was created with an older hashing algorithm.

**Fix:**
```bash
grantha-converter update-hash -i path/to/file.md
```

### "Hash INVALID" (but you didn't edit Devanagari)

Possible causes:
- Invisible character changes (copy/paste from different source)
- Line ending changes (CRLF vs LF) affecting Devanagari lines
- Unicode normalization differences

**Fix:**
```bash
# Check what Devanagari text is actually in the file
grantha-converter verify-hash -i path/to/file.md

# If the Devanagari looks correct, update the hash
grantha-converter update-hash -i path/to/file.md
```

### Pre-Commit Hook Not Running

Check if the hook is executable:

```bash
ls -l .git/hooks/pre-commit
# Should show: -rwxr-xr-x (executable)

# If not executable, fix it:
chmod +x .git/hooks/pre-commit
```

## Technical Details

### Hash Algorithm (Version 1)

1. **Extract Devanagari**: Find all sequences matching `[\u0900-\u097F]+`
2. **Join with spaces**: Word sequences joined with single space
3. **Hash**: SHA256 of the resulting string
4. **Prefix**: Result prefixed with `sha256:`

**Example:**
```markdown
# Mantra 1

<!-- sanskrit:devanagari -->
अग्निमीळे पुरोहितं
<!-- /sanskrit:devanagari -->

**Translation**: I praise Agni, the priest...
```

**Extracted text:** `अग्निमीळे पुरोहितं`
**Hash:** SHA256 of `अग्निमीळे पुरोहितं`

### What's Included vs. Excluded

| Content Type | Included in Hash? |
|--------------|-------------------|
| Devanagari text | ✅ Yes |
| Devanagari dandas (।॥) | ✅ Yes |
| Devanagari numerals (०१२...) | ✅ Yes |
| Spaces between Devanagari words | ✅ Yes |
| Roman transliteration | ❌ No |
| English translation | ❌ No |
| Markdown formatting | ❌ No |
| YAML frontmatter | ❌ No |
| HTML comments | ❌ No |
| Multiple spaces → normalized to 1 | ✅ Yes (as 1 space) |

## See Also

- [GRANTHA_MARKDOWN.md](../formats/GRANTHA_MARKDOWN.md) - Full format specification
- [grantha-converter CLI](../tools/lib/grantha_converter/) - Source code for validation tools
- [devanagari_extractor.py](../tools/lib/grantha_converter/devanagari_extractor.py) - Hash algorithm implementation
