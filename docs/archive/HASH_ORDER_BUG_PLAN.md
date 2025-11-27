# Hash Order Bug Fix Plan

## Problem Statement

The validation hash system has a critical ordering bug that prevents round-trip validation when commentaries are included in grantha files.

### Current Behavior

**JSON Structure** (separated):
```json
{
  "prefatory_material": [...],
  "passages": [
    {"ref": "1.1.1", "content": "..."},
    {"ref": "1.1.2", "content": "..."}
  ],
  "commentaries": {
    "commentary-id": {
      "passages": [
        {"ref": "1.1.1", "content": "..."},
        {"ref": "1.1.2", "content": "..."}
      ]
    }
  }
}
```

**Markdown Structure** (interleaved):
```markdown
# Mantra 1.1.1
<mantra text>

# Commentary: 1.1.1
<commentary text>

# Mantra 1.1.2
<mantra text>

# Commentary: 1.1.2
<commentary text>
```

### Hash Calculation Order

**Current `hash_grantha()` order**:
1. All prefatory_material
2. All passages (mantras)
3. All concluding_material
4. All commentary passages

**Markdown order** (as it appears in the file):
1. Prefatory_material
2. Mantra 1.1.1
3. Commentary 1.1.1
4. Mantra 1.1.2
5. Commentary 1.1.2
6. ...
7. Concluding_material

**Result**: Different Devanagari text concatenation order → Different hashes → Round-trip validation fails

### Misleading Message Removed

The message `"✓ Validation hash verified - no data loss detected."` in `cli.py:224` has been **removed** because it was false - no hash verification actually happens during md2json conversion.

## Solution Approach

### Phase 1: Analysis (Current Status: NOT STARTED)

1. **Analyze commentary ref patterns** across all structured_md files:
   - Single refs: `"1.1.1"`
   - Range refs: `"1.1.1-1.1.5"`, `"1.1.1-5"`, etc.
   - Section refs: `"1.1"` (covering all mantras in that section)
   - Determine if refs can be non-contiguous or overlap

2. **Document ref patterns** with examples from actual files

### Phase 2: Implementation (NOT STARTED)

Modify `hash_grantha()` in `tools/lib/grantha_converter/hasher.py` to:

1. **Add ref parsing utilities**:
   - `parse_commentary_ref(ref: str) -> RefRange` - Parse ref into structure
   - `commentary_covers_passage(commentary_ref: str, passage_ref: str) -> bool` - Check if commentary ref includes passage ref

2. **Change hash order to interleaved**:
   ```python
   all_texts = []

   # Hash prefatory material first
   for item in data.get('prefatory_material', []):
       all_texts.append(extract_content_text(item['content'], scripts))

   # Process passages in order, interleaving their commentaries
   for passage in data.get('passages', []):
       passage_ref = passage['ref']

       # Hash the passage
       all_texts.append(extract_content_text(passage['content'], scripts))

       # Find and hash commentaries that reference this passage
       if commentaries and 'commentaries' in data:
           for commentary in data['commentaries']:
               if commentary['commentary_id'] in commentaries:
                   for comm_passage in commentary['passages']:
                       if commentary_covers_passage(comm_passage['ref'], passage_ref):
                           all_texts.append(extract_content_text(comm_passage['content'], scripts))

   # Hash concluding material last
   for item in data.get('concluding_material', []):
       all_texts.append(extract_content_text(item['content'], scripts))
   ```

3. **Handle edge cases**:
   - Commentaries that cover ranges (hash at first passage in range)
   - Commentaries with no matching passages (skip or error?)
   - Multiple commentaries for same passage (preserve order from commentaries list)

### Phase 3: Testing (NOT STARTED)

1. **Unit tests** for ref parsing logic
2. **Integration tests** for hash calculation with various ref patterns
3. **Round-trip tests** to verify MD→JSON→MD produces same hash
4. **Regression tests** to ensure non-commentary hashes still work

### Phase 4: Migration (NOT STARTED)

1. Regenerate all validation hashes in existing structured_md files
2. Update BUILD files to rebuild JSON outputs
3. Verify all files pass validation

## Current Status

- [x] TODO comment added to `hasher.py` documenting the issue
- [x] Misleading success message removed from `cli.py`
- [ ] Phase 1: Ref pattern analysis
- [ ] Phase 2: Implementation
- [ ] Phase 3: Testing
- [ ] Phase 4: Migration

## Files Modified

- `tools/lib/grantha_converter/hasher.py:108-133` - Added TODO comment
- `tools/lib/grantha_converter/cli.py:224` - Removed misleading message

## Next Steps

1. Run analysis to understand commentary ref patterns (see Phase 1)
2. Implement ref parsing utilities based on analysis
3. Modify hash_grantha() to use interleaved order
4. Add comprehensive tests
5. Regenerate all hashes in the repository
