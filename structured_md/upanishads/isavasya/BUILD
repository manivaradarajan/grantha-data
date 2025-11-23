# BUILD file for upanishads/isavasya
# Converts structured Markdown to JSON format (Vedanta Desika commentary only)

load(
    "//tools/bazel:grantha_converter.bzl",
    "grantha_md2json_single",
)

grantha_md2json_single(
    name = "md2json",
    grantha_id = "isavasya-upanishad",
    markdown_file = "isavasya-upanishad-vedanta-desika-01.md",
)
