# GMAIK your life easier

## Overview

GMAIK is a small collection of shell and Python helpers that pull your Gmail account down to local Maildir storage using mbsync, index it with notmuch, and provide terminal workflows for searching and reading mail and saving attachments.

Mirroring your Gmail to local storage makes it easier to free up Google account storage, which can reduce or avoid Google One subscription costs, especially if you receive a lot of large attachments. Note that gmaik does not delete any emails from your Gmail account by itself, leaving the deletion subsequent to your verification that emails have been synced.

## Roadmap

At a high level, gmaik works like this:

1. You configure mbsync to talk to Gmail IMAP and to store all mail in a Maildir on your NAS or other local disk.
2. You run gm-setup.sh once to create the Maildir tree and notmuch index based on your mbsync configuration.
3. You run gm-pull.sh whenever you want to pull new mail from Gmail to local storage.
4. You use gm-find.sh to search the local archive with notmuch and to read messages and save attachments.

Everything happens on your machine. The only network access is mbsync talking to Gmail IMAP to sync emails to your computer.

## Prerequisites on Linux Mint

The examples below assume a recent Linux Mint release with APT.

Install the required packages:

```sh
sudo apt update

# mbsync (from the isync package) and notmuch for indexing
sudo apt install isync notmuch

# Python 3 for the helper scripts
sudo apt install python3 python3-venv 
```

You also need a working Gmail account with IMAP enabled and either an app password or OAuth-based access. The usual and simplest option is to create an app password in your Google account security settings and store it in a file such as `~/.config/mbsync/gmail.pass` with permissions restricted to your user.

## Initial configuration and setup

### Configure mbsync

Create or edit `~/.mbsyncrc` to define your Gmail account, remote store, local Maildir, and a channel that connects them. 

A minimal example looks like this. Note in particular the User, PassCmd, Path, Inbox and Patterns fields, and corresponding comments where applicable:

```ini
IMAPAccount gmail
Host imap.gmail.com
Port 993
User <user>@gmail.com
PassCmd "cat ~/.config/mbsync/gmail.pass"
SSLType IMAPS
AuthMechs LOGIN
PipelineDepth 50

IMAPStore gmail-remote
Account gmail

MaildirStore gmail-local
Path <path>
Inbox <path>INBOX
SubFolders Verbatim

Channel gmail
Far :gmail-remote:
Near :gmail-local:
# The following settings are designed to avoid duplicates (All Mail) 
#  as well as spam and trash. Configure to suit your preferences.
Patterns * !"[Gmail]/All Mail" !"[Gmail]/Spam" !"[Gmail]/Trash"
Create Both
Expunge None
SyncState *
Sync PullNew PullFlags
```

Replace `<user>@gmail.com` with your Gmail address.

Replace `<path>` with the absolute path to the Maildir root where you want mail stored, making sure it is a path that is always accessible when you run gmaik. The path must end with a slash, and the `Inbox` line must point to `INBOX` inside that path.

Verify the `Patterns` field matches the folders that you wish to exclude. See mbsync documentation for details. 

Save the file and run a quick test sync to confirm that mbsync can connect and that the Maildir is created:

```sh
mbsync -VVV gmail
```

This should populate your chosen Maildir path with standard Maildir subdirectories and message files.

### Run gm-setup.sh

Once mbsync is working, run the gmaik setup script from the gmaik repository:

```sh
cd /path/to/gmaik
./gm-setup.sh
```

gm-setup.sh reads your existing `~/.mbsyncrc` and uses it to discover the local Maildir path and channel configuration. It then prepares the local archive for use with gmaik. In particular, it:

- Verifies that the Maildir configured in `MaildirStore gmail-local` exists.
- Configures notmuch to index that Maildir.
- Builds or updates the initial notmuch database so that gm-find.sh can query your archive.

Note gm-setup.sh does not talk to Gmail directly. It only operates on the local Maildir created by mbsync. If you later change the Maildir location in `~/.mbsyncrc`, re-run gm-setup.sh so that gmaik and notmuch are aware of the new path.

## Syncing mail with gm-pull.sh

After initial setup, use the gmaik wrapper script to sync:

```sh
./gm-pull.sh
```

gm-pull.sh calls mbsync for the `gmail` channel using the configuration in `~/.mbsyncrc`. It is safe to run it repeatedly. On each run, it will:

- Connect to Gmail IMAP.
- Pull any new messages into the local Maildir.
- Update message flags locally to reflect changes on the server.

A typical workflow is:

Step 1: Run `./gm-pull.sh` to fetch any new mail from Gmail.
Step 2: Run `./gm-find.sh` to search and work with your local archive.
Step 3: Optionally delete or archive mail inside Gmail once you are satisfied that it has been mirrored locally.

## Searching mail and working with attachments using gm-find.sh

The gm-find.sh script provides an interactive interface for searching your locally mirrored Gmail using notmuch and for opening messages and saving attachments.

Run it from the gmaik repository:

```sh
cd /path/to/gmaik
./gm-find.sh <search string> 
```

The basic flow is:

Step 1: Run gm-find.sh with search query. You can use terms such as

`from:alice@example.com`
`subject:invoice`
`attachment:pdf`
`tag:inbox`

Or any combination that notmuch supports. The query runs entirely against your local Maildir and notmuch index.

Step 2: gm-find.sh shows you a lists the subjects of matching messages, which you can select by entering the corresponding numbers.

Step 3: When you select a message, gm-find.sh launches the viewer script (for example `view-mails.py`) in a pager. Inside the viewer, you can read the message body and headers.

### Saving attachments

While you are viewing a message in the viewer, you can trigger attachment saving from inside the pager using `s`. 

## Typical usage pattern

A simple day to day usage sequence looks like this:

Step 1: Run `./gm-pull.sh` to pull new mail from Gmail to your NAS.
Step 2: Run `./gm-find.sh` and search for whatever you need. Open messages, read them in the terminal, and save any important attachments to local disk.
Step 3: Periodically log in to the Gmail web UI and delete or archive messages that are safely mirrored locally in your gmaik archive to free up Google account storage.

With this workflow, your Gmail becomes a lighter, online inbox, while your NAS (or other local storage) holds the long term archive with full search and attachment access.