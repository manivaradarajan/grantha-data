load("@rules_python//python:defs.bzl", "py_test")
load("@grantha_pip//:requirements.bzl", "requirement")

py_test(
    name = "test_convert_meghamala",
    srcs = ["test_convert_meghamala.py"],
    data = [
        "//tools/scripts/meghamala_converter/prompts",
    ],
    imports = [".."],
    deps = [
        "//tools/lib/gemini_processor:replay_client",
        "//tools/scripts/meghamala_converter:convert_meghamala_lib",
        requirement("diff_match_patch"),
        requirement("rapidfuzz"),
    ],
)
