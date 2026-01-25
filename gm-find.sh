#!/usr/bin/env bash
set -euo pipefail

# Locate the directory where this script lives
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
finder="$script_dir/_find-mails.py"

if [ ! -f "$finder" ]; then
    echo "Error: Helper script '_find-mails.py' not found in $script_dir"
    exit 1
fi

# Pass all arguments (the search query) to the python script
python3 "$finder" "$@"