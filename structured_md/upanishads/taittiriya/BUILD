# BUILD file for upanishads/taittiriya
# Converts structured Markdown to JSON format

load("//tools/bazel:grantha_converter.bzl", "grantha_md2json_multipart")

grantha_md2json_multipart(
    name = "md2json",
    grantha_id = "taittiriya-upanishad",
    markdown_files = [
        "taittiriya-upanishad-rangaramanuja-01-01-01.md",
        "taittiriya-upanishad-rangaramanuja-02-01-01.md",
        "taittiriya-upanishad-rangaramanuja-03-01-01.md",
    ],
)
