#!/bin/bash
#
# Git pre-commit hook to validate validation_hash in structured_md files

#!/bin/bash
#
# Git pre-commit hook to validate validation_hash in structured_md files
#
# This hook checks files passed as arguments (which come from the pre-commit framework)
# to ensure their validation_hash matches the Devanagari content.
#

set -e

echo "🔍 Validating Devanagari hashes in structured_md files..."

# The pre-commit framework passes the staged files matching the regex as arguments ($@)
staged_files="$@"

if [ -z "$staged_files" ];
then
    echo "✓ No structured_md files to validate"
    exit 0
fi

# We need to treat the arguments as separate lines for the loop
# We'll use 'echo "$staged_files"' and pipe it to the loop, which handles spaces better
# than the original `staged_files=$(...)` method for counting.

# Count files passed as arguments
file_count=$(echo "$staged_files" | wc -w | tr -d ' ')
echo "  Found $file_count file(s) to validate"

# Track failures
failed_files=()

# Validate each file
# IFS=' ' ensures files with spaces in their names are handled correctly if passed as separate arguments
while IFS= read -r file;
do
    if [ -f "$file" ]; then
        # Use grantha-converter verify-hash command
        if grantha-converter verify-hash -i "$file" > /dev/null 2>&1;
        then
            echo "  ✓ $file"
        else
            echo "  ✗ $file - validation_hash INVALID" >&2
            failed_files+=("$file")
        fi
    fi
done <<< "$staged_files"

# Report results
if [ ${#failed_files[@]} -eq 0 ];
then
    echo "✓ All validation hashes are valid"
    exit 0
else
    echo ""  >&2
    echo "✗ Commit blocked: ${#failed_files[@]} file(s) have invalid validation_hash" >&2
    echo "" >&2
    echo "The following files have mismatched validation_hash:" >&2
    for file in "${failed_files[@]}";
    do
        echo "  - $file" >&2
    done
    echo "" >&2
    echo "To fix this, run:" >&2
    echo "  grantha-converter update-hash -i <file>" >&2
    echo "" >&2
    echo "Or update all failed files:" >&2
    for file in "${failed_files[@]}";
    do
        echo "  grantha-converter update-hash -i \"$file\"" >&2
    done
    echo "" >&2
    exit 1
fi
