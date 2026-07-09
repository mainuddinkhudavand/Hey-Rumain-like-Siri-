# ============================================================
#  tools/system_tools.py — System Control Tools (Volume, Brightness, Specs)
# ============================================================
import os
from datetime import datetime
import psutil
import pyautogui
from tools import tool

# ── Volume Control (Windows pycaw) ───────────────────────────
def get_volume_interface():
    """Retrieve Windows speaker control endpoint, or raise on other OS."""
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))

@tool(
    name="set_volume",
    description="Adjust the system volume level (0 to 100) or toggle mute/unmute.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["set", "mute", "unmute", "up", "down"],
                "description": "The adjustment action to perform"
            },
            "level": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Desired volume percentage (required only if action is 'set')"
            }
        },
        "required": ["action"]
    }
)
def set_volume(action: str, level: int = None) -> str:
    try:
        volume = get_volume_interface()
        if action == "mute":
            volume.SetMute(1, None)
            return "System audio muted."
        elif action == "unmute":
            volume.SetMute(0, None)
            return "System audio unmuted."
        elif action == "up":
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(min(1.0, current + 0.1), None)
            return "System volume increased by 10%."
        elif action == "down":
            current = volume.GetMasterVolumeLevelScalar()
            volume.SetMasterVolumeLevelScalar(max(0.0, current - 0.1), None)
            return "System volume decreased by 10%."
        elif action == "set" and level is not None:
            volume.SetMasterVolumeLevelScalar(max(0.0, min(100.0, float(level))) / 100.0, None)
            return f"System volume set to {level}%."
        return "Unknown volume command."
    except Exception:
        # Fallback to pyautogui simulation keypresses
        if action == "up":
            pyautogui.press("volumeup")
            return "Volume increased."
        elif action == "down":
            pyautogui.press("volumedown")
            return "Volume decreased."
        elif action == "mute" or action == "unmute":
            pyautogui.press("volumemute")
            return "Volume mute toggled."
        return "System audio adjustment failed."

# ── Screen Brightness ─────────────────────────────────────────
@tool(
    name="set_brightness",
    description="Control the display monitor brightness (0 to 100).",
    parameters={
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Brightness percentage (e.g. 50)"
            },
            "direction": {
                "type": "string",
                "enum": ["up", "down"],
                "description": "Shift up or down by 10% (optional alternative to setting a level)"
            }
        }
    }
)
def set_brightness(level: int = None, direction: str = None) -> str:
    try:
        import screen_brightness_control as sbc
        current = sbc.get_brightness()[0]
        if direction == "up":
            target = min(100, current + 10)
            sbc.set_brightness(target)
            return f"Screen brightness increased to {target}%."
        elif direction == "down":
            target = max(0, current - 10)
            sbc.set_brightness(target)
            return f"Screen brightness decreased to {target}%."
        elif level is not None:
            sbc.set_brightness(level)
            return f"Screen brightness set to {level}%."
        return "Please specify either a level or a direction."
    except Exception as e:
        return f"Could not adjust brightness. Error: {e}"

# ── Media Player Keys ─────────────────────────────────────────
@tool(
    name="media_playback",
    description="Control system music/video playback (play, pause, skip, go back).",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["play", "pause", "next", "previous"],
                "description": "The media control signal to broadcast"
            }
        },
        "required": ["command"]
    }
)
def media_playback(command: str) -> str:
    key_map = {
        "play": "playpause",
        "pause": "playpause",
        "next": "nexttrack",
        "previous": "prevtrack"
    }
    key = key_map.get(command)
    if key:
        pyautogui.press(key)
        return f"Media playback command '{command}' triggered."
    return "Invalid media command."

# ── System Stats ──────────────────────────────────────────────
@tool(
    name="get_system_status",
    description="Check current PC telemetry: CPU usage, RAM utilization, battery charge, disk space.",
    parameters={"type": "object", "properties": {}}
)
def get_system_status() -> str:
    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    battery = psutil.sensors_battery()
    
    status = [
        f"CPU load is at {cpu:.0f}%.",
        f"RAM is at {memory.percent:.0f}% capacity ({memory.used/1024**3:.1f} GB used)."
    ]
    
    if battery:
        charging_str = "charging" if battery.power_plugged else "discharging"
        status.append(f"Battery is at {battery.percent}% ({charging_str}).")
        
    try:
        import shutil
        total, used, free = shutil.disk_usage(".")
        used_percent = (used / total) * 100
        status.append(f"Primary Disk is {used_percent:.0f}% full ({free/1024**3:.1f} GB free).")
    except Exception:
        pass
        
    return " ".join(status)

# ── Screenshot ────────────────────────────────────────────────
@tool(
    name="take_screenshot",
    description="Capture the desktop screen and save the image to the Pictures library.",
    parameters={"type": "object", "properties": {}}
)
def take_screenshot() -> str:
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        filepath = os.path.join(pictures_dir, f"rumain_screenshot_{timestamp}.png")
        
        pyautogui.screenshot(filepath)
        return f"Screenshot successfully saved to: {filepath}"
    except Exception as e:
        return f"Failed to capture screenshot. Error: {e}"
