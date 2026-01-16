#!/usr/bin/env python3
import curses
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple


def run_notmuch_json(msg_query: str) -> Any:
    result = subprocess.run(
        ["notmuch", "show", "--format=json", "--entire-thread=false", msg_query],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def find_first_message(node: Any) -> Optional[Dict[str, Any]]:
    if isinstance(node, dict):
        if "headers" in node and "body" in node:
            return node
        for v in node.values():
            m = find_first_message(v)
            if m is not None:
                return m
    elif isinstance(node, list):
        for item in node:
            m = find_first_message(item)
            if m is not None:
                return m
    return None


def collect_body_and_attachments(parts: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    body_lines: List[str] = []
    attachments: List[Dict[str, Any]] = []

    def walk(part: Dict[str, Any]) -> None:
        ctype = part.get("content-type", "")
        filename = part.get("filename") or ""
        part_id = part.get("id")

        if filename:
            attachments.append(
                {"id": part_id, "filename": filename, "content_type": ctype}
            )

        content = part.get("content")
        if isinstance(content, str) and ctype.startswith("text/"):
            body_lines.extend(content.splitlines())
            body_lines.append("")

        children = part.get("content")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    walk(child)

    for p in parts:
        if isinstance(p, dict):
            walk(p)

    while body_lines and body_lines[-1] == "":
        body_lines.pop()

    return body_lines, attachments


def render_message(msg: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]]]:
    width = shutil.get_terminal_size((80, 24)).columns

    headers = msg.get("headers", {})
    norm_headers = {k.lower(): v for k, v in headers.items()}

    subj = norm_headers.get("subject", "(no subject)")
    frm = norm_headers.get("from", "")
    to = norm_headers.get("to", "")
    date = norm_headers.get("date", "")

    body_parts = msg.get("body", [])
    body_lines, attachments = collect_body_and_attachments(body_parts)

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
            fn = att.get("filename") or ""
            ct = att.get("content_type") or ""
            if ct:
                lines.append(f"  [{i}] {fn} ({ct})")
            else:
                lines.append(f"  [{i}] {fn}")

    lines.append("")
    lines.append("-" * min(width, 80))
    lines.append("")

    if body_lines:
        lines.extend(body_lines)
        lines.append("")
    else:
        lines.append("[No text body]")
        lines.append("")

    return lines, attachments


def save_attachment(msg_query: str, att: Dict[str, Any]) -> str:
    part_id = att.get("id")
    filename = att.get("filename") or "attachment.bin"
    if part_id is None:
        return "Cannot save attachment: missing part ID."

    out_path = os.path.abspath(filename)
    try:
        with open(out_path, "wb") as f:
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
    except subprocess.CalledProcessError as e:
        return f"Error saving attachment: {e}"

    return f"Saved to {out_path}"


def attachment_prompt(
    stdscr, attachments: List[Dict[str, Any]], msg_query: str, status: str
) -> str:
    """
    Run an attachment selection prompt inside curses.
    Returns a new status string.
    """
    max_y, max_x = stdscr.getmaxyx()
    stdscr.clear()

    stdscr.addnstr(0, 0, "Attachments:", max_x - 1)
    for i, att in enumerate(attachments, start=1):
        fn = att.get("filename") or ""
        ct = att.get("content_type") or ""
        line = f"{i}. {fn}"
        if ct:
            line += f" ({ct})"
        stdscr.addnstr(i, 0, line, max_x - 1)

    prompt = f"Save which attachment [1-{len(attachments)}], a=all, ESC=cancel: "
    stdscr.addnstr(max_y - 2, 0, prompt[: max_x - 1], max_x - 1)
    stdscr.clrtoeol()
    stdscr.refresh()

    buf = ""
    while True:
        ch = stdscr.getch()
        if ch == 27:  # ESC
            return status
        if ch in (curses.KEY_ENTER, 10, 13):
            choice = buf.strip().lower()
            if not choice:
                return status
            if choice == "a":
                msgs = []
                for att in attachments:
                    msgs.append(save_attachment(msg_query, att))
                return "; ".join(msgs)
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(attachments):
                    return save_attachment(msg_query, attachments[idx - 1])
            return "Invalid attachment selection."
        elif ch in range(ord("0"), ord("9") + 1) or ch in (ord("a"), ord("A")):
            if len(buf) < 10:
                buf += chr(ch)
                stdscr.addnstr(
                    max_y - 2, len(prompt), buf[: max_x - len(prompt) - 1], max_x - 1
                )
                stdscr.refresh()
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if buf:
                buf = buf[:-1]
                stdscr.addnstr(
                    max_y - 2, len(prompt),
                    " " * (max_x - len(prompt) - 1),
                    max_x - 1,
                )
                stdscr.addnstr(
                    max_y - 2, len(prompt),
                    buf[: max_x - len(prompt) - 1],
                    max_x - 1,
                )
                stdscr.refresh()


def curses_pager(
    stdscr, lines: List[str], attachments: List[Dict[str, Any]], msg_query: str
) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)

    top = 0
    status = "↑/↓ PgUp/PgDn scroll  q:back  Q:quit  s:save attachment"

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()
        page_size = max_y - 1  # last line for status

        if top < 0:
            top = 0
        max_top = max(0, len(lines) - page_size)
        if top > max_top:
            top = max_top

        for i in range(page_size):
            idx = top + i
            if idx >= len(lines):
                break
            stdscr.addnstr(i, 0, lines[idx], max_x - 1)

        stdscr.addnstr(page_size, 0, status.ljust(max_x - 1), max_x - 1)
        stdscr.refresh()

        ch = stdscr.getch()

        if ch == ord("q"):
            # back to menu
            return
        if ch == ord("Q"):
            # quit everything
            sys.exit(0)
        if ch == ord("s"):
            if attachments:
                status = attachment_prompt(stdscr, attachments, msg_query, status)
            else:
                status = "No attachments."
            continue

        if ch == curses.KEY_UP:
            if top > 0:
                top -= 1
        elif ch == curses.KEY_DOWN:
            if top < max_top:
                top += 1
        elif ch == curses.KEY_PPAGE:
            top = max(0, top - page_size)
        elif ch == curses.KEY_NPAGE:
            top = min(max_top, top + page_size)
        # ignore everything else


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} 'notmuch-id-term'", file=sys.stderr)
        sys.exit(1)

    msg_query = sys.argv[1]
    data = run_notmuch_json(msg_query)
    msg = find_first_message(data)
    if msg is None:
        print("Error: no message found in notmuch JSON output.", file=sys.stderr)
        sys.exit(1)

    lines, attachments = render_message(msg)
    curses.wrapper(curses_pager, lines, attachments, msg_query)


if __name__ == "__main__":
    main()
