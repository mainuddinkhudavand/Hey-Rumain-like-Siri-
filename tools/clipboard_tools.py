# ============================================================
#  tools/clipboard_tools.py — Clipboard and Typing Simulator Tools
# ============================================================
import time
import pyperclip
import pyautogui
from tools import tool

@tool(
    name="read_clipboard",
    description="Read the current text content copied to the clipboard.",
    parameters={"type": "object", "properties": {}}
)
def read_clipboard() -> str:
    try:
        content = pyperclip.paste()
        if not content:
            return "The clipboard is currently empty."
        return f"Clipboard Content:\n\"\"\"\n{content}\n\"\"\""
    except Exception as e:
        return f"Failed to read clipboard. Error: {e}"

@tool(
    name="write_clipboard",
    description="Copy text content to the user's clipboard.",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to copy to the clipboard"
            }
        },
        "required": ["text"]
    }
)
def write_clipboard(text: str) -> str:
    try:
        pyperclip.copy(text)
        return "Successfully copied text to the clipboard."
    except Exception as e:
        return f"Failed to copy to clipboard. Error: {e}"

@tool(
    name="type_text",
    description="Simulate keyboard typing to input text at the current cursor focus. Use this to write notes, emails, or messages.",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The message or text block to type out"
            }
        },
        "required": ["text"]
    }
)
def type_text(text: str) -> str:
    try:
        # Give the user a brief moment (0.8s) to focus their target window/field
        time.sleep(0.8)
        pyautogui.typewrite(text, interval=0.02)
        return f"Successfully typed text."
    except Exception as e:
        return f"Failed to type text. Error: {e}"
