#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 'search terms'" >&2
  exit 1
fi

query=$1

# notmuch search is case-insensitive and searches headers + body.
results="$(notmuch search "${query}")"

if [ -z "$results" ]; then
  echo "No results."
  exit 1
fi

# Strip everything up to and including the first "; " to get just the subject,
# then number the subjects.
printf '%s\n' "$results" \
  | sed 's/.*; //' \
  | nl -w3 -s'. '
