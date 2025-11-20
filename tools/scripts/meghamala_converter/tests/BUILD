load("@rules_python//python:defs.bzl", "py_test")

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
    ],
)
