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
        # 1. Capture the absolute path of the output file BEFORE changing directories
        OUTPUT_PATH="$$(pwd)/$@"

        # 2. Create temporary directory structure
        TMP_DIR=$$(mktemp -d)
        LIBRARY_DIR=$$TMP_DIR/library
        mkdir -p $$LIBRARY_DIR

        # 3. Copy all JSON files, preserving directory structure
        for json_file in $(SRCS); do
            # Get the relative path after structured_md/
            REL_PATH=$$(echo $$json_file | sed 's|.*/structured_md/||')

            # Create parent directory
            mkdir -p $$(dirname $$LIBRARY_DIR/$$REL_PATH)

            # Copy the file
            cp $$json_file $$LIBRARY_DIR/$$REL_PATH
        done

        # 4. Create zip file
        # We cd into temp so the zip root is 'library/'
        cd $$TMP_DIR

        # Zip directly to the captured absolute path ( -q for quiet )
        zip -q -r "$$OUTPUT_PATH" library/

        # 5. Clean up
        cd - > /dev/null
        rm -rf $$TMP_DIR
    """,
    visibility = ["//visibility:public"],
)
