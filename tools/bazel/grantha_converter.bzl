"""Bazel build rules for grantha-converter md2json conversions."""

def _platform_agnostic_filegroup_impl(ctx):
    """Rule implementation that forwards files from deps using exec configuration."""
    files = []
    for dep in ctx.attr.srcs:
        files.extend(dep.files.to_list())
    return [DefaultInfo(files = depset(files))]

platform_agnostic_filegroup = rule(
    implementation = _platform_agnostic_filegroup_impl,
    attrs = {
        "srcs": attr.label_list(
            allow_files = True,
            cfg = "exec",  # Use built-in exec configuration
        ),
    },
)

def grantha_md2json_single(name, grantha_id, markdown_file, visibility = ["//visibility:public"]):
    """Convert a single markdown file to JSON.

    Args:
        name: Name of the build target (typically "md2json")
        grantha_id: The grantha_id from the markdown frontmatter
        markdown_file: Name of the markdown source file
        visibility: Bazel visibility (default: public)
    """
    native.filegroup(
        name = "markdown_files",
        srcs = [markdown_file],
        visibility = visibility,
    )

    # Internal genrule with platform-specific output
    native.genrule(
        name = "_{}_impl".format(name),
        srcs = [":markdown_files"],
        outs = ["{}.json".format(grantha_id)],
        cmd = """
            $(location //tools/lib/grantha_converter:grantha-converter) md2json \\
                -i $(location :markdown_files) \\
                -o $(location {grantha_id}.json)
        """.format(
            grantha_id = grantha_id,
        ),
        tools = ["//tools/lib/grantha_converter:grantha-converter"],
        visibility = ["//visibility:private"],
    )

    # Wrapper that applies null transition for platform-agnostic output
    platform_agnostic_filegroup(
        name = name,
        srcs = [":_{}_impl".format(name)],
        visibility = visibility,
    )

    # Alias for json_files
    platform_agnostic_filegroup(
        name = "json_files",
        srcs = [":{name}".format(name = name)],
        visibility = visibility,
    )


def grantha_md2json_multipart(name, grantha_id, num_parts, visibility = ["//visibility:public"]):
    """Convert multiple markdown files to multipart JSON with envelope.

    Args:
        name: Name of the build target (typically "md2json")
        grantha_id: The grantha_id from the markdown frontmatter
        num_parts: Number of parts (markdown files)
        visibility: Bazel visibility (default: public)
    """
    native.filegroup(
        name = "markdown_files",
        srcs = native.glob(["*.md"]),
        visibility = visibility,
    )

    # Generate list of part output files
    part_outs = ["part{}.json".format(i) for i in range(1, num_parts + 1)]
    all_outs = ["{}.json".format(grantha_id)] + part_outs

    # Get the package path (e.g., "structured_md/upanishads/taittiriya")
    pkg = native.package_name()

    # Internal genrule with platform-specific output
    native.genrule(
        name = "_{}_impl".format(name),
        srcs = [":markdown_files"],
        outs = all_outs,
        cmd = """
            OUT_DIR=$$(dirname $(location {grantha_id}.json))
            $(location //tools/lib/grantha_converter:grantha-converter) md2json \\
                -i {pkg} \\
                -o $$OUT_DIR
        """.format(
            grantha_id = grantha_id,
            pkg = pkg,
        ),
        tools = ["//tools/lib/grantha_converter:grantha-converter"],
        visibility = ["//visibility:private"],
    )

    # Wrapper that applies null transition for platform-agnostic output
    platform_agnostic_filegroup(
        name = name,
        srcs = [":_{}_impl".format(name)],
        visibility = visibility,
    )

    # Alias for json_files
    platform_agnostic_filegroup(
        name = "json_files",
        srcs = [":{name}".format(name = name)],
        visibility = visibility,
    )
