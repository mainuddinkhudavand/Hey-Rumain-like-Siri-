# ============================================================
#  config.py — Central Configuration & Settings
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv()

# ── Wake Word Settings ───────────────────────────────────────
# Supported engines: "vosk" | "pyaudio_threshold"
WAKE_WORD_ENGINE = os.getenv("WAKE_WORD_ENGINE", "pyaudio_threshold")
WAKE_WORD = os.getenv("WAKE_WORD", "hey rumain").lower()
WAKE_WORD_SENSITIVITY = float(os.getenv("WAKE_WORD_SENSITIVITY", "0.5"))

# ── Speech-To-Text (STT) Settings ────────────────────────────
# Supported: "google" (online free) | "whisper_api" (openai api) | "vosk" (local)
STT_ENGINE = os.getenv("STT_ENGINE", "google")
WHISPER_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── LLM Brain Settings ───────────────────────────────────────
# Supported: "claude" (anthropic api) | "ollama" (local)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

# Ollama settings (for fully local operation)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# ── Text-To-Speech (TTS) Settings ────────────────────────────
# Supported: "edge-tts" (high quality, natural soft girl voice) | "pyttsx3" (fully offline offline)
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge-tts")

# Voice selection for Edge-TTS (Soft female voices):
# "en-US-EmmaMultilingualNeural" or "en-US-AnaNeural" or "en-US-JennyNeural"
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-EmmaMultilingualNeural")

# Local pyttsx3 fallback settings
TTS_RATE = int(os.getenv("TTS_RATE", "175"))
TTS_VOLUME = float(os.getenv("TTS_VOLUME", "1.0"))
TTS_VOICE_INDEX = int(os.getenv("TTS_VOICE_INDEX", "1")) # 1 is typically female on Windows

# ── System Hotkey ────────────────────────────────────────────
# Double tap hotkey (defaults to 'ctrl' double-tap)
TOGGLE_HOTKEY = os.getenv("TOGGLE_HOTKEY", "ctrl")

# ── Database (SQLite) ────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "assistant_memory.db")

# ── Server settings ──────────────────────────────────────────
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# Microphone settings
MIC_ENERGY_THRESHOLD = int(os.getenv("MIC_ENERGY_THRESHOLD", "300"))
MIC_PAUSE_THRESHOLD = float(os.getenv("MIC_PAUSE_THRESHOLD", "0.8"))
MIC_PHRASE_LIMIT = int(os.getenv("MIC_PHRASE_LIMIT", "10"))

# Pipeline display mappings
AGENT_NAMES = {
    "ear":   "EarAgent",
    "mind":  "MindAgent",
    "hand":  "HandAgent",
    "voice": "VoiceAgent",
}

AGENT_COLORS = {
    "ear":   "#00f0ff",   # Cyan
    "mind":  "#b026ff",   # Violet/Purple
    "hand":  "#ffb300",   # Amber
    "voice": "#00ff88",   # Emerald
}
