#!/usr/bin/env python3
"""
Generate BUILD files in structured_md/ subdirectories for JSON conversion.

This script:
1. Scans structured_md/ for subdirectories
2. Generates BUILD files that convert .md to .json using grantha-converter
3. Places BUILD files alongside the source markdown files
"""

import sys
from pathlib import Path


def get_grantha_id(md_file: Path) -> str:
    """Extract grantha_id from a markdown file's frontmatter."""
    with open(md_file, 'r', encoding='utf-8') as f:
        in_frontmatter = False
        for line in f:
            line = line.strip()
            if line == '---':
                if in_frontmatter:
                    break  # End of frontmatter
                in_frontmatter = True
                continue
            if in_frontmatter and line.startswith('grantha_id:'):
                return line.split(':', 1)[1].strip()
    raise ValueError(f"Could not find grantha_id in {md_file}")


def create_build_file(
    structured_md_dir: Path,
    grantha_id: str,
    category: str,
    subdir: str,
    num_parts: int,
    md_files: list
):
    """Create a BUILD file for converting MD to JSON."""

    # grantha_id is used to name the output file
    # This is required by Bazel's genrule which needs declared outputs

    if num_parts == 1:
        # Single-file grantha
        markdown_file = md_files[0].name
        build_content = f'''# BUILD file for {category}/{subdir}
# Converts structured Markdown to JSON format

load("//tools/bazel:grantha_converter.bzl", "grantha_md2json_single")

grantha_md2json_single(
    name = "md2json",
    grantha_id = "{grantha_id}",
    markdown_file = "{markdown_file}",
)
'''
    else:
        # Multi-part grantha - list files explicitly
        file_list = ",\n        ".join([f'"{f.name}"' for f in md_files])
        build_content = f'''# BUILD file for {category}/{subdir}
# Converts structured Markdown to JSON format

load("//tools/bazel:grantha_converter.bzl", "grantha_md2json_multipart")

grantha_md2json_multipart(
    name = "md2json",
    grantha_id = "{grantha_id}",
    markdown_files = [
        {file_list},
    ],
)
'''

    build_path = structured_md_dir / "BUILD"
    build_path.write_text(build_content)
    print(f"  ✓ Created {build_path}")


def main():
    repo_root = Path(__file__).parent.parent.parent
    structured_md = repo_root / "structured_md"

    if not structured_md.exists():
        print(f"Error: {structured_md} does not exist", file=sys.stderr)
        return 1

    # Find all category directories (e.g., upanishads)
    categories = [d for d in structured_md.iterdir() if d.is_dir() and not d.name.startswith('.')]

    if not categories:
        print(f"No categories found in {structured_md}", file=sys.stderr)
        return 1

    print(f"Found {len(categories)} category directories in structured_md/")

    total_created = 0

    for category_dir in sorted(categories):
        category = category_dir.name
        print(f"\nProcessing category: {category}")

        # Find subdirectories (e.g., isavasya, katha, etc.)
        subdirs = [d for d in category_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

        for subdir_path in sorted(subdirs):
            subdir = subdir_path.name

            # Find markdown files
            md_files = sorted(subdir_path.glob('*.md'))
            if not md_files:
                print(f"  ⚠️  No .md files in {category}/{subdir}, skipping")
                continue

            # Extract grantha_id from first file
            try:
                grantha_id = get_grantha_id(md_files[0])
            except Exception as e:
                print(f"  ⚠️  Could not extract grantha_id from {md_files[0].name}: {e}")
                continue

            # Create BUILD file in the structured_md subdirectory
            num_parts = len(md_files)
            create_build_file(subdir_path, grantha_id, category, subdir, num_parts, md_files)

            total_created += 1
            print(f"  ✓ {category}/{subdir} -> structured_md/{category}/{subdir}/BUILD (grantha_id: {grantha_id}, {num_parts} parts)")

    print(f"\n{'='*60}")
    print(f"✅ Created {total_created} BUILD files in structured_md/")
    print(f"{'='*60}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
