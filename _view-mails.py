#!/usr/bin/env python3
import curses
import json
import os
import subprocess
import sys
import textwrap
import html
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

# --- Configuration ---
COLOR_PAIR_NORMAL = 1
COLOR_PAIR_BAR = 2

# --- HTML Processing (Restored from the "Working" Version) ---

class LayoutHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.block_tags = {
            "p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
            "blockquote", "title", "table", "ul", "ol"
        }
        self.ignore_tags = {"style", "script", "head", "meta", "link"}
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.current_tag in self.ignore_tags:
            return
        
        # Strip invisible junk (ZWNJ, ZWJ, etc)
        clean = data.replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '').replace('\u00a0', ' ')
        # Collapse whitespace
        clean = " ".join(clean.split())
        
        if clean:
            self.parts.append(clean)

    def get_text(self):
        return "".join(self.parts)

def clean_html_to_text(html_content: str) -> str:
    parser = LayoutHTMLParser()
    parser.feed(html_content)
    return parser.get_text()

# --- Content Fetching ---

def run_notmuch_json(msg_query: str) -> Any:
    try:
        result = subprocess.run(
            ["notmuch", "show", "--format=json", "--entire-thread=false", msg_query],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
        )
        return json.loads(result.stdout)
    except:
        return []

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

def get_part_content(part: Dict[str, Any], msg_query: str) -> str:
    content = part.get("content")
    if isinstance(content, str):
        return content
    part_id = part.get("id")
    if part_id is not None:
        try:
            res = subprocess.run(
                ["notmuch", "show", "--format=raw", f"--part={part_id}", msg_query],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
            )
            if res.returncode == 0:
                return res.stdout
        except: pass
    return ""

def collect_body_and_attachments(parts: List[Dict[str, Any]], msg_query: str) -> Tuple[str, List[Dict[str, Any]]]:
    plain_content: List[str] = []
    html_content: List[str] = []
    attachments: List[Dict[str, Any]] = []

    def walk(part: Dict[str, Any]) -> None:
        raw_ctype = part.get("content-type", "").lower()
        media_type = raw_ctype.split(";")[0].strip()
        filename = part.get("filename") or ""
        part_id = part.get("id")

        if filename:
            attachments.append({"id": part_id, "filename": filename, "content_type": raw_ctype})
            if part.get("content-disposition") == "attachment":
                return

        payload = get_part_content(part, msg_query)

        if media_type == "text/plain":
            plain_content.append(payload)
        elif media_type == "text/html":
            html_content.append(payload)

        children = part.get("content")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    walk(child)

    for p in parts:
        if isinstance(p, dict):
            walk(p)

    if html_content:
        full_html = "\n".join(html_content)
        return clean_html_to_text(full_html), attachments
    elif plain_content:
        return "\n".join(plain_content), attachments
    
    return "[No readable text content found]", attachments

def reflow_text(text: str, width: int) -> List[str]:
    lines = []
    raw_lines = text.splitlines()
    for raw_line in raw_lines:
        clean_line = raw_line.strip()
        if not clean_line:
            lines.append("")
            continue
        wrapped = textwrap.wrap(clean_line, width=width, break_long_words=True)
        lines.extend(wrapped)

    final_lines = []
    empty_count = 0
    while lines and not lines[0]:
        lines.pop(0)
    for line in lines:
        if not line:
            empty_count += 1
            if empty_count <= 1:
                final_lines.append("")
        else:
            empty_count = 0
            final_lines.append(line)
    return final_lines

# --- UI Logic ---

def view_mail(stdscr, thread_id: str):
    # Setup Colors (White on Blue for bars)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_PAIR_NORMAL, -1, -1)
    curses.init_pair(COLOR_PAIR_BAR, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.curs_set(0)

    data = run_notmuch_json(thread_id)
    message = find_first_message(data)
    
    if not message:
        full_content = ["Error: Could not load message body."]
        attachments = []
    else:
        headers = message.get("headers", {})
        raw_body, attachments = collect_body_and_attachments(message.get("body", []), thread_id)
        
        max_y, max_x = stdscr.getmaxyx()
        wrap_width = min(max_x - 4, 100)
        
        body_lines = reflow_text(raw_body, wrap_width)
        
        header_block = [
            f"From:    {headers.get('From', '???')}",
            f"Date:    {headers.get('Date', '???')}",
            f"Subject: {headers.get('Subject', '???')}",
            "-" * wrap_width
        ]
        full_content = header_block + body_lines
        if attachments:
            full_content.append("")
            full_content.append(f"[{len(attachments)} Attachments included. Press 's' to save]")

    top = 0
    total_lines = len(full_content)

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()
        page_size = max_y - 2 

        # Draw Text
        for i in range(page_size):
            idx = top + i
            if idx >= total_lines:
                break
            
            line = full_content[idx]
            # Headers in Blue (first 3 lines) to match theme? 
            # Or just keep plain. Let's keep plain for readability, maybe Bold.
            attr = curses.A_BOLD if idx < 3 else curses.A_NORMAL
            
            if len(line) > max_x:
                line = line[:max_x-1]
            try:
                stdscr.addstr(i, 0, line, attr)
            except curses.error:
                pass

        # Draw Status Bar
        status = f" [Arrows] Scroll  [PgUp/PgDn] Page  [q] Back"
        if attachments:
            status += "  [s] Save Att."
            
        try:
            stdscr.attron(curses.color_pair(COLOR_PAIR_BAR))
            stdscr.addstr(max_y - 1, 0, status.ljust(max_x - 1))
            stdscr.attroff(curses.color_pair(COLOR_PAIR_BAR))
        except curses.error:
            pass

        stdscr.refresh()

        ch = stdscr.getch()

        if ch == ord("q"):
            return 

        elif ch == ord("s") and attachments:
            # Simple save
            count = 0
            for att in attachments:
                fname = os.path.basename(att["filename"]) or f"att_{att['id']}"
                try:
                    with open(fname, "wb") as f:
                        subprocess.run(
                            ["notmuch", "show", "--format=raw", f"--part={att['id']}", thread_id],
                            stdout=f, check=True
                        )
                    count += 1
                except: pass
            
            # Feedback
            msg = f"Saved {count} files to {os.getcwd()}"
            stdscr.attron(curses.color_pair(COLOR_PAIR_BAR))
            stdscr.addstr(max_y-2, 0, msg.ljust(max_x-1))
            stdscr.attroff(curses.color_pair(COLOR_PAIR_BAR))
            stdscr.refresh()
            curses.napms(1000)

        # Scroll Down (j / Down)
        elif ch == ord("j") or ch == curses.KEY_DOWN:
            if top < total_lines - page_size:
                top += 1

        # Scroll Up (k / Up)
        elif ch == ord("k") or ch == curses.KEY_UP:
            if top > 0:
                top -= 1

        # Page Down (Ctrl+F / PgDn / Space)
        elif ch == 6 or ch == curses.KEY_NPAGE or ch == ord(" "):
            top = min(total_lines - page_size, top + page_size)
            if top < 0: top = 0

        # Page Up (Ctrl+B / PgUp)
        elif ch == 2 or ch == curses.KEY_PPAGE:
            top = max(0, top - page_size)

        # Top / Bottom
        elif ch == ord("g") or ch == curses.KEY_HOME:
            top = 0
        elif ch == ord("G") or ch == curses.KEY_END:
            top = max(0, total_lines - page_size)

def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    
    thread_id = sys.argv[1]
    curses.wrapper(view_mail, thread_id)

if __name__ == "__main__":
    main()