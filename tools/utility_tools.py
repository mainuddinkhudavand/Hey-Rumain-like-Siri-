# ============================================================
#  tools/utility_tools.py — File Search, Notes, and Timers
# ============================================================
import os
import time
import threading
import glob
from typing import Optional
from tools import tool

NOTES_DIR = os.path.join(os.path.expanduser("~"), "Documents", "RumainNotes")

# ── Note Taking Tools ─────────────────────────────────────────
@tool(
    name="save_note",
    description="Create a new note or overwrite an existing note with text content.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The title of the note (will be used as filename, e.g. 'shopping_list')"
            },
            "content": {
                "type": "string",
                "description": "The content to write into the note"
            }
        },
        "required": ["title", "content"]
    }
)
def save_note(title: str, content: str) -> str:
    try:
        os.makedirs(NOTES_DIR, exist_ok=True)
        # Sanitise title
        filename = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
        filename = filename.replace(" ", "_") + ".txt"
        
        filepath = os.path.join(NOTES_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        return f"Note saved successfully to Documents/RumainNotes/{filename}"
    except Exception as e:
        return f"Failed to save note. Error: {e}"

@tool(
    name="read_note",
    description="Retrieve the text content of a saved note.",
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The title of the note to read"
            }
        },
        "required": ["title"]
    }
)
def read_note(title: str) -> str:
    try:
        filename = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
        filename = filename.replace(" ", "_") + ".txt"
        
        filepath = os.path.join(NOTES_DIR, filename)
        if not os.path.exists(filepath):
            return f"Note '{title}' does not exist."
            
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        return f"Note Content for '{title}':\n{content}"
    except Exception as e:
        return f"Failed to read note. Error: {e}"

# ── File Search Tools ─────────────────────────────────────────
@tool(
    name="search_files",
    description="Search for files matching a keyword on the Desktop or Documents folder.",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "File name pattern or extension to search (e.g. '*.pdf', 'invoice')"
            }
        },
        "required": ["keyword"]
    }
)
def search_files(keyword: str) -> str:
    search_dirs = [
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "Documents")
    ]
    
    results = []
    # If the user did not provide a wildcard, add general pattern matching
    clean_kw = keyword.strip()
    if "*" not in clean_kw:
        pattern = f"*{clean_kw}*"
    else:
        pattern = clean_kw
        
    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
        # Search recursively up to 2 levels deep to keep it fast
        for root, dirs, files in os.walk(directory):
            # Calculate depth
            depth = root[len(directory):].count(os.sep)
            if depth > 2:
                continue
            for file in files:
                if clean_kw.lower() in file.lower() or (pattern != clean_kw and glob.fnmatch.fnmatch(file.lower(), pattern.lower())):
                    results.append(os.path.join(root, file))
                    if len(results) >= 10:  # Limit results to keep response clean
                        break
            if len(results) >= 10:
                break
                
    if results:
        formatted_paths = "\n".join(f"- {path}" for path in results)
        return f"Found matching files:\n{formatted_paths}"
    return f"No files matching '{keyword}' were found in Desktop or Documents."

# ── Timers / Reminders ────────────────────────────────────────
def trigger_alert_notification(message: str):
    """Trigger system alert or prints to console as notification."""
    try:
        # Cross platform print and bell sound
        print(f"\n🔔 [REMINDER ALERT] {message}\n")
        # Generate standard beep sound on Windows
        if os.name == 'nt':
            import winsound
            winsound.Beep(1000, 500)
    except Exception:
        pass

@tool(
    name="set_timer",
    description="Set a countdown timer (in seconds) that notifies the user when it expires.",
    parameters={
        "type": "object",
        "properties": {
            "seconds": {
                "type": "integer",
                "description": "Duration in seconds (e.g., 60 for 1 minute)"
            },
            "reminder_text": {
                "type": "string",
                "description": "Message to display when the timer ends (e.g., 'Take the pizza out')"
            }
        },
        "required": ["seconds", "reminder_text"]
    }
)
def set_timer(seconds: int, reminder_text: str) -> str:
    def timer_thread():
        time.sleep(seconds)
        trigger_alert_notification(f"Timer Expired: {reminder_text}")
        
    thread = threading.Thread(target=timer_thread, daemon=True)
    thread.start()
    return f"I have set a timer for {seconds} seconds: '{reminder_text}'."
