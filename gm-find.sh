#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
finder="$script_dir/_find-mails.py"

if [ ! -f "$finder" ]; then
    echo "Error: Helper script '_find-mails.py' not found in $script_dir"
    exit 1
fi

# If no arguments provided, default to standard Inbox view
if [ $# -eq 0 ]; then
    python3 "$finder" "tag:inbox"
else
    python3 "$finder" "$@"
fi