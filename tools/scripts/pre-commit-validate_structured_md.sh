#!/bin/bash
#
# Git pre-commit hook to validate structured_md files
#
# This hook checks files passed as arguments (which come from the pre-commit framework)
# to ensure:
#   1. Their frontmatter structure is valid (validate-header)
#   2. Their validation_hash matches the Devanagari content (verify-hash)
#

set -e

echo "🔍 Validating structured_md files..."

# The pre-commit framework passes the staged files matching the regex as arguments ($@)
staged_files="$@"

if [ -z "$staged_files" ];
then
    echo "✓ No structured_md files to validate"
    exit 0
fi

# Count files passed as arguments
file_count=$(echo "$staged_files" | wc -w | tr -d ' ')
echo "  Found $file_count file(s) to validate"

# Track failures
failed_header_files=()
failed_hash_files=()

# Validate each file
for file in $staged_files;
do
    if [ -f "$file" ]; then
        header_ok=true
        hash_ok=true

        # 1. Validate header structure
        if ! grantha-converter validate-header -i "$file" > /dev/null 2>&1;
        then
            header_ok=false
            failed_header_files+=("$file")
        fi

        # 2. Validate hash
        if ! grantha-converter verify-hash -i "$file" > /dev/null 2>&1;
        then
            hash_ok=false
            failed_hash_files+=("$file")
        fi

        # Print status
        if [ "$header_ok" = true ] && [ "$hash_ok" = true ];
        then
            echo "  ✓ $file"
        else
            status=""
            if [ "$header_ok" = false ]; then
                status="${status}header"
            fi
            if [ "$hash_ok" = false ]; then
                if [ -n "$status" ]; then
                    status="${status}, hash"
                else
                    status="hash"
                fi
            fi
            echo "  ✗ $file - $status INVALID" >&2
        fi
    fi
done

# Report results
total_failures=$((${#failed_header_files[@]} + ${#failed_hash_files[@]}))

if [ $total_failures -eq 0 ];
then
    echo "✓ All validations passed"
    exit 0
else
    echo ""  >&2
    echo "✗ Commit blocked: validation failures detected" >&2
    echo "" >&2

    # Report header validation failures
    if [ ${#failed_header_files[@]} -gt 0 ];
    then
        echo "Header validation failed for ${#failed_header_files[@]} file(s):" >&2
        for file in "${failed_header_files[@]}";
        do
            echo "  - $file" >&2
        done
        echo "" >&2
        echo "To see details, run:" >&2
        for file in "${failed_header_files[@]}";
        do
            echo "  grantha-converter validate-header -i \"$file\"" >&2
        done
        echo "" >&2
    fi

    # Report hash validation failures
    if [ ${#failed_hash_files[@]} -gt 0 ];
    then
        echo "Hash validation failed for ${#failed_hash_files[@]} file(s):" >&2
        for file in "${failed_hash_files[@]}";
        do
            echo "  - $file" >&2
        done
        echo "" >&2
        echo "To fix, run:" >&2
        for file in "${failed_hash_files[@]}";
        do
            echo "  grantha-converter update-hash -i \"$file\"" >&2
        done
        echo "" >&2
    fi

    exit 1
fi
