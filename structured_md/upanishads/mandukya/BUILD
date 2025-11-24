# BUILD file for upanishads/mandukya
# Three separate commentaries on Mandukya Upanishad

load(
    "//tools/bazel:grantha_converter.bzl",
    "grantha_md2json_single",
)

# Rangaramanuja commentary
grantha_md2json_single(
    name = "rangaramanuja",
    grantha_id = "mandukya-upanishad-rangaramanuja",
    markdown_file = "mandukya-upanishad-rangaramanuja-01-01.md",
)

# Kuranarayana Muni commentary
grantha_md2json_single(
    name = "kuranarayana",
    grantha_id = "mandukya-upanishad-kuranarayana",
    markdown_file = "mandukya-upanishad-kuranarayana-muni-01-01.md",
)

# Bharadvajaramanujacharya commentary (Gaudapadiya Karikas)
grantha_md2json_single(
    name = "bharadvajaramanujacharya",
    grantha_id = "mandukya-karika-bharadvajaramanujacharya",
    markdown_file = "mandukya-karika-bharadvajaramanujacharya-01.md",
)

# Aggregate all three commentaries
filegroup(
    name = "json_files",
    srcs = [
        ":bharadvajaramanujacharya",
        ":kuranarayana",
        ":rangaramanuja",
    ],
    visibility = ["//visibility:public"],
)
