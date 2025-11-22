load("@rules_python//python:defs.bzl", "py_binary", "py_library")

# The executable target for running the script.
py_binary(
    name = "convert_meghamala",
    srcs = ["convert_meghamala.py"],
    main = "convert_meghamala.py",
    deps = [":convert_meghamala_lib"],
)

# The library target that tests can depend on.
py_library(
    name = "convert_meghamala_lib",
    srcs = ["convert_meghamala.py"],
    imports = [".."],
    visibility = ["//visibility:public"],
    deps = [
        "//tools/lib/gemini_processor:client",
        "//tools/lib/gemini_processor:prompt_manager",
        "//tools/lib/gemini_processor:replay_client",
        "//tools/lib/grantha_converter:analyzer",
        "//tools/lib/grantha_converter:meghamala_converter",
        "//tools/lib/grantha_converter:utils",
    ],
)

py_binary(
    name = "batch_repair",
    srcs = ["batch_repair.py"],
    main = "batch_repair.py",
    deps = [":batch_repair_lib"],
)

py_library(
    name = "batch_repair_lib",
    srcs = ["batch_repair.py"],
    imports = [".."],
    visibility = ["//visibility:public"],
    deps = [
        "//tools/lib/grantha_converter:devanagari_extractor",
        "//tools/lib/grantha_converter:devanagari_repair",
        "//tools/lib/grantha_converter:devanagari_validator",
        "//tools/lib/grantha_converter:hasher",
    ],
)
