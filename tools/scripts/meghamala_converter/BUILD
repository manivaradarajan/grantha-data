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
    visibility = ["//visibility:public"],
    deps = [
        "//tools/lib/gemini_processor:client",
        "//tools/lib/gemini_processor:replay_client",
        "//tools/lib/gemini_processor:prompt_manager",
        "//tools/lib/grantha_converter:meghamala_converter",
        "//tools/lib/grantha_converter:utils",
        "//tools/lib/grantha_converter:analyzer",
    ],
)
