#!/bin/bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
python_app="${LOCALSCRIBE_PYTHON:-$project_dir/.build/venv/bin/python}"

if [[ ! -x "$python_app" ]]; then
    printf '%s\n' 'Set up the Python environment using the instructions in README.md.'
    exit 1
fi

exec "$python_app" -B "$project_dir/localscribe.py" "$@"
