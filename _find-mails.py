#!/usr/bin/env python3
import curses
import json
import subprocess
import sys
import os
from datetime import datetime

# --- Configuration ---
COLOR_PAIR_NORMAL = 1
COLOR_PAIR_BAR = 2

# Default view: Inbox minus the noise (using robust wildcards)
DEFAULT_QUERY = (
    'tag:inbox '
    'and not path:"**/Promotions/**" '
    'and not path:"**/Social/**" '
    'and not path:"**/Forums/**"'
)

def format_date_strict(timestamp):
    if not timestamp: return "            "
    try:
        dt = datetime.fromtimestamp(int(timestamp))
    except:
        return "   Error    "

    now = datetime.now()
    if dt.year == now.year:
        return dt.strftime("%b %d %H:%M").rjust(12)
    else:
        return dt.strftime("%b %d  %Y").rjust(12)

def run_search(query, limit):
    try:
        fetch_limit = limit + 20
        cmd = [
            "notmuch", "search", 
            "--format=json", 
            "--sort=newest-first", 
            f"--limit={fetch_limit}", 
            query
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        data = json.loads(result.stdout)
        
        normal_results = []
        future_results = []
        now_ts = datetime.now().timestamp()
        future_threshold = now_ts + 86400 

        for item in data:
            authors = item.get("authors", "???")
            subject = item.get("subject", "???")
            tags = item.get("tags", [])
            ts = item.get("timestamp", 0)
            
            # Simple subject cleanup
            if tags:
                tag_str = f"({', '.join(tags)})"
                full_subject = f"{subject} {tag_str}"
            else:
                full_subject = subject

            row = {
                "id": f"thread:{item['thread']}",
                "authors": authors,
                "subject": full_subject,
                "date_fmt": format_date_strict(ts),
                "timestamp": ts
            }
            
            if ts > future_threshold:
                future_results.append(row)
            else:
                normal_results.append(row)
        
        return normal_results + future_results
    except Exception as e:
        return str(e)

def draw_loading(stdscr, query):
    stdscr.clear()
    max_y, max_x = stdscr.getmaxyx()
    disp_query = "Primary Inbox" if "Promotions" in query else query
    msg = f"Searching: '{disp_query}'..."
    stdscr.addstr(max_y // 2, max(0, (max_x - len(msg)) // 2), msg, curses.A_BOLD)
    stdscr.refresh()

def draw_list(stdscr, results, selected_idx, scroll_offset, query, total_found, is_loading_more=False):
    stdscr.clear()
    max_y, max_x = stdscr.getmaxyx()
    safe_width = max_x - 1 

    # Header
    stdscr.attron(curses.color_pair(COLOR_PAIR_BAR) | curses.A_BOLD)
    
    # Cleaner Header Title
    if "Promotions" in query:
        header_text = f" GMAIK: Primary Inbox"
    else:
        header_text = f" GMAIK: {query}"
        
    stdscr.addstr(0, 0, " " * safe_width) 
    stdscr.addstr(0, 0, header_text[:safe_width])
    stdscr.attroff(curses.color_pair(COLOR_PAIR_BAR) | curses.A_BOLD)

    w_idx = 5 
    w_sender = 25
    w_sep1 = 3
    w_date = 12
    w_sep2 = 3
    fixed_overhead = w_idx + w_sender + w_sep1 + w_sep2 + w_date
    w_subj = safe_width - fixed_overhead
    if w_subj < 5: w_subj = 5

    height = max_y - 2 

    for i in range(height):
        idx = scroll_offset + i
        if idx >= len(results): break
        
        item = results[idx]
        str_idx = f"{idx+1:>3}.".ljust(w_idx)
        str_sender = item['authors'][:w_sender].ljust(w_sender)
        str_date = item['date_fmt']
        str_subj = item['subject'][:w_subj].ljust(w_subj)
        
        line = f"{str_idx}{str_sender} | {str_subj} | {str_date}"
        
        if idx == selected_idx:
            stdscr.attron(curses.color_pair(COLOR_PAIR_BAR))
            stdscr.addstr(i + 1, 0, line)
            stdscr.attroff(curses.color_pair(COLOR_PAIR_BAR))
        else:
            stdscr.addstr(i + 1, 0, line)

    # Status Bar
    count_str = f"{selected_idx + 1}/{len(results)}"
    status_tail = "[Fetching...]" if is_loading_more else "[/] Search  [q] Quit"
    status_text = f" {count_str}  [j/k] Nav  [Enter] Open  {status_tail}"
    
    try:
        stdscr.attron(curses.color_pair(COLOR_PAIR_BAR))
        stdscr.addstr(max_y - 1, 0, status_text.ljust(safe_width))
        stdscr.attroff(curses.color_pair(COLOR_PAIR_BAR))
    except:
        pass 
    stdscr.refresh()

def prompt_search(stdscr):
    max_y, max_x = stdscr.getmaxyx()
    # Vim style command line
    prompt = "/"
    stdscr.move(max_y - 1, 0)
    stdscr.clrtoeol()
    stdscr.addstr(max_y - 1, 0, prompt, curses.A_BOLD)
    curses.echo()
    curses.curs_set(1)
    try:
        byte_input = stdscr.getstr(max_y - 1, 1)
        return byte_input.decode("utf-8").strip()
    except:
        return None
    finally:
        curses.noecho()
        curses.curs_set(0)

def main(stdscr):
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_PAIR_NORMAL, -1, -1)
    curses.init_pair(COLOR_PAIR_BAR, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.curs_set(0)

    # Use arguments if provided, otherwise default to Primary Inbox
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = DEFAULT_QUERY
    
    max_y, _ = stdscr.getmaxyx()
    current_limit = max_y + 10
    
    draw_loading(stdscr, query)
    results = run_search(query, current_limit)
    
    if isinstance(results, str):
        stdscr.clear()
        stdscr.addstr(0, 0, results)
        stdscr.getch()
        return

    selected_idx = 0
    scroll_offset = 0
    fully_loaded = len(results) < current_limit

    while True:
        max_y, _ = stdscr.getmaxyx()
        list_height = max_y - 2
        total = len(results)

        if not fully_loaded and (selected_idx >= total - 5):
            draw_list(stdscr, results, selected_idx, scroll_offset, query, total, is_loading_more=True)
            current_limit += max_y
            new_results = run_search(query, current_limit)
            if isinstance(new_results, list):
                if len(new_results) < current_limit:
                    fully_loaded = True
                results = new_results
                total = len(results)
            draw_list(stdscr, results, selected_idx, scroll_offset, query, total, is_loading_more=False)
        else:
            draw_list(stdscr, results, selected_idx, scroll_offset, query, total)
        
        key = stdscr.getch()

        if key == ord('q'):
            break
        elif key == ord('/'):  # VIM SEARCH
            new_query = prompt_search(stdscr)
            if new_query:
                query = new_query
                current_limit = max_y + 10
                fully_loaded = False
                draw_loading(stdscr, query)
                results = run_search(query, current_limit)
                if isinstance(results, list):
                    selected_idx = 0
                    scroll_offset = 0
                    fully_loaded = len(results) < current_limit
        elif key == ord('j') or key == curses.KEY_DOWN:
            if selected_idx < total - 1: selected_idx += 1
        elif key == ord('k') or key == curses.KEY_UP:
            if selected_idx > 0: selected_idx -= 1
        elif key == 6 or key == curses.KEY_NPAGE:
            selected_idx = min(total - 1, selected_idx + list_height)
            scroll_offset = min(total - list_height, scroll_offset + list_height)
            if scroll_offset < 0: scroll_offset = 0
        elif key == 2 or key == curses.KEY_PPAGE:
            selected_idx = max(0, selected_idx - list_height)
            scroll_offset = max(0, scroll_offset - list_height)
        elif key == ord('g') or key == curses.KEY_HOME:
            selected_idx = 0
        elif key == ord('G') or key == curses.KEY_END:
            selected_idx = total - 1
        elif (key == ord('\n') or key == curses.KEY_ENTER) and results:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            viewer_script = os.path.join(script_dir, "_view-mails.py")
            thread_id = results[selected_idx]['id']
            curses.endwin()
            subprocess.run([sys.executable, viewer_script, thread_id])
            stdscr.refresh()
            
        if total > 0:
            if selected_idx >= total: selected_idx = total - 1
            if selected_idx < 0: selected_idx = 0
            if selected_idx < scroll_offset:
                scroll_offset = selected_idx
            elif selected_idx >= scroll_offset + list_height:
                scroll_offset = selected_idx - list_height + 1

if __name__ == "__main__":
    curses.wrapper(main)