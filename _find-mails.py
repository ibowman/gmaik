#!/usr/bin/env python3
import curses
import json
import subprocess
import sys
import os

# --- Configuration ---
# High Contrast Scheme (White on Blue)
COLOR_PAIR_NORMAL = 1
COLOR_PAIR_BAR = 2

def run_search(query):
    """Run notmuch search and return a list of dicts. Blocking call."""
    try:
        cmd = ["notmuch", "search", "--format=json", query]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        data = json.loads(result.stdout)
        
        results = []
        for item in data:
            date_str = item.get("date_relative", "")
            authors = item.get("authors", "???")
            subject = item.get("subject", "???")
            tags = item.get("tags", [])
            
            # Format: "Authors | Subject (Tags)"
            summary = f"{authors:<20} | {subject} ({', '.join(tags)})"
            
            results.append({
                "id": f"thread:{item['thread']}",
                "summary": summary,
                "date": date_str
            })
        return results
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"
    except json.JSONDecodeError:
        return "Error: Could not parse notmuch output."
    except Exception as e:
        return f"Error: {str(e)}"

def draw_loading(stdscr, query):
    stdscr.clear()
    max_y, max_x = stdscr.getmaxyx()
    msg = f"Searching for: '{query}'..."
    y = max_y // 2
    x = max(0, (max_x - len(msg)) // 2)
    
    stdscr.addstr(y, x, msg, curses.A_BOLD)
    stdscr.refresh()

def draw_list(stdscr, results, selected_idx, scroll_offset, query):
    stdscr.clear()
    max_y, max_x = stdscr.getmaxyx()
    height = max_y - 2 # Reserve lines for status bar

    # Header
    # Blue background, White text
    stdscr.attron(curses.color_pair(COLOR_PAIR_BAR) | curses.A_BOLD)
    header = f" Results: {query} ({len(results)} found)"
    stdscr.addstr(0, 0, header.ljust(max_x)[:max_x])
    stdscr.attroff(curses.color_pair(COLOR_PAIR_BAR) | curses.A_BOLD)

    # Draw List
    for i in range(height):
        idx = scroll_offset + i
        if idx >= len(results):
            break
        
        item = results[idx]
        line_str = f"{idx+1:>3}. {item['summary']}"
        
        # Highlight selected row
        if idx == selected_idx:
            stdscr.attron(curses.color_pair(COLOR_PAIR_BAR)) # Blue bar for selection
            stdscr.addstr(i + 1, 0, line_str.ljust(max_x)[:max_x])
            stdscr.attroff(curses.color_pair(COLOR_PAIR_BAR))
        else:
            stdscr.addstr(i + 1, 0, line_str[:max_x-1])

    # Status Bar
    # We hide the "Ctrl+F" text but keep the functionality
    status_text = " [Arrows] Nav  [Enter] Open  [PgUp/PgDn] Page  [q] Quit"
    try:
        stdscr.attron(curses.color_pair(COLOR_PAIR_BAR))
        stdscr.addstr(max_y - 1, 0, status_text.ljust(max_x - 1))
        stdscr.attroff(curses.color_pair(COLOR_PAIR_BAR))
    except curses.error:
        pass 

    stdscr.refresh()

def main(stdscr):
    # Setup Colors
    curses.start_color()
    curses.use_default_colors()
    
    # Pair 1: Default Text
    curses.init_pair(COLOR_PAIR_NORMAL, -1, -1)
    # Pair 2: White Text on Blue Background (High Contrast)
    curses.init_pair(COLOR_PAIR_BAR, curses.COLOR_WHITE, curses.COLOR_BLUE)
    
    curses.curs_set(0)

    if len(sys.argv) < 2:
        return
    
    query = " ".join(sys.argv[1:])
    
    draw_loading(stdscr, query)
    results = run_search(query)
    
    if isinstance(results, str):
        stdscr.clear()
        stdscr.addstr(0, 0, results)
        stdscr.getch()
        return

    if not results:
        stdscr.clear()
        stdscr.addstr(0, 0, f"No results found for: {query}")
        stdscr.getch()
        return

    selected_idx = 0
    scroll_offset = 0
    
    while True:
        max_y, _ = stdscr.getmaxyx()
        list_height = max_y - 2

        # Keep Selection in View
        if selected_idx < scroll_offset:
            scroll_offset = selected_idx
        elif selected_idx >= scroll_offset + list_height:
            scroll_offset = selected_idx - list_height + 1

        draw_list(stdscr, results, selected_idx, scroll_offset, query)
        
        key = stdscr.getch()

        if key == ord('q'):
            break

        # Navigation: j / Down
        elif key == ord('j') or key == curses.KEY_DOWN:
            if selected_idx < len(results) - 1:
                selected_idx += 1
        
        # Navigation: k / Up
        elif key == ord('k') or key == curses.KEY_UP:
            if selected_idx > 0:
                selected_idx -= 1

        # Paging: Ctrl+F (6) / PgDn / Space
        elif key == 6 or key == curses.KEY_NPAGE: 
            selected_idx = min(len(results) - 1, selected_idx + list_height)
            scroll_offset = min(len(results) - list_height, scroll_offset + list_height)
            if scroll_offset < 0: scroll_offset = 0

        # Paging: Ctrl+B (2) / PgUp
        elif key == 2 or key == curses.KEY_PPAGE: 
            selected_idx = max(0, selected_idx - list_height)
            scroll_offset = max(0, scroll_offset - list_height)

        # Home / End (g/G)
        elif key == ord('g') or key == curses.KEY_HOME:
            selected_idx = 0
        elif key == ord('G') or key == curses.KEY_END:
            selected_idx = len(results) - 1

        # Open
        elif key == ord('\n') or key == curses.KEY_ENTER:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            viewer_script = os.path.join(script_dir, "_view-mails.py")
            thread_id = results[selected_idx]['id']

            curses.endwin()
            subprocess.run([sys.executable, viewer_script, thread_id])
            stdscr.refresh()

if __name__ == "__main__":
    curses.wrapper(main)