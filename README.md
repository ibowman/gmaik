# GMAIK Your Life Easier

## Overview

GMAIK is a lightweight suite of shell and Python tools designed to mirror your Gmail account to a local Maildir using `mbsync`, index it with `notmuch`, and provide a fast, terminal-based workflow for searching, reading, and managing attachments.

Mirroring your Gmail to local storage allows you to browse email instantly without network latency, leverage the powerful `notmuch` search engine, and archive attachments locally to free up Google account storage.

## Features

* **Local Mirror:** Robust syncing via `isync/mbsync`.
* **Instant Search:** Powered by `notmuch`.
* **Terminal UI:** Curses-based interface with Vim-style navigation (`j`/`k`, `/` search) and infinite scrolling.
* **Smart Inbox:** Automatically filters future-dated spam to the bottom of the list to keep your view clean.
* **Attachment Management:** Quickly download attachments directly from the viewer.

## Prerequisites

The examples below assume a Debian/Ubuntu-based system (like Linux Mint).

```sh
sudo apt update
sudo apt install isync notmuch python3
```

You need a Gmail account with IMAP enabled. It is highly recommended to use an **App Password** (generated in your Google Account security settings) rather than your main password.

## Installation & Setup

### 1. Configure mbsync

Create or edit `~/.mbsyncrc` to define your Gmail connection. Replace `<user>` with your Gmail username and `<path>` with the absolute path to your desired storage location.

```ini
IMAPAccount gmail
Host imap.gmail.com
Port 993
User <user>@gmail.com
PassCmd "cat ~/.config/mbsync/gmail.pass"
SSLType IMAPS
AuthMechs LOGIN

IMAPStore gmail-remote
Account gmail

MaildirStore gmail-local
Path <path>
Inbox <path>INBOX
SubFolders Verbatim

Channel gmail
Far :gmail-remote:
Near :gmail-local:
# Exclude duplicates and standard Gmail noise
Patterns * !"[Gmail]/All Mail" !"[Gmail]/Spam" !"[Gmail]/Trash"
Create Both
Expunge None
SyncState *
Sync PullNew PullFlags
```

Test the connection:

```sh
mbsync -V gmail
```

### 2. Install GMAIK

Run the installation script to initialize the index for your local Maildir:

```sh
cd /path/to/gmaik
./install.sh
```

## Usage

### Syncing Email

Pull new emails from Gmail to your local machine:

```sh
./gm-getmail.sh
```

This script is safe to run repeatedly; it only fetches changes since the last sync.

### Browsing & Searching

Launch the interactive interface:

```sh
./gm-find.sh                  # Opens your Inbox (default, newest first)
./gm-find.sh "from:amazon"    # Opens a search result for specific terms
```

### Navigation Controls

The interface supports both standard arrow keys and Vim bindings for efficiency.

| Action | Key (Standard) | Key (Vim) |
| :--- | :--- | :--- |
| **Move Up** | `Up Arrow` | `k` |
| **Move Down** | `Down Arrow` | `j` |
| **Page Up** | `PgUp` | `Ctrl`+`b` |
| **Page Down** | `PgDn` | `Ctrl`+`f` |
| **Jump to Top** | `Home` | `g` |
| **Jump to Bottom** | `End` | `G` |
| **Search** | | `/` |
| **Open Thread** | `Enter` | `Enter` |
| **Back / Quit** | `q` | `q` |

### Reading & Attachments

Once you open a thread, you can read the full conversation.

* **Download Attachments:** Press `d` to save all attachments in the current thread to your current working directory.

## Recommended Workflow

1.  **Sync:** Run `./gm-getmail.sh` to update your local mirror.
2.  **Triage:** Run `./gm-find.sh` to browse your Inbox.
3.  **Search:** Press `/` to quickly find specific receipts or documents.
4.  **Archive:** Periodically log into the Gmail web UI to archive or delete old mail, knowing you have a fast, searchable local copy stored safely on your machine.