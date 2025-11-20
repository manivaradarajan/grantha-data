load("@grantha_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library")

py_library(
    name = "analyzer",
    srcs = ["analyzer.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//tools/lib/gemini_processor:cache_manager",
        "//tools/lib/gemini_processor:client",
        "//tools/lib/gemini_processor:prompt_manager",
        "//tools/lib/gemini_processor:sampler",
    ],
)

py_library(
    name = "chunk_converter",
    srcs = ["chunk_converter.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//tools/lib/gemini_processor:client",
        "//tools/lib/gemini_processor:prompt_manager",
        requirement("pyyaml"),
    ],
)

py_library(
    name = "meghamala_converter",
    srcs = ["meghamala_converter.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":analyzer",
        ":chunk_converter",
        ":devanagari_repair",
        ":meghamala_chunker",
        ":meghamala_stitcher",
        ":utils",
        ":validator",
        "//tools/lib/gemini_processor:client",
        "//tools/lib/gemini_processor:prompt_manager",
        requirement("colorama"),
    ],
)

py_library(
    name = "validator",
    srcs = ["validator.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":devanagari_extractor",
        ":diff_utils",
    ],
)

py_library(
    name = "utils",
    srcs = ["utils.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "devanagari_extractor",
    srcs = ["devanagari_extractor.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "diff_utils",
    srcs = ["diff_utils.py"],
    visibility = ["//visibility:public"],
    deps = [requirement("aksharamukha"), requirement("colorama"), ":devanagari_repair"],
)

py_library(
    name = "devanagari_repair",
    srcs = ["devanagari_repair.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "hasher",
    srcs = ["hasher.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "md_to_json",
    srcs = ["md_to_json.py"],
    visibility = ["//visibility:public"],
    deps = [requirement("pyyaml")],
)

py_library(
    name = "meghamala_chunker",
    srcs = ["meghamala_chunker.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "meghamala_stitcher",
    srcs = ["meghamala_stitcher.py"],
    visibility = ["//visibility:public"],
    deps = [
        requirement("pyyaml"),
        ":devanagari_repair",
    ],
)