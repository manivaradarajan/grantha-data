"""Bazel build rules for creating grantha-data releases."""

def grantha_release_artifact(name, data, schemas, version_file, visibility = ["//visibility:public"]):
    """Create a versioned release artifact (.zip) containing JSON data and schemas.

    Args:
        name: Name of the build target (typically "release")
        data: Label pointing to filegroup with all JSON data files
        schemas: List of schema file labels (e.g., glob(["formats/schemas/*.schema.json"]))
        version_file: Label pointing to VERSION file
        visibility: Bazel visibility (default: public)
    """

    # Read version to use in output filename
    # Note: This is a simplification - in practice we'd need to read VERSION at build time
    # For now, we'll use a pattern-based name
    output_zip = "grantha-data-release.zip"
    manifest_file = "manifest.json"

    native.genrule(
        name = name,
        srcs = [data] + schemas + [version_file],
        outs = [output_zip],
        cmd = """
            set -e

            # Save output path before changing directories
            OUTPUT_PATH="$$(pwd)/$@"

            # Read version from VERSION file
            VERSION=$$(cat $(location {version_file}) | tr -d '\\n')
            echo "Building release for version: $$VERSION" >&2

            # Create temporary working directory
            WORK_DIR=$$(mktemp -d)
            RELEASE_DIR="$$WORK_DIR/grantha-data-v$$VERSION"
            mkdir -p "$$RELEASE_DIR/data/upanishads"
            mkdir -p "$$RELEASE_DIR/schemas"

            # Copy all JSON data files
            echo "Copying JSON data files..." >&2
            for json_file in $(locations {data}); do
                # Extract the relative path structure from the file path
                # Files are in structured_md/upanishads/... pattern
                rel_path=$$(echo $$json_file | sed 's|.*/structured_md/upanishads/|data/upanishads/|')
                dest_dir="$$RELEASE_DIR/$$(dirname $$rel_path)"
                mkdir -p "$$dest_dir"
                cp "$$json_file" "$$RELEASE_DIR/$$rel_path"
            done

            # Copy schema files
            echo "Copying schema files..." >&2
            for schema_file in $(locations {schemas}); do
                cp "$$schema_file" "$$RELEASE_DIR/schemas/"
            done

            # Generate manifest using grantha-manifest CLI
            echo "Generating manifest..." >&2
            $(location //tools/lib/grantha_converter:grantha-manifest) \\
                --data-dir "$$RELEASE_DIR/data/upanishads" \\
                --schemas-dir "$$RELEASE_DIR/schemas" \\
                --version-file $(location {version_file}) \\
                --output "$$RELEASE_DIR/manifest.json"

            # Create zip archive
            echo "Creating release archive..." >&2
            cd "$$WORK_DIR"
            zip -r "grantha-data-v$$VERSION.zip" "grantha-data-v$$VERSION/" >/dev/null

            # Copy to output location (using saved OUTPUT_PATH)
            cp "grantha-data-v$$VERSION.zip" "$$OUTPUT_PATH"

            # Cleanup
            rm -rf "$$WORK_DIR"

            echo "✓ Release artifact created: $$OUTPUT_PATH" >&2
            echo "   (contains grantha-data-v$$VERSION/)" >&2
        """.format(
            data = data,
            schemas = schemas[0] if type(schemas) == type([]) else schemas,
            version_file = version_file,
        ),
        tools = ["//tools/lib/grantha_converter:grantha-manifest"],
        visibility = visibility,
    )
