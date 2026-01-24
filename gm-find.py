#!/usr/bin/env python3
import curses
import json
import subprocess
import sys
import os

def load_search_results(query):
    """Run notmuch search and return a list of dicts (thread_id, summary)."""
    try:
        # We use JSON format for reliable parsing
        cmd = ["notmuch", "search", "--format=json", query]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        data = json.loads(result.stdout)
        
        results = []
        for item in data:
            # Format a nice summary line similar to standard notmuch output
            # "Authors  Subject (date)"
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
        print(f"Error running notmuch: {e.stderr}")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error parsing notmuch output.")
        sys.exit(1)

def draw_list(stdscr, results, selected_idx, scroll_offset):
    stdscr.clear()
    max_y, max_x = stdscr.getmaxyx()
    height = max_y - 2 # Reserve lines for status bar

    # Header
    stdscr.attron(curses.A_BOLD)
    header = f" Search Results ({len(results)} found)"
    stdscr.addstr(0, 0, header[:max_x-1])
    stdscr.addstr(1, 0, "-" * (max_x - 1))
    stdscr.attroff(curses.A_BOLD)

    # Draw List
    for i in range(height):
        idx = scroll_offset + i
        if idx >= len(results):
            break
        
        item = results[idx]
        line_str = f"{idx+1:>3}. {item['summary']}"
        
        # Highlight selected row
        if idx == selected_idx:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(i + 2, 0, line_str[:max_x-1])
            stdscr.attroff(curses.A_REVERSE)
        else:
            stdscr.addstr(i + 2, 0, line_str[:max_x-1])

    # Status Bar
    status_text = " [j/k] Nav  [Enter] Read  [Ctrl+F/B] Page  [q] Quit"
    try:
        stdscr.attron(curses.color_pair(1) | curses.A_REVERSE)
        stdscr.addstr(max_y - 1, 0, status_text.ljust(max_x - 1))
        stdscr.attroff(curses.color_pair(1) | curses.A_REVERSE)
    except curses.error:
        pass # Ignore corner case errors

    stdscr.refresh()

def main(stdscr):
    # Setup Colors
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.curs_set(0) # Hide cursor

    # Get Query
    if len(sys.argv) < 2:
        # If no args, maybe prompt? For now, just exit
        return
    
    query = " ".join(sys.argv[1:])
    results = load_search_results(query)

    if not results:
        stdscr.addstr(0, 0, f"No results for: {query}")
        stdscr.addstr(2, 0, "Press any key to exit.")
        stdscr.getch()
        return

    selected_idx = 0
    scroll_offset = 0
    
    # Main Loop
    while True:
        # Determine Page Size (dynamic)
        max_y, _ = stdscr.getmaxyx()
        list_height = max_y - 3 # Header + Divider + Status

        # Ensure scroll follows selection
        if selected_idx < scroll_offset:
            scroll_offset = selected_idx
        elif selected_idx >= scroll_offset + list_height:
            scroll_offset = selected_idx - list_height + 1

        draw_list(stdscr, results, selected_idx, scroll_offset)
        
        key = stdscr.getch()

        # Quit
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

        # Paging: Ctrl+F (Forward) or PgDn
        elif key == 6 or key == curses.KEY_NPAGE: # Ctrl+F is ASCII 6
            selected_idx = min(len(results) - 1, selected_idx + list_height)
            scroll_offset = min(len(results) - list_height, scroll_offset + list_height)
            if scroll_offset < 0: scroll_offset = 0

        # Paging: Ctrl+B (Back) or PgUp
        elif key == 2 or key == curses.KEY_PPAGE: # Ctrl+B is ASCII 2
            selected_idx = max(0, selected_idx - list_height)
            scroll_offset = max(0, scroll_offset - list_height)

        # Home / End
        elif key == curses.KEY_HOME:
            selected_idx = 0
        elif key == curses.KEY_END:
            selected_idx = len(results) - 1

        # Open Message
        elif key == ord('\n') or key == curses.KEY_ENTER:
            # Get the viewer path
            script_dir = os.path.dirname(os.path.abspath(__file__))
            viewer_script = os.path.join(script_dir, "_view-mails.py")
            thread_id = results[selected_idx]['id']

            # Temporarily leave curses mode to run the viewer
            curses.endwin()
            subprocess.run([sys.executable, viewer_script, thread_id])
            # Restore curses mode upon return
            stdscr.refresh()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} 'search terms'")
        sys.exit(1)
    
    # Run
    curses.wrapper(main)