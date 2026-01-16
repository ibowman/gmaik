#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 'search terms'" >&2
  exit 1
fi

query=$1

# notmuch search is case-insensitive, Gmail-style.
# --output=files gives you the actual Maildir file paths.
results=$(notmuch search --output=files --format=text "${query}")

if [ -z "${results}" ]; then
  # No matches
  exit 1
fi

printf '%s\n' "${results}"
