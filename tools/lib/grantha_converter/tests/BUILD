load("@grantha_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "test_utils",
    srcs = ["test_utils.py"],
    imports = ["../.."],
    deps = [
        "//tools/lib/grantha_converter:utils",
    ],
)

py_test(
    name = "test_chunk_converter",
    srcs = ["test_chunk_converter.py"],
    imports = ["../.."],
    deps = [
        "//tools/lib/gemini_processor:client",
        "//tools/lib/grantha_converter:chunk_converter",
    ],
)

py_test(
    name = "test_validator",
    srcs = ["test_validator.py"],
    imports = ["../.."],
    deps = [
        "//tools/lib/grantha_converter:validator",
        requirement("rapidfuzz"),
    ],
)
