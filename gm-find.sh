#!/usr/bin/env bash
set -euo pipefail

if ! command -v notmuch >/dev/null 2>&1; then
  echo "Error: notmuch not found in PATH" >&2
  exit 1
fi

if [ $# -lt 1 ]; then
  echo "Usage: $0 'search terms'" >&2
  exit 1
fi

# Allow multi-word queries without extra quoting
query="$*"

# 1. Fetch Summaries (Default output is one line per THREAD)
summaries_raw="$(notmuch search "${query}")"

# 2. Fetch Thread IDs (Ensure we get one ID per THREAD to match summaries)
# changed --output=messages to --output=threads
ids_raw="$(notmuch search --output=threads --format=text "${query}")"

if [ -z "$summaries_raw" ] || [ -z "$ids_raw" ]; then
  echo "No results."
  exit 0
fi

mapfile -t summaries <<<"$summaries_raw"
mapfile -t thread_ids <<<"$ids_raw"

# Sanity check: These should now always match
if [ "${#summaries[@]}" -ne "${#thread_ids[@]}" ]; then
  echo "Error: notmuch returned mismatched summary and thread counts." >&2
  echo "Summaries: ${#summaries[@]}, Threads: ${#thread_ids[@]}" >&2
  exit 1
fi

# Clean up summaries for display (remove the 'thread:xxx' prefix visual noise if present, 
# though standard summary usually formats nicely).
# We'll just display the raw summary line as notmuch formats it well.

num_results=${#summaries[@]}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
viewer="$script_dir/_view-mails.py"

while true; do
  echo
  echo "Search results for: $query"
  echo
  
  # Print list with indices
  for ((i = 0; i < num_results; i++)); do
    # Cleanup: remove the leading 'thread:...' ID from the display line for cleanliness
    # Notmuch summary usually looks like: "thread:000...   Today [1/1] Sender; Subject (tags)"
    # We strip everything up to the first space to hide the ID.
    display_line="${summaries[$i]}"
    # obscure the raw thread-id from the visual output
    clean_line=$(echo "$display_line" | sed -E 's/^thread:[^[:space:]]+ +//')
    
    printf "%3d. %s\n" "$((i + 1))" "$clean_line"
  done

  echo
  read -r -p "Read [1-$num_results] (q to quit): " choice

  if [[ "$choice" == "q" || "$choice" == "Q" ]]; then
    exit 0
  fi

  # Validate input is a number
  if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "$num_results" ]; then
    idx=$((choice - 1))
    selected_thread_id="${thread_ids[$idx]}"
    
    # Pass the THREAD ID to the python viewer
    python3 "$viewer" "$selected_thread_id"
    
    # Clear screen after returning from viewer for a clean menu
    clear
  else
    echo "Invalid selection."
    sleep 1
    clear
  fi
done