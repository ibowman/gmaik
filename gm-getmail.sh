#!/usr/bin/env bash
set -euo pipefail

mbsync gmail
notmuch new
echo "now you can find emails with ./gm-find.sh" 