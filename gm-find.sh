#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
finder="$script_dir/_find-mails.py"

if [ ! -f "$finder" ]; then
    echo "Error: Helper script '_find-mails.py' not found in $script_dir"
    exit 1
fi

# If no arguments provided, default to "Primary" view
if [ $# -eq 0 ]; then
    # We use **/.../** wildcards to match these folders regardless of 
    # where mbsync put them (e.g. inside [Gmail] or at the root).
    query="tag:inbox \
    and not path:\"**/Promotions/**\" \
    and not path:\"**/Social/**\" \
    and not path:\"**/Updates/**\" \
    and not path:\"**/Forums/**\""
    
    python3 "$finder" "$query"
else
    # Pass user arguments directly
    python3 "$finder" "$@"
fi