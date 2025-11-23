load("@grantha_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library", "py_test")

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
        ":devanagari_extractor",
        ":hasher",
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
        ":visual_diff",  # Added visual_diff dependency
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
    deps = [
        requirement("aksharamukha"),
        requirement("colorama"),
        ":devanagari_extractor",
    ],  # Corrected dependency
)

py_library(
    name = "devanagari_repair",
    srcs = ["devanagari_repair.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":devanagari_extractor",
        requirement("rapidfuzz"),
    ],
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
    deps = [
        ":devanagari_extractor",
        ":hasher",
        requirement("pyyaml"),
    ],
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
        ":devanagari_extractor",
        ":hasher",
        requirement("pyyaml"),
    ],
)

py_library(
    name = "visual_diff",  # New py_library rule for visual_diff
    srcs = ["visual_diff.py"],
    visibility = ["//visibility:public"],
    deps = [
        requirement("diff_match_patch"),
        requirement("aksharamukha"),
        requirement("colorama"),
        requirement("rich"),
    ],
)

py_library(
    name = "devanagari_validator",
    srcs = ["devanagari_validator.py"],
    visibility = ["//visibility:public"],
)

# Tests
py_test(
    name = "test_devanagari_extractor",
    srcs = ["test_devanagari_extractor.py"],
    imports = [".."],
    deps = [
        ":devanagari_extractor",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_devanagari_consistency",
    srcs = ["test_devanagari_consistency.py"],
    imports = [".."],
    deps = [
        ":devanagari_extractor",
        ":devanagari_repair",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_cli_smoke",
    srcs = ["test_cli_smoke.py"],
    imports = [".."],
    deps = [
        requirement("pytest"),
    ],
    # Note: Integration tests will be skipped in Bazel sandbox due to @pytest.mark.skipif
    # decorators. This is expected - smoke tests still verify CLI wiring without data files.
)

py_test(
    name = "test_extraction_consistency",
    srcs = ["test_extraction_consistency.py"],
    imports = [".."],
    deps = [
        ":devanagari_extractor",
        ":hasher",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_commentary_parser",
    srcs = ["test_commentary_parser.py"],
    imports = [".."],
    deps = [
        ":md_to_json",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_conversion_logic",
    srcs = ["test_conversion_logic.py"],
    imports = [".."],
    data = glob(["test_data/**"]),
    deps = [
        ":md_to_json",
        requirement("pytest"),
    ],
)
