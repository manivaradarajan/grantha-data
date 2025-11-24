# BUILD file for upanishads/kausitaki
# Converts structured Markdown to JSON format

load("//tools/bazel:grantha_converter.bzl", "grantha_md2json_multipart")

grantha_md2json_multipart(
    name = "md2json",
    grantha_id = "kaushitaki-upanishad",
    markdown_files = [
        "kaushitaki-upanishad-rangaramanuja-01-01.md",
        "kaushitaki-upanishad-mula-02-01.md",
        "kaushitaki-upanishad-rangaramanuja-03-01.md",
        "kaushitaki-upanishad-rangaramanuja-04-01.md",
    ],
)
