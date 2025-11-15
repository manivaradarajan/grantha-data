# Logging and Error Handling Improvements

## What's Been Implemented

### 1. Timestamped Log Directories
- **Location**: `logs/run_YYYYMMDD_HHMMSS/`
- **Function**: `create_log_directory()` - creates timestamped directory
- **Function**: `save_to_log(filename, content, subdir)` - saves files to log directory

### 2. Analysis Logging (DONE)
The following files are now saved for each analysis:
- `analysis/01_analysis_prompt.txt` - The full prompt sent to Gemini
- `analysis/02_analysis_response_raw.txt` - Raw response from Gemini
- `analysis/03_analysis_response_cleaned.json` - After removing markdown fences
- `analysis/04_analysis_response_repaired.json` - After escape sequence repair (if needed)
- `analysis/05_analysis_result.json` - Successfully parsed JSON

## What Still Needs to Be Done

### 3. Chunk Conversion Logging
For each chunk conversion, save:
- `chunks/chunk_{N:03d}_prompt.txt` - Prompt for chunk N
- `chunks/chunk_{N:03d}_response_raw.txt` - Raw response
- `chunks/chunk_{N:03d}_response_cleaned.md` - After removing fences
- `chunks/chunk_{N:03d}_result.md` - Final converted chunk

### 4. Full Stack Traces
Remove or simplify try/except blocks that catch and re-raise. Current locations:
- Line ~518: Gemini client creation
- Line ~538-557: Gemini API call for analysis
- Line ~1840+: Chunk conversion loops
- All validation and file I/O operations

**Recommended approach**: Let Python's default exception handling show full stack traces. Only catch exceptions where we can actually recover or provide better context.

### 5. Error Summary File
Create `error_summary.txt` in log directory if any errors occur:
```
Run: 2025-01-15 14:30:45
Input: /path/to/file.md
Error at: Phase 3, Chunk 5/13

Exception Type: JSONDecodeError
Message: Invalid \escape: line 27 column 31

Full Traceback:
[full stack trace]
```

## Implementation Steps

1. **Add chunk logging**: In `convert_with_regex_chunking()` around line 1840:
   ```python
   # Save chunk prompt
   save_to_log(f"chunk_{chunk_num:03d}_prompt.txt", chunk_prompt, subdir="chunks")

   # Call Gemini...

   # Save response
   save_to_log(f"chunk_{chunk_num:03d}_response_raw.txt", response.text, subdir="chunks")
   save_to_log(f"chunk_{chunk_num:03d}_result.md", chunk_converted, subdir="chunks")
   ```

2. **Simplify error handling**: Replace verbose try/except with simple error messages:
   ```python
   # Before:
   try:
       result = some_operation()
   except Exception as e:
       print(f"Error: {e}")
       if verbose:
           traceback.print_exc()
       raise

   # After:
   result = some_operation()  # Let it raise naturally
   ```

3. **Add error logger**: Wrap main() with top-level exception handler:
   ```python
   def main():
       try:
           # existing code...
       except Exception as e:
           log_dir = create_log_directory()
           error_file = log_dir / "error_summary.txt"
           with open(error_file, 'w') as f:
               f.write(f"Run: {datetime.now()}\n")
               f.write(f"Error: {type(e).__name__}: {e}\n\n")
               traceback.print_exc(file=f)

           # Re-raise to show in console
           raise
   ```

## Benefits

- **Full visibility**: See exactly what's being sent/received from Gemini
- **Debugging**: Can manually inspect/retry failed conversions
- **Reproducibility**: Can recreate exact prompts that caused errors
- **Transparency**: Complete audit trail of the conversion process
