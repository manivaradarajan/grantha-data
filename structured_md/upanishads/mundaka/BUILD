# BUILD file for upanishads/mundaka
# Converts structured Markdown to JSON format

load("//tools/bazel:grantha_converter.bzl", "grantha_md2json_multipart")

grantha_md2json_multipart(
    name = "md2json",
    grantha_id = "mundaka-upanishad",
    markdown_files = [
        "mundaka-upanishad-rangaramanuja-01-01-01.md",
        "mundaka-upanishad-rangaramanuja-01-02-01.md",
        "mundaka-upanishad-rangaramanuja-02-01-01.md",
        "mundaka-upanishad-rangaramanuja-02-02-01.md",
        "mundaka-upanishad-rangaramanuja-03-01-01.md",
        "mundaka-upanishad-rangaramanuja-03-02-01.md",
    ],
)
