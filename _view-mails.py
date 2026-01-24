#!/usr/bin/env python3
import curses
import json
import os
import subprocess
import sys
import textwrap
import html
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

# --- HTML Processing ---

class LayoutHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        # Structural tags: just a single newline to keep things tight.
        # We rely on 'reflow_text' to add readable spacing later if needed.
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
        
        # 1. Strip "Invisible" junk (ZWNJ, ZWJ, BOM, etc) common in email hacks
        # \u200c = Zero Width Non-Joiner (The Economist uses this heavily)
        # \u200d = Zero Width Joiner
        # \ufeff = BOM
        # \u00a0 = Non-breaking space (turn into normal space)
        clean = data.replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '').replace('\u00a0', ' ')
        
        # 2. Collapse internal whitespace to single spaces
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
    result = subprocess.run(
        ["notmuch", "show", "--format=json", "--entire-thread=false", msg_query],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
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
        except Exception:
            pass
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

    # Always prefer HTML for newsletters because plain text is often broken/missing
    if html_content:
        full_html = "\n".join(html_content)
        return clean_html_to_text(full_html), attachments
    elif plain_content:
        return "\n".join(plain_content), attachments
    
    return "[No readable text content found]", attachments

def reflow_text(text: str, width: int) -> List[str]:
    """
    Wraps text and aggressively collapses vertical whitespace.
    """
    lines = []
    # 1. Split into paragraphs by newline
    # Since our HTML parser emits newlines for tags, we respect them here.
    raw_lines = text.splitlines()
    
    for raw_line in raw_lines:
        clean_line = raw_line.strip()
        if not clean_line:
            lines.append("") # Mark empty line
            continue
        
        # Wrap the line naturally
        wrapped = textwrap.wrap(clean_line, width=width, break_long_words=True)
        lines.extend(wrapped)

    # 2. Vertical Squeeze: Max 1 empty line in a row
    # This specifically fixes the "Also:... [huge gap] ... January" issue
    final_lines = []
    empty_count = 0
    
    # Strip leading empty lines completely
    while lines and not lines[0]:
        lines.pop(0)

    for line in lines:
        if not line:
            empty_count += 1
            if empty_count <= 1: # Allow only 1 blank line
                final_lines.append("")
        else:
            empty_count = 0
            final_lines.append(line)

    return final_lines

# --- UI Logic ---

def render_message(stdscr: Any, msg: Dict[str, Any], msg_query: str) -> None:
    curses.curs_set(0)
    stdscr.nodelay(False)
    
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN, -1)   # Headers
    curses.init_pair(2, curses.COLOR_GREEN, -1)  # Status bar

    headers = msg.get("headers", {})
    raw_body, attachments = collect_body_and_attachments(msg.get("body", []), msg_query)
    
    max_y, max_x = stdscr.getmaxyx()
    wrap_width = min(max_x - 4, 100) # -4 for margins, cap at 100 chars
    
    body_lines = reflow_text(raw_body, wrap_width)
    
    header_block = [
        f"From:    {headers.get('From', '???')}",
        f"Date:    {headers.get('Date', '???')}",
        f"Subject: {headers.get('Subject', '???')}",
        "-" * wrap_width
    ]
    
    full_content = header_block + body_lines
    total_lines = len(full_content)
    top = 0
    
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
            attr = curses.color_pair(1) if idx < 3 else curses.A_NORMAL
            
            if len(line) > max_x:
                line = line[:max_x-1]
            try:
                stdscr.addstr(i, 0, line, attr)
            except curses.error:
                pass

        # Draw Status Bar
        status = f" [q] Quit  [s] Save ({len(attachments)})  [Arrows] Scroll"
        try:
            stdscr.attron(curses.color_pair(2) | curses.A_REVERSE)
            stdscr.addstr(max_y - 1, 0, status.ljust(max_x - 1)[:max_x-1])
            stdscr.attroff(curses.color_pair(2) | curses.A_REVERSE)
        except curses.error:
            pass
            
        stdscr.refresh()

        ch = stdscr.getch()

        if ch == ord('q'):
            return 

        elif ch == ord('s'):
            if attachments:
                save_dir = os.getcwd()
                count = 0
                for att in attachments:
                    fname = os.path.basename(att["filename"]) or f"att_{att['id']}"
                    try:
                        with open(fname, "wb") as f:
                            subprocess.run(
                                ["notmuch", "show", "--format=raw", f"--part={att['id']}", msg_query],
                                stdout=f, check=True
                            )
                        count += 1
                    except: pass
                
                msg_str = f"Saved {count} files."
                stdscr.addstr(max_y-2, 0, msg_str[:max_x-1], curses.A_BOLD)
                stdscr.refresh()
                curses.napms(1000)
            else:
                stdscr.addstr(max_y-2, 0, "No attachments.", curses.A_BOLD)
                stdscr.refresh()
                curses.napms(500)

        elif ch == curses.KEY_UP:
            top = max(0, top - 1)
        elif ch == curses.KEY_DOWN:
            top = min(max(0, total_lines - page_size), top + 1)
        elif ch == curses.KEY_PPAGE:
            top = max(0, top - page_size)
        elif ch == curses.KEY_NPAGE:
            top = min(max(0, total_lines - page_size), top + page_size)
        elif ch == curses.KEY_HOME:
            top = 0
        elif ch == curses.KEY_END:
            top = max(0, total_lines - page_size)

def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(1)

    msg_query = sys.argv[1]
    try:
        data = run_notmuch_json(msg_query)
        msg = find_first_message(data)
        if msg:
            curses.wrapper(lambda stdscr: render_message(stdscr, msg, msg_query))
        else:
            print("Error: content not found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()