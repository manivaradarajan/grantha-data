# BUILD file for upanishads/isavasya
# Converts structured Markdown to JSON format (Vedanta Desika commentary only)

load(
    "//tools/bazel:grantha_converter.bzl",
    "grantha_md2json_single",
)

grantha_md2json_single(
    name = "vedanta-desika",
    grantha_id = "isavasya-upanishad-vedantadesika",
    markdown_file = "isavasya-upanishad-vedantadesika-01.md",
)

grantha_md2json_single(
    name = "srivatsa-narayana",
    grantha_id = "isavasya-upanishad-srivatsanarayana",
    markdown_file = "isavasya-upanishad-srivatsanarayana-01.md",
)
