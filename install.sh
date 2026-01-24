#!/usr/bin/env bash
set -euo pipefail

MBSYNCRC="$HOME/.mbsyncrc"

if [ ! -f "$MBSYNCRC" ]; then
  echo "Error: $MBSYNCRC not found" >&2
  exit 1
fi

# Extract Maildir path from MaildirStore gmail-local
maildir_path=$(
  awk '
    /^MaildirStore[ \t]+gmail-local/ { in_store=1; next }
    in_store && /^MaildirStore[ \t]+/ { in_store=0 }  # next store, stop caring
    in_store && /^Path[ \t]+/ { print $2; exit }
  ' "$MBSYNCRC"
)

# Extract primary email from IMAPAccount gmail
primary_email=$(
  awk '
    /^IMAPAccount[ \t]+gmail/ { in_acct=1; next }
    in_acct && /^IMAPAccount[ \t]+/ { in_acct=0 }     # next account, stop caring
    in_acct && /^User[ \t]+/ { print $2; exit }
  ' "$MBSYNCRC"
)

echo "Detected values from $MBSYNCRC"
echo
echo "Use these when running 'notmuch setup':"
echo "  Primary email address       -> $primary_email"
echo "  Top-level directory of your email archive -> $maildir_path"
echo
read -r -p "Press Enter to run 'notmuch setup' now, or Ctrl-C to abort..."

notmuch setup
