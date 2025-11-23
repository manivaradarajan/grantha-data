# BUILD file for structured_md/
# Top-level aggregation of all JSON conversions

filegroup(
    name = "all_json",
    srcs = [
        "//structured_md/upanishads:all_upanishads_json",
    ],
    visibility = ["//visibility:public"],
)

# Create json_library.zip containing all JSON files organized by category
genrule(
    name = "json_library_zip",
    srcs = [":all_json"],
    outs = ["json_library.zip"],
    cmd = """
        # Create temporary directory structure
        TMP_DIR=$$(mktemp -d)
        LIBRARY_DIR=$$TMP_DIR/library
        mkdir -p $$LIBRARY_DIR

        # Copy all JSON files, preserving directory structure
        for json_file in $(SRCS); do
            # Extract the category and subdirectory from the path
            # Path format: bazel-out/.../structured_md/upanishads/katha/katha-upanishad.json
            # We want: library/upanishads/katha/katha-upanishad.json

            # Get the relative path after structured_md/
            REL_PATH=$$(echo $$json_file | sed 's|.*/structured_md/||')

            # Create parent directory
            mkdir -p $$(dirname $$LIBRARY_DIR/$$REL_PATH)

            # Copy the file
            cp $$json_file $$LIBRARY_DIR/$$REL_PATH
        done

        # Create zip file
        cd $$TMP_DIR
        zip -r $(location json_library.zip) library/

        # Clean up
        rm -rf $$TMP_DIR
    """,
    visibility = ["//visibility:public"],
)
