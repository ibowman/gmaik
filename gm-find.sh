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

summaries_raw="$(notmuch search "${query}")"
ids_raw="$(notmuch search --output=messages --format=text "${query}")"

if [ -z "$summaries_raw" ] || [ -z "$ids_raw" ]; then
  echo "No results."
  exit 1
fi

mapfile -t summaries <<<"$summaries_raw"
mapfile -t msg_ids <<<"$ids_raw"

if [ "${#summaries[@]}" -ne "${#msg_ids[@]}" ]; then
  echo "Error: notmuch returned mismatched summary and message counts." >&2
  exit 1
fi

# Extract just the subject part after the first "; "
subjects=()
for line in "${summaries[@]}"; do
  subjects+=( "${line#*; }" )
done

num_results=${#subjects[@]}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
viewer="$script_dir/_view-mails.py"

while true; do
  echo
  echo "Search results for: $query"
  echo

  for ((i = 0; i < num_results; i++)); do
    printf "%3d. %s\n" "$((i + 1))" "${subjects[$i]}"
  done

  echo
  read -r -p "Read [1-${num_results}] (Q to quit): " choice

  case "$choice" in
    Q|q)
      exit 0
      ;;
    *)
      if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= num_results )); then
        idx=$((choice - 1))
        id="${msg_ids[$idx]}"
        # Call the viewer via python3 explicitly
        python3 "$viewer" "$id"
      else
        echo "Invalid selection."
      fi
      ;;
  esac
done
