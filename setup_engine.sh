#!/bin/bash
# Build LocalScribe's pinned speech executable with Xcode on Apple Silicon.
# This fetches source code from GitHub. Model files are provisioned separately.
set -euo pipefail

argmax_url=https://github.com/argmaxinc/argmax-oss-swift
argmax_revision=dcf3a00f0ae4d5b57bc0aad92063b102b70d5fd1
parser_url=https://github.com/apple/swift-argument-parser.git
parser_version=1.8.2
parser_revision=6a52f3251125d74daf04fcbd5e6f08a75d074382

if [[ $(uname -s) != Darwin || $(uname -m) != arm64 ]]; then
    printf '%s\n' 'This setup requires a Mac with Apple Silicon.' >&2
    exit 1
fi
if ! xcrun --find swift >/dev/null || ! command -v python3 >/dev/null; then
    printf '%s\n' 'Install Xcode and Python 3 before building the engine.' >&2
    exit 1
fi

project_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
engine_dir="$project_dir/.build/engine"
mkdir -p "$engine_dir"
stage=$(mktemp -d "$engine_dir/setup.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

source_dir="$stage/argmax-oss-swift"
scratch_dir="$stage/swiftpm"
git init -q "$source_dir"
git -C "$source_dir" fetch --no-tags --depth=1 "$argmax_url" "$argmax_revision"
git -C "$source_dir" checkout --quiet --detach FETCH_HEAD
if [[ $(git -C "$source_dir" rev-parse HEAD) != "$argmax_revision" ]]; then
    printf '%s\n' 'Argmax source revision did not match the expected pin.' >&2
    exit 1
fi
