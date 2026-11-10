#!/bin/bash
# Build LocalScribe's pinned speech executable with Xcode on Apple Silicon.
# This fetches source code from GitHub. Model files are provisioned separately.
set -euo pipefail

argmax_url=https://github.com/argmaxinc/argmax-oss-swift
argmax_revision=dcf3a00f0ae4d5b57bc0aad92063b102b70d5fd1
parser_url=https://github.com/apple/swift-argument-parser.git
parser_version=1.8.2
parser_revision=6a52f3251125d74daf04fcbd5e6f08a75d074382
