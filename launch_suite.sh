#!/usr/bin/env bash
# Yu-Gi-Oh! Forbidden Memories ROM Suite Launcher (Linux / macOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "Error: Python 3 could not be found. Please install Python 3.10 or newer."
    exit 1
fi

"$PYTHON_CMD" main.py "$@"
