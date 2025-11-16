#!/bin/bash
#
# Git pre-commit hook to validate validation_hash in structured_md files
#
# This hook checks all modified .md files in the structured_md/ directory
# to ensure their validation_hash matches the Devanagari content.
#

set -e

echo "🔍 Validating Devanagari hashes in structured_md files..."

# Get list of staged .md files in structured_md/ directory
staged_files=$(git diff --cached --name-only --diff-filter=ACM | grep '^structured_md/.*\.md$' | grep -v 'README.md' || true)

if [ -z "$staged_files" ]; then
    echo "✓ No structured_md files to validate"
    exit 0
fi

# Count files
file_count=$(echo "$staged_files" | wc -l | tr -d ' ')
echo "  Found $file_count file(s) to validate"

# Track failures
failed_files=()

# Validate each file
while IFS= read -r file; do
    if [ -f "$file" ]; then
        # Use grantha-converter verify-hash command
        if grantha-converter verify-hash -i "$file" > /dev/null 2>&1; then
            echo "  ✓ $file"
        else
            echo "  ✗ $file - validation_hash INVALID" >&2
            failed_files+=("$file")
        fi
    fi
done <<< "$staged_files"

# Report results
if [ ${#failed_files[@]} -eq 0 ]; then
    echo "✓ All validation hashes are valid"
    exit 0
else
    echo ""  echo "✗ Commit blocked: ${#failed_files[@]} file(s) have invalid validation_hash" >&2
    echo "" >&2
    echo "The following files have mismatched validation_hash:" >&2
    for file in "${failed_files[@]}"; do
        echo "  - $file" >&2
    done
    echo "" >&2
    echo "To fix this, run:" >&2
    echo "  grantha-converter update-hash -i <file>" >&2
    echo "" >&2
    echo "Or update all failed files:" >&2
    for file in "${failed_files[@]}"; do
        echo "  grantha-converter update-hash -i \"$file\"" >&2
    done
    echo "" >&2
    exit 1
fi
