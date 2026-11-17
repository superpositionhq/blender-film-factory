#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$script_dir/bootstrap.py" --yes "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "$script_dir/bootstrap.py" --yes "$@"
else
    echo "Python 3.9 or newer is required." >&2
    exit 127
fi
