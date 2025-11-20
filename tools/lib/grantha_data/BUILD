load("@grantha_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library", "py_test")

# Main grantha_data library
py_library(
    name = "grantha_data",
    srcs = glob(
        ["**/*.py"],
        exclude = [
            "tests/**/*.py",
            "cli.py",
        ],
    ),
    visibility = ["//visibility:public"],
    deps = [
        "//tools/lib/grantha_converter:md_to_json",
        "//tools/lib/grantha_converter:hasher",
    ],
)

# CLI binary (to be implemented)
# py_binary(
#     name = "cli",
#     srcs = ["cli.py"],
#     main = "cli.py",
#     deps = [
#         ":grantha_data",
#         "@pypi//click",
#     ],
#     visibility = ["//visibility:public"],
# )

# Tests
py_test(
    name = "grantha_data_test",
    srcs = glob(["tests/**/*.py"]),
    main = "tests/__init__.py",
    deps = [
        ":grantha_data",
        requirement("pytest"),
    ],
)
