load("@rules_python//python:defs.bzl", "py_test")
load("@grantha_pip//:requirements.bzl", "requirement")

py_test(
    name = "test_batch_repair",
    srcs = ["test_batch_repair.py"],
    deps = [
        "//tools/scripts/meghamala_converter:batch_repair_lib",
        requirement("pytest"),
        requirement("pyyaml"),
        requirement("rapidfuzz"),
    ],
)

py_test(
    name = "test_convert_meghamala",
    srcs = ["test_convert_meghamala.py"],
    data = ["//tools/scripts/meghamala_converter/prompts"],
    imports = ["../.."],
    deps = [
        "//tools/scripts/meghamala_converter:convert_meghamala_lib",
        requirement("pytest"),
    ],
)
