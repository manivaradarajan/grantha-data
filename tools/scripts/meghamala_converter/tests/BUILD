load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_convert_meghamala",
    srcs = ["test_convert_meghamala.py"],
    imports = ["../../../..", "../../../../tools/lib"],
    data = [
        "//tools/scripts/meghamala_converter/prompts",
    ],
    deps = [
        "//tools/scripts/meghamala_converter:convert_meghamala_lib",
        "//tools/lib/gemini_processor:replay_client",
    ],
)
