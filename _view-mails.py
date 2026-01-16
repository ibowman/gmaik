#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Tuple


def run_notmuch_text(msg_query: str) -> str:
    """Run `notmuch show` in text mode and return its output."""
    result = subprocess.run(
        ["notmuch", "show", "--format=text", "--entire-thread=false", msg_query],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout


def parse_notmuch_text(output: str) -> Tuple[Dict[str, str], List[str], List[Dict[str, object]]]:
    """
    Parse notmuch --format=text output.

    Returns:
      headers: dict with keys like 'subject', 'from', 'to', 'date'
      body_lines: list of body lines (no ^L markers, no non-text notices)
      attachments: list of dicts {id: int, filename: str, content_type: str}
                   where `id` is the MIME part number (for --part=N).
    """
    headers: Dict[str, str] = {}
    body_lines: List[str] = []
    attachments: List[Dict[str, object]] = []

    in_header = False
    in_body = False

    for line in output.splitlines():
        if line.startswith("\x0c"):  # Control-L marker
            marker = line[1:].strip()

            if marker.startswith("header{"):
                in_header = True
                continue
            if marker.startswith("header}"):
                in_header = False
                continue

            if marker.startswith("body{"):
                in_body = True
                continue
            if marker.startswith("body}"):
                in_body = False
                continue

            if marker.startswith("attachment{"):
                # Example:
                # attachment{ ID: 3, Filename: invoice-20225109.pdf, Content-type: application/pdf
                meta = marker[len("attachment{"):].strip()
                parts = [p.strip() for p in meta.split(",")]
                part_id = None
                filename = None
                ctype = None
                for p in parts:
                    if p.startswith("ID:"):
                        try:
                            part_id = int(p.split(":", 1)[1].strip())
                        except ValueError:
                            part_id = None
                        continue
                    if p.startswith("Filename:"):
                        filename = p.split(":", 1)[1].strip()
                        continue
                    if p.startswith("Content-type:"):
                        ctype = p.split(":", 1)[1].strip()
                        continue
                if filename:
                    attachments.append(
                        {"id": part_id, "filename": filename, "content_type": ctype}
                    )
                continue

            # Ignore other markers (message{, part{, etc.)
            continue

        if in_header:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
            continue

        if in_body:
            if line.startswith("[Non-text part:"):
                # Skip notmuch's "non-text part" notices
                continue
            body_lines.append(line)

    return headers, body_lines, attachments


def render_message(headers: Dict[str, str], body_lines: List[str], attachments: List[Dict[str, object]]) -> str:
    """Build the display text for the pager."""
    width = shutil.get_terminal_size((80, 24)).columns

    subj = headers.get("subject", "(no subject)")
    frm = headers.get("from", "")
    to = headers.get("to", "")
    date = headers.get("date", "")

    lines: List[str] = []

    lines.append(f"Subject: {subj}")
    if frm:
        lines.append(f"From:    {frm}")
    if to:
        lines.append(f"To:      {to}")
    if date:
        lines.append(f"Date:    {date}")

    if attachments:
        lines.append("")
        lines.append("Attachments:")
        for i, att in enumerate(attachments, start=1):
            ct = att.get("content_type") or ""
            fn = att.get("filename") or ""
            if ct:
                lines.append(f"  [{i}] {fn} ({ct})")
            else:
                lines.append(f"  [{i}] {fn}")

    lines.append("")
    lines.append("-" * min(width, 80))
    lines.append("")

    # Body as-is; notmuch already decoded text parts to UTF-8
    lines.extend(body_lines)

    return "\n".join(lines) + "\n"


def page_text(text: str) -> None:
    """Send text to $PAGER (default less) for scrolling."""
    pager = os.environ.get("PAGER", "less")
    proc = subprocess.run(
        [pager],
        input=text.encode("utf-8", errors="replace"),
    )
    # Ignore pager exit code


def save_attachment(msg_query: str, att: Dict[str, object]) -> None:
    """
    Save a single attachment using notmuch --format=raw --part=N.

    File is written into the current working directory, named as the attachment's filename.
    """
    part_id = att.get("id")
    filename = att.get("filename") or "attachment.bin"
    if part_id is None:
        print("Cannot save attachment: missing part ID.")
        return

    print(f"Saving attachment part {part_id} as {filename} ...")
    with open(filename, "wb") as f:
        subprocess.run(
            [
                "notmuch",
                "show",
                "--format=raw",
                "--entire-thread=false",
                f"--part={part_id}",
                msg_query,
            ],
            stdout=f,
            check=True,
        )
    print(f"Saved to: {os.path.abspath(filename)}")


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} 'notmuch-id-term'", file=sys.stderr)
        sys.exit(1)

    msg_query = sys.argv[1]  # e.g. "id:abcd@example.com"

    # Get and parse notmuch text output
    raw = run_notmuch_text(msg_query)
    headers, body_lines, attachments = parse_notmuch_text(raw)

    # Show message in pager
    text = render_message(headers, body_lines, attachments)
    page_text(text)

    # Post-view command loop (for saving attachments)
    if not attachments:
        return

    while True:
        print()
        cmd = input("Command: [Enter]=back, s=save attachment, q=quit: ").strip().lower()
        if cmd == "":
            # Back to gm-search menu
            return
        if cmd == "q":
            # Quit entire tool chain
            sys.exit(0)
        if cmd == "s":
            # List attachments again with numbers
            print("Attachments:")
            for i, att in enumerate(attachments, start=1):
                ct = att.get("content_type") or ""
                fn = att.get("filename") or ""
                if ct:
                    print(f"  {i}. {fn} ({ct})")
                else:
                    print(f"  {i}. {fn}")
            choice = input(f"Save which attachment [1-{len(attachments)}] (or a=all): ").strip().lower()
            if choice == "a":
                for att in attachments:
                    save_attachment(msg_query, att)
                return
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(attachments):
                    save_attachment(msg_query, attachments[idx - 1])
                    return
            print("Invalid choice.")
        else:
            print("Unknown command.")


if __name__ == "__main__":
    main()
