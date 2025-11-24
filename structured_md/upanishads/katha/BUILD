# BUILD file for upanishads/katha
# Converts structured Markdown to JSON format

load("//tools/bazel:grantha_converter.bzl", "grantha_md2json_multipart")

grantha_md2json_multipart(
    name = "md2json",
    grantha_id = "katha-upanishad",
    markdown_files = [
        "katha-upanishad-rangaramanuja-01-01.md",
        "katha-upanishad-rangaramanuja-02-01.md",
        "katha-upanishad-rangaramanuja-03-01.md",
        "katha-upanishad-rangaramanuja-04-01.md",
        "katha-upanishad-rangaramanuja-05-01.md",
        "katha-upanishad-rangaramanuja-06-01.md",
    ],
)
