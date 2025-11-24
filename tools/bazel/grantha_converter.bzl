"""Bazel build rules for grantha-converter md2json conversions."""

def grantha_md2json_single(name, grantha_id, markdown_file, visibility = ["//visibility:public"]):
    """Convert a single markdown file to JSON.

    Args:
        name: Name of the build target (typically "md2json")
        grantha_id: The grantha_id from the markdown frontmatter
        markdown_file: Name of the markdown source file
        visibility: Bazel visibility (default: public)
    """
    native.genrule(
        name = name,
        srcs = [markdown_file],
        outs = ["{}.json".format(grantha_id)],
        cmd = """
            echo "Converting: {markdown_file}" >&2
            $(location //tools/lib/grantha_converter:grantha-converter) md2json \\
                -i $(location {markdown_file}) \\
                -o $(location {grantha_id}.json) || {{
                echo "ERROR: Failed to convert {markdown_file}" >&2
                echo "To see full command, run: bazel build --verbose_failures <target>" >&2
                exit 1
            }}
        """.format(
            markdown_file = markdown_file,
            grantha_id = grantha_id,
        ),
        tools = ["//tools/lib/grantha_converter:grantha-converter"],
        visibility = visibility,
    )

    # Alias for json_files (if name is "md2json")
    if name == "md2json":
        native.filegroup(
            name = "json_files",
            srcs = [":{}".format(name)],
            visibility = visibility,
        )


def _grantha_md2json_part(name, markdown_file, part_num):
    """Generate a single JSON part from a Markdown file as an intermediate output."""
    part_rule_name = "{}_part_{}_rule".format(name, part_num)
    intermediate_out_file = "{}.part{}.json".format(name, part_num)

    native.genrule(
        name = part_rule_name,
        srcs = [markdown_file],
        outs = [intermediate_out_file],
        cmd = """
            echo "Converting part {part_num}: {markdown_file}" >&2
            $(location //tools/lib/grantha_converter:grantha-converter) md2json \\
                --format multipart \\
                -i $(location {markdown_file}) \\
                -o $(location {intermediate_out_file}) || {{
                echo "ERROR: Failed to convert part {part_num}: {markdown_file}" >&2
                echo "To see full command, run: bazel build --verbose_failures <target>" >&2
                exit 1
            }}
        """.format(
            markdown_file = markdown_file,
            intermediate_out_file = intermediate_out_file,
            part_num = part_num,
        ),
        tools = ["//tools/lib/grantha_converter:grantha-converter"],
    )
    return ":" + intermediate_out_file

def grantha_md2json_multipart(name, grantha_id, markdown_files, visibility = ["//visibility:public"]):
    """Convert multiple markdown files to multipart JSON with envelope.

    Args:
        name: Name of the build target (typically "md2json")
        grantha_id: The grantha_id from the markdown frontmatter
        markdown_files: List of markdown source files (in order)
        visibility: Bazel visibility (default: public)
    """
    intermediate_part_labels = [
        _grantha_md2json_part(
            name = name,
            markdown_file = md_file,
            part_num = i + 1,
        )
        for i, md_file in enumerate(markdown_files)
    ]

    envelope_file = "{}/envelope.json".format(grantha_id)
    final_part_files = ["{}/part{}.json".format(grantha_id, i + 1) for i in range(len(markdown_files))]
    all_final_outs = [envelope_file] + final_part_files

    # Generate explicit list of part files for envelope generation
    part_file_locations = " ".join([
        "$$(dirname $(location {envelope_file}))/part{part_num}.json".format(
            envelope_file = envelope_file,
            part_num = i + 1,
        )
        for i in range(len(markdown_files))
    ])

    native.genrule(
        name = name,
        srcs = intermediate_part_labels,
        outs = all_final_outs,
        cmd = """
            OUT_DIR=$$(dirname $(location {envelope_file}))
            mkdir -p $$OUT_DIR

            # Copy intermediate parts to final destination with correct names
            echo "Assembling multipart grantha: {grantha_id}" >&2
            i=1
            for src_part in $(SRCS); do
                cp $$src_part $$OUT_DIR/part$$i.json || {{
                    echo "ERROR: Failed to copy part $$i for {grantha_id}" >&2
                    exit 1
                }}
                i=$$((i+1))
            done

            # Generate envelope from explicitly listed part files
            echo "Generating envelope for: {grantha_id}" >&2
            $(location //tools/lib/grantha_converter:grantha-converter) generate-envelope \\
                --grantha-id {grantha_id} \\
                --output-file $(location {envelope_file}) \\
                {part_files} || {{
                echo "ERROR: Failed to generate envelope for {grantha_id}" >&2
                echo "To see full command, run: bazel build --verbose_failures <target>" >&2
                exit 1
            }}
        """.format(
            grantha_id = grantha_id,
            envelope_file = envelope_file,
            part_files = part_file_locations,
        ),
        tools = ["//tools/lib/grantha_converter:grantha-converter"],
        visibility = visibility,
    )

    # Alias for json_files (if name is "md2json")
    if name == "md2json":
        native.filegroup(
            name = "json_files",
            srcs = [":{}".format(name)],
            visibility = visibility,
        )
