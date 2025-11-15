# JSON Error Handling & Debugging

## Problem
Gemini sometimes returns JSON with invalid escape sequences, particularly in regex patterns. For example:
- **Invalid**: `"regex": "^\*\*\S+ खण्डः\*\*$"` (single backslashes)
- **Valid**: `"regex": "^\\*\\*\\S+ खण्डः\\*\\*$"` (double backslashes)

This causes `JSONDecodeError: Invalid \escape` when parsing the response.

## Solution

We've implemented a multi-layered approach to handle this:

### 1. Updated Prompt (Prevention)

**File**: `prompts/full_file_analysis_prompt.txt`

Added explicit instructions to Gemini about JSON escaping:

```
CRITICAL JSON FORMATTING RULES:
1. All backslashes (\) in regex patterns MUST be escaped as double backslashes (\\)
2. Example: "regex": "^\\*\\*\\S+ खण्डः\\*\\*$" (NOT "^\*\*\S+ खण्डः\*\*$")
3. All string values must use double quotes (")
4. Use JSON null (not the string "null") for missing values
```

### 2. Automatic JSON Repair (Fallback)

**Function**: `repair_json_escapes(text)`

Automatically attempts to fix common escape sequence issues:

```python
def repair_json_escapes(text: str) -> str:
    """Attempt to repair common JSON escape sequence issues.

    Finds all "regex": "..." patterns and doubles single backslashes.
    """
    regex_pattern = r'"regex":\s*"([^"]*)"'

    def fix_regex(match):
        regex_value = match.group(1)
        fixed = regex_value.replace('\\', '\\\\')
        # Avoid quadrupling already-doubled backslashes
        fixed = fixed.replace('\\\\\\\\', '\\\\')
        return f'"regex": "{fixed}"'

    return re.sub(regex_pattern, fix_regex, text)
```

**Flow**:
1. Try parsing JSON as-is
2. If `JSONDecodeError`, apply `repair_json_escapes()`
3. Try parsing repaired JSON
4. If still fails, show detailed error with context

### 3. Detailed Logging

**What gets logged**:

#### Success Path:
```
📝 Gemini response received (15,234 chars)
💾 Debug: Raw response saved to .debug_gemini_response_filename.txt
🔍 Parsing JSON response...
✓ JSON parsed successfully
```

#### Repair Path:
```
📝 Gemini response received (15,234 chars)
💾 Debug: Raw response saved to .debug_gemini_response_filename.txt
🔍 Parsing JSON response...
⚠️  Initial JSON parse failed: Invalid \escape: line 27 column 31 (char 1258)
🔧 Attempting to repair JSON escape sequences...
✓ JSON parsed successfully after repair!
```

#### Error Path:
```
📝 Gemini response received (15,234 chars)
💾 Debug: Raw response saved to .debug_gemini_response_filename.txt
🔍 Parsing JSON response...
⚠️  Initial JSON parse failed: Invalid \escape: line 27 column 31 (char 1258)
🔧 Attempting to repair JSON escape sequences...

❌ Error: Could not parse JSON even after repair:
  JSONDecodeError: Expecting ',' delimiter: line 45 column 12 (char 2145)
  Error at line 45, column 12

  Context around error (line 45):
      42:     "examples": [
      43:       "**प्रथमः खण्डः**",
      44:       "**द्वितीयः खण्डः**"
  >>> 45:     ]
            ^-- Error here

  Full response saved to: .debug_gemini_response_filename.txt
  First 500 chars of cleaned text:
  {
    "metadata": {
      "canonical_title": "छान्दोग्योपनिषत्",
      ...
```

### 4. Debug Files

**Automatically created**: `.debug_gemini_response_<filename>.txt`

**Contents**:
```
=== RAW GEMINI RESPONSE ===
{original response from Gemini, possibly with ```json fences}
=== END RAW RESPONSE ===

=== CLEANED JSON (after fence removal) ===
{response after removing markdown code fences}
=== END CLEANED JSON ===

=== REPAIRED JSON (after escape fix) ===
{response after repair_json_escapes() if repair was attempted}
=== END REPAIRED JSON ===
```

**Purpose**:
- Debug why JSON parsing failed
- See exactly what Gemini returned
- Compare original vs cleaned vs repaired versions
- Manually fix the JSON if automatic repair failed

## Error Messages

### Before (Unhelpful):
```
Error: Could not parse JSON from Gemini response:
  JSONDecodeError: Invalid \escape: line 27 column 31 (char 1258)
❌ File analysis failed: Invalid JSON response from Gemini: Invalid \escape: line 27 column 31 (char 1258)
```

### After (Detailed):
```
📝 Gemini response received (15,234 chars)
💾 Debug: Raw response saved to .debug_gemini_response_test.txt
🔍 Parsing JSON response...
⚠️  Initial JSON parse failed: Invalid \escape: line 27 column 31 (char 1258)
🔧 Attempting to repair JSON escape sequences...
✓ JSON parsed successfully after repair!

✓ Analysis complete:
  📖 Text: छान्दोग्योपनिषत्
  🆔 ID: chhandogya-upanishad
  ...
```

OR if repair fails:

```
❌ Error: Could not parse JSON even after repair:
  JSONDecodeError: Invalid \escape: line 27 column 31 (char 1258)
  Error at line 27, column 31

  Context around error (line 27):
      24:     },
      25:     "start_pattern": {
      26:       "description": "Each Khanda begins with...",
  >>> 27:       "regex": "^\*\*\S+ खण्डः\*\*$"
                                  ^-- Error here

  Full response saved to: .debug_gemini_response_test.txt
  First 500 chars of cleaned text:
  {
    "metadata": {
      "canonical_title": "छान्दोग्योपनिषत्",
      "grantha_id": "chhandogya-upanishad",
      ...
```

## Manual Recovery

If automatic repair fails:

1. **Check the debug file**:
   ```bash
   cat .debug_gemini_response_<filename>.txt
   ```

2. **Look at the "REPAIRED JSON" section**

3. **Manually fix the JSON**:
   - Find all regex patterns
   - Double all backslashes: `\*` → `\\*`, `\S` → `\\S`

4. **Save the fixed JSON** to a file (e.g., `fixed_analysis.json`)

5. **Manually load it** (temporary workaround - would need code modification)

## Common Issues

### Issue 1: Single Backslash in Regex
**Symptom**: `Invalid \escape`
**Cause**: `"regex": "^\*\*\S+ खण्डः\*\*$"`
**Fix**: Automatic repair doubles backslashes

### Issue 2: Missing Comma
**Symptom**: `Expecting ',' delimiter`
**Cause**: Gemini forgot comma between array/object elements
**Fix**: Manual edit required

### Issue 3: Trailing Comma
**Symptom**: `Expecting property name`
**Cause**: Extra comma after last element
**Fix**: Manual edit required

### Issue 4: Unescaped Quotes
**Symptom**: `Unterminated string`
**Cause**: String contains unescaped `"` characters
**Fix**: Manual edit required

## Testing

To test the error handling:

1. **Force an error**: Modify `repair_json_escapes()` to do nothing
2. **Run conversion**: Should see detailed error output
3. **Check debug file**: Should show all three versions of JSON
4. **Restore function**: Re-enable repair logic
5. **Run again**: Should succeed with "after repair!" message

## Statistics

Track JSON repair success rate by checking logs for:
- `✓ JSON parsed successfully` (no repair needed)
- `✓ JSON parsed successfully after repair!` (repair worked)
- `❌ Error: Could not parse JSON even after repair` (repair failed)

This helps identify if Gemini is consistently returning invalid JSON despite our prompt instructions.
