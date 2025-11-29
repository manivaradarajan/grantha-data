# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""A client for interacting with the Gemini API."""

load("@grantha_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_library", "py_test")

py_library(
    name = "base_client",
    srcs = ["base_client.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "client",
    srcs = ["client.py"],
    imports = [".."],
    visibility = ["//visibility:public"],
    deps = [
        "//tools/lib/gemini_processor:base_client",
        "//tools/lib/gemini_processor:file_manager",
        requirement("google-genai"),
    ],
)

py_library(
    name = "replay_client",
    srcs = ["replay_client.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//tools/lib/gemini_processor:base_client",
    ],
)

py_library(
    name = "cache_manager",
    srcs = ["cache_manager.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "prompt_manager",
    srcs = ["prompt_manager.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "sampler",
    srcs = ["sampler.py"],
    visibility = ["//visibility:public"],
)

py_library(
    name = "file_manager",
    srcs = ["file_manager.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//tools/lib/grantha_converter:hasher",
    ],
)

py_library(
    name = "response_parser",
    srcs = ["response_parser.py"],
    visibility = ["//visibility:public"],
)

# Tests
py_test(
    name = "test_cache_manager",
    srcs = ["test_cache_manager.py"],
    imports = [".."],
    deps = [
        ":cache_manager",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_file_manager",
    srcs = ["test_file_manager.py"],
    imports = [".."],
    deps = [
        ":file_manager",
        requirement("google-genai"),
        requirement("pytest"),
    ],
)

py_test(
    name = "test_prompt_manager",
    srcs = ["test_prompt_manager.py"],
    imports = [".."],
    deps = [
        ":prompt_manager",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_response_parser",
    srcs = ["test_response_parser.py"],
    imports = [".."],
    deps = [
        ":response_parser",
        requirement("pytest"),
    ],
)

py_test(
    name = "test_sampler",
    srcs = ["test_sampler.py"],
    imports = [".."],
    deps = [
        ":sampler",
        requirement("pytest"),
    ],
)
