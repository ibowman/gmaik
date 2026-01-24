#!/usr/bin/env bash
set -euo pipefail

mbsync gmail
notmuch new
echo "search emails with ./gm-search-sh 'search text'" 