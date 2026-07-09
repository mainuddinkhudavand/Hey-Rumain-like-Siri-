# ============================================================
#  tools/os_tools.py — OS App and Web Automation Tools
# ============================================================
import os
import subprocess
import webbrowser
import psutil
from tools import tool

# Normalise common app name aliases
APP_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "vscode": "code",
    "vs code": "code",
    "paint": "mspaint",
    "explorer": "explorer",
    "task manager": "taskmgr",
    "terminal": "wt",
    "cmd": "cmd",
    "powershell": "powershell",
}

@tool(
    name="open_application",
    description="Launch a desktop application or utility on the computer.",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the app (e.g., 'notepad', 'chrome', 'calculator')"
            }
        },
        "required": ["app_name"]
    }
)
def open_application(app_name: str) -> str:
    app_lower = app_name.strip().lower()
    executable = APP_ALIASES.get(app_lower, app_lower)
    try:
        # Try OS specific launch
        if os.name == 'nt':
            os.startfile(executable)
        else:
            subprocess.Popen([executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Successfully opened {app_name}."
    except Exception:
        # Fallback to subprocess search
        try:
            subprocess.Popen(executable, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"Successfully opened {app_name}."
        except Exception as e:
            return f"Failed to open {app_name}. Error: {e}"

@tool(
    name="close_application",
    description="Close or terminate a running desktop application.",
    parameters={
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Name of the application process to terminate (e.g., 'notepad', 'chrome')"
            }
        },
        "required": ["app_name"]
    }
)
def close_application(app_name: str) -> str:
    app_lower = app_name.strip().lower()
    terminated = []
    
    # Map friendly names to common process names
    process_targets = [app_lower]
    if app_lower == "chrome":
        process_targets.append("chrome.exe")
    elif app_lower == "notepad":
        process_targets.append("notepad.exe")
    elif app_lower == "calculator" or app_lower == "calc":
        process_targets.append("calculator.exe")
        process_targets.append("calc.exe")

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info["name"].lower()
            if any(target in name for target in process_targets):
                proc.terminate()
                terminated.append(proc.info["name"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    if terminated:
        return f"Closed processes: {', '.join(set(terminated))}."
    return f"Could not find any running application matching '{app_name}'."

@tool(
    name="launch_url",
    description="Open a website URL in the user's default browser.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full website URL to launch (e.g., 'https://github.com')"
            }
        },
        "required": ["url"]
    }
)
def launch_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return f"Opened website: {url}"
    except Exception as e:
        return f"Failed to open URL. Error: {e}"

@tool(
    name="search_web",
    description="Perform a Google search in the default web browser.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search keywords (e.g., 'weather in London today')"
            }
        },
        "required": ["query"]
    }
)
def search_web(query: str) -> str:
    try:
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(search_url)
        return f"Searching Google for: '{query}'"
    except Exception as e:
        return f"Web search failed. Error: {e}"
